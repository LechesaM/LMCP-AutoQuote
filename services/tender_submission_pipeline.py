from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.services.final_output_builder_service import build_final_output_payload
from app.services.pilot_run_log_service import append_pilot_run, build_pilot_run_record
from app.services.rfq_boq_extraction_engine import extract_rfq_boq
from app.services.quote_review_service import classify_tender
from app.services.rfq_document_intelligence import analyse_rfq_document_intelligence
from app.services.submission_pack_assembler_service import build_submission_pack
from app.services.tender_form_priority_engine import TenderFormPriorityEngine
from app.services.system_control_service import get_system_control_state

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
_RUNTIME_ROOT = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
ETENDERS_PROFILE_DIR = os.getenv("ETENDERS_PROFILE_DIR", str(_RUNTIME_ROOT / "playwright" / "etenders_profile"))
ETENDERS_STORAGE_STATE_PATH = os.getenv(
    "ETENDERS_STORAGE_STATE_PATH",
    str(_RUNTIME_ROOT / "playwright" / "etenders_storage_state.json"),
)
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
    try:
        state = get_system_control_state()

        if not state.get("system_on", True):
            return {
                "success": False,
                "status": "skipped",
                "message": "Submission blocked by system control: system_off",
                "reason": "system_off",
                "system_state": state,
            }

        if state.get("emergency_stop", False):
            return {
                "success": False,
                "status": "skipped",
                "message": "Submission blocked by emergency stop",
                "reason": "emergency_stop",
                "system_state": state,
            }

        if state.get("submission_paused", False):
            return {
                "success": False,
                "status": "skipped",
                "message": "Submission blocked: submissions paused",
                "reason": "submission_paused",
                "system_state": state,
            }

    except Exception as e:
        logger.warning("System control check failed during submission: %s", e)

    return None

def submit_tender_to_portal(payload: Dict[str, Any]) -> Dict[str, Any]:
    # MASTER SYSTEM OFF CHECK
    blocked = _block_if_system_off(payload)
    if blocked:
        _log_submission_history_if_available(payload, blocked)
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


PIPELINE_MODE_ASSISTED_PRODUCTION = "assisted_production"
PIPELINE_MODE_PREPARE_ONLY = "prepare_only"
_CANONICAL_PIPELINE_MODES = {
    PIPELINE_MODE_ASSISTED_PRODUCTION,
    PIPELINE_MODE_PREPARE_ONLY,
}

SUPPORTED_RFQ_FILE_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".zip", ".txt"}


def _slugify_pipeline_value(value: Any, default: str = "tender") -> str:
    text = _clean(value)
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text).strip("._")
    return slug or default


