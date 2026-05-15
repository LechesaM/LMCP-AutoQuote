
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
import traceback

SERVICE_VERSION = "V47_2_ASSISTED_BROWSER_AUTOMATION"
DEFAULT_OUTPUT_DIR = Path("runtime/assisted_browser_v47_2")
DEFAULT_BROWSER_PROFILE = Path("runtime/playwright/portal_assist_profile")


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


def _load_autofill_plan(plan_json: str) -> Dict[str, Any]:
    path = _resolve_path(plan_json)
    if not path.exists():
        raise FileNotFoundError(f"V47.1 autofill plan not found: {path}")
    data = _read_json(path)
    data["_source_autofill_plan_json"] = str(path)
    return data


def _sanitize_url(url: Optional[str]) -> str:
    if not url:
        return "https://www.etenders.gov.za"
    if not re.match(r"^https?://", url, flags=re.I):
        return "https://" + url
    return url


def _make_workspace(plan: Dict[str, Any], output_dir: Optional[str]) -> Path:
    rfq = plan.get("buyer_rfq_number") or "RFQ"
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not root.is_absolute():
        root = Path.cwd() / root
    workspace = root / f"{_safe_name(rfq)}__BROWSER-{stamp}"
    (workspace / "screenshots").mkdir(parents=True, exist_ok=True)
    return workspace


def _build_upload_queue(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    queue = []
    for item in ((plan.get("playwright_plan") or {}).get("upload_candidates") or []):
        p = _resolve_path(str(item.get("path") or ""))
        queue.append({
            "file_type": item.get("file_type"),
            "filename": item.get("filename"),
            "path": str(p),
            "exists": p.exists(),
            "auto_uploaded": False,
            "action": "operator_select_upload_field_then_upload_file",
            "reason": "V47.2 does not guess upload fields automatically; operator confirms the correct field first.",
        })
    return queue


def run_assisted_browser_from_plan(
    autofill_plan_json: str,
    output_dir: Optional[str] = None,
    headless: bool = True,
    timeout_ms: int = 60000,
    stop_before_submit: bool = True,
) -> Dict[str, Any]:
    started_at = _now_iso()

    try:
        plan = _load_autofill_plan(autofill_plan_json)
        workspace = _make_workspace(plan, output_dir)
        screenshots_dir = workspace / "screenshots"
        portal_url = _sanitize_url(plan.get("portal_url"))

        profile_dir = _resolve_path(DEFAULT_BROWSER_PROFILE)
        profile_dir.mkdir(parents=True, exist_ok=True)

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

        fill_results: List[Dict[str, Any]] = []
        screenshots: List[str] = []

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                accept_downloads=True,
            )
            page = context.new_page()
            page.goto(portal_url, wait_until="domcontentloaded", timeout=timeout_ms)

            s1 = screenshots_dir / "01_portal_loaded.png"
            page.screenshot(path=str(s1), full_page=True)
            screenshots.append(str(s1))

            for item in ((plan.get("playwright_plan") or {}).get("field_fill_candidates") or []):
                field = item.get("field")
                value = item.get("value")
                selectors = item.get("selectors") or []

                if value in [None, ""]:
                    fill_results.append({"field": field, "status": "skipped_empty_value", "value": value})
                    continue

                filled = False
                for selector in selectors:
                    try:
                        locator_group = page.locator(selector)
                        if locator_group.count() <= 0:
                            fill_results.append({"field": field, "selector": selector, "status": "not_found", "value": value})
                            continue

                        locator = locator_group.first
                        if not locator.is_visible(timeout=1000):
                            fill_results.append({"field": field, "selector": selector, "status": "found_not_visible", "value": value})
                            continue

                        locator.fill(str(value), timeout=3000)
                        fill_results.append({"field": field, "selector": selector, "status": "filled", "value": value})
                        filled = True
                        break
                    except Exception as exc:
                        fill_results.append({"field": field, "selector": selector, "status": "error", "value": value, "error": str(exc)})

                if not filled:
                    fill_results.append({"field": field, "status": "not_filled", "value": value})

            s2 = screenshots_dir / "02_after_field_attempts.png"
            page.screenshot(path=str(s2), full_page=True)
            screenshots.append(str(s2))
            context.close()

        result = {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "message": "Assisted browser automation completed. No final submission was performed.",
            "buyer_rfq_number": plan.get("buyer_rfq_number"),
            "quote_number": plan.get("quote_number"),
            "portal_url": portal_url,
            "portal_type": plan.get("portal_type"),
            "workspace": str(workspace),
            "source_autofill_plan_json": plan.get("_source_autofill_plan_json"),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "safety_policy": {
                "auto_submit": False,
                "captcha_bypass": False,
                "operator_confirmation_required": True,
                "stop_before_submit": stop_before_submit,
                "zip_upload_allowed": False,
            },
            "field_fill_results": fill_results,
            "upload_queue": _build_upload_queue(plan),
            "screenshots": screenshots,
            "next_operator_steps": [
                "Review screenshots.",
                "Confirm correct portal and RFQ/tender page.",
                "Upload files from upload_queue to the correct portal fields.",
                "Do not upload ZIP files.",
                "Do not submit until all declarations and uploaded files are reviewed.",
                "Capture receipt/proof after manual submission.",
            ],
            "artifacts": {
                "browser_run_json": str(workspace / "browser_assist_run_v47_2.json"),
                "screenshots_dir": str(screenshots_dir),
            },
        }

        _write_json(workspace / "browser_assist_run_v47_2.json", result)
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47.2 assisted browser automation failed.",
            "autofill_plan_json": autofill_plan_json,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v47_2_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V47.2 Assisted Browser Automation",
        "description": "Uses a V47.1 autofill plan to open portal pages, attempt safe visible-field filling, generate upload queue, and capture screenshots. It does not bypass CAPTCHA and does not submit.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "default_browser_profile": str(DEFAULT_BROWSER_PROFILE),
        "safety_policy": {
            "auto_submit": False,
            "captcha_bypass": False,
            "operator_confirmation_required": True,
            "zip_upload_allowed": False,
        },
        "endpoints": {
            "status": "/v47-assisted-browser/status",
            "run_from_plan": "/v47-assisted-browser/run-from-plan",
        },
        "ready": True,
    }
