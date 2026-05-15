
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
import traceback

SERVICE_VERSION = "V47_5_GUARDED_FINAL_SUBMISSION_AUTOMATION"
DEFAULT_OUTPUT_DIR = Path("runtime/final_submission_v47_5")
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
REQUIRED_CONFIRMATION_PHRASE = "I CONFIRM FINAL SUBMISSION"


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
    workspace = root / f"{_safe_name(rfq)}__FINAL-{stamp}"
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


def _safe_click_by_text(page: Any, labels: List[str], timeout: int = 5000) -> Dict[str, Any]:
    last_error = None
    for label in labels:
        try:
            target = page.get_by_text(label, exact=False).first
            if target.is_visible(timeout=1200):
                target.click(timeout=timeout)
                return {"status": "clicked", "label": label, "method": "text"}
        except Exception as exc:
            last_error = str(exc)

    for label in labels:
        try:
            target = page.get_by_role("button", name=re.compile(label, re.I)).first
            if target.is_visible(timeout=1200):
                target.click(timeout=timeout)
                return {"status": "clicked", "label": label, "method": "button_role"}
        except Exception as exc:
            last_error = str(exc)

    return {"status": "not_clicked", "labels": labels, "error": last_error}


def _extract_page_state(page: Any) -> Dict[str, Any]:
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        body_text = ""

    return {
        "url": page.url,
        "title": page.title(),
        "body_text_excerpt": body_text[:3000],
        "checklist": {
            "valid_csd_seen": "Valid Central Supplier Database" in body_text,
            "quote_seen": "Quote" in body_text,
            "mbd_seen": "MBD" in body_text or "Filled MBD" in body_text,
            "bbbee_seen": "BBBE" in body_text or "B-BBEE" in body_text or "BBBEE" in body_text,
            "pending_seen": "Pending" in body_text,
            "submit_now_seen": "Submit now" in body_text or "Submit Now" in body_text,
            "confirm_proceed_seen": "Confirm & Proceed" in body_text,
        },
    }


def guarded_final_submission(
    autofill_plan_json: str,
    cdp_url: str = DEFAULT_CDP_URL,
    output_dir: Optional[str] = None,
    dry_run: bool = True,
    execute_final_submit: bool = False,
    confirmation_phrase: Optional[str] = None,
    capture_screenshots: bool = True,
    wait_after_click_ms: int = 3000,
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

        actions: List[Dict[str, Any]] = []
        screenshots: List[str] = []
        submitted = False
        blocked_reason = None

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            page = _pick_active_page(browser)

            before_state = _extract_page_state(page)

            if capture_screenshots:
                s1 = screenshots_dir / "01_before_final_submission.png"
                page.screenshot(path=str(s1), full_page=True)
                screenshots.append(str(s1))

            page_url = (page.url or "").lower()
            if "etenders.gov.za" not in page_url:
                blocked_reason = "Current browser page is not an eTenders page."
            elif "/esubmission/" not in page_url:
                blocked_reason = "Current browser page is not an eSubmission page."
            elif not before_state["checklist"]["confirm_proceed_seen"] and not before_state["checklist"]["submit_now_seen"]:
                blocked_reason = "Final submission controls were not detected on the current page."
            elif dry_run or not execute_final_submit:
                blocked_reason = "Dry-run/planning mode only. No final submission was attempted."
            elif confirmation_phrase != REQUIRED_CONFIRMATION_PHRASE:
                blocked_reason = f"Missing required confirmation phrase: {REQUIRED_CONFIRMATION_PHRASE}"
            else:
                confirm_result = _safe_click_by_text(page, ["Confirm & Proceed", "Confirm and Proceed", "Confirm"])
                actions.append({"step": "confirm_and_proceed", **confirm_result})
                page.wait_for_timeout(wait_after_click_ms)

                if capture_screenshots:
                    s2 = screenshots_dir / "02_after_confirm_proceed.png"
                    page.screenshot(path=str(s2), full_page=True)
                    screenshots.append(str(s2))

                submit_result = _safe_click_by_text(page, ["Submit now", "Submit Now", "Submit"])
                actions.append({"step": "submit_now", **submit_result})
                page.wait_for_timeout(wait_after_click_ms)

                if submit_result.get("status") == "clicked":
                    submitted = True
                else:
                    blocked_reason = "Submit button was not clicked. It may be disabled, hidden, or portal validation blocked it."

            after_state = _extract_page_state(page)

            if capture_screenshots:
                s3 = screenshots_dir / "03_after_final_submission_attempt.png"
                page.screenshot(path=str(s3), full_page=True)
                screenshots.append(str(s3))

            browser.close()

        status = "submitted_attempted" if submitted else ("dry_run" if dry_run else "blocked")
        message = "Final submission click sequence was attempted. Review portal proof immediately." if submitted else "Final submission was not performed."

        result = {
            "status": status,
            "service_version": SERVICE_VERSION,
            "message": message,
            "buyer_rfq_number": plan.get("buyer_rfq_number"),
            "quote_number": plan.get("quote_number"),
            "workspace": str(workspace),
            "source_autofill_plan_json": plan.get("_source_autofill_plan_json"),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "dry_run": dry_run,
            "execute_final_submit": execute_final_submit,
            "required_confirmation_phrase": REQUIRED_CONFIRMATION_PHRASE,
            "confirmation_phrase_valid": confirmation_phrase == REQUIRED_CONFIRMATION_PHRASE,
            "submitted_click_attempted": submitted,
            "blocked_reason": blocked_reason,
            "safety_policy": {
                "captcha_bypass": False,
                "silent_submission": False,
                "requires_confirmation_phrase": True,
                "operator_review_required_after_run": True,
                "zip_upload_allowed": False,
            },
            "before_state": before_state,
            "actions": actions,
            "after_state": after_state,
            "screenshots": screenshots,
            "next_operator_steps": [
                "Review the portal page after the run.",
                "Check whether the portal generated a receipt or confirmation number.",
                "Save screenshots and any receipt page.",
                "Record proof using V47 /record-proof after confirmation.",
            ],
            "artifacts": {
                "final_submission_run_json": str(workspace / "final_submission_run_v47_5.json"),
                "screenshots_dir": str(screenshots_dir),
            },
        }

        _write_json(workspace / "final_submission_run_v47_5.json", result)
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47.5 guarded final submission failed.",
            "autofill_plan_json": autofill_plan_json,
            "cdp_url": cdp_url,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v47_5_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V47.5 Guarded Final Submission Automation",
        "description": "Attaches to a live eTenders page, validates final controls, captures proof screenshots, and only attempts final submit when dry_run=false, execute_final_submit=true, and the exact confirmation phrase is provided.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "default_cdp_url": DEFAULT_CDP_URL,
        "required_confirmation_phrase": REQUIRED_CONFIRMATION_PHRASE,
        "safety_policy": {
            "captcha_bypass": False,
            "silent_submission": False,
            "requires_confirmation_phrase": True,
            "dry_run_default": True,
            "operator_review_required_after_run": True,
        },
        "endpoints": {
            "status": "/v47-final-submit/status",
            "guarded_submit": "/v47-final-submit/guarded-submit",
        },
        "ready": True,
    }