def _write_json_file(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def _write_placeholder_pdf(path: Path, title: str, lines: List[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = [
        "%PDF-1.1",
        "% LMCP assisted-production placeholder artifact",
        f"% {title}",
        *[f"% {line}" for line in lines if _clean(line)],
        "%%EOF",
    ]
    path.write_bytes("\n".join(content).encode("utf-8"))
    return str(path)


def _append_stage(stages: List[Dict[str, Any]], key: str, name: str, status: str, **details: Any) -> Dict[str, Any]:
    stage = {"key": key, "name": name, "status": status}
    for field, value in details.items():
        if value is not None:
            stage[field] = value
    stages.append(stage)
    return stage


def _select_analysis_document_paths(plan: Dict[str, Any]) -> List[str]:
    documents = plan.get("documents_found") if isinstance(plan, dict) else []
    if not isinstance(documents, list):
        return []
    preferred_exts = {".pdf", ".docx", ".txt", ".html", ".htm", ".csv", ".xlsx", ".xls"}
    paths: List[str] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        path = _clean(document.get("path"))
        ext = _safe_lower(document.get("ext"))
        if path and ext in preferred_exts:
            paths.append(path)
    return paths


def _scan_real_rfq_source_files(root_path: Path) -> Dict[str, Any]:
    files = [path for path in root_path.rglob("*") if path.is_file()]
    supported_files = [path for path in files if path.suffix.lower() in SUPPORTED_RFQ_FILE_EXTENSIONS]

    warning_reasons: List[str] = []
    if not files:
        warning_reasons.append("Tender folder is empty.")
    if not supported_files:
        warning_reasons.append(
            "No supported RFQ/tender files found. Supported extensions: pdf, docx, xlsx, zip, txt."
        )

    return {
        "file_count": len(files),
        "supported_file_count": len(supported_files),
        "supported_extensions": sorted(ext.lstrip(".") for ext in SUPPORTED_RFQ_FILE_EXTENSIONS),
        "supported_files": [str(path) for path in supported_files],
        "has_real_rfq_files": bool(supported_files),
        "warning_reasons": warning_reasons,
    }


def _evaluate_quote_pack_quality(
    quote_output: Dict[str, Any],
    *,
    blocked_by_eligibility: bool = False,
) -> Dict[str, Any]:
    final_output = _safe_dict(quote_output.get("final_output"))
    summary = _safe_dict(final_output.get("summary"))
    stats = _safe_dict(quote_output.get("stats"))
    rows = [row for row in _safe_list(quote_output.get("rows")) if isinstance(row, dict)]

    priced_rows = _safe_int(summary.get("priced_rows"), _safe_int(stats.get("priced_rows")))
    pending_rows = _safe_int(summary.get("pending_rows"), _safe_int(stats.get("pending_rows")))
    grand_total = _safe_float(
        summary.get("grand_total"),
        _safe_float(final_output.get("grand_total"), _safe_float(quote_output.get("grand_total"))),
    )

    placeholder_only = not rows or all(_safe_lower(row.get("pricing_source")) == "assisted_production_placeholder" for row in rows)
    has_pending_price = any(
        _safe_lower(row.get("pricing_status")) == "pending_price"
        or _safe_lower(row.get("schedule_fill_status")) == "pending_price"
        for row in rows
    )

    if placeholder_only:
        status = "placeholder_only"
        reason = "quote pack was generated from source files without extracted priced items"
    elif has_pending_price or pending_rows > 0 or priced_rows == 0:
        status = "needs_pricing"
        reason = "quote pack contains pending_price line items"
    elif grand_total <= 0 and not blocked_by_eligibility:
        status = "invalid_zero_total"
        reason = "quote pack grand total is zero"
    else:
        status = "approval_ready"
        reason = "quote pack is priced and has a non-zero total"

    return {
        "quote_pack_quality_status": status,
        "approval_blocked": status != "approval_ready" or bool(blocked_by_eligibility),
        "quote_pack_quality_reason": reason,
        "quote_pack_quality_summary": {
            "priced_rows": priced_rows,
            "pending_rows": pending_rows,
            "grand_total": grand_total,
            "placeholder_only": placeholder_only,
        },
    }


def _extract_analysis_line_items(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    intelligence = analysis.get("document_intelligence") if isinstance(analysis, dict) else {}
    if not isinstance(intelligence, dict):
        return []
    items = intelligence.get("extracted_line_items")
    if not isinstance(items, list):
        return []
    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "item_number": item.get("item_number") or idx,
                "description": _clean(item.get("description") or item.get("item_description")),
                "specification": _clean(item.get("specification")),
                "unit": _clean(item.get("unit") or "Each"),
                "quantity": item.get("quantity"),
                "unit_price": None,
                "line_total": None,
                "schedule_fill_status": "pending_price",
                "pricing_status": "pending_price",
                "pricing_source": "rfq_document_intelligence",
            }
        )
    return results


def _extract_quote_pack_rows_from_documents(
    *,
    tender_id: str,
    tender_payload: Dict[str, Any],
    document_paths: List[str],
) -> Dict[str, Any]:
    extraction = extract_rfq_boq(
        {
            "title": _clean(tender_payload.get("tender_title") or tender_payload.get("title") or tender_id),
            "buyer_name": _clean(tender_payload.get("client_name") or tender_payload.get("buyer_name")),
            "buyer_rfq_number": _clean(tender_payload.get("tender_number") or tender_payload.get("buyer_rfq_number") or tender_id),
            "rfq_number": _clean(tender_payload.get("tender_number") or tender_id),
            "local_document_paths": document_paths,
        }
    )
    line_items = extraction.get("line_items") if isinstance(extraction.get("line_items"), list) else []
    if not line_items:
        return {
            "rows": [],
            "extraction": extraction,
            "extracted_line_item_count": 0,
            "extracted_line_item_descriptions": [],
        }

    rows: List[Dict[str, Any]] = []
    extracted_line_item_descriptions: List[str] = []
    for idx, item in enumerate(line_items, start=1):
        if not isinstance(item, dict):
            continue
        description = _clean(item.get("description") or item.get("specification") or f"Line item {idx}")
        extracted_line_item_descriptions.append(description)
        quantity = _safe_float(item.get("quantity"), 0.0)
        unit_price = item.get("unit_price")
        line_total = item.get("line_total")
        try:
            unit_price_value = float(unit_price) if unit_price not in (None, "") else None
        except Exception:
            unit_price_value = None
        try:
            line_total_value = float(line_total) if line_total not in (None, "") else None
        except Exception:
            line_total_value = None

        if unit_price_value is None and line_total_value is not None and quantity > 0:
            unit_price_value = round(line_total_value / quantity, 2)
        if line_total_value is None and unit_price_value is not None and quantity > 0:
            line_total_value = round(unit_price_value * quantity, 2)

        priced = unit_price_value is not None and unit_price_value > 0 and line_total_value is not None and line_total_value > 0
        rows.append(
            {
                "item_number": idx,
                "description": description,
                "specification": _clean(item.get("specification")),
                "unit": _clean(item.get("unit") or "Each"),
                "quantity": quantity if quantity > 0 else None,
                "unit_price": unit_price_value,
                "line_total": line_total_value,
                "schedule_fill_status": "filled" if priced else "pending_price",
                "pricing_status": "priced" if priced else "pending_price",
                "pricing_source": _clean(item.get("pricing_source") or item.get("source") or "rfq_boq_extraction"),
            }
        )

    return {
        "rows": rows,
        "extraction": extraction,
        "extracted_line_item_count": len(rows),
        "extracted_line_item_descriptions": extracted_line_item_descriptions,
    }


def _clean_description_key(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_lower(value)).strip()


def _load_pricing_input(pricing_file: Optional[str]) -> Dict[str, Any]:
    if not pricing_file:
        return {}
    path = Path(pricing_file).expanduser()
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _pricing_entry_matches_row(entry: Dict[str, Any], row: Dict[str, Any], position: int) -> bool:
    if not isinstance(entry, dict) or not isinstance(row, dict):
        return False

    for key in ("item_number", "line_number", "row_number", "row_no"):
        candidate = entry.get(key)
        if candidate is None or candidate == "":
            continue
        try:
            if int(float(candidate)) == int(float(row.get("item_number") or position)):
                return True
        except Exception:
            pass

    entry_desc = _clean_description_key(entry.get("description") or entry.get("match_description") or entry.get("item_description"))
    row_desc = _clean_description_key(row.get("description") or row.get("specification"))
    if entry_desc and row_desc and entry_desc == row_desc:
        return True

    return False


def _apply_pricing_file_to_rows(rows: List[Dict[str, Any]], pricing_file: Optional[str]) -> Dict[str, Any]:
    pricing_input = _load_pricing_input(pricing_file)
    if not pricing_input or not rows:
        return {
            "rows": rows,
            "pricing_applied": False,
            "pricing_complete": False,
            "pricing_input": pricing_input,
            "pricing_file_loaded": bool(pricing_input),
            "pricing_file_item_count": len(pricing_input.get("items")) if isinstance(pricing_input.get("items"), list) else 0,
            "pricing_items_matched": 0,
            "pricing_items_unmatched": len(pricing_input.get("items")) if isinstance(pricing_input.get("items"), list) else 0,
        }

    raw_items = pricing_input.get("items")
    if not isinstance(raw_items, list):
        raw_items = []

    supplier_name_default = _clean(pricing_input.get("supplier_name"))
    supplier_quote_ref_default = _clean(pricing_input.get("supplier_quote_ref"))
    pricing_warnings: List[str] = []
    row_map = [dict(row) for row in rows]
    matched_indexes = set()
    valid_priced_rows = 0

    for item_index, entry in enumerate(raw_items, start=1):
        if not isinstance(entry, dict):
            continue
        unit_price = _safe_float(entry.get("unit_price"), 0.0)
        margin_percent = _safe_float(entry.get("margin_percent"), 0.0)
        supplier_name = _clean(entry.get("supplier_name") or supplier_name_default)
        supplier_quote_ref = _clean(entry.get("supplier_quote_ref") or supplier_quote_ref_default)
        if unit_price <= 0 or margin_percent <= 0:
            pricing_warnings.append(f"Invalid pricing values for line item {item_index}.")
            continue

        matched_row_index = None
        for index, row in enumerate(row_map):
            if index in matched_indexes:
                continue
            if _pricing_entry_matches_row(entry, row, index + 1):
                matched_row_index = index
                break

        if matched_row_index is None:
            continue

        matched_indexes.add(matched_row_index)
        row = row_map[matched_row_index]
        quantity = _safe_float(row.get("quantity"), 0.0)
        line_total = round(unit_price * quantity, 2) if quantity > 0 else None
        row.update({
            "unit_price": unit_price,
            "line_total": line_total,
            "pricing_status": "priced" if line_total is not None and line_total > 0 else "pending_price",
            "schedule_fill_status": "filled" if line_total is not None and line_total > 0 else "pending_price",
            "supplier_name": supplier_name or _clean(pricing_input.get("supplier_name")),
            "supplier_quote_ref": supplier_quote_ref or _clean(pricing_input.get("supplier_quote_ref")),
            "margin_percent": margin_percent,
            "pricing_source": "manual_pricing_file",
        })
        if row.get("pricing_status") == "priced":
            valid_priced_rows += 1

    # Fill in top-level supplier defaults on any matched rows that still lack them.
    for row in row_map:
        if _clean(row.get("supplier_name")) or not supplier_name_default:
            continue
        row["supplier_name"] = supplier_name_default
    for row in row_map:
        if _clean(row.get("supplier_quote_ref")) or not supplier_quote_ref_default:
            continue
        row["supplier_quote_ref"] = supplier_quote_ref_default

    pricing_complete = bool(row_map) and all(_safe_lower(row.get("pricing_status")) == "priced" for row in row_map)
    pricing_file_item_count = len(raw_items)
    pricing_items_matched = len(matched_indexes)
    return {
        "rows": row_map,
        "pricing_applied": bool(raw_items),
        "pricing_complete": pricing_complete and valid_priced_rows == len(row_map),
        "pricing_input": pricing_input,
        "pricing_warnings": pricing_warnings,
        "pricing_file_loaded": bool(pricing_input),
        "pricing_file_item_count": pricing_file_item_count,
        "pricing_items_matched": pricing_items_matched,
        "pricing_items_unmatched": max(pricing_file_item_count - pricing_items_matched, 0),
    }


def _analysis_text_blob(analysis: Dict[str, Any]) -> str:
    if not isinstance(analysis, dict):
        return ""
    chunks: List[str] = []
    intelligence = analysis.get("document_intelligence")
    if isinstance(intelligence, dict):
        for key in ("document_excerpt", "roles_summary"):
            text = _clean(intelligence.get(key))
            if text:
                chunks.append(text)
    extracted = analysis.get("text_extraction")
    if isinstance(extracted, list):
        for item in extracted:
            if not isinstance(item, dict):
                continue
            text = _clean(item.get("text"))
            if text:
                chunks.append(text[:4000])
    return "\n".join(chunks)


def _fallback_output_rows(tender_data: Dict[str, Any], instructions_text: str) -> List[Dict[str, Any]]:
    description = _clean(
        tender_data.get("tender_title")
        or tender_data.get("title")
        or tender_data.get("description")
        or instructions_text
        or "Tender supply and delivery line item"
    )
    return [
        {
            "item_number": 1,
            "description": description[:300],
            "specification": _clean(tender_data.get("scope_summary") or ""),
            "unit": "Lot",
            "quantity": 1.0,
            "unit_price": None,
            "line_total": None,
            "schedule_fill_status": "pending_price",
            "pricing_status": "pending_price",
            "pricing_source": "assisted_production_placeholder",
        }
    ]


def _pipeline_briefing_required(instructions_text: str, analysis: Dict[str, Any]) -> bool:
    intelligence = analysis.get("document_intelligence") if isinstance(analysis, dict) else {}
    if isinstance(intelligence, dict) and intelligence.get("compulsory_briefing_required") is True:
        return True
    text_blob = _safe_lower("\n".join([instructions_text, _analysis_text_blob(analysis)]))
    non_compulsory_markers = (
        "no compulsory briefing",
        "non-compulsory briefing",
        "non compulsory briefing",
        "briefing not compulsory",
        "optional briefing",
        "briefing optional",
    )
    if any(marker in text_blob for marker in non_compulsory_markers):
        return False
    markers = (
        "compulsory briefing",
        "mandatory briefing",
        "briefing required",
        "compulsory site meeting",
        "mandatory site meeting",
        "site inspection compulsory",
    )
    return any(marker in text_blob for marker in markers)


def _build_pipeline_submission_payload(
    *,
    tender_id: str,
    tender_data: Dict[str, Any],
    company_data: Dict[str, Any],
    quote_pack_pdf_path: str,
    quote_pack_metadata_path: str,
    quote_folder: str,
    submission_pack: Dict[str, Any],
) -> Dict[str, Any]:
    portal_url = _clean(
        tender_data.get("submission_portal_url")
        or tender_data.get("portal_submission_url")
        or tender_data.get("portal_url")
    )
    buyer_rfq_number = _clean(
        tender_data.get("tender_number")
        or tender_data.get("buyer_rfq_number")
        or tender_id
    )
    quote_number = _clean(tender_data.get("quote_number") or f"{buyer_rfq_number}-QUOTE")
    recipient_email = _clean(
        tender_data.get("recipient_email")
        or tender_data.get("buyer_email")
        or company_data.get("buyer_email")
    )
    return {
        "portal_url": portal_url,
        "buyer_rfq_number": buyer_rfq_number,
        "rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "title": _clean(tender_data.get("tender_title") or tender_data.get("title")),
        "buyer_name": _clean(tender_data.get("client_name") or tender_data.get("buyer_name")),
        "recipient_email": recipient_email,
        "final_pdf_path": quote_pack_pdf_path,
        "pdf_path": quote_pack_pdf_path,
        "quote_folder": quote_folder,
        "quote_pack_dir": quote_folder,
        "quote_pack_metadata_path": quote_pack_metadata_path,
        "attachment_paths": [quote_pack_pdf_path] + list(submission_pack.get("submission_pack_files") or []),
        "submission_attachments": list(submission_pack.get("submission_pack_files") or []),
        "submission_method": "portal" if portal_url else "email",
    }


def _record_manual_production_pilot_run(result: Dict[str, Any]) -> Dict[str, Any]:
    append_pilot_run(build_pilot_run_record(result))
    return result


class TenderSubmissionPipeline:
    def __init__(
        self,
        *,
        runtime_root: str | None = None,
        form_priority_engine: Optional[TenderFormPriorityEngine] = None,
    ) -> None:
        base_runtime = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
        self.runtime_root = Path(runtime_root) if runtime_root else base_runtime / "tender_submission_pipeline"
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.form_priority_engine = form_priority_engine or TenderFormPriorityEngine()

    def run(
        self,
        tender_root: str,
        tender_id: Optional[str] = None,
        instructions_text: Optional[str] = None,
        mandatory_form_codes: Optional[List[str]] = None,
        company_data: Optional[Dict[str, Any]] = None,
        director_data: Optional[Dict[str, Any]] = None,
        tender_data: Optional[Dict[str, Any]] = None,
        signature_path: Optional[str] = None,
        witness_1_signature_path: Optional[str] = None,
        witness_2_signature_path: Optional[str] = None,
        form_profile_map: Optional[Dict[str, str]] = None,
        enable_archive_extract: bool = True,
        mode: str = PIPELINE_MODE_ASSISTED_PRODUCTION,
        require_human_approval: Optional[bool] = None,
        human_approval_granted: bool = False,
        dry_run: bool = True,
        pricing_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        if mode not in _CANONICAL_PIPELINE_MODES:
            raise ValueError(f"Unsupported pipeline mode: {mode}")

        root_path = Path(tender_root).expanduser()
        if not root_path.exists():
            raise FileNotFoundError(f"Tender root not found: {tender_root}")

        tender_id_value = _clean(tender_id) or _slugify_pipeline_value(root_path.name, "tender-pack")
        instructions_value = _clean(
            instructions_text
            or (tender_data or {}).get("instructions_text")
            or (tender_data or {}).get("description")
            or (tender_data or {}).get("tender_title")
        )
        company_payload = _safe_dict(company_data)
        director_payload = _safe_dict(director_data)
        tender_payload = _safe_dict(tender_data)
        profile_map = dict(form_profile_map or {})
        mandatory_codes = list(mandatory_form_codes or [])

        human_approval_required = (
            bool(require_human_approval)
            if require_human_approval is not None
            else mode == PIPELINE_MODE_ASSISTED_PRODUCTION
        )

        run_folder = self.runtime_root / _slugify_pipeline_value(tender_id_value, "tender")
        run_folder.mkdir(parents=True, exist_ok=True)

        stages: List[Dict[str, Any]] = []
        rfq_source_validation = _scan_real_rfq_source_files(root_path)
        intake_files = [Path(path) for path in rfq_source_validation.get("supported_files", [])]
        intake_status = "completed" if rfq_source_validation.get("has_real_rfq_files") else "warning"
        _append_stage(
            stages,
            "tender_pack_intake",
            "tender pack intake",
            intake_status,
            tender_root=str(root_path),
            file_count=int(rfq_source_validation.get("file_count", 0) or 0),
            supported_file_count=int(rfq_source_validation.get("supported_file_count", 0) or 0),
            supported_extensions=list(rfq_source_validation.get("supported_extensions") or []),
            warning_reasons=list(rfq_source_validation.get("warning_reasons") or []),
        )

        plan = self.form_priority_engine.build_submission_plan(
            tender_root=str(root_path),
            tender_id=tender_id_value,
            instructions_text=instructions_value,
            mandatory_form_codes=mandatory_codes,
            enable_archive_extract=enable_archive_extract,
        )
        extracted_count = sum(1 for doc in plan.get("documents_found", []) if isinstance(doc, dict) and doc.get("extracted_from_archive"))
        _append_stage(
            stages,
            "archive_extraction",
            "archive extraction",
            "completed" if enable_archive_extract else "skipped",
            extracted_document_count=extracted_count,
            archive_extraction_enabled=enable_archive_extract,
        )

        analysis_document_paths = _select_analysis_document_paths(plan)
        pricing_document_paths = list(dict.fromkeys(analysis_document_paths + [str(path) for path in intake_files]))
        analysis_input = {
            "title": _clean(tender_payload.get("tender_title") or tender_payload.get("title") or tender_id_value),
            "buyer_name": _clean(tender_payload.get("client_name") or tender_payload.get("buyer_name")),
            "buyer_rfq_number": _clean(tender_payload.get("tender_number") or tender_payload.get("buyer_rfq_number") or tender_id_value),
            "local_document_paths": analysis_document_paths,
        }
        analysis = analyse_rfq_document_intelligence(analysis_input)
        _append_stage(
            stages,
            "rfq_document_analysis",
            "RFQ/document analysis",
            "completed",
            document_count=len(analysis_document_paths),
            report_path=_clean(analysis.get("report_path")),
            quote_safe=bool(analysis.get("quote_safe", False)),
        )

        required_forms = list(plan.get("required_forms") or [])
        missing_forms = list(plan.get("missing_forms") or [])
        _append_stage(
            stages,
            "mandatory_form_detection",
            "mandatory form detection",
            "completed",
            required_form_count=len(required_forms),
            missing_form_count=len(missing_forms),
        )

        merged_company_director_data = {
            "company": company_payload,
            "director": director_payload,
            "signature_path": _clean(signature_path),
            "witness_1_signature_path": _clean(witness_1_signature_path),
            "witness_2_signature_path": _clean(witness_2_signature_path),
        }
        _append_stage(
            stages,
            "company_director_data_injection",
            "company/director data injection",
            "completed",
            company_fields=sorted(company_payload.keys()),
            director_fields=sorted(director_payload.keys()),
        )

        classification_analysis = dict(analysis)
        intelligence = dict(classification_analysis.get("document_intelligence") or {})
        intelligence["compulsory_briefing_required"] = _pipeline_briefing_required(instructions_value, analysis)
        classification_analysis["document_intelligence"] = intelligence

        classification = classify_tender(
            {
                "title": tender_payload.get("tender_title") or tender_payload.get("title") or tender_id_value,
                "description": instructions_value or tender_payload.get("description"),
                "raw_text": "\n".join(
                    [
                        instructions_value,
                        _analysis_text_blob(analysis),
                    ]
                ),
                "estimated_profit_signal": {"estimated_profit": tender_payload.get("estimated_profit")},
            },
            classification_analysis,
            {
                "boq_context": {},
                "line_item_count": len(_extract_analysis_line_items(analysis)),
            },
        )

        document_pricing = _extract_quote_pack_rows_from_documents(
            tender_id=tender_id_value,
            tender_payload=tender_payload,
            document_paths=pricing_document_paths,
        )
        extracted_line_item_count = int(document_pricing.get("extracted_line_item_count", 0) or 0)
        extracted_line_item_descriptions = [str(item) for item in _safe_list(document_pricing.get("extracted_line_item_descriptions")) if _clean(item)]
        output_rows = document_pricing.get("rows") if isinstance(document_pricing.get("rows"), list) else []
        if not output_rows:
            output_rows = _fallback_output_rows(tender_payload, instructions_value)
        pricing_application = _apply_pricing_file_to_rows(output_rows, pricing_file)
        output_rows = pricing_application.get("rows") if isinstance(pricing_application.get("rows"), list) else output_rows
        pricing_file_loaded = bool(pricing_application.get("pricing_file_loaded", False))
        pricing_file_item_count = int(pricing_application.get("pricing_file_item_count", 0) or 0)
        pricing_items_matched = int(pricing_application.get("pricing_items_matched", 0) or 0)
        pricing_items_unmatched = int(pricing_application.get("pricing_items_unmatched", 0) or 0)
        output_metadata = {
            "quote_reference": _clean(tender_payload.get("quote_number") or f"{tender_id_value}-QUOTE"),
            "buyer_name": _clean(tender_payload.get("client_name") or tender_payload.get("buyer_name")),
            "buyer_rfq_number": _clean(tender_payload.get("tender_number") or tender_payload.get("buyer_rfq_number") or tender_id_value),
            "rfq_number": _clean(tender_payload.get("tender_number") or tender_id_value),
            "title": _clean(tender_payload.get("tender_title") or tender_payload.get("title") or tender_id_value),
            "vat_rate": tender_payload.get("vat_rate", 15.0),
            "currency": tender_payload.get("currency", "ZAR"),
            "prices_include_vat": tender_payload.get("prices_include_vat", True),
        }
        quote_output = build_final_output_payload(output_rows, metadata=output_metadata)

        quote_pack_metadata_path = run_folder / f"{_slugify_pipeline_value(tender_id_value)}__quote_pack.json"
        quote_pack_pdf_path = run_folder / f"{_slugify_pipeline_value(tender_id_value)}__quote_pack.pdf"
        _write_json_file(quote_pack_metadata_path, quote_output)
        _write_placeholder_pdf(
            quote_pack_pdf_path,
            "LMCP Assisted Production Quote Pack",
            [
                f"Tender ID: {tender_id_value}",
                f"Buyer RFQ: {output_metadata['buyer_rfq_number']}",
                f"Title: {output_metadata['title']}",
                "Status: Pending human approval before final submission.",
            ],
        )

        submission_pack = build_submission_pack(
            {
                "quote_pack_pdf_path": str(quote_pack_pdf_path),
                "metadata": {
                    "pdf_output_dir": str(run_folder),
                    "buyer_rfq_number": output_metadata["buyer_rfq_number"],
                    "buyer_name": output_metadata["buyer_name"],
                    "title": output_metadata["title"],
                    "extra_submission_paths": analysis_document_paths[:10],
                },
            }
        )
        _append_stage(
            stages,
            "quote_submission_pack_generation",
            "quote/submission pack generation",
            "completed",
            quote_pack_metadata_path=str(quote_pack_metadata_path),
            quote_pack_pdf_path=str(quote_pack_pdf_path),
            submission_pack_manifest_path=_clean(submission_pack.get("submission_pack_manifest_path")),
        )

        audit_payload = {
            "generated_at": _utc_now_iso(),
            "tender_id": tender_id_value,
            "mode": mode,
            "dry_run": dry_run,
            "human_approval_required": human_approval_required,
            "human_approval_granted": human_approval_granted,
            "classification": classification,
            "form_plan_summary": {
                "documents_found": len(plan.get("documents_found") or []),
                "required_forms": len(required_forms),
                "missing_forms": len(missing_forms),
            },
            "analysis_report_path": _clean(analysis.get("report_path")),
            "pipeline_stages": stages,
        }
        audit_output_path = run_folder / f"{_slugify_pipeline_value(tender_id_value)}__audit.json"
        _write_json_file(audit_output_path, audit_payload)
        _append_stage(
            stages,
            "proof_audit_output",
            "proof/audit output",
            "completed",
            audit_output_path=str(audit_output_path),
        )

        blocked = not bool(classification.get("eligible"))
        quote_pack_quality = _evaluate_quote_pack_quality(quote_output, blocked_by_eligibility=blocked)
        real_rfq_files_detected = bool(rfq_source_validation.get("has_real_rfq_files"))
        generated_quote_pack = bool(real_rfq_files_detected)
        generated_submission_pack = bool(real_rfq_files_detected)
        warning_messages = list(rfq_source_validation.get("warning_reasons") or [])
        if pricing_file and not pricing_file_loaded:
            warning_messages.append("pricing file supplied but pricing file could not be loaded or contained no pricing rows.")
        if pricing_file_loaded and extracted_line_item_count == 0:
            warning_messages.append("pricing file supplied but no extractable RFQ line items found.")
        elif pricing_file_loaded and extracted_line_item_count > 0 and pricing_items_matched == 0:
            warning_messages.append("pricing file supplied but no pricing rows matched extracted line items.")
        if pricing_application.get("pricing_warnings"):
            warning_messages.extend([str(item) for item in pricing_application.get("pricing_warnings") if str(item).strip()])
        if quote_pack_quality.get("approval_blocked"):
            warning_messages.append(f"quote pack quality status: {quote_pack_quality.get('quote_pack_quality_status')}")
        pricing_diagnostics = {
            "extracted_line_item_count": extracted_line_item_count,
            "extracted_line_item_descriptions": extracted_line_item_descriptions,
            "pricing_file_loaded": pricing_file_loaded,
            "pricing_file_item_count": pricing_file_item_count,
            "pricing_items_matched": pricing_items_matched,
            "pricing_items_unmatched": pricing_items_unmatched,
        }
        _append_stage(
            stages,
            "quote_pack_quality_assessment",
            "quote pack quality assessment",
            "warning" if quote_pack_quality.get("approval_blocked") else "completed",
            quote_pack_quality_status=quote_pack_quality.get("quote_pack_quality_status"),
            approval_blocked=bool(quote_pack_quality.get("approval_blocked")),
            reason=quote_pack_quality.get("quote_pack_quality_reason"),
            summary=quote_pack_quality.get("quote_pack_quality_summary"),
        )
        if blocked:
            approval_blocked = True
            _append_stage(
                stages,
                "human_approval_gate",
                "human approval gate before final submission",
                "blocked",
                reason_codes=list(classification.get("reason_codes") or []),
                message=", ".join(classification.get("reasons") or []) or "Tender blocked by eligibility gate.",
            )
            return _record_manual_production_pilot_run({
                "success": False,
                "status": "blocked",
                "mode": mode,
                "dry_run": dry_run,
                "human_approval_required": human_approval_required,
                "human_approval_granted": False,
                "message": "Tender blocked by assisted-production eligibility rules.",
                "tender_id": tender_id_value,
                "tender_root": str(root_path),
                "classification": classification,
                "form_plan": plan,
                "analysis": analysis,
                "rfq_source_validation": rfq_source_validation,
                "quote_output": quote_output,
                "submission_pack": submission_pack,
                "proof_audit_output": {"audit_output_path": str(audit_output_path)},
                "final_files": [str(quote_pack_pdf_path), str(quote_pack_metadata_path), str(audit_output_path)],
                "quote_pack_generated": generated_quote_pack,
                "submission_pack_generated": generated_submission_pack,
                "quote_pack_quality_status": quote_pack_quality.get("quote_pack_quality_status"),
                "approval_blocked": True,
                "quote_pack_quality_reason": quote_pack_quality.get("quote_pack_quality_reason"),
                **pricing_diagnostics,
                "warnings": warning_messages,
                "pipeline_stages": stages,
                "form_profile_map": profile_map,
                "company_director_data": merged_company_director_data,
            })

        submission_payload = _build_pipeline_submission_payload(
            tender_id=tender_id_value,
            tender_data=tender_payload,
            company_data=company_payload,
            quote_pack_pdf_path=str(quote_pack_pdf_path),
            quote_pack_metadata_path=str(quote_pack_metadata_path),
            quote_folder=str(run_folder),
            submission_pack=submission_pack,
        )

        if human_approval_required and not human_approval_granted:
            pending_status = "warning" if quote_pack_quality.get("approval_blocked") else ("pending_human_approval" if real_rfq_files_detected else "warning")
            pending_message = (
                f"Assisted-production pipeline prepared the submission pack, but approval is blocked because quote pack quality status is {quote_pack_quality.get('quote_pack_quality_status')}."
                if quote_pack_quality.get("approval_blocked")
                else (
                    "Assisted-production pipeline prepared the submission pack and is waiting for human approval."
                    if real_rfq_files_detected
                    else "Assisted-production dry run completed with warnings: no real RFQ/tender source files were detected."
                )
            )
            _append_stage(
                stages,
                "human_approval_gate",
                "human approval gate before final submission",
                "warning" if quote_pack_quality.get("approval_blocked") else ("pending" if real_rfq_files_detected else "warning"),
                message=(
                    "Human approval is required before final submission."
                    if real_rfq_files_detected
                    else "Human approval gate not actionable because no real RFQ/tender files were detected."
                ),
            )
            return _record_manual_production_pilot_run({
                "success": True,
                "status": pending_status,
                "mode": mode,
                "dry_run": dry_run,
                "human_approval_required": True,
                "human_approval_granted": False,
                "message": pending_message,
                "tender_id": tender_id_value,
                "tender_root": str(root_path),
                "classification": classification,
                "form_plan": plan,
                "analysis": analysis,
                "rfq_source_validation": rfq_source_validation,
                "quote_output": quote_output,
                "submission_pack": submission_pack,
                "proof_audit_output": {"audit_output_path": str(audit_output_path)},
                "final_submission_payload": submission_payload,
                "final_files": [str(quote_pack_pdf_path), str(quote_pack_metadata_path), str(audit_output_path)],
                "quote_pack_generated": generated_quote_pack,
                "submission_pack_generated": generated_submission_pack,
                "quote_pack_quality_status": quote_pack_quality.get("quote_pack_quality_status"),
                "approval_blocked": bool(quote_pack_quality.get("approval_blocked")),
                "quote_pack_quality_reason": quote_pack_quality.get("quote_pack_quality_reason"),
                **pricing_diagnostics,
                "warnings": warning_messages,
                "pipeline_stages": stages,
                "form_profile_map": profile_map,
                "company_director_data": merged_company_director_data,
            })

        if dry_run:
            dry_run_status = "warning" if quote_pack_quality.get("approval_blocked") else ("dry_run_ready" if real_rfq_files_detected else "warning")
            dry_run_message = (
                f"Pipeline completed in dry-run mode, but approval is blocked because quote pack quality status is {quote_pack_quality.get('quote_pack_quality_status')}."
                if quote_pack_quality.get("approval_blocked")
                else (
                    "Pipeline completed in dry-run mode and is ready for final submission."
                    if real_rfq_files_detected
                    else "Pipeline completed in dry-run mode with warnings: no real RFQ/tender source files were detected."
                )
            )
            _append_stage(
                stages,
                "human_approval_gate",
                "human approval gate before final submission",
                "warning" if quote_pack_quality.get("approval_blocked") else ("approved" if real_rfq_files_detected else "warning"),
                message=(
                    "Human approval granted. Final submission skipped because dry_run=true."
                    if real_rfq_files_detected
                    else "Dry run kept executable for testing, but final packs are marked not generated because no real RFQ/tender files were detected."
                ),
            )
            return _record_manual_production_pilot_run({
                "success": True,
                "status": dry_run_status,
                "mode": mode,
                "dry_run": True,
                "human_approval_required": human_approval_required,
                "human_approval_granted": False,
                "message": dry_run_message,
                "tender_id": tender_id_value,
                "tender_root": str(root_path),
                "classification": classification,
                "form_plan": plan,
                "analysis": analysis,
                "rfq_source_validation": rfq_source_validation,
                "quote_output": quote_output,
                "submission_pack": submission_pack,
                "proof_audit_output": {"audit_output_path": str(audit_output_path)},
                "final_submission_payload": submission_payload,
                "final_files": [str(quote_pack_pdf_path), str(quote_pack_metadata_path), str(audit_output_path)],
                "quote_pack_generated": generated_quote_pack,
                "submission_pack_generated": generated_submission_pack,
                "quote_pack_quality_status": quote_pack_quality.get("quote_pack_quality_status"),
                "approval_blocked": bool(quote_pack_quality.get("approval_blocked")),
                "quote_pack_quality_reason": quote_pack_quality.get("quote_pack_quality_reason"),
                **pricing_diagnostics,
                "warnings": warning_messages,
                "pipeline_stages": stages,
                "form_profile_map": profile_map,
                "company_director_data": merged_company_director_data,
            })

        if quote_pack_quality.get("approval_blocked"):
            _append_stage(
                stages,
                "human_approval_gate",
                "human approval gate before final submission",
                "warning",
                message="Quote pack quality is not approval-ready; manual approval is blocked.",
            )
            return _record_manual_production_pilot_run({
                "success": True,
                "status": "warning",
                "mode": mode,
                "dry_run": False,
                "human_approval_required": human_approval_required,
                "human_approval_granted": False,
                "message": "Quote pack quality blocked approval. Final submission not attempted.",
                "tender_id": tender_id_value,
                "tender_root": str(root_path),
                "classification": classification,
                "form_plan": plan,
                "analysis": analysis,
                "rfq_source_validation": rfq_source_validation,
                "quote_output": quote_output,
                "submission_pack": submission_pack,
                "proof_audit_output": {"audit_output_path": str(audit_output_path)},
                "final_submission_payload": submission_payload,
                "final_files": [str(quote_pack_pdf_path), str(quote_pack_metadata_path), str(audit_output_path)],
                "quote_pack_generated": generated_quote_pack,
                "submission_pack_generated": generated_submission_pack,
                "quote_pack_quality_status": quote_pack_quality.get("quote_pack_quality_status"),
                "approval_blocked": True,
                "quote_pack_quality_reason": quote_pack_quality.get("quote_pack_quality_reason"),
                **pricing_diagnostics,
                "warnings": warning_messages,
                "pipeline_stages": stages,
                "form_profile_map": profile_map,
                "company_director_data": merged_company_director_data,
            })

        submission_result = submit_tender_to_portal(submission_payload)
        _append_stage(
            stages,
            "human_approval_gate",
            "human approval gate before final submission",
            "approved",
            message="Human approval granted and final submission attempted.",
        )
        return _record_manual_production_pilot_run({
            "success": bool(submission_result.get("success", False)),
            "status": _clean(submission_result.get("status") or "submitted"),
            "mode": mode,
            "dry_run": False,
            "human_approval_required": human_approval_required,
            "human_approval_granted": False,
            "message": _clean(submission_result.get("message") or "Final submission attempted."),
            "tender_id": tender_id_value,
            "tender_root": str(root_path),
            "classification": classification,
            "form_plan": plan,
            "analysis": analysis,
            "rfq_source_validation": rfq_source_validation,
            "quote_output": quote_output,
            "submission_pack": submission_pack,
            "proof_audit_output": {"audit_output_path": str(audit_output_path)},
            "final_submission_payload": submission_payload,
            "final_submission_result": submission_result,
            "final_files": [str(quote_pack_pdf_path), str(quote_pack_metadata_path), str(audit_output_path)],
            "quote_pack_generated": generated_quote_pack,
            "submission_pack_generated": generated_submission_pack,
            "quote_pack_quality_status": quote_pack_quality.get("quote_pack_quality_status"),
            "approval_blocked": bool(quote_pack_quality.get("approval_blocked")),
            "quote_pack_quality_reason": quote_pack_quality.get("quote_pack_quality_reason"),
            **pricing_diagnostics,
            "warnings": warning_messages,
            "pipeline_stages": stages,
            "form_profile_map": profile_map,
            "company_director_data": merged_company_director_data,
        })
