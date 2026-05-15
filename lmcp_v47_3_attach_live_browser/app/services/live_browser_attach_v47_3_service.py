
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
import traceback

SERVICE_VERSION = "V47_3_ATTACH_LIVE_BROWSER_SESSION"
DEFAULT_OUTPUT_DIR = Path("runtime/live_browser_attach_v47_3")
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


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
    workspace = root / f"{_safe_name(rfq)}__LIVE-{stamp}"
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
            "reason": "V47.3 attaches to live page but does not guess upload fields or click final submit.",
        })
    return queue


def _pick_active_page(browser: Any) -> Any:
    pages = []
    for context in browser.contexts:
        for page in context.pages:
            pages.append(page)

    if not pages:
        raise RuntimeError("No open pages found in attached browser.")

    # Prefer the most recently opened visible-looking page.
    return pages[-1]


def attach_to_live_browser_and_assist(
    autofill_plan_json: str,
    cdp_url: str = DEFAULT_CDP_URL,
    output_dir: Optional[str] = None,
    fill_visible_fields: bool = True,
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

        fill_results: List[Dict[str, Any]] = []
        screenshots: List[str] = []

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            page = _pick_active_page(browser)

            current_url = page.url
            title = page.title()

            if capture_screenshots:
                s1 = screenshots_dir / "01_live_page_before_fill.png"
                page.screenshot(path=str(s1), full_page=True)
                screenshots.append(str(s1))

            if fill_visible_fields:
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
                            group = page.locator(selector)
                            count = group.count()
                            if count <= 0:
                                fill_results.append({"field": field, "selector": selector, "status": "not_found", "value": value})
                                continue

                            locator = group.first
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

            if capture_screenshots:
                s2 = screenshots_dir / "02_live_page_after_fill.png"
                page.screenshot(path=str(s2), full_page=True)
                screenshots.append(str(s2))

            # Do not close the live browser. Only disconnect from CDP.
            browser.close()

        result = {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "message": "Attached to live browser and completed safe assist. No final submission was performed.",
            "buyer_rfq_number": plan.get("buyer_rfq_number"),
            "quote_number": plan.get("quote_number"),
            "portal_url_from_plan": plan.get("portal_url"),
            "workspace": str(workspace),
            "source_autofill_plan_json": plan.get("_source_autofill_plan_json"),
            "started_at": started_at,
            "completed_at": _now_iso(),
            "live_page": {
                "cdp_url": cdp_url,
                "url": locals().get("current_url"),
                "title": locals().get("title"),
            },
            "safety_policy": {
                "auto_submit": False,
                "captcha_bypass": False,
                "operator_confirmation_required": True,
                "stop_before_submit": stop_before_submit,
                "zip_upload_allowed": False,
                "does_not_close_user_browser": True,
            },
            "field_fill_results": fill_results,
            "upload_queue": _build_upload_queue(plan),
            "screenshots": screenshots,
            "next_operator_steps": [
                "Review the browser page and screenshots.",
                "Confirm all filled values are correct.",
                "Upload files from upload_queue to the correct portal fields.",
                "Do not upload ZIP files.",
                "Do not submit until declarations and attachments are reviewed.",
                "Capture receipt/proof after manual submission.",
            ],
            "artifacts": {
                "live_browser_run_json": str(workspace / "live_browser_assist_run_v47_3.json"),
                "screenshots_dir": str(screenshots_dir),
            },
        }

        _write_json(workspace / "live_browser_assist_run_v47_3.json", result)
        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V47.3 live browser attach failed.",
            "autofill_plan_json": autofill_plan_json,
            "cdp_url": cdp_url,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_v47_3_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V47.3 Attach to Live Browser Session",
        "description": "Connects to an existing Chrome/Chromium session over CDP, uses a V47.1 autofill plan to fill visible fields on the currently open page, captures screenshots, and stops before submit.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "default_cdp_url": DEFAULT_CDP_URL,
        "safety_policy": {
            "auto_submit": False,
            "captcha_bypass": False,
            "operator_confirmation_required": True,
            "zip_upload_allowed": False,
        },
        "browser_start_example": "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/Users/Shared/LMCP-AutoQuote-Server/runtime/chrome_v47_3_profile",
        "endpoints": {
            "status": "/v47-live-browser/status",
            "attach_and_assist": "/v47-live-browser/attach-and-assist",
        },
        "ready": True,
    }
