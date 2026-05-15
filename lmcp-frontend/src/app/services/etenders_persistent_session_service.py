from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

RUNTIME_DIR = Path("runtime")
ETENDERS_DIR = RUNTIME_DIR / "etenders_session"
ETENDERS_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_DIR = ETENDERS_DIR / "playwright_profile"
PROOF_DIR = ETENDERS_DIR / "proofs"
PROOF_DIR.mkdir(parents=True, exist_ok=True)

STATUS_FILE = ETENDERS_DIR / "status.json"

ETENDERS_LOGIN_URL = "https://www.etenders.gov.za/Login/Login"
ETENDERS_HOME_URL = "https://www.etenders.gov.za"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save(data: Dict[str, Any]) -> Dict[str, Any]:
    STATUS_FILE.write_text(json.dumps(data, indent=2, default=str))
    return data


def _load_status() -> Dict[str, Any]:
    if not STATUS_FILE.exists():
        return {}
    try:
        data = json.loads(STATUS_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa
        return True
    except Exception:
        return False


def get_etenders_session_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "session": _load_status(),
        "profile_dir": str(PROFILE_DIR),
        "proof_dir": str(PROOF_DIR),
        "message": "Manual login/session reuse layer active. CAPTCHA is not bypassed.",
        "updated_at": _now(),
    }


def open_manual_login_instruction() -> Dict[str, Any]:
    return _save({
        "status": "manual_login_required",
        "message": "Open eTenders manually using the persistent profile, complete CAPTCHA/login, then run session probe.",
        "login_url": ETENDERS_LOGIN_URL,
        "profile_dir": str(PROFILE_DIR),
        "proof_dir": str(PROOF_DIR),
        "commands": [
            "docker compose exec api python -m playwright install chromium",
            "docker compose exec api python - <<'PY'",
            "from app.services.etenders_persistent_session_service import launch_manual_login_browser",
            "print(launch_manual_login_browser(headless=False))",
            "PY",
        ],
        "updated_at": _now(),
    })


def launch_manual_login_browser(headless: bool = False, timeout_ms: int = 120000) -> Dict[str, Any]:
    if not _playwright_available():
        return _save({
            "status": "error",
            "message": "Playwright is not available. Install it inside the api container first.",
            "profile_dir": str(PROFILE_DIR),
            "updated_at": _now(),
        })

    from playwright.sync_api import sync_playwright

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            viewport={"width": 1440, "height": 950},
            accept_downloads=True,
        )

        page = browser.new_page()
        page.goto(ETENDERS_LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        screenshot = PROOF_DIR / f"manual_login_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        page.screenshot(path=str(screenshot), full_page=True)

        # Keep the browser open briefly if headed; user may need to complete CAPTCHA/login.
        # In API calls this cannot wait forever, so use terminal workflow for manual login.
        if not headless:
            page.wait_for_timeout(15000)

        browser.close()

    return _save({
        "status": "manual_login_browser_opened",
        "message": "Login browser opened using persistent profile. Complete CAPTCHA/login manually if headed mode is available.",
        "headless": headless,
        "login_url": ETENDERS_LOGIN_URL,
        "profile_dir": str(PROFILE_DIR),
        "screenshot": str(screenshot),
        "updated_at": _now(),
    })


def probe_persistent_session(headless: bool = True, timeout_ms: int = 120000) -> Dict[str, Any]:
    if not _playwright_available():
        return _save({
            "status": "error",
            "likely_logged_in": False,
            "login_required": True,
            "message": "Playwright is not available. Cannot probe persistent session.",
            "updated_at": _now(),
        })

    from playwright.sync_api import sync_playwright

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            viewport={"width": 1440, "height": 950},
            accept_downloads=True,
        )

        page = browser.new_page()
        page.goto(ETENDERS_HOME_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(3000)

        title = page.title()
        url = page.url

        try:
            body = page.locator("body").inner_text(timeout=8000)
        except Exception:
            body = ""

        screenshot = PROOF_DIR / f"session_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        page.screenshot(path=str(screenshot), full_page=True)

        browser.close()

    lower = body.lower()
    login_required = any(word in lower for word in ["captcha", "username", "password", "login", "sign in"])
    likely_logged_in = bool(body.strip()) and not login_required

    return _save({
        "status": "ok",
        "likely_logged_in": likely_logged_in,
        "login_required": login_required,
        "title": title,
        "url": url,
        "screenshot": str(screenshot),
        "profile_dir": str(PROFILE_DIR),
        "message": "Persistent session appears usable." if likely_logged_in else "Manual login/CAPTCHA likely required.",
        "checked_at": _now(),
    })


def classify_etenders_submission_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    rfq = payload.get("buyer_rfq_number") or payload.get("tender_number") or ""
    session = _load_status()

    if not rfq:
        return {
            "status": "manual_action_required",
            "buyer_rfq_number": "",
            "reason": "RFQ/tender number missing.",
            "session": session,
            "checked_at": _now(),
        }

    if not session.get("likely_logged_in"):
        return {
            "status": "manual_action_required",
            "buyer_rfq_number": rfq,
            "reason": "No confirmed logged-in persistent eTenders session. Manual CAPTCHA/login required.",
            "session": session,
            "checked_at": _now(),
        }

    if session.get("login_required"):
        return {
            "status": "manual_action_required",
            "buyer_rfq_number": rfq,
            "reason": "Session probe indicates login/CAPTCHA is required.",
            "session": session,
            "checked_at": _now(),
        }

    return {
        "status": "portal_session_ready",
        "buyer_rfq_number": rfq,
        "reason": "Persistent session appears ready. Actual upload/submit still requires a tested portal adapter and proof capture.",
        "session": session,
        "checked_at": _now(),
    }
