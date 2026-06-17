from __future__ import annotations

"""
LMCP AutoQuote - V25 Monthly CSD Refresh Engine

Drop-in path:
    app/services/csd_monthly_refresh_service.py

Runs monthly on the 1st, attempts to pull a fresh CSD report from:
    https://secure.csd.gov.za

If the portal requires OTP/CAPTCHA/manual action, the service records that
safely and keeps the current compliance pack working.
"""

import json
import os
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SERVICE_VERSION = "V25_MONTHLY_CSD_REFRESH_ENGINE"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOCAL_PROJECT_ROOT = Path.cwd().resolve()

COMPLIANCE_DIR = PROJECT_ROOT / "runtime" / "compliance"
CSD_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "csd_monthly_refresh"
DOWNLOAD_DIR = CSD_RUNTIME_DIR / "downloads"
PROOF_DIR = CSD_RUNTIME_DIR / "proof"

for folder in (COMPLIANCE_DIR, CSD_RUNTIME_DIR, DOWNLOAD_DIR, PROOF_DIR):
    folder.mkdir(parents=True, exist_ok=True)

CSD_STATUS_FILE = COMPLIANCE_DIR / "csd_refresh_status.json"
CSD_REPORT_TARGET = COMPLIANCE_DIR / "CSD_Report.pdf"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, fallback: str = "") -> str:
    value = "" if value is None else str(value)
    return value.strip() or fallback


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return _safe_str(value).lower() in {"1", "true", "yes", "y", "on"}


def _safe_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _runtime_root(runtime_dir: Optional[str] = None) -> Path:
    if runtime_dir:
        return Path(runtime_dir).expanduser().resolve()
    return PROJECT_ROOT / "runtime"


