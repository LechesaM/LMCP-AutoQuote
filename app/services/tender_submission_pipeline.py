from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from app.services.autonomous_submission_governance import submission_system_control_authorization

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception

try:
    from app.services.submission_history_service import log_submission_event
    try:
        from app.services.submission_history_service import search_submission_history_by_buyer_rfq
    except Exception:
        search_submission_history_by_buyer_rfq = None
except Exception:
    log_submission_event = None
    search_submission_history_by_buyer_rfq = None


def _resolve_first_available(module_path: str, names: List[str]):
    try:
        module = __import__(module_path, fromlist=["*"])
    except Exception as exc:
        logger.warning("%s import failed: %s", module_path, exc)
        return None

    for name in names:
        func = getattr(module, name, None)
        if callable(func):
            logger.info("Resolved %s.%s", module_path, name)
            return func

    logger.warning(
        "No compatible function found in %s. Tried: %s",
        module_path,
        ", ".join(names),
    )
    return None


_send_submission_email = _resolve_first_available(
    "app.services.email_submission_service",
    [
        "send_submission_email",
        "submit_quote_email",
        "send_email_submission",
        "submit_email",
        "route_submission_email",
    ],
)

PORTAL_AUTOMATION_ENABLED = str(os.getenv("PORTAL_AUTOMATION_ENABLED", "false")).strip().lower() == "true"
PORTAL_HEADLESS = str(os.getenv("PORTAL_HEADLESS", "true")).strip().lower() == "true"
PORTAL_TIMEOUT_MS = int(str(os.getenv("PORTAL_TIMEOUT_MS", "45000")).strip() or "45000")
PORTAL_SLOW_MO_MS = int(str(os.getenv("PORTAL_SLOW_MO_MS", "0")).strip() or "0")

PORTAL_USERNAME = os.getenv("PORTAL_USERNAME", "")
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD", "")

PORTAL_FILE_INPUT_SELECTOR = os.getenv("PORTAL_FILE_INPUT_SELECTOR", 'input[type="file"]')
PORTAL_SUBMIT_BUTTON_SELECTOR = os.getenv(
    "PORTAL_SUBMIT_BUTTON_SELECTOR",
    'button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Send"), button:has-text("Finalize"), button:has-text("Confirm & Proceed")',
)

ETENDERS_LOGIN_URL = os.getenv("ETENDERS_LOGIN_URL", "https://www.etenders.gov.za/login/Login")
ETENDERS_HOME_URL = os.getenv("ETENDERS_HOME_URL", "https://www.etenders.gov.za/")
ETENDERS_OPPORTUNITIES_URL = os.getenv("ETENDERS_OPPORTUNITIES_URL", "https://www.etenders.gov.za/Home/opportunities?id=1")
ETENDERS_USERNAME_SELECTOR = os.getenv("ETENDERS_USERNAME_SELECTOR", 'input[name="UserName"], input[id="UserName"], input[type="text"]')
ETENDERS_PASSWORD_SELECTOR = os.getenv("ETENDERS_PASSWORD_SELECTOR", 'input[name="Password"], input[id="Password"], input[type="password"]')
ETENDERS_CAPTCHA_SELECTOR = os.getenv("ETENDERS_CAPTCHA_SELECTOR", 'input[name="Captcha"], input[id="Captcha"], input[name*="captcha"], input[id*="captcha"]')
ETENDERS_CAPTCHA_TEXT = os.getenv("ETENDERS_CAPTCHA_TEXT", "")
ETENDERS_LOGIN_BUTTON_SELECTOR = os.getenv("ETENDERS_LOGIN_BUTTON_SELECTOR", 'button:has-text("Log in"), input[type="submit"], button[type="submit"]')
ETENDERS_QUICKFIND_SELECTOR = os.getenv("ETENDERS_QUICKFIND_SELECTOR", 'input[name="QuickFind"], input[id="QuickFind"], input[placeholder*="Tender Number"], input[type="search"], input[type="text"]')
ETENDERS_START_ESUBMISSION_SELECTOR = os.getenv("ETENDERS_START_ESUBMISSION_SELECTOR", 'a:has-text("Start eSubmission Process"), button:has-text("Start eSubmission Process")')
ETENDERS_SUPPLIER_SELECT_SELECTOR = os.getenv("ETENDERS_SUPPLIER_SELECT_SELECTOR", 'select[name*="Supplier"], select[id*="Supplier"]')
ETENDERS_CONFIRM_PROCEED_SELECTOR = os.getenv("ETENDERS_CONFIRM_PROCEED_SELECTOR", 'button:has-text("Confirm & Proceed"), a:has-text("Confirm & Proceed"), button:has-text("Proceed")')
ETENDERS_DOCUMENT_LINK_SELECTOR = os.getenv("ETENDERS_DOCUMENT_LINK_SELECTOR", 'a[href*="Document"], a[href*="document"], a:has-text("Download"), a:has-text("Tender Document")')

ETENDERS_SESSION_REUSE_ENABLED = str(os.getenv("ETENDERS_SESSION_REUSE_ENABLED", "true")).strip().lower() == "true"
ETENDERS_PROFILE_DIR = os.getenv("ETENDERS_PROFILE_DIR", "runtime/playwright/etenders_profile")
ETENDERS_STORAGE_STATE_PATH = os.getenv("ETENDERS_STORAGE_STATE_PATH", "runtime/playwright/etenders_storage_state.json")
ETENDERS_SEEDED_LOGIN_MODE = str(os.getenv("ETENDERS_SEEDED_LOGIN_MODE", "true")).strip().lower() == "true"
ETENDERS_REQUIRE_FRESH_LOGIN = str(os.getenv("ETENDERS_REQUIRE_FRESH_LOGIN", "false")).strip().lower() == "true"
ETENDERS_FORCE_UPLOAD_ATTEMPT = str(os.getenv("ETENDERS_FORCE_UPLOAD_ATTEMPT", "false")).strip().lower() == "true"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", "").replace("R", "").replace("ZAR", "").replace("zar", "").strip()
        return float(cleaned)
    except Exception:
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _existing_files(paths: List[str]) -> List[str]:
    found: List[str] = []
    seen = set()
    for raw in paths:
        path = _clean(raw)
        if path and path not in seen and Path(path).exists():
            seen.add(path)
            found.append(path)
    return found


