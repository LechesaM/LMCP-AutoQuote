from __future__ import annotations

"""
LMCP AutoQuote - V25.1 Persistent CSD Session Engine

Drop-in:
    app/services/csd_persistent_session_service.py

Purpose:
    Reuse a persistent Playwright browser profile for CSD.

Flow:
    1. Start manual login browser/profile.
    2. User logs in once.
    3. Session cookies/profile are saved in runtime/playwright/csd_profile.
    4. Monthly refresh reuses profile.
    5. If CSD session expires or OTP/CAPTCHA appears, return manual_action_required.
"""

import json
import os
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVICE_VERSION = "V25_1_PERSISTENT_CSD_SESSION_ENGINE"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
RUNTIME_DIR = PROJECT_ROOT / "runtime"
COMPLIANCE_DIR = RUNTIME_DIR / "compliance"
PLAYWRIGHT_DIR = RUNTIME_DIR / "playwright"
CSD_PROFILE_DIR = PLAYWRIGHT_DIR / "csd_profile"
CSD_RUNTIME_DIR = RUNTIME_DIR / "csd_monthly_refresh"
DOWNLOAD_DIR = CSD_RUNTIME_DIR / "downloads"
PROOF_DIR = CSD_RUNTIME_DIR / "proof"
STATUS_FILE = COMPLIANCE_DIR / "csd_persistent_session_status.json"
CSD_REPORT_TARGET = COMPLIANCE_DIR / "CSD_Report.pdf"

for folder in (COMPLIANCE_DIR, PLAYWRIGHT_DIR, CSD_PROFILE_DIR, CSD_RUNTIME_DIR, DOWNLOAD_DIR, PROOF_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, fallback: str = "") -> str:
    value = "" if value is None else str(value)
    return value.strip() or fallback


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return _safe_str(value).lower() in {"1", "true", "yes", "y", "on"}


def _write_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    payload.setdefault("service_version", SERVICE_VERSION)
    payload.setdefault("checked_at", _now())
    STATUS_FILE.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def _read_status() -> Dict[str, Any]:
    try:
        if STATUS_FILE.exists():
            data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _profile_has_data() -> bool:
    try:
        return CSD_PROFILE_DIR.exists() and any(CSD_PROFILE_DIR.iterdir())
    except Exception:
        return False


def _find_downloaded_pdf() -> Optional[Path]:
    files: List[Path] = []
    try:
        files.extend(DOWNLOAD_DIR.glob("*.pdf"))
    except Exception:
        pass
    if not files:
        return None
    files = [p for p in files if p.exists() and p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _copy_to_standard_report(source: Path) -> str:
    COMPLIANCE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, CSD_REPORT_TARGET)
    return str(CSD_REPORT_TARGET)


def get_persistent_csd_session_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "csd_url": _safe_str(os.getenv("CSD_LOGIN_URL"), "https://secure.csd.gov.za"),
        "profile_dir": str(CSD_PROFILE_DIR),
        "profile_exists": CSD_PROFILE_DIR.exists(),
        "profile_has_data": _profile_has_data(),
        "standard_csd_report": str(CSD_REPORT_TARGET),
        "standard_csd_report_exists": CSD_REPORT_TARGET.exists(),
        "last_status": _read_status(),
    }


def start_manual_csd_login_session(headless: Optional[bool] = None, wait_seconds: int = 180) -> Dict[str, Any]:
    """
    Opens persistent browser profile so the user can log in manually.

    For Docker without display, run this on a machine/container with GUI support.
    If headless=True, manual login is not useful.
    """
    csd_url = _safe_str(os.getenv("CSD_LOGIN_URL"), "https://secure.csd.gov.za")
    if headless is None:
        headless = _safe_bool(os.getenv("CSD_HEADLESS"), False)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return _write_status({
            "status": "manual_action_required",
            "reason": "playwright_unavailable",
            "message": f"Playwright unavailable: {exc}",
        })

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(CSD_PROFILE_DIR),
                headless=headless,
                accept_downloads=True,
                downloads_path=str(DOWNLOAD_DIR),
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(csd_url, wait_until="domcontentloaded", timeout=90000)

            proof = PROOF_DIR / f"csd_manual_login_start_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            try:
                page.screenshot(path=str(proof), full_page=True)
            except Exception:
                proof = None

            # Give user time to complete login. In non-GUI Docker, this will not help unless display is exposed.
            page.wait_for_timeout(max(5, int(wait_seconds)) * 1000)

            proof_after = PROOF_DIR / f"csd_manual_login_after_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            try:
                page.screenshot(path=str(proof_after), full_page=True)
            except Exception:
                proof_after = None

            context.close()

        return _write_status({
            "status": "ok",
            "message": "Persistent CSD profile session was opened and saved. If login was completed, future refresh can reuse it.",
            "profile_dir": str(CSD_PROFILE_DIR),
            "profile_has_data": _profile_has_data(),
            "proof_start": str(proof) if proof else "",
            "proof_after": str(proof_after) if proof_after else "",
        })

    except Exception as exc:
        return _write_status({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })


