from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from playwright.async_api import async_playwright


SERVICE_VERSION = "V47_3_LIVE_BROWSER_ATTACH_ENGINE_SESSION_PERSISTENCE"

BASE_DIR = Path("runtime/live_browser_attach_v47_3")
SCREENSHOT_DIR = BASE_DIR / "screenshots"
LAST_RESULT_FILE = BASE_DIR / "last_attach_result.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _parse_plan(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw, "parse_error": True}
    return {}


def _save_last(result: Dict[str, Any]) -> None:
    _ensure_dirs()
    LAST_RESULT_FILE.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")


async def attach_documents_to_live_browser(payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs()

    cdp_url = payload.get("cdp_url") or "http://127.0.0.1:9222"
    plan = _parse_plan(payload.get("autofill_plan_json"))
    rfq_reference = plan.get("rfq_reference") or payload.get("rfq_reference") or "UNKNOWN-RFQ"

    allow_final_submit = bool(plan.get("allow_final_submit") or payload.get("allow_final_submit"))
    if allow_final_submit:
        allow_final_submit = False

    result: Dict[str, Any] = {
        "status": "started",
        "service_version": SERVICE_VERSION,
        "cdp_url": cdp_url,
        "rfq_reference": rfq_reference,
        "allow_final_submit": False,
        "started_at": _now(),
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url)

            contexts = browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = await browser.new_context()

            pages = context.pages
            page = pages[0] if pages else await context.new_page()

            title = ""
            url = ""
            try:
                title = await page.title()
                url = page.url
            except Exception:
                pass

            screenshot_name = f"{rfq_reference}__live_browser_attach.png".replace("/", "_")
            screenshot_path = SCREENSHOT_DIR / screenshot_name

            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception as screenshot_exc:
                screenshot_path = None
                result["screenshot_error"] = str(screenshot_exc)

            await browser.close()

            result.update({
                "status": "ok",
                "message": "Connected to live Chrome CDP session successfully. Operator-controlled assist is ready.",
                "browser_connected": True,
                "page_title": title,
                "page_url": url,
                "screenshot_path": str(screenshot_path) if screenshot_path else None,
                "plan": plan,
                "completed_at": _now(),
                "safety": {
                    "captcha_bypass_allowed": False,
                    "final_submit_blocked": True,
                    "operator_must_review": True,
                },
            })

    except Exception as exc:
        result.update({
            "status": "error",
            "message": "Live browser attach failed.",
            "error": str(exc),
            "completed_at": _now(),
            "safety": {
                "captcha_bypass_allowed": False,
                "final_submit_blocked": True,
            },
        })

    _save_last(result)
    return result


async def attach_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await attach_documents_to_live_browser(payload)


def get_status() -> Dict[str, Any]:
    _ensure_dirs()

    last_result: Dict[str, Any] = {}
    if LAST_RESULT_FILE.exists():
        try:
            last_result = json.loads(LAST_RESULT_FILE.read_text(encoding="utf-8"))
        except Exception:
            last_result = {}

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "summary": {
            "screenshot_dir": str(SCREENSHOT_DIR),
            "headless": False,
            "operator_controlled": True,
        },
        "last_result": last_result,
        "updated_at": _now(),
    }