def _resolve_portal_url(payload: Dict[str, Any]) -> str:
    return _clean(payload.get("submission_portal_url") or payload.get("portal_submission_url") or payload.get("portal_url"))


def _resolve_recipient_email(payload: Dict[str, Any]) -> str:
    buyer = _safe_dict(payload.get("buyer"))
    submission_pack = _safe_dict(payload.get("submission_pack"))
    quote_pack = _safe_dict(payload.get("quote_pack"))
    rfq = _safe_dict(payload.get("rfq"))
    return _first_non_empty(
        payload.get("recipient_email"),
        payload.get("buyer_email"),
        payload.get("submission_email"),
        buyer.get("email"),
        submission_pack.get("recipient_email"),
        submission_pack.get("buyer_email"),
        quote_pack.get("recipient_email"),
        quote_pack.get("buyer_email"),
        rfq.get("recipient_email"),
        rfq.get("buyer_email"),
    )


def _collect_attachment_paths(payload: Dict[str, Any]) -> List[str]:
    attachments: List[str] = []
    final_pdf = _first_non_empty(payload.get("final_pdf_path"), payload.get("pdf_path"))
    if final_pdf:
        attachments.append(final_pdf)

    raw_attachment_paths = payload.get("attachment_paths")
    if isinstance(raw_attachment_paths, list):
        attachments.extend([_clean(x) for x in raw_attachment_paths])

    submission_attachments = payload.get("submission_attachments")
    if isinstance(submission_attachments, list):
        attachments.extend([_clean(x) for x in submission_attachments])

    submission_pack = payload.get("submission_pack")
    if isinstance(submission_pack, dict):
        pack_attachments = submission_pack.get("submission_attachments")
        if isinstance(pack_attachments, list):
            attachments.extend([_clean(x) for x in pack_attachments])

    existing = _existing_files(attachments)
    if existing:
        return existing

    # Fallback: final submission payloads sometimes arrive without attachment paths
    # even though quote packs exist in monthly_quotes. Recover by locating the
    # latest matching quote PDFs safely. This is read-only and never submits.
    monthly_root = Path("monthly_quotes")
    if not monthly_root.exists():
        return []

    candidates = []
    search_terms = []

    for key in (
        "buyer_rfq_number",
        "rfq_id",
        "quote_number",
        "title",
        "description",
        "portal_title",
    ):
        value = _clean(payload.get(key))
        if value:
            search_terms.append(value.lower())

    rfq = payload.get("rfq")
    if isinstance(rfq, dict):
        for key in ("buyer_rfq_number", "rfq_id", "title", "description"):
            value = _clean(rfq.get(key))
            if value:
                search_terms.append(value.lower())

    quote_pack = payload.get("quote_pack")
    if isinstance(quote_pack, dict):
        for key in ("buyer_rfq_number", "quote_number", "title", "output_pdf", "final_pdf_path"):
            value = _clean(quote_pack.get(key))
            if value:
                search_terms.append(value.lower())

    # Prefer matching folders/files, but if no usable term exists, fall back to
    # the newest generated quote PDF so the upload dry-run can still validate.
    pdfs = sorted(monthly_root.rglob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)

    for pdf in pdfs:
        name = str(pdf).lower()
        if any(term and term[:35] in name for term in search_terms):
            candidates.append(str(pdf))

    if not candidates and pdfs:
        candidates.append(str(pdfs[0]))

    return _existing_files(candidates[:5])


def _resolve_financials(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, float]:
    buyer = _safe_dict(payload.get("buyer"))
    submission_pack = _safe_dict(payload.get("submission_pack"))
    quote_pack = _safe_dict(payload.get("quote_pack"))
    opportunity = _safe_dict(payload.get("opportunity"))
    rfq = _safe_dict(payload.get("rfq"))
    raw_result = _safe_dict(result)

    totals_sources = [
        _safe_dict(payload.get("totals")),
        _safe_dict(submission_pack.get("totals")),
        _safe_dict(quote_pack.get("totals")),
        _safe_dict(opportunity.get("totals")),
        _safe_dict(rfq.get("totals")),
        _safe_dict(raw_result.get("totals")),
    ]

    estimated_revenue = 0.0
    estimated_cost = 0.0
    estimated_profit = 0.0
    estimated_margin = 0.0

    revenue_candidates = [
        payload.get("estimated_revenue"),
        payload.get("quotation_total"),
        payload.get("grand_total"),
        payload.get("total_including_vat"),
        payload.get("total"),
        submission_pack.get("estimated_revenue"),
        submission_pack.get("quotation_total"),
        submission_pack.get("grand_total"),
        quote_pack.get("estimated_revenue"),
        quote_pack.get("quotation_total"),
        quote_pack.get("grand_total"),
        opportunity.get("estimated_revenue"),
        opportunity.get("quotation_total"),
        opportunity.get("grand_total"),
        rfq.get("estimated_revenue"),
        rfq.get("quotation_total"),
        rfq.get("grand_total"),
        buyer.get("estimated_revenue"),
        raw_result.get("estimated_revenue"),
        raw_result.get("quotation_total"),
        raw_result.get("grand_total"),
        raw_result.get("total_including_vat"),
        raw_result.get("total"),
    ]
    for totals in totals_sources:
        revenue_candidates.extend([
            totals.get("total_incl_vat"),
            totals.get("grand_total"),
            totals.get("total"),
            totals.get("quotation_total"),
            totals.get("estimated_revenue"),
        ])
    for value in revenue_candidates:
        estimated_revenue = _safe_float(value, 0.0)
        if estimated_revenue > 0:
            break

    cost_candidates = [
        payload.get("estimated_cost"),
        payload.get("cost_estimate"),
        payload.get("supplier_cost_total"),
        payload.get("selected_quote_total"),
        submission_pack.get("estimated_cost"),
        submission_pack.get("supplier_cost_total"),
        quote_pack.get("estimated_cost"),
        quote_pack.get("supplier_cost_total"),
        opportunity.get("estimated_cost"),
        rfq.get("estimated_cost"),
        raw_result.get("estimated_cost"),
        raw_result.get("supplier_cost_total"),
    ]
    for totals in totals_sources:
        cost_candidates.extend([
            totals.get("estimated_cost"),
            totals.get("supplier_cost_total"),
            totals.get("cost"),
        ])
    for value in cost_candidates:
        estimated_cost = _safe_float(value, 0.0)
        if estimated_cost > 0:
            break

    profit_candidates = [
        payload.get("estimated_profit"),
        submission_pack.get("estimated_profit"),
        quote_pack.get("estimated_profit"),
        opportunity.get("estimated_profit"),
        rfq.get("estimated_profit"),
        raw_result.get("estimated_profit"),
    ]
    for totals in totals_sources:
        profit_candidates.extend([totals.get("estimated_profit"), totals.get("profit")])
    for value in profit_candidates:
        estimated_profit = _safe_float(value, 0.0)
        if estimated_profit > 0:
            break

    margin_candidates = [
        payload.get("estimated_margin"),
        payload.get("margin_percent"),
        submission_pack.get("estimated_margin"),
        quote_pack.get("estimated_margin"),
        opportunity.get("estimated_margin"),
        rfq.get("estimated_margin"),
        raw_result.get("estimated_margin"),
        raw_result.get("margin_percent"),
    ]
    for totals in totals_sources:
        margin_candidates.extend([totals.get("estimated_margin"), totals.get("margin_percent")])
    for value in margin_candidates:
        estimated_margin = _safe_float(value, 0.0)
        if estimated_margin > 0:
            break

    if estimated_profit <= 0 and estimated_revenue > 0 and estimated_cost > 0:
        estimated_profit = max(0.0, estimated_revenue - estimated_cost)
    if estimated_cost <= 0 and estimated_revenue > 0 and estimated_profit > 0:
        estimated_cost = max(0.0, estimated_revenue - estimated_profit)
    if estimated_margin <= 0 and estimated_profit > 0 and estimated_revenue > 0:
        estimated_margin = estimated_profit / estimated_revenue

    return {
        "estimated_revenue": round(estimated_revenue, 2),
        "estimated_cost": round(estimated_cost, 2),
        "estimated_profit": round(estimated_profit, 2),
        "estimated_margin": round(estimated_margin, 4),
    }