def refresh_csd_report_with_persistent_session() -> Dict[str, Any]:
    csd_url = _safe_str(os.getenv("CSD_LOGIN_URL"), "https://secure.csd.gov.za")
    headless = _safe_bool(os.getenv("CSD_HEADLESS"), True)

    if not _profile_has_data():
        return _write_status({
            "status": "manual_action_required",
            "reason": "profile_missing",
            "message": "Persistent CSD browser profile is empty. Run manual login setup first.",
            "profile_dir": str(CSD_PROFILE_DIR),
        })

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return _write_status({
            "status": "manual_action_required",
            "reason": "playwright_unavailable",
            "message": f"Playwright unavailable: {exc}",
        })

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(CSD_PROFILE_DIR),
                headless=headless,
                accept_downloads=True,
                downloads_path=str(DOWNLOAD_DIR),
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(csd_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)

            proof = PROOF_DIR / f"csd_persistent_refresh_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            try:
                page.screenshot(path=str(proof), full_page=True)
            except Exception:
                proof = None

            text = ""
            try:
                text = page.locator("body").inner_text(timeout=5000).lower()
            except Exception:
                pass

            if any(t in text for t in ["captcha", "otp", "verification code", "one time pin"]):
                context.close()
                return _write_status({
                    "status": "manual_action_required",
                    "reason": "captcha_or_otp_required",
                    "message": "CSD requires OTP/CAPTCHA again. Manual session refresh required.",
                    "proof_screenshot": str(proof) if proof else "",
                })

            if any(t in text for t in ["login", "sign in", "username", "password"]) and not any(
                t in text for t in ["supplier", "report", "dashboard", "central supplier database"]
            ):
                context.close()
                return _write_status({
                    "status": "manual_action_required",
                    "reason": "session_expired_or_login_page",
                    "message": "Persistent CSD session appears expired. Run manual login setup again.",
                    "proof_screenshot": str(proof) if proof else "",
                })

            selectors = [
                'text=CSD Report',
                'text=Supplier Report',
                'text=Registration Report',
                'text=Download Report',
                'text=Download',
                'a:has-text("CSD")',
                'a:has-text("Report")',
                'button:has-text("Download")',
                'button:has-text("Report")',
            ]

            downloaded = None
            for selector in selectors:
                try:
                    loc = page.locator(selector).first
                    if loc.count() <= 0:
                        continue
                    with page.expect_download(timeout=30000) as download_info:
                        loc.click()
                    download = download_info.value
                    suggested = download.suggested_filename or f"CSD_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
                    if not suggested.lower().endswith(".pdf"):
                        suggested += ".pdf"
                    save_path = DOWNLOAD_DIR / suggested
                    download.save_as(str(save_path))
                    downloaded = save_path
                    break
                except Exception:
                    continue

            if not downloaded:
                downloaded = _find_downloaded_pdf()

            context.close()

            if downloaded and downloaded.exists():
                standard = _copy_to_standard_report(downloaded)
                return _write_status({
                    "status": "ok",
                    "message": "CSD report refreshed using persistent session.",
                    "downloaded_pdf": str(downloaded),
                    "standard_csd_report": standard,
                    "standard_csd_report_exists": True,
                    "proof_screenshot": str(proof) if proof else "",
                    "last_success_at": _now(),
                    "last_success_month": datetime.now().strftime("%Y-%m"),
                })

            return _write_status({
                "status": "manual_action_required",
                "reason": "download_link_not_found",
                "message": "Persistent session opened, but CSD report download link was not found.",
                "proof_screenshot": str(proof) if proof else "",
            })

    except Exception as exc:
        return _write_status({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })


def clear_persistent_csd_session() -> Dict[str, Any]:
    try:
        if CSD_PROFILE_DIR.exists():
            shutil.rmtree(CSD_PROFILE_DIR)
        CSD_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        return _write_status({
            "status": "ok",
            "message": "Persistent CSD session profile cleared.",
            "profile_dir": str(CSD_PROFILE_DIR),
        })
    except Exception as exc:
        return _write_status({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })
