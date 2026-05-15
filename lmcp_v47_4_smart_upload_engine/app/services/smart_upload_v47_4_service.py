
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
import traceback

SERVICE_VERSION = "V47_4_SMART_UPLOAD_ENGINE"
DEFAULT_OUTPUT_DIR = Path("runtime/smart_upload_v47_4")
DEFAULT_CDP_URL = "http://127.0.0.1:9222"

BLOCKED_UPLOAD_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".exe", ".bat", ".cmd", ".sh", ".js", ".vbs"}
SAFE_UPLOAD_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".docx", ".doc", ".png", ".jpg", ".jpeg"}

FILE_TYPE_KEYWORDS = {
    "quotation": ["quote", "quotation", "bid", "offer", "price"],
    "pricing_schedule": ["pricing", "schedule", "boq", "financial", "price"],
    "csd_report": ["csd", "supplier", "database"],
    "bbbee_certificate": ["bbbee", "b-bbee", "bee", "specific goals"],
    "tax_compliance": ["tax", "sars", "pin", "compliance"],
    "company_registration": ["company", "cipc", "registration", "reg"],
    "director_id": ["id", "identity", "director"],
    "supporting_document": ["support", "other", "document", "attachment"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: Any, fallback: str = "RFQ") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _resolve_path(value: str | Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _read_json(path_value: str | Path) -> Dict[str, Any]:
    path = _resolve_path(path_value)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_plan(plan_json: str) -> Dict[str, Any]:
    path = _resolve_path(plan_json)
    if not path.exists():
        raise FileNotFoundError(f"V47.1 autofill plan not found: {path}")
    data = _read_json(path)
    data["_source_autofill_plan_json"] = str(path)
    return data


def _make_workspace(plan: Dict[str, Any], output_dir: Optional[str]) -> Path:
    rfq = plan.get("buyer_rfq_number") or "RFQ"
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not root.is_absolute():
        root = Path.cwd() / root
    workspace = root / f"{_safe_name(rfq)}__UPLOAD-{stamp}"
    (workspace / "screenshots").mkdir(parents=True, exist_ok=True)
    return workspace


def _pick_active_page(browser: Any) -> Any:
    pages = []
    for context in browser.contexts:
        for page in context.pages:
            pages.append(page)
    if not pages:
        raise RuntimeError("No open pages found in attached browser.")
    return pages[-1]


def _blocked_reason(path: Path) -> str:
    suffix = path.suffix.lower()
    if not path.exists():
        return "file not found"
    if not path.is_file():
        return "not a file"
    if suffix in BLOCKED_UPLOAD_EXTENSIONS:
        return "blocked unsafe/zip file extension"
    if suffix not in SAFE_UPLOAD_EXTENSIONS:
        return "unsupported upload extension"
    return "unknown"


def _upload_candidates_from_plan(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in ((plan.get("playwright_plan") or {}).get("upload_candidates") or []):
        p = _resolve_path(str(item.get("path") or ""))
        suffix = p.suffix.lower()
        allowed = p.exists() and p.is_file() and suffix in SAFE_UPLOAD_EXTENSIONS and suffix not in BLOCKED_UPLOAD_EXTENSIONS
        out.append({
            "file_type": item.get("file_type") or "supporting_document",
            "filename": item.get("filename") or p.name,
            "path": str(p),
            "exists": p.exists(),
            "extension": suffix,
            "allowed": allowed,
            "blocked_reason": None if allowed else _blocked_reason(p),
        })
    return out


def _score_input_for_file_type(input_info: Dict[str, Any], file_type: str) -> int:
    blob = " ".join([
        str(input_info.get("name") or ""),
        str(input_info.get("id") or ""),
        str(input_info.get("accept") or ""),
        str(input_info.get("aria_label") or ""),
        str(input_info.get("label_text") or ""),
        str(input_info.get("nearby_text") or ""),
    ]).lower()

    score = 0
    for kw in FILE_TYPE_KEYWORDS.get(file_type, []) + FILE_TYPE_KEYWORDS["supporting_document"]:
        if kw in blob:
            score += 10
    if file_type in blob:
        score += 20
    return score


def _extract_upload_inputs(page: Any) -> List[Dict[str, Any]]:
    inputs: List[Dict[str, Any]] = []
    locator = page.locator("input[type='file']")
    count = locator.count()

    for i in range(count):
        el = locator.nth(i)
        try:
            handle = el.element_handle()
            attrs = page.evaluate(
                """(e) => {
                    const label = e.id ? document.querySelector('label[for="' + e.id + '"]') : null;
                    let nearby = "";
                    let parent = e.parentElement;
                    for (let i=0; i<3 && parent; i++, parent=parent.parentElement) {
                        nearby += " " + (parent.innerText || "");
                    }
                    return {
                        id: e.getAttribute("id"),
                        name: e.getAttribute("name"),
                        accept: e.getAttribute("accept"),
                        multiple: e.hasAttribute("multiple"),
                        aria_label: e.getAttribute("aria-label"),
                        visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length),
                        disabled: e.disabled,
                        label_text: label ? label.innerText : null,
                        nearby_text: nearby.slice(0, 500)
                    };
                }""",
                handle,
            )
            attrs["index"] = i
            inputs.append(attrs)
        except Exception as exc:
            inputs.append({"index": i, "error": str(exc)})
    return inputs


def _build_upload_matches(upload_inputs: List[Dict[str, Any]], files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    used_inputs = set()

    for f in files:
        if not f.get("allowed"):
            matches.append({"file": f, "matched_input_index": None, "score": 0, "status": "skipped", "reason": f.get("blocked_reason")})
            continue

        best_score = -1
        best_input = None
        for inp in upload_inputs:
            idx = inp.get("index")
            if idx in used_inputs or inp.get("disabled"):
                continue
            score = _score_input_for_file_type(inp, f.get("file_type") or "")
            if score > best_score:
                best_score = score
                best_input = inp

        if best_input is None:
            matches.append({"file": f, "matched_input_index": None, "score": 0, "status": "no_input_available", "reason": "No file input found."})
            continue

        status = "matched" if best_score >= 10 else "matched_low_confidence"
        if len(upload_inputs) == 1 and best_score < 10:
            status = "matched_single_input_low_confidence"

        used_inputs.add(best_input.get("index"))
        matches.append({
            "file": f,
            "matched_input_index": best_input.get("index"),
            "score": best_score,
            "status": status,
            "input": best_input,
            "reason": "Matched by field text/attributes." if best_score >= 10 else "Weak/generic match; operator must review.",
        })

    return matches


def attach_and_smart_upload(
    autofill_plan_json: str,
    cdp_url: str = DEFAULT_CDP_URL,
    output_dir: Optional[str] = None,
    execute_uploads: bool = False,
    capture_screenshots: bool = True,
    stop_before_submit: bool = True,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        plan = _load_plan(autofill_plan_json)
        workspace = _make_workspace(plan, output_dir)
        screenshots_dir = workspace / "screenshots"

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "Playwright is not installed. Install with: pip install playwright && playwright install chromium",
                "error": str(exc),
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        files = _upload_candidates_from_plan(plan)
        upload_inputs: List[Dict[str, Any]] = []
        upload_matches: List[Dict[str, Any]] = []
        upload_results: List[Dict[str, Any]] = []
        screenshots: List[str] = []
        current_url = None
        title = None

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            page = _pick_active_page(browser)
            current_url = page.url
            title = page.title()

            if capture_screenshots:
                s1 = screenshots_dir / "01_before_upload.png"
                page.screenshot(path=str(s1), full_page=True)
                screenshots.append(str(s1))

            upload_inputs = _extract_upload_inputs(page)
            upload_matches = _build_upload_matches(upload_inputs, files)

            if execute_uploads:
                for match in upload_matches:
                    if match.get("status") not in {"matched", "matched_single_input_low_confidence", "matched_low_confidence"}:
                        upload_results.append({"filename": (match.get("file") or {}).get("filename"), "status": "skipped", "reason": match.get("reason")})
                        continue

                    file_info = match["file"]
                    input_index = match.get("matched_input_index")
                    try:
                        page.locator("input[type='file']").nth(int(input_index)).set_input_files(file_info["path"], timeout=10000)
                        upload_results.append({
                            "filename": file_info.get("filename"),
                            "file_type": file_info.get("file_type"),
                            "path": file_info.get("path"),
                            "matched_input_index": input_index,
                            "status": "uploaded",
                            "operator_review_required": True,
                            "confidence_status": match.get("status"),
                        })
                    except Exception as exc:
                        upload_results.append({
                            "filename": file_info.get("filename"),
                            "file_type": file_info.get("file_type"),
                            "path": file_info.get("path"),
                            "matched_input_index": input_index,
                            "status": "upload_failed",
                            "error": str(exc),
                        })
            else:
                upload_results = [{
                    "filename": (m.get("file") or {}).get("filename"),
                    "file_type": (m.get("file") or {}).get("file_type"),
                    "path": (m.get("file") or {}).get("path"),
                    "matched_input_index": m.get("matched_input_index"),
                    "status": "planned_not_uploaded",
                    "match_status": m.get("status"),
                    "score": m.get("score"),
                    "reason": m.get("reason"),
                } for m in upload_matches]

            if capture_screenshots:
                s2 = screenshots_dir / "02_after_upload_attempts.png"
                page.screenshot(path=str(s2), full_page=True)
                screenshots.append(str(s2))

            browser.close()

        result = {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "message": "Smart upload planning completed." if not execute_uploads else "Smart upload execution completed. Review portal before final submit.",
            "buyer_rfq_number": plan.get("buyer_rfq_number"),
            "quote_number": plan.get("quote_number"),
            "workspace": str(workspace),
            "source_autofill_plan_json": plan.get("_source_autofill_plan_json"),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "live_page": {"cdp_url": cdp_url, "url": current_url, "title": title},
            "safety_policy": {
                "auto_submit": False,
                "captcha_bypass": False,
                "operator_confirmation_required": True,
                "stop_before_submit": stop_before_submit,
                "zip_upload_allowed": False,
                "execute_uploads": execute_uploads,
            },
            "file_candidates": files,
            "detected_upload_inputs": upload_inputs,
            "upload_matches": upload_matches,
            "upload_results": upload_results,
            "screenshots": screenshots,
            "next_operator_steps": [
                "Review uploaded files on the portal.",
                "Confirm each file landed in the correct upload slot.",
                "Remove any incorrect upload manually before proceeding.",
                "Confirm declarations and checklist items.",
                "Do not click final Submit until all content is reviewed.",
                "Capture receipt/proof after manual submission.",
            ],
            "artifacts": {
                "smart_upload_run_json": str(workspace / "smart_upload_run_v47_4.json"),
                "screenshots_dir": str(screenshots_dir),
            },
        }

        _write_json(workspace / "smart_upload_run_v47_4.json", result)
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47.4 smart upload failed.",
            "autofill_plan_json": autofill_plan_json,
            "cdp_url": cdp_url,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v47_4_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V47.4 Smart Upload Engine",
        "description": "Attaches to a live browser, detects file upload inputs, matches portal-ready files to likely upload fields, optionally uploads safe files, captures screenshots, and never clicks final submit.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "default_cdp_url": DEFAULT_CDP_URL,
        "safety_policy": {
            "auto_submit": False,
            "captcha_bypass": False,
            "operator_confirmation_required": True,
            "zip_upload_allowed": False,
            "execute_uploads_default": False,
        },
        "endpoints": {
            "status": "/v47-smart-upload/status",
            "attach_and_upload": "/v47-smart-upload/attach-and-upload",
        },
        "ready": True,
    }