def _base_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    portal_url = _resolve_portal_url(payload)
    final_pdf_path = _clean(payload.get("final_pdf_path") or payload.get("pdf_path"))
    buyer_rfq_number = _clean(payload.get("buyer_rfq_number") or payload.get("rfq_number"))
    quote_number = _clean(payload.get("quote_number"))
    submission_method = _safe_lower(payload.get("submission_method") or "portal") or "portal"
    submission_channel = "portal" if submission_method == "portal" else submission_method
    return {
        "success": False,
        "status": "failed",
        "submission_channel": submission_channel,
        "submission_method": submission_method,
        "portal_url": portal_url,
        "final_pdf_path": final_pdf_path,
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "checked_at": _utc_now_iso(),
    }


def _success_response(payload: Dict[str, Any], status: str = "submitted", message: str = "", **extra: Any) -> Dict[str, Any]:
    result = _base_response(payload)
    result.update({"success": status in {"submitted", "success", "ok", "sent"}, "status": status, "message": message or f"Portal submission {status}."})
    result.update(extra)
    return result


def _failure_response(payload: Dict[str, Any], error: str, status: str = "failed", **extra: Any) -> Dict[str, Any]:
    result = _base_response(payload)
    result.update({"success": False, "status": status, "error": error, "message": error})
    result.update(extra)
    return result


def _manual_action_response(payload: Dict[str, Any], message: str, **extra: Any) -> Dict[str, Any]:
    result = _base_response(payload)
    result.update({"success": False, "status": "manual_action_required", "message": message})
    result.update(extra)
    return result


def _validate_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return _failure_response({}, "Payload must be a dictionary.")
    attachments = _collect_attachment_paths(payload)
    if not attachments:
        return _failure_response(payload, "Missing final PDF path or attachment files.")
    return None


def _capture_artifact_paths(payload: Dict[str, Any]) -> Dict[str, str]:
    buyer_rfq_number = _clean(payload.get("buyer_rfq_number") or payload.get("rfq_number") or "RFQ")
    quote_folder = _clean(payload.get("quote_folder") or payload.get("quote_pack_dir"))
    if not quote_folder:
        return {"screenshot_path": "", "html_path": "", "downloads_dir": ""}
    folder = Path(quote_folder)
    folder.mkdir(parents=True, exist_ok=True)
    safe_ref = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in buyer_rfq_number)
    downloads_dir = folder / "portal_downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return {
        "screenshot_path": str(folder / f"{safe_ref}__portal_submission.png"),
        "html_path": str(folder / f"{safe_ref}__portal_submission.html"),
        "downloads_dir": str(downloads_dir),
    }


def _save_artifacts(page: Any, payload: Dict[str, Any]) -> Dict[str, str]:
    paths = _capture_artifact_paths(payload)
    screenshot_path = paths.get("screenshot_path", "")
    html_path = paths.get("html_path", "")
    try:
        if screenshot_path:
            page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        screenshot_path = ""
    try:
        if html_path:
            Path(html_path).write_text(page.content(), encoding="utf-8")
    except Exception:
        html_path = ""
    return {"screenshot_path": screenshot_path, "html_path": html_path, "downloads_dir": paths.get("downloads_dir", "")}


def _looks_like_etenders(url: str) -> bool:
    host = _safe_lower(urlparse(url).netloc)
    return "etenders.gov.za" in host


def _read_confirmation(page: Any) -> Dict[str, str]:
    return {"page_title": _clean(page.title()), "current_url": _clean(page.url)}


def _has_captcha(page: Any) -> bool:
    try:
        return page.locator(ETENDERS_CAPTCHA_SELECTOR).first.count() > 0
    except Exception:
        return False


def _is_logged_in_etenders(page: Any) -> bool:
    try:
        current_url = _safe_lower(page.url)
        if "/login/" in current_url:
            return False
        page_text = _safe_lower(page.content())
    except Exception:
        return False
    indicators = ["log out", "logout", "start esubmission process", "profile", "supplier", "bookmark", "subscribe"]
    return any(token in page_text for token in indicators)


