from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from playwright.sync_api import BrowserContext, Page, sync_playwright

logger = logging.getLogger(__name__)

ETENDERS_BASE_URL = "https://www.etenders.gov.za"
ETENDERS_LOGIN_URL = f"{ETENDERS_BASE_URL}/Login/Login"
ETENDERS_OPPORTUNITIES_URL = f"{ETENDERS_BASE_URL}/Home/opportunities"
DEFAULT_TIMEOUT_MS = 60000


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runtime_dir() -> Path:
    path = _project_root() / "runtime" / "playwright"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _profile_dir() -> Path:
    path = _runtime_dir() / "etenders_webkit_profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _storage_state_file() -> Path:
    return _runtime_dir() / "etenders_webkit_storage_state.json"


def _downloads_dir() -> Path:
    path = _runtime_dir() / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _login_proof_file() -> Path:
    return _runtime_dir() / "etenders_login_status.json"


def _maintenance_proof_file() -> Path:
    return _runtime_dir() / "etenders_maintenance_status.json"


def _screenshot_file(prefix: str) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return _runtime_dir() / f"{prefix}_{ts}.png"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _to_bool_yes_no(value: str) -> Optional[bool]:
    value = _safe_lower(value)
    if value in {"yes", "true", "y"}:
        return True
    if value in {"no", "false", "n"}:
        return False
    return None


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_env_value(name: str) -> str:
    return _clean(os.getenv(name))


def _page_text(page: Page) -> str:
    try:
        return _safe_lower(page.locator("body").inner_text(timeout=5000))
    except Exception:
        try:
            return _safe_lower(page.content())
        except Exception:
            return ""


def _current_status_payload(
    status: str,
    page: Optional[Page] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "status": status,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if page is not None:
        try:
            payload["url"] = page.url
        except Exception:
            payload["url"] = ""
    if extra:
        payload.update(extra)
    return payload


def detect_csd_maintenance(page: Page) -> Dict[str, Any]:
    text = _page_text(page)

    phrases = [
        "currently undergoing scheduled maintenance",
        "scheduled maintenance",
        "please check back later",
        "we expect to be back online shortly",
        "central supplier database is currently undergoing scheduled maintenance",
    ]

    matched = [p for p in phrases if p in text]
    is_maintenance = bool(matched)

    payload = _current_status_payload(
        status="maintenance" if is_maintenance else "available",
        page=page,
        extra={"matched_phrases": matched},
    )

    if is_maintenance:
        screenshot = _screenshot_file("etenders_csd_maintenance")
        try:
            page.screenshot(path=str(screenshot), full_page=True)
            payload["screenshot"] = str(screenshot)
        except Exception as exc:
            payload["screenshot_error"] = str(exc)

        _save_json(_maintenance_proof_file(), payload)

    return payload


def is_logged_in(page: Page) -> bool:
    url = _safe_lower(getattr(page, "url", ""))
    if "login" not in url and "account/login" not in url:
        return True

    text = _page_text(page)
    positive_markers = [
        "logout",
        "log out",
        "dashboard",
        "my profile",
        "welcome",
        "tender opportunities",
        "opportunities",
    ]
    return any(marker in text for marker in positive_markers)


def is_invalid_login(page: Page) -> bool:
    text = _page_text(page)
    markers = [
        "invalid login attempt to csd",
        "please verify your details and try again",
        "invalid login attempt",
    ]
    return any(marker in text for marker in markers)


def dismiss_etenders_popups(page: Page, wait_after_ms: int = 1500) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "popup_detected": False,
        "dismissed": False,
        "method": "",
        "details": [],
    }

    selectors = [
        "#educationalPopup",
        ".modal.show",
        ".modal.fade.show",
    ]

    try:
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() and locator.first.is_visible():
                result["popup_detected"] = True
                result["details"].append(f"visible:{selector}")

                close_selectors = [
                    f"{selector} button.close",
                    f"{selector} .btn-close",
                    f"{selector} [data-dismiss='modal']",
                    f"{selector} [data-bs-dismiss='modal']",
                    f"{selector} .close",
                    f"{selector} button:has-text('Close')",
                    f"{selector} button:has-text('Ok')",
                    f"{selector} button:has-text('Okay')",
                    f"{selector} button:has-text('Got it')",
                    f"{selector} button:has-text('Continue')",
                ]

                for close_selector in close_selectors:
                    try:
                        button = page.locator(close_selector).first
                        if button.count() and button.is_visible():
                            button.click(timeout=3000)
                            page.wait_for_timeout(wait_after_ms)
                            result["dismissed"] = True
                            result["method"] = f"click:{close_selector}"
                            return result
                    except Exception as exc:
                        result["details"].append(f"close_failed:{close_selector}:{exc}")

                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(wait_after_ms)
                    result["dismissed"] = True
                    result["method"] = "keyboard:Escape"
                    return result
                except Exception as exc:
                    result["details"].append(f"escape_failed:{exc}")

        return result
    except Exception as exc:
        result["details"].append(f"popup_detection_error:{exc}")
        return result