def _compliance_dir(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_root(runtime_dir) / "compliance"


def _csd_runtime_dir(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_root(runtime_dir) / "csd_monthly_refresh"


def _download_dir(runtime_dir: Optional[str] = None) -> Path:
    return _csd_runtime_dir(runtime_dir) / "downloads"


def _proof_dir(runtime_dir: Optional[str] = None) -> Path:
    return _csd_runtime_dir(runtime_dir) / "proof"


def _status_file(runtime_dir: Optional[str] = None) -> Path:
    return _compliance_dir(runtime_dir) / "csd_refresh_status.json"


def _report_target(runtime_dir: Optional[str] = None) -> Path:
    return _compliance_dir(runtime_dir) / "CSD_Report.pdf"


def _write_status(status: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    status = dict(status or {})
    status.setdefault("service_version", SERVICE_VERSION)
    status.setdefault("checked_at", _utc_now_iso())
    status_file = _status_file(runtime_dir)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    return status


def _read_status(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    try:
        status_file = _status_file(runtime_dir)
        if status_file.exists():
            data = json.loads(status_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def should_run_monthly_csd_refresh(today: Optional[datetime] = None, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    today = today or datetime.now()
    refresh_day = _safe_int(os.getenv("CSD_REFRESH_DAY", "1"), 1)
    last_status = _read_status(runtime_dir=runtime_dir)
    last_success = _safe_str(last_status.get("last_success_month"))
    current_month = today.strftime("%Y-%m")
    should_run = today.day == refresh_day and last_success != current_month

    return {
        "status": "ok",
        "today": today.date().isoformat(),
        "refresh_day": refresh_day,
        "current_month": current_month,
        "last_success_month": last_success,
        "should_run": should_run,
    }


def _candidate_csd_files(runtime_dir: Optional[str] = None) -> List[Path]:
    compliance_dir = _compliance_dir(runtime_dir)
    csd_runtime_dir = _csd_runtime_dir(runtime_dir)
    download_dir = _download_dir(runtime_dir)
    runtime_root = _runtime_root(runtime_dir)
    folders = [
        compliance_dir,
        download_dir,
        runtime_root / "compliance_docs",
        runtime_root / "company_docs",
        LOCAL_PROJECT_ROOT / "runtime" / "compliance",
    ]
    patterns = [
        "*CSD*.pdf",
        "*Central*Supplier*Database*.pdf",
        "*Supplier*Database*.pdf",
        "*supplier*database*.pdf",
    ]

    files: List[Path] = []
    for folder in folders:
        try:
            if not folder.exists() or not folder.is_dir():
                continue
            for pattern in patterns:
                files.extend(folder.glob(pattern))
                files.extend(folder.glob(pattern.upper()))
                files.extend(folder.glob(pattern.lower()))
        except Exception:
            continue

    clean: List[Path] = []
    seen = set()
    for path in files:
        try:
            if path.exists() and path.is_file() and path.suffix.lower() == ".pdf":
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    clean.append(path)
        except Exception:
            continue

    clean.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return clean


def _copy_to_standard_csd_report(source: Path, runtime_dir: Optional[str] = None) -> str:
    report_target = _report_target(runtime_dir)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, report_target)
    return str(report_target)


def _run_playwright_csd_download(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    login_url = _safe_str(os.getenv("CSD_LOGIN_URL"), "https://secure.csd.gov.za")
    username = _safe_str(os.getenv("CSD_USERNAME"))
    password = _safe_str(os.getenv("CSD_PASSWORD"))
    headless = _safe_bool(os.getenv("CSD_HEADLESS"), False)

    if not username or not password:
        return {
            "status": "manual_action_required",
            "reason": "missing_credentials",
            "message": "CSD_USERNAME and CSD_PASSWORD are required.",
            "login_url": login_url,
        }

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "status": "manual_action_required",
            "reason": "playwright_unavailable",
            "message": f"Playwright is unavailable: {exc}",
            "login_url": login_url,
        }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            page.goto(login_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(3000)

            proof_start = _proof_dir(runtime_dir) / f"csd_start_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            try:
                page.screenshot(path=str(proof_start), full_page=True)
            except Exception:
                proof_start = None

            username_selectors = [
                'input[name="UserName"]', 'input[name="Username"]',
                'input[name="username"]', 'input[name="Email"]',
                'input[type="email"]', '#UserName', '#Username', '#username',
            ]
            password_selectors = [
                'input[name="Password"]', 'input[name="password"]',
                'input[type="password"]', '#Password', '#password',
            ]

            filled_user = False
            for selector in username_selectors:
                try:
                    loc = page.locator(selector).first
                    if loc.count() > 0:
                        loc.fill(username)
                        filled_user = True
                        break
                except Exception:
                    continue

            filled_pass = False
            for selector in password_selectors:
                try:
                    loc = page.locator(selector).first
                    if loc.count() > 0:
                        loc.fill(password)
                        filled_pass = True
                        break
                except Exception:
                    continue

            if not filled_user or not filled_pass:
                return {
                    "status": "manual_action_required",
                    "reason": "login_fields_not_found",
                    "message": "Could not locate CSD login fields.",
                    "proof_screenshot": str(proof_start) if proof_start else "",
                    "login_url": login_url,
                }

            for selector in [
                'button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Login")', 'button:has-text("Sign in")',
                'text=Login', 'text=Sign in',
            ]:
                try:
                    loc = page.locator(selector).first
                    if loc.count() > 0:
                        loc.click()
                        break
                except Exception:
                    continue

            page.wait_for_timeout(8000)

            proof_after_login = PROOF_DIR / f"csd_after_login_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            try:
                page.screenshot(path=str(proof_after_login), full_page=True)
            except Exception:
                proof_after_login = None

            try:
                body_text = page.locator("body").inner_text(timeout=5000).lower()
            except Exception:
                body_text = ""

            if any(t in body_text for t in ["captcha", "otp", "verification code", "one time pin", "multi-factor"]):
                return {
                    "status": "manual_action_required",
                    "reason": "captcha_or_otp_required",
                    "message": "CSD requires CAPTCHA/OTP/manual verification.",
                    "proof_screenshot": str(proof_after_login) if proof_after_login else "",
                    "login_url": login_url,
                }

            for selector in [
                'text=CSD Report', 'text=Supplier Report', 'text=Registration Report',
                'text=Download Report', 'text=Download', 'a:has-text("CSD")',
                'a:has-text("Report")', 'button:has-text("Download")',
                'button:has-text("Report")',
            ]:
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
                    standard = _copy_to_standard_csd_report(save_path)
                    return {
                        "status": "ok",
                        "message": "CSD report downloaded and saved.",
                        "downloaded_pdf": str(save_path),
                        "standard_csd_report": standard,
                        "proof_screenshot": str(proof_after_login) if proof_after_login else "",
                    }
                except Exception:
                    continue

            return {
                "status": "manual_action_required",
                "reason": "download_link_not_found",
                "message": "Could not find/download the CSD report automatically.",
                "proof_screenshot": str(proof_after_login) if proof_after_login else "",
                "login_url": login_url,
            }

        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass


def refresh_csd_report(force: bool = False, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now()
    schedule = should_run_monthly_csd_refresh(now, runtime_dir=runtime_dir)
    report_target = _report_target(runtime_dir)

    if not force and not schedule.get("should_run"):
        return _write_status({
            "status": "skipped",
            "message": "CSD refresh not due today.",
            "schedule": schedule,
            "existing_csd_report": str(report_target) if report_target.exists() else "",
            "existing_csd_report_found": report_target.exists(),
        }, runtime_dir=runtime_dir)

    try:
        result = _run_playwright_csd_download(runtime_dir=runtime_dir)

        if result.get("status") == "ok":
            result.update({
                "last_success_at": _utc_now_iso(),
                "last_success_month": now.strftime("%Y-%m"),
                "next_refresh_due_day": _safe_int(os.getenv("CSD_REFRESH_DAY", "1"), 1),
            })
            return _write_status(result, runtime_dir=runtime_dir)

        candidates = _candidate_csd_files(runtime_dir=runtime_dir)
        if candidates:
            standard = _copy_to_standard_csd_report(candidates[0], runtime_dir=runtime_dir)
            return _write_status({
                "status": "ok_with_existing_report",
                "message": "Auto-download did not complete, but existing CSD report was standardized.",
                "manual_result": result,
                "existing_source": str(candidates[0]),
                "standard_csd_report": standard,
                "last_success_at": _utc_now_iso(),
                "last_success_month": now.strftime("%Y-%m"),
            }, runtime_dir=runtime_dir)

        return _write_status({
            **result,
            "last_attempt_at": _utc_now_iso(),
            "standard_csd_report": "",
        }, runtime_dir=runtime_dir)

    except Exception as exc:
        return _write_status({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "last_attempt_at": _utc_now_iso(),
        }, runtime_dir=runtime_dir)


def get_csd_refresh_status(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    compliance_dir = _compliance_dir(runtime_dir)
    report_target = _report_target(runtime_dir)
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _utc_now_iso(),
        "csd_login_url": _safe_str(os.getenv("CSD_LOGIN_URL"), "https://secure.csd.gov.za"),
        "compliance_dir": str(compliance_dir),
        "standard_csd_report": str(report_target),
        "standard_csd_report_exists": report_target.exists(),
        "schedule": should_run_monthly_csd_refresh(runtime_dir=runtime_dir),
        "last_status": _read_status(runtime_dir=runtime_dir),
    }


def run_monthly_csd_refresh_if_due(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    return refresh_csd_report(force=False, runtime_dir=runtime_dir)


def run(force: bool = False, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    return refresh_csd_report(force=force, runtime_dir=runtime_dir)


if __name__ == "__main__":
    print(json.dumps(refresh_csd_report(force=True), indent=2, default=str))