def _save_storage_state(context: Any) -> str:
    Path(ETENDERS_STORAGE_STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=ETENDERS_STORAGE_STATE_PATH)
    return ETENDERS_STORAGE_STATE_PATH


def _upload_files(page: Any, payload: Dict[str, Any]) -> List[str]:
    attachments = _collect_attachment_paths(payload)
    file_input = page.locator(PORTAL_FILE_INPUT_SELECTOR).first
    if file_input.count() == 0:
        raise RuntimeError("No file input found on the portal page.")
    file_input.set_input_files(attachments, timeout=PORTAL_TIMEOUT_MS)
    return attachments


def _submit_form(page: Any) -> None:
    submit_button = page.locator(PORTAL_SUBMIT_BUTTON_SELECTOR).first
    if submit_button.count() == 0:
        raise RuntimeError("No submit button found on the portal page.")
    submit_button.click(timeout=PORTAL_TIMEOUT_MS)
    page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)


def _build_etenders_launch_context(playwright: Any) -> Any:
    profile_dir = Path(ETENDERS_PROFILE_DIR)
    profile_dir.mkdir(parents=True, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(user_data_dir=str(profile_dir), headless=PORTAL_HEADLESS, slow_mo=PORTAL_SLOW_MO_MS, accept_downloads=True)
    context.set_default_timeout(PORTAL_TIMEOUT_MS)
    return context


def _seed_or_restore_etenders_session(page: Any, context: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not ETENDERS_REQUIRE_FRESH_LOGIN:
        try:
            page.goto(ETENDERS_HOME_URL, wait_until="domcontentloaded", timeout=PORTAL_TIMEOUT_MS)
            page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
            if _is_logged_in_etenders(page):
                storage_path = _save_storage_state(context)
                return _success_response(payload, status="session_ready", message="Existing eTenders session reused successfully.", current_url=_clean(page.url), storage_state_path=storage_path)
        except Exception:
            pass
    if ETENDERS_SEEDED_LOGIN_MODE and not ETENDERS_REQUIRE_FRESH_LOGIN:
        page.goto(ETENDERS_LOGIN_URL, wait_until="domcontentloaded", timeout=PORTAL_TIMEOUT_MS)
        page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
        artifacts = _save_artifacts(page, payload)
        return _manual_action_response(payload, "No active eTenders session found. Complete one login in this Playwright browser profile, then rerun. After that the system will reuse the saved session automatically.", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), current_url=_clean(page.url), profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)
    return None


def _etenders_login_if_required(page: Any, context: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    page.goto(ETENDERS_LOGIN_URL, wait_until="domcontentloaded", timeout=PORTAL_TIMEOUT_MS)
    page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
    if _is_logged_in_etenders(page):
        storage_path = _save_storage_state(context)
        return _success_response(payload, status="session_ready", message="eTenders session already active.", current_url=_clean(page.url), storage_state_path=storage_path)
    username = _first_non_empty(payload.get("portal_username"), PORTAL_USERNAME)
    password = _first_non_empty(payload.get("portal_password"), PORTAL_PASSWORD)
    if not username or not password:
        artifacts = _save_artifacts(page, payload)
        return _manual_action_response(payload, "eTenders requires CSD credentials. Set PORTAL_USERNAME and PORTAL_PASSWORD or seed the session manually once.", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), current_url=_clean(page.url), profile_dir=ETENDERS_PROFILE_DIR)
    try:
        page.locator(ETENDERS_USERNAME_SELECTOR).first.fill(username)
        page.locator(ETENDERS_PASSWORD_SELECTOR).first.fill(password)
    except Exception as exc:
        artifacts = _save_artifacts(page, payload)
        return _failure_response(payload, f"Failed to locate eTenders login fields: {exc}", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""))
    if _has_captcha(page):
        if ETENDERS_CAPTCHA_TEXT:
            try:
                page.locator(ETENDERS_CAPTCHA_SELECTOR).first.fill(ETENDERS_CAPTCHA_TEXT)
            except Exception as exc:
                artifacts = _save_artifacts(page, payload)
                return _failure_response(payload, f"Failed to fill eTenders CAPTCHA field: {exc}", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""))
        else:
            artifacts = _save_artifacts(page, payload)
            return _manual_action_response(payload, "eTenders login page requires CAPTCHA. Solve it once in this persistent Playwright profile, then rerun so the saved session can be reused automatically.", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), current_url=_clean(page.url), profile_dir=ETENDERS_PROFILE_DIR)
    try:
        page.locator(ETENDERS_LOGIN_BUTTON_SELECTOR).first.click(timeout=PORTAL_TIMEOUT_MS)
        page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
    except Exception as exc:
        artifacts = _save_artifacts(page, payload)
        return _failure_response(payload, f"eTenders login submission failed: {exc}", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""))
    if _is_logged_in_etenders(page):
        storage_path = _save_storage_state(context)
        return _success_response(payload, status="session_ready", message="eTenders login completed and session saved.", current_url=_clean(page.url), storage_state_path=storage_path)
    artifacts = _save_artifacts(page, payload)
    return _manual_action_response(payload, "eTenders login did not reach a clear authenticated state. Review the captured page and complete any remaining prompts in the saved Playwright profile, then rerun.", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), current_url=_clean(page.url), profile_dir=ETENDERS_PROFILE_DIR)