def _slugify_filename(value: str) -> str:
    value = _clean(value)
    value = re.sub(r"[^\w\-. ]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:180] or f"etenders_{int(time.time())}"


def _extract_label_value_pairs(expanded_row: Any) -> Dict[str, str]:
    result: Dict[str, str] = {}
    try:
        rows = expanded_row.locator("table tbody tr")
        count = rows.count()
    except Exception:
        return result

    for idx in range(count):
        row = rows.nth(idx)
        try:
            tds = row.locator("td")
            td_count = tds.count()
            if td_count >= 2:
                label = _clean(tds.nth(0).inner_text()).rstrip(":").strip()
                value = _clean(tds.nth(1).inner_text())
                if label and value:
                    result[label] = value
        except Exception:
            continue
    return result


def _extract_document_links(expanded_row: Any) -> List[Dict[str, str]]:
    docs: List[Dict[str, str]] = []
    try:
        links = expanded_row.locator("a")
        count = links.count()
    except Exception:
        return docs

    for idx in range(count):
        link = links.nth(idx)
        try:
            text = _clean(link.inner_text())
            href = _clean(link.get_attribute("href"))
            full_url = urljoin(ETENDERS_BASE_URL, href) if href else ""
            docs.append(
                {
                    "text": text,
                    "href": href,
                    "url": full_url,
                }
            )
        except Exception:
            continue
    return docs



def _v50_normalize_ref(value: Any) -> str:
    raw = _clean(value).lower()
    raw = raw.replace("bid number:", "").replace("tender number:", "").replace("rfq number:", "")
    raw = re.sub(r"[^a-z0-9/-]+", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-")
    return raw


def _v50_score_document_link(doc: Dict[str, Any], tender_ref: str) -> Dict[str, Any]:
    url = _safe_lower(doc.get("url"))
    href = _safe_lower(doc.get("href"))
    text = _safe_lower(doc.get("text"))
    combined = " ".join([url, href, text])
    norm_ref = _v50_normalize_ref(tender_ref)

    score = 0
    reasons: List[str] = []

    if norm_ref and norm_ref in _v50_normalize_ref(combined):
        score += 100
        reasons.append("exact_reference_match")

    if ".zip" in combined:
        score += 35
        reasons.append("zip_package")
    elif any(ext in combined for ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls"]):
        score += 20
        reasons.append("document_file")

    if any(x in combined for x in ["download", "documents", "related documents"]):
        score += 20
        reasons.append("download_document_signal")

    if any(x in combined for x in ["declaration", "general-conditions", "instructions-to-tenderers", "receipt-of-tender"]):
        score -= 30
        reasons.append("generic_procurement_doc")

    scored = dict(doc)
    scored["v50_score"] = score
    scored["v50_reasons"] = reasons
    scored["v50_exact_reference_match"] = "exact_reference_match" in reasons
    return scored



def _v50_extract_true_reference_from_record(record: Dict[str, Any]) -> str:
    """
    Extract a true RFQ/tender reference from expanded eTenders detail fields,
    not from listing category labels like 'Supplies: General'.
    """
    candidates = [
        record.get("tender_number"),
        record.get("title"),
        record.get("special_conditions"),
        record.get("place_required"),
        record.get("organ_of_state"),
    ]

    blob = " ".join(_clean(x) for x in candidates if x)

    patterns = [
        r"\bFIN-SCM-[A-Z0-9-]+\b",
        r"\bRFQ[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bRFP[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bSCM[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bBID[\s:/#-]*(?:NO|NUMBER|REF)?[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bTENDER[\s:/#-]*(?:NO|NUMBER|REF)?[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bQUOTATION[\s:/#-]*(?:NO|NUMBER|REF)?[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\b[TQ]\d{2,}[-/][A-Z0-9./-]+\b",
    ]

    bad_values = {
        "supplies general",
        "supplies computer equipment",
        "services general",
        "administrative and support activities",
        "manufacture of textiles",
        "construction",
        "other service activities",
    }

    for pattern in patterns:
        for match in re.findall(pattern, blob, flags=re.I):
            ref = re.sub(r"\s+", " ", _clean(match)).strip(" .,:;")
            if not ref:
                continue
            if ref.lower() in bad_values:
                continue
            if len(ref) < 6:
                continue
            return ref

    tender_number = _clean(record.get("tender_number"))
    if tender_number and tender_number.lower() not in bad_values and len(tender_number) >= 6:
        return tender_number

    return ""


def _v50_apply_true_reference_override(record: Dict[str, Any]) -> Dict[str, Any]:
    true_ref = _v50_extract_true_reference_from_record(record)

    record["v50_true_reference"] = true_ref
    record["v50_reference_override_applied"] = False

    if not true_ref:
        return record

    bad_listing_refs = {
        "supplies general",
        "supplies computer equipment",
        "services general",
        "administrative and support activities",
        "manufacture of textiles",
        "construction",
        "other service activities",
    }

    current_ref_blob = " ".join([
        _clean(record.get("buyer_rfq_number")),
        _clean(record.get("rfq_number")),
        _clean(record.get("reference_number")),
        _clean(record.get("tender_number")),
    ]).lower()

    should_override = (
        not _clean(record.get("buyer_rfq_number"))
        or any(bad in current_ref_blob for bad in bad_listing_refs)
        or _clean(record.get("buyer_rfq_number")).lower() == _clean(record.get("category")).lower()
    )

    if should_override:
        record["buyer_rfq_number"] = true_ref
        record["rfq_number"] = true_ref
        record["reference_number"] = true_ref
        record["v50_reference_override_applied"] = True

    return record



def _v50_enrich_record(record: Dict[str, Any]) -> Dict[str, Any]:
    tender_ref = (
        record.get("tender_number")
        or record.get("buyer_rfq_number")
        or record.get("rfq_number")
        or record.get("reference_number")
        or ""
    )

    normalized_ref = _v50_normalize_ref(tender_ref)

    docs = record.get("document_links") or []
    scored_docs = [_v50_score_document_link(doc, tender_ref) for doc in docs if isinstance(doc, dict)]
    scored_docs.sort(key=lambda x: float(x.get("v50_score") or 0), reverse=True)

    exact_docs = [d for d in scored_docs if d.get("v50_exact_reference_match")]

    record["v50_engine_version"] = "V50_TRUE_RFQ_DETAIL_DISCOVERY_ENGINE"
    record["v50_normalized_reference"] = normalized_ref
    record["v50_document_links_scored"] = scored_docs
    record["v50_exact_document_links"] = exact_docs
    record["v50_exact_document_match"] = bool(exact_docs)
    record["v50_best_document_link"] = exact_docs[0] if exact_docs else (scored_docs[0] if scored_docs else None)

    if exact_docs:
        record["v50_recommended_document_url"] = exact_docs[0].get("url")
        record["document_url"] = exact_docs[0].get("url")
    else:
        record["v50_recommended_document_url"] = ""

    return record



def _is_supply_like(record: Dict[str, Any]) -> bool:
    text = " ".join(
        [
            _clean(record.get("category")),
            _clean(record.get("title")),
            _clean(record.get("tender_type")),
            _clean(record.get("special_conditions")),
            _clean(record.get("place_required")),
        ]
    ).lower()

    blocked_keywords = [
        "medical",
        "pharmaceutical",
        "syringe",
        "bandage",
        "clinic",
        "laptop",
        "computer",
        "printer",
        "server",
        "router",
        "monitor",
        "ups",
        "software",
        "tablet",
        "petrol",
        "diesel",
        "catering",
        "construction",
        "landscaping",
        "irrigation",
        "civil",
        "building",
        "repair",
        "maintenance",
        "professional service",
        "professional services",
        "consulting",
        "works",
    ]
    positive_keywords = [
        "supplies",
        "supply",
        "delivery",
        "supply and delivery",
        "goods",
        "stationery",
        "furniture",
        "office supplies",
        "consumables",
    ]

    if any(word in text for word in blocked_keywords):
        return False
    if any(word in text for word in positive_keywords):
        return True
    return False


def assess_lmcp_eligibility(record: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []

    compulsory_briefing = record.get("compulsory_briefing")
    if compulsory_briefing is True:
        reasons.append("Compulsory briefing is required.")

    briefing_required = record.get("briefing_required")
    if briefing_required is True and compulsory_briefing is None:
        reasons.append("Briefing session appears required and should be reviewed.")

    if not _is_supply_like(record):
        reasons.append("Opportunity does not appear to be supply/delivery only.")

    eligible = len(reasons) == 0

    return {
        "eligible": eligible,
        "blocked": not eligible,
        "reasons": reasons,
    }


def _extract_esubmission_status_from_row(row: Any) -> Dict[str, Any]:
    result = {
        "esubmission_allowed": None,
        "esubmission_class": "",
        "esubmission_icon_class": "",
        "esubmission_text": "",
    }

    try:
        tds = row.locator("td")
        if tds.count() < 4:
            return result

        esub_td = tds.nth(3)
        result["esubmission_text"] = _clean(esub_td.inner_text())
        try:
            span = esub_td.locator("span").first
            if span.count():
                result["esubmission_class"] = _clean(span.get_attribute("class"))
        except Exception:
            pass

        try:
            icon = esub_td.locator("i").first
            if icon.count():
                result["esubmission_icon_class"] = _clean(icon.get_attribute("class"))
        except Exception:
            pass

        esub_class_lower = _safe_lower(result["esubmission_class"])
        icon_class_lower = _safe_lower(result["esubmission_icon_class"])

        if "esuballowed" in esub_class_lower or "fas fa-check" in icon_class_lower:
            result["esubmission_allowed"] = True
        elif "esubnotallowed" in esub_class_lower or "fa fa-times" in icon_class_lower:
            result["esubmission_allowed"] = False
    except Exception:
        return result

    return result


def _open_authenticated_context(headless: bool = False) -> BrowserContext:
    storage_file = _storage_state_file()
    if not storage_file.exists():
        raise FileNotFoundError(f"Missing storage state: {storage_file}")

    pw = sync_playwright().start()
    browser = pw.webkit.launch(headless=headless)
    context = browser.new_context(storage_state=str(storage_file), accept_downloads=True)
    setattr(context, "_lmcp_pw", pw)
    setattr(context, "_lmcp_browser", browser)
    return context


def _close_authenticated_context(context: BrowserContext) -> None:
    browser = getattr(context, "_lmcp_browser", None)
    pw = getattr(context, "_lmcp_pw", None)
    try:
        context.close()
    finally:
        try:
            if browser is not None:
                browser.close()
        finally:
            if pw is not None:
                pw.stop()


def login_etenders_with_manual_captcha(
    username: Optional[str] = None,
    password: Optional[str] = None,
    headless: bool = False,
    timeout_seconds: int = 300,
) -> Dict[str, Any]:
    username = _clean(username) or _load_env_value("ETENDERS_USERNAME")
    password = _clean(password) or _load_env_value("ETENDERS_PASSWORD")

    result: Dict[str, Any] = {
        "status": "unknown",
        "storage_state_file": str(_storage_state_file()),
        "profile_dir": str(_profile_dir()),
        "login_url": ETENDERS_LOGIN_URL,
    }

    with sync_playwright() as pw:
        context = pw.webkit.launch_persistent_context(
            user_data_dir=str(_profile_dir()),
            headless=headless,
            accept_downloads=True,
        )

        try:
            page = context.new_page()
            page.goto(
                ETENDERS_LOGIN_URL,
                wait_until="domcontentloaded",
                timeout=DEFAULT_TIMEOUT_MS,
            )
            page.wait_for_timeout(2500)

            maintenance_status = detect_csd_maintenance(page)
            if maintenance_status.get("status") == "maintenance":
                result.update(
                    {
                        "status": "maintenance",
                        "message": "CSD is under scheduled maintenance.",
                        "url": page.url,
                        "maintenance": maintenance_status,
                    }
                )
                _save_json(_login_proof_file(), result)
                return result

            if username and password:
                try:
                    page.locator('input[name="UserName"]').fill(username, timeout=5000)
                    page.locator('input[name="Password"]').fill(password, timeout=5000)
                    result["credentials_filled"] = True
                except Exception as exc:
                    result["credentials_filled"] = False
                    result["credentials_fill_error"] = str(exc)
            else:
                result["credentials_filled"] = False
                result["message"] = "Credentials not supplied. Manual entry required."

            print("\nComplete the CAPTCHA manually in the browser.")
            print("Then click Log in.\n")

            deadline = time.time() + max(timeout_seconds, 60)
            final_page: Page = page

            while time.time() < deadline:
                if context.pages:
                    final_page = context.pages[-1]

                try:
                    maintenance_status = detect_csd_maintenance(final_page)
                    if maintenance_status.get("status") == "maintenance":
                        result.update(
                            {
                                "status": "maintenance",
                                "message": "CSD switched to maintenance during login flow.",
                                "url": final_page.url,
                                "maintenance": maintenance_status,
                            }
                        )
                        _save_json(_login_proof_file(), result)
                        return result
                except Exception:
                    pass

                if is_logged_in(final_page):
                    context.storage_state(path=str(_storage_state_file()))
                    screenshot = _screenshot_file("etenders_login_success")
                    try:
                        final_page.screenshot(path=str(screenshot), full_page=True)
                    except Exception:
                        screenshot = None

                    result.update(
                        {
                            "status": "logged_in",
                            "message": "Login successful and session saved.",
                            "url": final_page.url,
                            "screenshot": str(screenshot) if screenshot else "",
                        }
                    )
                    _save_json(_login_proof_file(), result)
                    return result

                if is_invalid_login(final_page):
                    screenshot = _screenshot_file("etenders_invalid_login")
                    try:
                        final_page.screenshot(path=str(screenshot), full_page=True)
                    except Exception:
                        screenshot = None

                    result.update(
                        {
                            "status": "invalid_login",
                            "message": "Invalid login attempt reported by eTenders/CSD.",
                            "url": final_page.url,
                            "screenshot": str(screenshot) if screenshot else "",
                        }
                    )
                    _save_json(_login_proof_file(), result)
                    return result

                time.sleep(2)

            screenshot = _screenshot_file("etenders_login_timeout")
            try:
                final_page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                screenshot = None

            result.update(
                {
                    "status": "timeout",
                    "message": "Login was not completed within the allowed time.",
                    "url": getattr(final_page, "url", ""),
                    "screenshot": str(screenshot) if screenshot else "",
                }
            )
            _save_json(_login_proof_file(), result)
            return result

        finally:
            try:
                context.close()
            except Exception:
                pass


def open_etenders_with_saved_session(
    target_url: str = ETENDERS_BASE_URL,
    headless: bool = False,
) -> Dict[str, Any]:
    storage_file = _storage_state_file()

    if not storage_file.exists():
        return {
            "status": "missing_storage_state",
            "message": "No saved storage state found. Login first.",
            "storage_state_file": str(storage_file),
        }

    with sync_playwright() as pw:
        browser = pw.webkit.launch(headless=headless)
        context = browser.new_context(storage_state=str(storage_file), accept_downloads=True)

        try:
            page = context.new_page()
            page.goto(target_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(2500)

            maintenance_status = detect_csd_maintenance(page)
            if maintenance_status.get("status") == "maintenance":
                return {
                    "status": "maintenance",
                    "message": "CSD is under maintenance.",
                    "url": page.url,
                    "maintenance": maintenance_status,
                }

            popup_status = dismiss_etenders_popups(page)

            screenshot = _screenshot_file("etenders_saved_session_open")
            try:
                page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                screenshot = None

            return {
                "status": "opened",
                "url": page.url,
                "logged_in": is_logged_in(page),
                "popup_status": popup_status,
                "screenshot": str(screenshot) if screenshot else "",
                "storage_state_file": str(storage_file),
            }
        finally:
            try:
                context.close()
            finally:
                browser.close()


def extract_expanded_row_record(
    expanded_row: Any,
    title: str = "",
    category: str = "",
    esubmission_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fields = _extract_label_value_pairs(expanded_row)
    docs = _extract_document_links(expanded_row)
    esubmission_status = esubmission_status or {}

    record: Dict[str, Any] = {
        "category": _clean(category),
        "title": _clean(title),
        "tender_number": fields.get("Tender Number", ""),
        "organ_of_state": fields.get("Organ Of State", ""),
        "tender_type": fields.get("Tender Type", ""),
        "province": fields.get("Province", ""),
        "date_published": fields.get("Date Published", ""),
        "closing_date": fields.get("Closing Date", ""),
        "place_required": fields.get("Place where goods, works or services are required", ""),
        "special_conditions": fields.get("Special Conditions", ""),
        "contact_person": fields.get("Contact Person", ""),
        "email": fields.get("Email", ""),
        "telephone_number": fields.get("Telephone number", ""),
        "fax_number": fields.get("FAX Number", ""),
        "briefing_required": _to_bool_yes_no(fields.get("Is there a briefing session?", "")),
        "compulsory_briefing": _to_bool_yes_no(fields.get("Is it compulsory?", "")),
        "briefing_date_time": fields.get("Briefing Date and Time", ""),
        "briefing_venue": fields.get("Briefing Venue", ""),
        "document_links": docs,
        "source_url": ETENDERS_OPPORTUNITIES_URL,
        "source_name": "eTenders",
        "esubmission_allowed": esubmission_status.get("esubmission_allowed"),
        "esubmission_class": _clean(esubmission_status.get("esubmission_class")),
        "esubmission_icon_class": _clean(esubmission_status.get("esubmission_icon_class")),
        "esubmission_text": _clean(esubmission_status.get("esubmission_text")),
    }
    record = _v50_apply_true_reference_override(record)
    record = _v50_apply_true_reference_override(record)
    record = _v50_enrich_record(record)
    record["eligibility"] = assess_lmcp_eligibility(record)
    record["portal_submission_possible"] = bool(record["eligibility"]["eligible"]) and record.get("esubmission_allowed") is True
    return record


def get_opportunities_page_summary(headless: bool = False) -> Dict[str, Any]:
    storage_file = _storage_state_file()

    if not storage_file.exists():
        return {
            "status": "missing_storage_state",
            "message": "No saved storage state found. Login first.",
            "storage_state_file": str(storage_file),
        }

    with sync_playwright() as pw:
        browser = pw.webkit.launch(headless=headless)
        context = browser.new_context(storage_state=str(storage_file), accept_downloads=True)

        try:
            page = context.new_page()
            page.goto(
                ETENDERS_OPPORTUNITIES_URL,
                wait_until="networkidle",
                timeout=DEFAULT_TIMEOUT_MS,
            )
            page.wait_for_timeout(5000)

            popup_status = dismiss_etenders_popups(page)
            page.wait_for_timeout(1500)

            rows = page.locator("table tbody tr")
            row_count = rows.count()

            first_row_text = ""
            first_row_esub = {}
            if row_count > 0:
                try:
                    first_row = rows.nth(0)
                    first_row_text = first_row.inner_text()
                    first_row_esub = _extract_esubmission_status_from_row(first_row)
                except Exception:
                    first_row_text = ""

            screenshot = _screenshot_file("etenders_opportunities_summary")
            try:
                page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                screenshot = None

            return {
                "status": "ok",
                "url": page.url,
                "logged_in": is_logged_in(page),
                "popup_status": popup_status,
                "row_count": row_count,
                "first_row_text": first_row_text,
                "first_row_esubmission": first_row_esub,
                "screenshot": str(screenshot) if screenshot else "",
            }
        finally:
            try:
                context.close()
            finally:
                browser.close()


def open_first_opportunity_detail(headless: bool = False) -> Dict[str, Any]:
    storage_file = _storage_state_file()

    if not storage_file.exists():
        return {
            "status": "missing_storage_state",
            "message": "No saved storage state found. Login first.",
            "storage_state_file": str(storage_file),
        }

    with sync_playwright() as pw:
        browser = pw.webkit.launch(headless=headless)
        context = browser.new_context(storage_state=str(storage_file), accept_downloads=True)

        try:
            page = context.new_page()
            page.goto(
                ETENDERS_OPPORTUNITIES_URL,
                wait_until="networkidle",
                timeout=DEFAULT_TIMEOUT_MS,
            )
            page.wait_for_timeout(5000)

            popup_status = dismiss_etenders_popups(page)
            page.wait_for_timeout(1500)

            rows = page.locator("table tbody tr")
            row_count = rows.count()

            if row_count < 1:
                screenshot = _screenshot_file("etenders_no_rows")
                try:
                    page.screenshot(path=str(screenshot), full_page=True)
                except Exception:
                    screenshot = None

                return {
                    "status": "no_rows",
                    "message": "No opportunity rows found.",
                    "url": page.url,
                    "popup_status": popup_status,
                    "row_count": row_count,
                    "screenshot": str(screenshot) if screenshot else "",
                }

            first_row = rows.nth(0)
            esubmission_status = _extract_esubmission_status_from_row(first_row)
            title = _clean(first_row.locator("td").nth(2).inner_text()) if first_row.locator("td").count() >= 3 else ""
            category = _clean(first_row.locator("td").nth(1).inner_text()) if first_row.locator("td").count() >= 2 else ""
            first_row.locator("td.details-control").first.click(timeout=8000)
            page.wait_for_timeout(3000)

            expanded_row = page.locator("table tbody tr").nth(1)
            record = extract_expanded_row_record(
                expanded_row,
                title=title,
                category=category,
                esubmission_status=esubmission_status,
            )

            screenshot = _screenshot_file("etenders_first_tender_detail")
            try:
                page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                screenshot = None

            return {
                "status": "opened_detail",
                "url": page.url,
                "logged_in": is_logged_in(page),
                "popup_status": popup_status,
                "row_count": row_count,
                "record": record,
                "screenshot": str(screenshot) if screenshot else "",
            }
        finally:
            try:
                context.close()
            finally:
                browser.close()



def _v51_clean_etenders_row_title(row_text: str, title: str = "", category: str = "") -> str:
    """
    V51: Resolve true eTenders title from row text instead of trusting fixed table columns.
    """
    raw = _clean(row_text)
    current_title = _clean(title)
    current_category = _clean(category)

    candidates = [raw, current_title]

    prefixes = [
        current_category,
        "Supplies: General",
        "Supplies: Clothing/Textiles/Footwear",
        "Supplies: Computer Equipment",
        "Supplies: Stationery/Printing",
        "Services: General",
        "Services: Professional",
        "Manufacture of textiles",
        "Manufacture of chemicals and chemical products",
        "Water supply; sewerage, waste management and remediation activities",
        "Other service activities",
        "Administrative and support activities",
    ]

    for candidate in candidates:
        cleaned = _clean(candidate)

        for prefix in prefixes:
            prefix = _clean(prefix)
            if prefix and cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip(" :-–—|\t\n")

        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        if cleaned and len(cleaned) > 10:
            return cleaned

    return current_title or raw



def find_tender_row(
    page: Page,
    buyer_rfq_number: str = "",
    title_contains: str = "",
) -> Dict[str, Any]:
    rows = page.locator("table tbody tr")
    count = rows.count()

    buyer_rfq_number = _clean(buyer_rfq_number)
    title_contains = _clean(title_contains)

    for idx in range(count):
        row = rows.nth(idx)
        try:
            text = row.inner_text()
        except Exception:
            text = ""

        if buyer_rfq_number and buyer_rfq_number in text:
            return {"found": True, "row_index": idx, "row_text": text}

        if title_contains and title_contains.lower() in text.lower():
            return {"found": True, "row_index": idx, "row_text": text}

    return {"found": False, "row_index": -1, "row_text": ""}


def probe_tender_submission_readiness(
    buyer_rfq_number: str,
    title_contains: str = "",
    headless: bool = False,
) -> Dict[str, Any]:
    storage_file = _storage_state_file()
    if not storage_file.exists():
        return {
            "status": "missing_storage_state",
            "message": "No saved storage state found. Login first.",
            "storage_state_file": str(storage_file),
        }

    with sync_playwright() as pw:
        browser = pw.webkit.launch(headless=headless)
        context = browser.new_context(storage_state=str(storage_file), accept_downloads=True)

        try:
            page = context.new_page()
            page.goto(
                ETENDERS_OPPORTUNITIES_URL,
                wait_until="networkidle",
                timeout=DEFAULT_TIMEOUT_MS,
            )
            page.wait_for_timeout(5000)
            popup_status = dismiss_etenders_popups(page)
            page.wait_for_timeout(1000)

            found = find_tender_row(page, buyer_rfq_number=buyer_rfq_number, title_contains=title_contains)
            if not found["found"]:
                screenshot = _screenshot_file("etenders_submission_probe_not_found")
                try:
                    page.screenshot(path=str(screenshot), full_page=True)
                except Exception:
                    screenshot = None
                return {
                    "status": "not_found",
                    "message": "Tender row not found.",
                    "buyer_rfq_number": buyer_rfq_number,
                    "title_contains": title_contains,
                    "popup_status": popup_status,
                    "screenshot": str(screenshot) if screenshot else "",
                }

            row = page.locator("table tbody tr").nth(found["row_index"])
            esubmission_status = _extract_esubmission_status_from_row(row)

            td_count = row.locator("td").count()
            category = _clean(row.locator("td").nth(1).inner_text()) if td_count >= 2 else ""
            title = _clean(row.locator("td").nth(2).inner_text()) if td_count >= 3 else ""
            try:
                row_text_for_title = row.inner_text()
            except Exception:
                row_text_for_title = title
            title = _v51_clean_etenders_row_title(row_text_for_title, title=title, category=category)
            row.locator("td.details-control").first.click(timeout=8000)
            page.wait_for_timeout(3000)

            expanded_row = page.locator("table tbody tr").nth(found["row_index"] + 1)
            record = extract_expanded_row_record(
                expanded_row,
                title=title,
                category=category,
                esubmission_status=esubmission_status,
            )

            body_text = _page_text(page)
            start_esub_found = "start esubmission process" in body_text

            screenshot = _screenshot_file("etenders_submission_probe")
            try:
                page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                screenshot = None

            if record.get("esubmission_allowed") is False:
                return {
                    "status": "manual_action_required",
                    "message": "eSubmission is not available for this tender on eTenders.",
                    "buyer_rfq_number": buyer_rfq_number,
                    "row_index": found["row_index"],
                    "record": record,
                    "start_esubmission_found": start_esub_found,
                    "popup_status": popup_status,
                    "screenshot": str(screenshot) if screenshot else "",
                }

            return {
                "status": "submission_possible" if record.get("portal_submission_possible") else "review_required",
                "buyer_rfq_number": buyer_rfq_number,
                "row_index": found["row_index"],
                "record": record,
                "start_esubmission_found": start_esub_found,
                "popup_status": popup_status,
                "screenshot": str(screenshot) if screenshot else "",
            }
        finally:
            try:
                context.close()
            finally:
                browser.close()


def harvest_etenders_opportunities(
    max_rows: int = 10,
    download_documents: bool = False,
    download_only_eligible: bool = True,
    headless: bool = False,
) -> Dict[str, Any]:
    storage_file = _storage_state_file()
    if not storage_file.exists():
        return {
            "status": "missing_storage_state",
            "message": "No saved storage state found. Login first.",
            "storage_state_file": str(storage_file),
        }

    context = _open_authenticated_context(headless=headless)
    try:
        page = context.new_page()
        page.goto(
            ETENDERS_OPPORTUNITIES_URL,
            wait_until="networkidle",
            timeout=DEFAULT_TIMEOUT_MS,
        )
        page.wait_for_timeout(5000)

        popup_status = dismiss_etenders_popups(page)
        page.wait_for_timeout(1500)

        row_locator = page.locator("table tbody tr")
        total_rows = row_locator.count()
        process_count = min(max_rows, total_rows)

        results: List[Dict[str, Any]] = []
        eligible_count = 0
        blocked_count = 0
        downloaded_count = 0
        esub_allowed_count = 0
        portal_submission_possible_count = 0

        for idx in range(process_count):
            page.goto(
                ETENDERS_OPPORTUNITIES_URL,
                wait_until="networkidle",
                timeout=DEFAULT_TIMEOUT_MS,
            )
            page.wait_for_timeout(3000)
            dismiss_etenders_popups(page)
            page.wait_for_timeout(1000)

            rows = page.locator("table tbody tr")
            if idx >= rows.count():
                break

            row = rows.nth(idx)
            esubmission_status = _extract_esubmission_status_from_row(row)

            td_count = row.locator("td").count()
            category = _clean(row.locator("td").nth(1).inner_text()) if td_count >= 2 else ""
            title = _clean(row.locator("td").nth(2).inner_text()) if td_count >= 3 else ""
            try:
                row_text_for_title = row.inner_text()
            except Exception:
                row_text_for_title = title
            title = _v51_clean_etenders_row_title(row_text_for_title, title=title, category=category)

            try:
                row.locator("td.details-control").first.click(timeout=8000)
                page.wait_for_timeout(2500)
            except Exception as exc:
                results.append(
                    {
                        "row_index": idx,
                        "title": title,
                        "status": "expand_failed",
                        "error": str(exc),
                    }
                )
                continue

            expanded_row = page.locator("table tbody tr").nth(idx + 1)
            record = extract_expanded_row_record(
                expanded_row,
                title=title,
                category=category,
                esubmission_status=esubmission_status,
            )
            record["row_index"] = idx
            record["status"] = "parsed"

            is_eligible = bool(record.get("eligibility", {}).get("eligible"))
            if is_eligible:
                eligible_count += 1
            else:
                blocked_count += 1

            if record.get("esubmission_allowed") is True:
                esub_allowed_count += 1

            if record.get("portal_submission_possible") is True:
                portal_submission_possible_count += 1

            should_download = bool(download_documents)
            if download_only_eligible and not is_eligible:
                should_download = False

            record["download_attempted"] = should_download
            record["download_skipped_reason"] = ""

            if download_documents and not should_download:
                record["download_skipped_reason"] = "Blocked tender: download limited to eligible opportunities."

            if should_download and record.get("document_links"):
                downloaded_files: List[str] = []
                link_locator = expanded_row.locator("a")
                link_count = min(link_locator.count(), len(record["document_links"]))

                for link_idx in range(link_count):
                    try:
                        link = link_locator.nth(link_idx)
                        with page.expect_download(timeout=15000) as dl_info:
                            link.click(timeout=8000)
                        download = dl_info.value
                        suggested_name = _slugify_filename(download.suggested_filename)
                        save_path = _downloads_dir() / suggested_name
                        download.save_as(str(save_path))
                        downloaded_files.append(str(save_path))
                        downloaded_count += 1
                    except Exception as exc:
                        downloaded_files.append(f"DOWNLOAD_FAILED: {exc}")

                record["downloaded_files"] = downloaded_files
            elif should_download:
                record["downloaded_files"] = []
                record["download_skipped_reason"] = "No document links found."

            results.append(record)

        proof_path = _runtime_dir() / "etenders_harvest_results.json"
        payload = {
            "status": "ok",
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "url": page.url,
            "popup_status": popup_status,
            "total_rows_seen": total_rows,
            "rows_processed": len(results),
            "download_documents": download_documents,
            "download_only_eligible": download_only_eligible,
            "eligible_count": eligible_count,
            "blocked_count": blocked_count,
            "downloaded_count": downloaded_count,
            "esub_allowed_count": esub_allowed_count,
            "portal_submission_possible_count": portal_submission_possible_count,
            "results": results,
        }
        _save_json(proof_path, payload)
        payload["proof_file"] = str(proof_path)
        return payload
    finally:
        _close_authenticated_context(context)


def get_etenders_login_health() -> Dict[str, Any]:
    storage_file = _storage_state_file()
    login_file = _login_proof_file()
    maintenance_file = _maintenance_proof_file()

    payload: Dict[str, Any] = {
        "profile_dir": str(_profile_dir()),
        "storage_state_file": str(storage_file),
        "storage_state_exists": storage_file.exists(),
        "login_status_file": str(login_file),
        "login_status_exists": login_file.exists(),
        "maintenance_status_file": str(maintenance_file),
        "maintenance_status_exists": maintenance_file.exists(),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    if login_file.exists():
        try:
            payload["last_login_status"] = json.loads(login_file.read_text(encoding="utf-8"))
        except Exception as exc:
            payload["last_login_status_error"] = str(exc)

    if maintenance_file.exists():
        try:
            payload["last_maintenance_status"] = json.loads(maintenance_file.read_text(encoding="utf-8"))
        except Exception as exc:
            payload["last_maintenance_status_error"] = str(exc)

    return payload


if __name__ == "__main__":
    print(
        json.dumps(
            harvest_etenders_opportunities(
                max_rows=3,
                download_documents=True,
                download_only_eligible=True,
            ),
            indent=2,
        )
    )


def run_etenders_playwright(max_items=20, headless=True):
    """
    SIMPLE + RELIABLE eTenders scraper (no login required)
    """

    from playwright.sync_api import sync_playwright

    results = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()

            page.goto("https://www.etenders.gov.za/Home/opportunities", timeout=60000)
            page.wait_for_timeout(5000)

            # Try multiple selectors (site changes often)
            selectors = [
                "table tbody tr",
                "table tr",
                ".table tbody tr",
            ]

            rows = []
            for sel in selectors:
                rows = page.query_selector_all(sel)
                if rows:
                    break

            for row in rows:
                try:
                    cols = row.query_selector_all("td")
                    if len(cols) < 2:
                        continue

                    text = " ".join(
                        (c.inner_text() or "").strip()
                        for c in cols
                    ).strip()

                    if not text:
                        continue

                    results.append({
                        "title": cols[1].inner_text().strip() if len(cols) > 1 else text[:120],
                        "description": text,
                        "closing_date": "",
                        "buyer_name": "eTenders",
                        "raw_text": text,
                    })

                    if len(results) >= max_items:
                        break

                except Exception:
                    continue

            browser.close()

    except Exception as e:
        print("eTenders scrape error:", e)

    return results
    """
    Compatibility wrapper required by tender_harvester.py.
    """

    # Try common existing function names in this file
    for fn_name in [
        "harvest_etenders",
        "scrape_etenders",
        "run_etenders",
        "extract_etenders",
        "get_etenders_opportunities",
    ]:
        fn = globals().get(fn_name)
        if callable(fn):
            try:
                return fn(max_items=max_items, headless=headless)
            except TypeError:
                try:
                    return fn(max_items=max_items)
                except TypeError:
                    return fn()

    return []