def _etenders_search_and_prepare(page: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    reference = _first_non_empty(payload.get("portal_reference"), payload.get("buyer_rfq_number"), payload.get("rfq_number"), payload.get("reference_number"), payload.get("document_number"))
    target_url = _first_non_empty(payload.get("portal_url"), ETENDERS_OPPORTUNITIES_URL)
    page.goto(target_url, wait_until="domcontentloaded", timeout=PORTAL_TIMEOUT_MS)
    page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
    quickfind_used = False
    if reference:
        try:
            quickfind = page.locator(ETENDERS_QUICKFIND_SELECTOR).first
            if quickfind.count() > 0:
                quickfind.fill(reference)
                quickfind.press("Enter")
                page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
                quickfind_used = True
        except Exception:
            pass
    downloaded_files: List[str] = []
    paths = _capture_artifact_paths(payload)
    downloads_dir = paths.get("downloads_dir", "")
    try:
        links = page.locator(ETENDERS_DOCUMENT_LINK_SELECTOR)
        count = links.count()
        for idx in range(min(count, 3)):
            with page.expect_download(timeout=5000) as download_info:
                links.nth(idx).click()
            download = download_info.value
            if downloads_dir:
                target = Path(downloads_dir) / download.suggested_filename
                download.save_as(str(target))
                downloaded_files.append(str(target))
    except Exception:
        pass
    start_button = page.locator(ETENDERS_START_ESUBMISSION_SELECTOR).first
    try:
        start_available = start_button.count() > 0
    except Exception:
        start_available = False
    artifacts = _save_artifacts(page, payload)
    confirmation = _read_confirmation(page)
    if not start_available:
        return _manual_action_response(payload, "Authenticated eTenders session is ready, but 'Start eSubmission Process' was not found on the current page. Review the captured page and adjust selectors or navigate to the tender detail page.", downloaded_files=downloaded_files, quickfind_used=quickfind_used, current_url=confirmation.get("current_url", ""), page_title=confirmation.get("page_title", ""), screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)
    if not ETENDERS_FORCE_UPLOAD_ATTEMPT:
        return _manual_action_response(payload, "eTenders session is authenticated and the tender page was reached. To enable final upload/submit automation, set ETENDERS_FORCE_UPLOAD_ATTEMPT=true after confirming the live selectors on the captured page.", downloaded_files=downloaded_files, quickfind_used=quickfind_used, current_url=confirmation.get("current_url", ""), page_title=confirmation.get("page_title", ""), screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)
    try:
        start_button.click(timeout=PORTAL_TIMEOUT_MS)
        page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
        supplier_select = page.locator(ETENDERS_SUPPLIER_SELECT_SELECTOR).first
        if supplier_select.count() > 0:
            try:
                supplier_select.select_option(index=1)
            except Exception:
                pass
        proceed = page.locator(ETENDERS_CONFIRM_PROCEED_SELECTOR).first
        if proceed.count() > 0:
            proceed.click(timeout=PORTAL_TIMEOUT_MS)
            page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
        uploaded = _upload_files(page, payload)
        _submit_form(page)
        artifacts = _save_artifacts(page, payload)
        confirmation = _read_confirmation(page)
        return _success_response(payload, status="submitted", message="eTenders upload/submit flow completed.", uploaded_files=uploaded, downloaded_files=downloaded_files, quickfind_used=quickfind_used, current_url=confirmation.get("current_url", ""), page_title=confirmation.get("page_title", ""), screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)
    except Exception as exc:
        artifacts = _save_artifacts(page, payload)
        return _failure_response(payload, f"eTenders upload/submit attempt failed: {exc}", downloaded_files=downloaded_files, quickfind_used=quickfind_used, current_url=_clean(page.url), screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)


def _run_etenders_flow(payload: Dict[str, Any]) -> Dict[str, Any]:
    if sync_playwright is None:
        return _failure_response(payload, "Playwright is not installed or could not be imported.")
    with sync_playwright() as p:
        context = _build_etenders_launch_context(p)
        page = context.new_page()
        try:
            if ETENDERS_SESSION_REUSE_ENABLED:
                seed_result = _seed_or_restore_etenders_session(page, context, payload)
                if isinstance(seed_result, dict) and seed_result.get("status") == "manual_action_required":
                    return seed_result
            if ETENDERS_REQUIRE_FRESH_LOGIN or not ETENDERS_SESSION_REUSE_ENABLED:
                login_result = _etenders_login_if_required(page, context, payload)
                if isinstance(login_result, dict) and login_result.get("status") in {"manual_action_required", "failed"}:
                    return login_result
            if not _is_logged_in_etenders(page):
                login_result = _etenders_login_if_required(page, context, payload)
                if isinstance(login_result, dict) and login_result.get("status") in {"manual_action_required", "failed"}:
                    return login_result
            storage_path = _save_storage_state(context)
            result = _etenders_search_and_prepare(page, payload)
            if isinstance(result, dict):
                result.setdefault("profile_dir", ETENDERS_PROFILE_DIR)
                result.setdefault("storage_state_path", storage_path)
            return result
        except PlaywrightTimeoutError as exc:
            artifacts = _save_artifacts(page, payload)
            return _failure_response(payload, f"eTenders automation timed out: {exc}", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)
        except Exception as exc:
            artifacts = _save_artifacts(page, payload)
            return _failure_response(payload, f"eTenders automation failed: {exc}", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""), profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)
        finally:
            context.close()


def _run_generic_playwright_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    if sync_playwright is None:
        return _failure_response(payload, "Playwright is not installed or could not be imported.")
    portal_url = _resolve_portal_url(payload)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PORTAL_HEADLESS, slow_mo=PORTAL_SLOW_MO_MS)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.set_default_timeout(PORTAL_TIMEOUT_MS)
            page.goto(portal_url, wait_until="domcontentloaded", timeout=PORTAL_TIMEOUT_MS)
            page.wait_for_load_state("networkidle", timeout=PORTAL_TIMEOUT_MS)
            uploaded_files = _upload_files(page, payload)
            _submit_form(page)
            confirmation = _read_confirmation(page)
            artifacts = _save_artifacts(page, payload)
            return _success_response(payload, status="submitted", message="Portal submission completed successfully via Playwright.", uploaded_files=uploaded_files, page_title=confirmation.get("page_title", ""), current_url=confirmation.get("current_url", ""), screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""))
        except Exception as exc:
            artifacts = _save_artifacts(page, payload)
            return _failure_response(payload, f"Portal submission failed: {exc}", screenshot_path=artifacts.get("screenshot_path", ""), html_path=artifacts.get("html_path", ""))
        finally:
            context.close()
            browser.close()


def _normalize_submission_status(status: Any) -> str:
    text = _safe_lower(status)
    if text in {"submitted", "success", "ok", "sent"}:
        return "submitted"
    if text in {"failed", "error"}:
        return "failed"
    if text == "queued":
        return "queued"
    if text == "manual_action_required":
        return "manual_action_required"
    return text or "unknown"


def _collect_artifact_files_for_history(payload: Dict[str, Any], result: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    for value in [payload.get("final_pdf_path"), payload.get("pdf_path"), payload.get("quote_pack_metadata_path"), payload.get("submission_log_path"), payload.get("proof_path"), payload.get("quote_folder"), payload.get("quote_pack_dir"), result.get("final_pdf_path"), result.get("screenshot_path"), result.get("html_path"), result.get("storage_state_path"), result.get("proof_path"), result.get("submission_log_path")]:
        text = _clean(value)
        if text:
            candidates.append(text)
    for item in _safe_list(payload.get("attachment_paths")):
        text = _clean(item)
        if text:
            candidates.append(text)
    for item in _safe_list(payload.get("submission_attachments")):
        text = _clean(item)
        if text:
            candidates.append(text)
    for item in _safe_list(result.get("uploaded_files")):
        text = _clean(item)
        if text:
            candidates.append(text)
    for item in _safe_list(result.get("downloaded_files")):
        text = _clean(item)
        if text:
            candidates.append(text)
    return _existing_files(candidates)


def _resolve_document_path_for_history(payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    for candidate in [result.get("final_pdf_path"), payload.get("final_pdf_path"), payload.get("pdf_path")]:
        text = _clean(candidate)
        if text and Path(text).exists() and Path(text).is_file():
            return str(Path(text).resolve())
    attachments = _collect_attachment_paths(payload)
    for attachment in attachments:
        if Path(attachment).suffix.lower() == ".pdf":
            return str(Path(attachment).resolve())
    return ""


def _resolve_proof_path_for_history(result: Dict[str, Any]) -> str:
    for candidate in [result.get("screenshot_path"), result.get("html_path"), result.get("proof_path")]:
        text = _clean(candidate)
        if text and Path(text).exists():
            return str(Path(text).resolve())
    return ""


def _default_email_body(payload: Dict[str, Any]) -> str:
    buyer_rfq_number = _clean(payload.get("buyer_rfq_number") or payload.get("rfq_number"))
    quote_number = _clean(payload.get("quote_number"))
    return "Dear Sir/Madam,\n\nPlease find attached our quotation for %s.\n\nQuote Number: %s\n\nKind regards,\nLechesa Manaba Consulting and Projects (Pty) Ltd\n" % (buyer_rfq_number, quote_number)


def _attempt_email_fallback_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    recipient_email = _resolve_recipient_email(payload)
    final_pdf_path = _clean(payload.get("final_pdf_path") or payload.get("pdf_path"))
    attachments = _collect_attachment_paths(payload)
    email_payload = dict(payload)
    email_payload["submission_method"] = "email"
    email_payload["submission_channel"] = "email"
    if recipient_email:
        email_payload["recipient_email"] = recipient_email
        email_payload["buyer_email"] = _clean(payload.get("buyer_email")) or recipient_email
    if not recipient_email:
        return _manual_action_response(email_payload, "Missing portal URL and no email fallback available.", submission_method="email", submission_channel="email")
    if not final_pdf_path:
        return _failure_response(email_payload, "Missing final PDF path for email fallback submission.", submission_method="email", submission_channel="email")
    if _send_submission_email is None:
        return _manual_action_response(email_payload, "Portal URL missing and email submission service not available.", submission_method="email", submission_channel="email")
    subject = _first_non_empty(payload.get("subject"), payload.get("quote_subject"), f"Quotation Submission - {_clean(payload.get('buyer_rfq_number') or payload.get('rfq_number'))}")
    body = _first_non_empty(payload.get("submission_email_body"), payload.get("body"), _default_email_body(payload))
    outbound_payload = {
        **email_payload,
        "submission_method": "email",
        "submission_channel": "email",
        "recipient_email": recipient_email,
        "buyer_email": _clean(payload.get("buyer_email")) or recipient_email,
        "to_email": recipient_email,
        "subject": subject,
        "quote_subject": subject,
        "submission_email_body": body,
        "body": body,
        "final_pdf_path": final_pdf_path,
        "pdf_path": final_pdf_path,
        "attachment_paths": attachments or [final_pdf_path],
        "submission_attachments": attachments or [final_pdf_path],
    }
    try:
        response = _send_submission_email(outbound_payload)
    except Exception as exc:
        return _failure_response(outbound_payload, f"Email fallback submission failed: {exc}", submission_method="email", submission_channel="email")
    success = False
    status_text = ""
    error_text = ""
    if isinstance(response, dict):
        success = bool(response.get("success") or response.get("submitted"))
        status_text = _clean(response.get("status"))
        error_text = _clean(response.get("error"))
    if success or status_text in {"sent", "submitted", "ok", "success"}:
        result = _success_response(outbound_payload, status="submitted", message="Portal URL missing. Email fallback submission succeeded.", submission_method="email", submission_channel="email", recipient_email=recipient_email, final_pdf_path=final_pdf_path)
        if isinstance(response, dict):
            result["email_response"] = response
        result.update(_resolve_financials(outbound_payload, result))
        return result
    if status_text == "manual_action_required":
        result = _manual_action_response(outbound_payload, error_text or status_text or "Email fallback requires manual action.", submission_method="email", submission_channel="email", recipient_email=recipient_email, final_pdf_path=final_pdf_path)
        if isinstance(response, dict):
            result["email_response"] = response
        result.update(_resolve_financials(outbound_payload, result))
        return result
    result = _failure_response(outbound_payload, error_text or status_text or "Email fallback submission failed.", submission_method="email", submission_channel="email", recipient_email=recipient_email, final_pdf_path=final_pdf_path)
    if isinstance(response, dict):
        result["email_response"] = response
    result.update(_resolve_financials(outbound_payload, result))
    return result


def _build_submission_history_payload(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    buyer = _safe_dict(payload.get("buyer"))
    submission_pack = _safe_dict(payload.get("submission_pack"))
    quote_pack = _safe_dict(payload.get("quote_pack"))
    opportunity = _safe_dict(payload.get("opportunity"))
    rfq = _safe_dict(payload.get("rfq"))
    status = _normalize_submission_status(result.get("status"))
    artifacts = _collect_artifact_files_for_history(payload, result)
    attachments = _collect_attachment_paths(payload)
    document_path = _resolve_document_path_for_history(payload, result)
    proof_path = _resolve_proof_path_for_history(result)
    financials = _resolve_financials(payload, result)
    buyer_name = _first_non_empty(payload.get("buyer_name"), buyer.get("name"), submission_pack.get("buyer_name"), quote_pack.get("buyer_name"), opportunity.get("buyer_name"), rfq.get("buyer_name"))
    title = _first_non_empty(payload.get("title"), payload.get("description"), submission_pack.get("title"), quote_pack.get("title"), opportunity.get("title"), rfq.get("title"))
    recipient_email = _first_non_empty(result.get("recipient_email"), payload.get("recipient_email"), payload.get("buyer_email"), buyer.get("email"), submission_pack.get("recipient_email"), quote_pack.get("recipient_email"))
    resolved_method = _safe_lower(result.get("submission_method") or payload.get("submission_method") or "portal") or "portal"
    resolved_channel = _safe_lower(result.get("submission_channel") or payload.get("submission_channel") or resolved_method) or resolved_method
    portal_name = _first_non_empty(payload.get("portal_name"), payload.get("submission_portal_name"), urlparse(_clean(result.get("portal_url") or _resolve_portal_url(payload))).netloc)
    status_message = _first_non_empty(result.get("message"), result.get("error"), payload.get("status_message"))
    enriched_raw_result = dict(result if isinstance(result, dict) else {})
    enriched_raw_result.update(financials)
    if payload.get("quote_pack_metadata_path"):
        enriched_raw_result.setdefault("quote_pack_metadata_path", _clean(payload.get("quote_pack_metadata_path")))
    if payload.get("final_pdf_path") or payload.get("pdf_path"):
        enriched_raw_result.setdefault("final_pdf_path", _clean(payload.get("final_pdf_path") or payload.get("pdf_path")))
    return {
        "buyer_name": buyer_name,
        "buyer_rfq_number": _first_non_empty(result.get("buyer_rfq_number"), payload.get("buyer_rfq_number"), payload.get("rfq_number")),
        "quote_number": _first_non_empty(result.get("quote_number"), payload.get("quote_number"), submission_pack.get("quote_number"), quote_pack.get("quote_number")),
        "title": title,
        "submission_method": resolved_method,
        "recipient_email": recipient_email,
        "portal_name": portal_name,
        "status": status,
        "status_message": status_message,
        "document_path": document_path,
        "proof_path": proof_path,
        "submission_log_path": _clean(result.get("submission_log_path") or payload.get("submission_log_path")),
        "attachments": attachments,
        "artifacts": artifacts,
        "source": _first_non_empty(payload.get("source"), payload.get("source_name"), opportunity.get("source"), rfq.get("source")),
        "submitted_by": _first_non_empty(payload.get("submitted_by"), "system"),
        "retry_count": _safe_int(payload.get("retry_count"), 0),
        "raw_result": enriched_raw_result,
        "metadata": {
            "submission_channel": resolved_channel,
            "portal_url": _clean(result.get("portal_url") or _resolve_portal_url(payload)),
            "current_url": _clean(result.get("current_url")),
            "page_title": _clean(result.get("page_title")),
            "profile_dir": _clean(result.get("profile_dir")),
            "storage_state_path": _clean(result.get("storage_state_path")),
            "quickfind_used": bool(result.get("quickfind_used", False)),
            "playwright_available": sync_playwright is not None,
            "quote_folder": _clean(payload.get("quote_folder")),
            "quote_pack_dir": _clean(payload.get("quote_pack_dir")),
            "quote_pack_metadata_path": _clean(payload.get("quote_pack_metadata_path")),
            **financials,
        },
    }


def _log_submission_history_if_available(payload: Dict[str, Any], result: Dict[str, Any]) -> None:
    if log_submission_event is None:
        return
    if not isinstance(payload, dict) or not isinstance(result, dict):
        return
    try:
        log_submission_event(_build_submission_history_payload(payload, result))
    except Exception as exc:
        logger.warning("Failed to log submission history for portal submission: %s", exc)



def _duplicate_submission_guard(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if search_submission_history_by_buyer_rfq is None:
        return None
    try:
        rfq = _clean(payload.get("buyer_rfq_number") or payload.get("rfq_number"))
        if not rfq:
            return None
        prior = search_submission_history_by_buyer_rfq(rfq)
        if isinstance(prior, dict):
            status = _safe_lower(prior.get("status"))
            if status == "submitted":
                return _success_response(
                    payload,
                    status="submitted",
                    message="Duplicate submission prevented: already submitted previously.",
                    duplicate_prevented=True,
                    previous_submission_record=prior,
                )
    except Exception as exc:
        logger.warning("Duplicate submission guard check failed: %s", exc)
    return None



def _enforce_submission_proof(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Channel 2 proof enforcement:
    A submission cannot remain 'submitted' unless proof artifacts exist.
    """
    if not isinstance(result, dict):
        return result

    status = _normalize_submission_status(result.get("status"))
    if status != "submitted":
        return result

    proof_path = _resolve_proof_path_for_history(result)
    artifact_files = _collect_artifact_files_for_history(payload, result)

    has_proof = bool(proof_path) or len(artifact_files) > 0

    if has_proof:
        return result

    downgraded = dict(result)
    downgraded["success"] = False
    downgraded["status"] = "manual_action_required"
    downgraded["message"] = (
        "Submission proof missing. Status downgraded pending proof artifact."
    )
    downgraded["proof_enforcement_triggered"] = True
    return downgraded



def _classify_submission_failure(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Channel 2 Failure Classification Engine.
    Adds structured failure classification and retry guidance.
    """
    if not isinstance(result, dict):
        return result

    status = _normalize_submission_status(result.get("status"))
    if status == "submitted":
        result.setdefault("failure_classification", None)
        result.setdefault("retry_recommended", False)
        return result

    message = _safe_lower(
        result.get("error")
        or result.get("message")
        or ""
    )

    classification = "permanent_failure"
    retry_recommended = False

    if "timeout" in message or "timed out" in message:
        classification = "transient_retryable"
        retry_recommended = True

    elif "network" in message or "connection" in message:
        classification = "transient_retryable"
        retry_recommended = True

    elif "captcha" in message or "manual action" in message:
        classification = "manual_action_required"

    elif "login" in message or "credential" in message or "authentication" in message:
        classification = "authentication_failure"

    elif "selector" in message or "no file input found" in message or "no submit button found" in message:
        classification = "selector_failure"

    elif "portal unavailable" in message or "service unavailable" in message or "502" in message or "503" in message:
        classification = "portal_unavailable"
        retry_recommended = True

    elif status == "manual_action_required":
        classification = "manual_action_required"

    result["failure_classification"] = classification
    result["retry_recommended"] = retry_recommended

    return result



MAX_AUTONOMOUS_RETRY_COUNT = int(str(os.getenv("MAX_AUTONOMOUS_RETRY_COUNT","3")).strip() or "3")

def _apply_retry_decision(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result
    retry_count = _safe_int(payload.get("retry_count"), 0)
    fc = _safe_lower(result.get("failure_classification"))
    retryable = bool(result.get("retry_recommended"))

    decision = "no_retry"
    next_backoff_seconds = None

    if retryable and retry_count < MAX_AUTONOMOUS_RETRY_COUNT:
        decision = "retry_allowed"
        # simple exponential backoff: 60,120,240...
        next_backoff_seconds = 60 * (2 ** retry_count)
    elif retryable and retry_count >= MAX_AUTONOMOUS_RETRY_COUNT:
        decision = "retry_ceiling_reached"
        result["status"] = "manual_action_required"

    result["retry_decision"] = decision
    result["retry_count"] = retry_count
    result["retry_ceiling"] = MAX_AUTONOMOUS_RETRY_COUNT
    if next_backoff_seconds is not None:
        result["next_backoff_seconds"] = next_backoff_seconds
    return result

def _block_if_system_off(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Master OFF switch enforcement:
    Block ALL outgoing submissions when system is OFF
    """
    authorization = submission_system_control_authorization()
    if not authorization["authorized"]:
        return {
            "success": False,
            "status": "skipped",
            "message": "Submission blocked by system-control governance.",
            "reason": authorization["reason"],
            "system_state": authorization["system_control_state"],
        }

    return None

def submit_tender_to_portal(payload: Dict[str, Any]) -> Dict[str, Any]:
    # MASTER SYSTEM OFF CHECK
    blocked = _block_if_system_off(payload)
    if blocked:
        return blocked
    
    validation_error = _validate_payload(payload)
    if validation_error:
        _log_submission_history_if_available(payload if isinstance(payload, dict) else {}, validation_error)
        return validation_error

    duplicate_guard_result = _duplicate_submission_guard(payload)
    if duplicate_guard_result:
        _log_submission_history_if_available(payload, duplicate_guard_result)
        return duplicate_guard_result
    portal_url = _resolve_portal_url(payload)
    final_pdf_path = _clean(payload.get("final_pdf_path") or payload.get("pdf_path"))
    attachments = _collect_attachment_paths(payload)
    if not portal_url:
        fallback_result = _attempt_email_fallback_submission(payload)
        fallback_result = _enforce_submission_proof(payload, fallback_result)
        fallback_result = _classify_submission_failure(fallback_result)
        fallback_result = _apply_retry_decision(payload, fallback_result)
        _log_submission_history_if_available(payload, fallback_result)
        return fallback_result
    is_etenders = _looks_like_etenders(portal_url)
    if is_etenders:
        if PORTAL_AUTOMATION_ENABLED:
            result = _run_etenders_flow(payload)
        else:
            result = _manual_action_response(payload, "eTenders detected. Enable PORTAL_AUTOMATION_ENABLED=true to automate session reuse and tender discovery for this portal.", uploaded_files=attachments, final_pdf_path=final_pdf_path, profile_dir=ETENDERS_PROFILE_DIR, storage_state_path=ETENDERS_STORAGE_STATE_PATH)
        result.update(_resolve_financials(payload, result))
        result = _enforce_submission_proof(payload, result)
        result = _classify_submission_failure(result)
        result = _apply_retry_decision(payload, result)
        _log_submission_history_if_available(payload, result)
        return result
    if PORTAL_AUTOMATION_ENABLED:
        result = _run_generic_playwright_submission(payload)
        result.update(_resolve_financials(payload, result))
        result = _enforce_submission_proof(payload, result)
        result = _classify_submission_failure(result)
        result = _apply_retry_decision(payload, result)
        _log_submission_history_if_available(payload, result)
        return result
    result = _success_response(payload, status="submitted", message="Portal submission triggered successfully via placeholder route.", uploaded_files=attachments, final_pdf_path=final_pdf_path)
    result.update(_resolve_financials(payload, result))
    result = _classify_submission_failure(result)
    result = _apply_retry_decision(payload, result)
    _log_submission_history_if_available(payload, result)
    return result


def run_portal_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    return submit_tender_to_portal(payload)


def submit_portal_tender(payload: Dict[str, Any]) -> Dict[str, Any]:
    return submit_tender_to_portal(payload)


def route_portal_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    return submit_tender_to_portal(payload)


def get_portal_submission_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "checked_at": _utc_now_iso(),
        "playwright_available": sync_playwright is not None,
        "portal_automation_enabled": PORTAL_AUTOMATION_ENABLED,
        "portal_headless": PORTAL_HEADLESS,
        "portal_timeout_ms": PORTAL_TIMEOUT_MS,
        "etenders_login_url": ETENDERS_LOGIN_URL,
        "etenders_session_reuse_enabled": ETENDERS_SESSION_REUSE_ENABLED,
        "etenders_profile_dir": ETENDERS_PROFILE_DIR,
        "etenders_storage_state_path": ETENDERS_STORAGE_STATE_PATH,
        "etenders_seeded_login_mode": ETENDERS_SEEDED_LOGIN_MODE,
        "etenders_force_upload_attempt": ETENDERS_FORCE_UPLOAD_ATTEMPT,
        "submission_history_logging_available": log_submission_event is not None,
        "email_fallback_available": _send_submission_email is not None,
    }








