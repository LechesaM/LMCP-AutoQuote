from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
LIVE_BROWSER_DIR = RUNTIME_DIR / "live_browser_attach_v47_3"
PROFILE_DIR = RUNTIME_DIR / "playwright_profiles" / "etenders"
SCREENSHOT_DIR = LIVE_BROWSER_DIR / "screenshots"

LIVE_BROWSER_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = LIVE_BROWSER_DIR / "attach_history.json"
ASSISTED_FILE = LIVE_BROWSER_DIR / "assisted_browser_required.json"
LAST_RESULT_FILE = LIVE_BROWSER_DIR / "last_attach_result.json"
SESSION_STATE_FILE = LIVE_BROWSER_DIR / "session_state.json"

DEFAULT_TIMEOUT_MS = int(os.getenv("LMCP_PORTAL_BROWSER_TIMEOUT_MS", "45000"))
HEADLESS = os.getenv("LMCP_PORTAL_BROWSER_HEADLESS", "true").lower() in {"1", "true", "yes", "on"}
ETENDERS_HOME = "https://www.etenders.gov.za/Home/opportunities"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return deepcopy(default)
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _append_json(path: Path, item: Dict[str, Any]) -> None:
    data = _read_json(path, [])
    if not isinstance(data, list):
        data = []
    data.append(item)
    _write_json(path, data)


def _slug(value: Any, fallback: str = "browser-attach") -> str:
    text = _safe_str(value, fallback)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return text[:120] or fallback


def _merge_autofill_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    plan_raw = payload.get("autofill_plan_json")
    if isinstance(plan_raw, str) and plan_raw.strip():
        try:
            plan = json.loads(plan_raw)
            if isinstance(plan, dict):
                merged = deepcopy(payload)
                merged.update({k: v for k, v in plan.items() if v is not None})
                return merged
        except Exception:
            pass
    return payload


def _buyer_rfq_number(payload: Dict[str, Any]) -> str:
    return _safe_str(
        payload.get("_locked_buyer_rfq_number")
        or payload.get("buyer_rfq_number")
        or payload.get("rfq_reference")
        or payload.get("rfq_number")
        or payload.get("reference_number")
        or payload.get("document_number")
        or payload.get("tender_number")
        or "UNKNOWN-RFQ"
    )


def _quote_number(payload: Dict[str, Any]) -> str:
    buyer_rfq = _buyer_rfq_number(payload)
    return _safe_str(payload.get("quote_number") or payload.get("lmcp_quote_number") or f"LMCP-{buyer_rfq}")


def _normalise_portal_url(payload: Dict[str, Any]) -> str:
    url = _safe_str(
        payload.get("portal_url")
        or payload.get("submission_url")
        or payload.get("url")
        or payload.get("tender_url")
        or payload.get("source_url")
        or ETENDERS_HOME
    )
    if url and "://" not in url:
        url = "https://" + url
    return url


def _normalise_attachments(payload: Dict[str, Any]) -> List[str]:
    values: List[Any] = []

    for key in [
        "attachments",
        "submission_attachments",
        "supporting_documents",
        "documents",
        "resolved_attachments",
        "attachment_paths",
    ]:
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif raw:
            values.append(raw)

    submission_pack = payload.get("submission_pack")
    if isinstance(submission_pack, dict):
        for key in ["attachments", "submission_attachments", "supporting_documents", "supporting_docs"]:
            raw = submission_pack.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif raw:
                values.append(raw)

    for key in ["pdf_path", "final_pdf_path", "quote_pdf_path"]:
        raw = payload.get(key)
        if raw:
            values.append(raw)

    output: List[str] = []
    seen = set()
    for item in values:
        path = _safe_str(item)
        if not path or path in seen:
            continue
        seen.add(path)
        output.append(path)
    return output


def _resolve_path(path_value: str) -> Optional[str]:
    if not path_value:
        return None

    candidates = [
        Path(path_value),
        Path("/app") / path_value,
        Path.cwd() / path_value,
        Path("/Users/Shared/LMCP-AutoQuote-Server") / path_value,
    ]

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return str(candidate.resolve())
        except Exception:
            continue

    return None


def _resolve_attachments(attachments: List[str]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    resolved: List[str] = []
    missing: List[str] = []

    for attachment in attachments:
        resolved_path = _resolve_path(attachment)
        exists = bool(resolved_path)
        rows.append({"path": attachment, "exists": exists, "resolved_path": resolved_path})

        if exists and resolved_path:
            resolved.append(resolved_path)
        else:
            missing.append(attachment)

    return {
        "status": "ok" if not missing else "missing_files",
        "count": len(attachments),
        "resolved": resolved,
        "missing": missing,
        "checked": rows,
    }


def _captcha_detected_text(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in [
            "captcha",
            "recaptcha",
            "i'm not a robot",
            "i am not a robot",
            "verify you are human",
            "security check",
        ]
    )


async def _capture(page: Any, buyer_rfq: str, label: str) -> Optional[str]:
    try:
        filename = f"{_slug(buyer_rfq)}__{label}__{_stamp()}.png"
        path = SCREENSHOT_DIR / filename
        await page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None


async def _body_text(page: Any) -> str:
    try:
        return await page.locator("body").inner_text(timeout=10000)
    except Exception:
        return ""


async def _is_logged_in(page: Any) -> Dict[str, Any]:
    text = await _body_text(page)
    lower = text.lower()

    logged_out_markers = ["login", "sign in", "username", "password"]
    logged_in_markers = ["logout", "my profile", "dashboard", "my tenders", "submitted", "respond"]

    return {
        "logged_in": any(m in lower for m in logged_in_markers) and not ("password" in lower and "username" in lower),
        "logged_out_likely": any(m in lower for m in logged_out_markers),
        "captcha_detected": _captcha_detected_text(text),
        "body_excerpt": text[:1200],
    }


async def _find_file_inputs(page: Any) -> List[Any]:
    handles: List[Any] = []
    for selector in ['input[type="file"]', "input[type=file]", "input[accept]"]:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            for i in range(count):
                handles.append(loc.nth(i))
        except Exception:
            continue
    return handles


async def _try_set_input_files(page: Any, files: List[str]) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    inputs = await _find_file_inputs(page)

    if not inputs:
        return {
            "status": "no_file_input",
            "uploaded": False,
            "attempts": attempts,
            "message": "No file input fields were found on the current page.",
        }

    for idx, input_locator in enumerate(inputs):
        try:
            await input_locator.set_input_files(files, timeout=DEFAULT_TIMEOUT_MS)
            attempts.append({"input_index": idx, "status": "set_input_files_ok", "file_count": len(files)})
            return {
                "status": "ok",
                "uploaded": True,
                "input_index": idx,
                "uploaded_files": files,
                "attempts": attempts,
            }
        except Exception as exc:
            attempts.append({"input_index": idx, "status": "failed", "error": str(exc)})

    return {
        "status": "failed",
        "uploaded": False,
        "attempts": attempts,
        "message": "File inputs were found, but none accepted the files.",
    }


async def _try_click_candidates(page: Any, candidates: List[str], wait_ms: int = 1500) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []

    for selector in candidates:
        try:
            loc = page.locator(selector)
            count = await loc.count()

            if count <= 0:
                attempts.append({"selector": selector, "status": "not_found"})
                continue

            await loc.first.scroll_into_view_if_needed(timeout=3000)
            await loc.first.click(timeout=10000)
            await page.wait_for_timeout(wait_ms)

            attempts.append({"selector": selector, "status": "clicked"})
            return {"status": "ok", "clicked": True, "selector": selector, "attempts": attempts}

        except Exception as exc:
            attempts.append({"selector": selector, "status": "failed", "error": str(exc)})

    return {"status": "not_clicked", "clicked": False, "attempts": attempts}


async def _force_remove_etenders_popups(page: Any) -> None:
    try:
        await page.evaluate(
            """
            (() => {
                const ids = ['educationalPopup'];
                ids.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.remove();
                });

                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = 'auto';
                document.body.style.paddingRight = '0px';
            })();
            """
        )
        await page.wait_for_timeout(1000)
    except Exception:
        pass


async def _ensure_session(page: Any, payload: Dict[str, Any], buyer_rfq: str) -> Dict[str, Any]:
    await page.goto(ETENDERS_HOME, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    await page.wait_for_timeout(2000)

    await _force_remove_etenders_popups(page)

    initial = await _is_logged_in(page)
    screenshot = await _capture(page, buyer_rfq, "session_check")

    if initial.get("logged_in"):
        result = {
            "status": "ok",
            "logged_in": True,
            "mode": "reused_persistent_profile",
            "initial_state": initial,
            "screenshot": screenshot,
            "checked_at": _now(),
            "profile_dir": str(PROFILE_DIR),
        }
        _write_json(SESSION_STATE_FILE, result)
        return result

    result = {
        "status": "manual_login_required",
        "logged_in": False,
        "mode": "manual_first_login_needed",
        "initial_state": initial,
        "screenshot_before": screenshot,
        "checked_at": _now(),
        "profile_dir": str(PROFILE_DIR),
    }
    _write_json(SESSION_STATE_FILE, result)
    return result


async def _fill_search_field(page: Any, buyer_rfq: str) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []

    search_candidates = [
        "input[placeholder*='Tender Number']",
        "input[placeholder*='Enter Tender Number']",
        "input[name*='Tender']",
        "input[id*='Tender']",
        "input[type='search']",
        "input[placeholder*='Search']",
        "input[placeholder*='search']",
        "input.form-control",
        "input[type='text']",
    ]

    for selector in search_candidates:
        try:
            loc = page.locator(selector)
            if await loc.count() <= 0:
                steps.append({"action": "fill_search", "status": "not_found", "selector": selector})
                continue

            try:
                await loc.first.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass

            try:
                await loc.first.click(timeout=3000)
            except Exception:
                pass

            filled = False

            try:
                await loc.first.fill(buyer_rfq, timeout=5000)
                filled = True
            except Exception:
                try:
                    handle = await loc.first.element_handle()
                    if handle:
                        await page.evaluate(
                            "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }",
                            handle,
                            buyer_rfq,
                        )
                        filled = True
                except Exception:
                    pass

            steps.append({
                "action": "fill_search",
                "status": "ok" if filled else "failed",
                "selector": selector,
                "value": buyer_rfq,
            })

            if filled:
                return {"status": "ok", "filled": True, "selector": selector, "steps": steps}

        except Exception as exc:
            steps.append({"action": "fill_search", "status": "failed", "selector": selector, "error": str(exc)})

    return {"status": "failed", "filled": False, "steps": steps}


async def _detect_submission_capability(page: Any) -> Dict[str, Any]:
    body = (await _body_text(page)).lower()

    capability = {
        "status": "ok",
        "documents_visible": False,
        "upload_controls_visible": False,
        "submission_controls_visible": False,
        "esubmission_marker": False,
        "file_inputs_present": False,
        "capability": "unknown",
    }

    document_markers = [
        "tender documents",
        "download",
        "bid document",
        "rfq document",
        "specification",
        "document collection",
    ]

    upload_markers = [
        "upload",
        "attach",
        "choose file",
        "browse",
        "drag and drop",
        "select file",
    ]

    submit_markers = [
        "submit",
        "final submit",
        "participate",
        "continue",
        "confirm submission",
        "respond",
    ]

    if any(marker in body for marker in document_markers):
        capability["documents_visible"] = True

    if any(marker in body for marker in upload_markers):
        capability["upload_controls_visible"] = True

    if any(marker in body for marker in submit_markers):
        capability["submission_controls_visible"] = True

    if "esubmission" in body:
        capability["esubmission_marker"] = True

    try:
        capability["file_inputs_present"] = len(await _find_file_inputs(page)) > 0
    except Exception:
        capability["file_inputs_present"] = False

    if capability["file_inputs_present"]:
        capability["upload_controls_visible"] = True

    if capability["documents_visible"] and not capability["upload_controls_visible"]:
        capability["capability"] = "documents_only"

    if capability["upload_controls_visible"] and not capability["submission_controls_visible"]:
        capability["capability"] = "upload_capable"

    if capability["upload_controls_visible"] and capability["submission_controls_visible"]:
        capability["capability"] = "fully_submittable"

    return capability


async def _scan_tender_details_and_click_action(page: Any, buyer_rfq: str) -> Dict[str, Any]:
    detail_scan = {
        "status": "started",
        "buyer_rfq_number": buyer_rfq,
        "expanded_rows": 0,
        "matched": False,
        "clicked_action": False,
        "attempts": [],
    }

    try:
        expanders = page.locator(
            "table#tendeList .details-control, "
            "table#tendeList td.details-control, "
            "table#tendeList tbody tr td:first-child"
        )
        count = await expanders.count()

        for i in range(min(count, 35)):
            try:
                await expanders.nth(i).scroll_into_view_if_needed(timeout=3000)
                await expanders.nth(i).click(timeout=5000)
                await page.wait_for_timeout(1200)

                detail_scan["expanded_rows"] += 1
                body = await _body_text(page)

                if buyer_rfq.lower() in body.lower():
                    detail_scan["matched"] = True
                    detail_scan["matched_row_index"] = i

                    action_result = await _try_click_candidates(
                        page,
                        [
                            f"tr:has-text('{buyer_rfq}') a:has-text('Respond')",
                            f"tr:has-text('{buyer_rfq}') a:has-text('Submit')",
                            f"tr:has-text('{buyer_rfq}') a:has-text('eSubmission')",
                            f"tr:has-text('{buyer_rfq}') button:has-text('Respond')",
                            f"tr:has-text('{buyer_rfq}') button:has-text('Submit')",
                            "a:has-text('Respond')",
                            "a:has-text('Submit')",
                            "a:has-text('eSubmission')",
                            "button:has-text('Respond')",
                            "button:has-text('Submit')",
                            "button:has-text('eSubmission')",
                            f"tr:has-text('{buyer_rfq}') td:has-text('✓')",
                            f"tr:has-text('{buyer_rfq}') td:nth-child(4)",
                            f"tr:has-text('{buyer_rfq}') .fa-check",
                            f"tr:has-text('{buyer_rfq}') i.fa",
                            "text=eSubmission",
                            "text=Respond",
                            "text=Submit",
                        ],
                        wait_ms=3000,
                    )

                    detail_scan["action_result"] = action_result
                    detail_scan["clicked_action"] = bool(action_result.get("clicked"))
                    break

            except Exception as exc:
                detail_scan["attempts"].append({"row_index": i, "status": "failed", "error": str(exc)})

        if not detail_scan["matched"]:
            detail_scan["status"] = "not_matched"
        elif detail_scan["clicked_action"]:
            detail_scan["status"] = "matched_and_clicked"
        else:
            detail_scan["status"] = "matched_no_action_clicked"

    except Exception as exc:
        detail_scan["status"] = "failed"
        detail_scan["error"] = str(exc)

    return detail_scan


async def _navigate_to_target(page: Any, payload: Dict[str, Any], buyer_rfq: str) -> Dict[str, Any]:
    portal_url = _normalise_portal_url(payload)

    result: Dict[str, Any] = {
        "target_url": portal_url,
        "buyer_rfq_number": buyer_rfq,
        "steps": [],
    }

    try:
        await page.goto(portal_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        await page.wait_for_timeout(2500)
        await _force_remove_etenders_popups(page)
        result["steps"].append({"action": "goto_target", "status": "ok", "url": portal_url})
    except Exception as exc:
        result["steps"].append({"action": "goto_target", "status": "failed", "error": str(exc)})

    try:
        adv = page.locator("text=Advanced Search")
        if await adv.count() > 0:
            await adv.first.click(timeout=5000)
            await page.wait_for_timeout(2000)
            await _force_remove_etenders_popups(page)
            result["steps"].append({"action": "advanced_search", "status": "clicked"})
    except Exception as exc:
        result["steps"].append({"action": "advanced_search", "status": "failed", "error": str(exc)})

    search_result = await _fill_search_field(page, buyer_rfq)
    result["search_fill_result"] = search_result
    result["steps"].extend(search_result.get("steps", []))

    try:
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(4000)
    except Exception:
        pass

    result["search_click_result"] = await _try_click_candidates(
        page,
        [
            "button:has-text('Search')",
            "input[type='submit'][value*='Search']",
            "text=Search",
        ],
        wait_ms=5000,
    )

    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    await page.wait_for_timeout(5000)
    await _force_remove_etenders_popups(page)

    result["rfq_click_result"] = await _try_click_candidates(
        page,
        [
            f"text={buyer_rfq}",
            f"a:has-text('{buyer_rfq}')",
            f"td:has-text('{buyer_rfq}')",
            "button:has-text('View')",
            "a:has-text('View')",
            "button:has-text('Details')",
            "a:has-text('Details')",
        ],
        wait_ms=3000,
    )

    result["target_screenshot"] = await _capture(page, buyer_rfq, "target_page")

    result["detail_scan"] = await _scan_tender_details_and_click_action(page, buyer_rfq)

    if not result["detail_scan"].get("clicked_action"):
        result["respond_click_result"] = await _try_click_candidates(
            page,
            [
                ".details-control",
                "button.details-control",
                "td.details-control",
                "tr td:first-child",
                "[aria-label='Expand row']",
                "button:has-text('+')",
                "text=View Details",
                "text=Details",
                "text=Expand",
                "text=Submit",
                "text=Respond",
                "text=Apply",
                "text=Bid",
                "text=Upload Documents",
                "text=Upload",
                "button:has-text('Submit')",
                "button:has-text('Respond')",
                "button:has-text('Apply')",
                "button:has-text('Bid')",
                "a:has-text('Submit')",
                "a:has-text('Respond')",
                "a:has-text('Apply')",
                "a:has-text('Bid')",
            ],
            wait_ms=3000,
        )
    else:
        result["respond_click_result"] = {
            "status": "ok",
            "clicked": True,
            "selector": "detail_scan_action",
            "detail_scan": result["detail_scan"],
        }

    result["after_respond_screenshot"] = await _capture(page, buyer_rfq, "after_respond_click")
    result["submission_capability_after_respond"] = await _detect_submission_capability(page)

    return result


async def _try_click_upload_buttons(page: Any) -> Dict[str, Any]:
    return await _try_click_candidates(
        page,
        [
            "input[type='file']",
            "text=Upload",
            "text=Attach",
            "text=Add document",
            "text=Add Document",
            "text=Browse",
            "text=Choose File",
            "text=Select File",
            "text=Submit Documents",
            "button:has-text('Upload')",
            "button:has-text('Attach')",
            "button:has-text('Add')",
            "button:has-text('Browse')",
            "button:has-text('Choose File')",
            "input[type='button'][value*='Upload']",
        ],
        wait_ms=1500,
    )


async def _page_upload_signal(page: Any, files: List[str]) -> Dict[str, Any]:
    text = await _body_text(page)
    lower = text.lower()

    uploaded_markers = [
        "uploaded",
        "upload complete",
        "successfully uploaded",
        "attached",
        "document added",
        "file added",
        "remove file",
    ]

    file_name_hits = 0
    for f in files:
        name = Path(f).name.lower()
        if name and name in lower:
            file_name_hits += 1

    return {
        "status": "ok",
        "marker_hit": any(marker in lower for marker in uploaded_markers),
        "file_name_hits": file_name_hits,
        "captcha_detected": _captcha_detected_text(text),
        "body_excerpt": text[:1200],
    }


async def _safe_close(context: Any, browser: Any, using_cdp: bool) -> None:
    try:
        if using_cdp:
            if browser:
                await browser.close()
        else:
            if context:
                await context.close()
    except Exception:
        pass


async def attach_documents_to_live_browser(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(payload if isinstance(payload, dict) else {})
    payload = _merge_autofill_plan(payload)

    cdp_url = _safe_str(payload.get("cdp_url") or payload.get("browser_cdp_url"))
    using_cdp = bool(cdp_url)

    buyer_rfq = _buyer_rfq_number(payload)
    quote_number = _quote_number(payload)
    portal_url = _normalise_portal_url(payload)

    attachments = _normalise_attachments(payload)
    resolved_info = _resolve_attachments(attachments)
    files = resolved_info.get("resolved", [])

    result: Dict[str, Any] = {
        "status": "started",
        "service_version": "V47_3_LIVE_BROWSER_ATTACH_ENGINE_SESSION_PERSISTENCE",
        "buyer_rfq_number": buyer_rfq,
        "quote_number": quote_number,
        "portal_url": portal_url,
        "portal_domain": _safe_str(payload.get("portal_domain")),
        "attachments": attachments,
        "attachment_resolution": resolved_info,
        "started_at": _now(),
        "headless": False if using_cdp else HEADLESS,
        "profile_dir": "external_cdp_session" if using_cdp else str(PROFILE_DIR),
        "cdp_url": cdp_url,
        "using_cdp": using_cdp,
        "safety": {
            "captcha_bypass_allowed": False,
            "final_submit_allowed": False,
            "operator_must_review": True,
        },
    }

    if not files:
        result.update({
            "status": "assisted_required",
            "uploaded": False,
            "documents_uploaded": False,
            "reason": "No existing attachment files were provided. Browser cannot upload without files.",
            "finished_at": _now(),
        })
        _write_json(LAST_RESULT_FILE, result)
        _append_json(ASSISTED_FILE, result)
        _append_json(HISTORY_FILE, result)
        return result

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        result.update({
            "status": "assisted_required",
            "uploaded": False,
            "documents_uploaded": False,
            "reason": "Playwright is not installed or not available in the API container.",
            "error": str(exc),
            "finished_at": _now(),
        })
        _write_json(LAST_RESULT_FILE, result)
        _append_json(ASSISTED_FILE, result)
        _append_json(HISTORY_FILE, result)
        return result

    context = None
    browser = None

    try:
        async with async_playwright() as p:
            if using_cdp:
                browser = await p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
            else:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    headless=HEADLESS,
                    accept_downloads=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                )

            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(DEFAULT_TIMEOUT_MS)

            if using_cdp:
                session = {
                    "status": "ok",
                    "logged_in": True,
                    "mode": "cdp_existing_session",
                    "checked_at": _now(),
                }
            else:
                session = await _ensure_session(page, payload, buyer_rfq)

            result["session"] = session

            if (not using_cdp) and session.get("status") == "manual_login_required":
                result.update({
                    "status": "manual_login_required",
                    "uploaded": False,
                    "documents_uploaded": False,
                    "reason": "Login session is required before portal upload. Use credentials or run manual login with persistent profile.",
                    "finished_at": _now(),
                })
                await _safe_close(context, browser, using_cdp)
                _write_json(LAST_RESULT_FILE, result)
                _append_json(ASSISTED_FILE, result)
                _append_json(HISTORY_FILE, result)
                return result

            result["navigation"] = await _navigate_to_target(page, payload, buyer_rfq)

            capability_after_respond = result["navigation"].get("submission_capability_after_respond", {})
            result["submission_capability"] = capability_after_respond

            if capability_after_respond.get("capability") == "documents_only":
                result.update({
                    "status": "documents_only",
                    "uploaded": False,
                    "documents_uploaded": False,
                    "reason": "Tender exposes public tender documents but no upload/submission controls were detected.",
                    "finished_at": _now(),
                })
                await _safe_close(context, browser, using_cdp)
                _write_json(LAST_RESULT_FILE, result)
                _append_json(ASSISTED_FILE, result)
                _append_json(HISTORY_FILE, result)
                return result

            signal_before = await _page_upload_signal(page, files)
            result["page_signal_before_upload"] = signal_before

            if signal_before.get("captcha_detected"):
                result.update({
                    "status": "assisted_required",
                    "uploaded": False,
                    "documents_uploaded": False,
                    "captcha_detected": True,
                    "reason": "CAPTCHA/security challenge detected. Manual human action required.",
                    "captcha_screenshot": await _capture(page, buyer_rfq, "captcha_detected"),
                    "finished_at": _now(),
                })
                await _safe_close(context, browser, using_cdp)
                _write_json(LAST_RESULT_FILE, result)
                _append_json(ASSISTED_FILE, result)
                _append_json(HISTORY_FILE, result)
                return result

            result["upload_button_click_result"] = await _try_click_upload_buttons(page)

            await page.wait_for_timeout(2500)

            result["submission_capability_after_upload_click"] = await _detect_submission_capability(page)

            file_result = await _try_set_input_files(page, files)
            result["file_input_result"] = file_result

            await page.wait_for_timeout(2500)
            result["after_upload_screenshot"] = await _capture(page, buyer_rfq, "after_upload")

            signal_after = await _page_upload_signal(page, files)
            result["page_signal_after_upload"] = signal_after

            uploaded = bool(file_result.get("uploaded")) and not signal_after.get("captcha_detected")

            if uploaded:
                result.update({
                    "status": "ok",
                    "uploaded": True,
                    "documents_uploaded": True,
                    "attachments_uploaded": True,
                    "uploaded_files": files,
                    "uploaded_count": len(files),
                    "message": "Documents were attached to the authenticated portal page through Playwright.",
                    "finished_at": _now(),
                })
                await _safe_close(context, browser, using_cdp)
                _write_json(LAST_RESULT_FILE, result)
                _append_json(HISTORY_FILE, result)
                return result

            result.update({
                "status": "assisted_required",
                "uploaded": False,
                "documents_uploaded": False,
                "reason": file_result.get("message") or "Could not confirm file upload on portal page.",
                "finished_at": _now(),
            })

            await _safe_close(context, browser, using_cdp)
            _write_json(LAST_RESULT_FILE, result)
            _append_json(ASSISTED_FILE, result)
            _append_json(HISTORY_FILE, result)
            return result

    except Exception as exc:
        result.update({
            "status": "assisted_required",
            "uploaded": False,
            "documents_uploaded": False,
            "error": str(exc),
            "reason": "Live browser attach failed and requires assisted browser action.",
            "finished_at": _now(),
        })

        await _safe_close(context, browser, using_cdp)

        _write_json(LAST_RESULT_FILE, result)
        _append_json(ASSISTED_FILE, result)
        _append_json(HISTORY_FILE, result)
        return result


async def attach_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await attach_documents_to_live_browser(payload)


async def upload_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await attach_documents_to_live_browser(payload)


def get_live_browser_attach_status(limit: int = 50) -> Dict[str, Any]:
    history = _read_json(HISTORY_FILE, [])
    assisted = _read_json(ASSISTED_FILE, [])
    last = _read_json(LAST_RESULT_FILE, {})
    session = _read_json(SESSION_STATE_FILE, {})

    if not isinstance(history, list):
        history = []

    if not isinstance(assisted, list):
        assisted = []

    uploaded_total = len([x for x in history if isinstance(x, dict) and x.get("uploaded") is True])

    return {
        "status": "ok",
        "service_version": "V47_3_LIVE_BROWSER_ATTACH_ENGINE_SESSION_PERSISTENCE",
        "summary": {
            "history_total": len(history),
            "uploaded_total": uploaded_total,
            "assisted_required_total": len(assisted),
            "screenshot_dir": str(SCREENSHOT_DIR),
            "headless": HEADLESS,
            "profile_dir": str(PROFILE_DIR),
        },
        "session_state": session,
        "last_result": last,
        "recent_history": history[-limit:],
        "recent_assisted": assisted[-limit:],
        "files": {
            "history": str(HISTORY_FILE),
            "assisted": str(ASSISTED_FILE),
            "last_result": str(LAST_RESULT_FILE),
            "session_state": str(SESSION_STATE_FILE),
            "screenshots": str(SCREENSHOT_DIR),
            "profile_dir": str(PROFILE_DIR),
        },
        "updated_at": _now(),
    }


def attach_to_live_browser_and_assist(
    autofill_plan_json=None,
    cdp_url="http://127.0.0.1:9222",
    output_dir=None,
    fill_visible_fields=True,
    capture_screenshots=True,
    stop_before_submit=True,
    payload=None,
):
    if payload is None:
        payload = {}

    payload.update({
        "autofill_plan_json": autofill_plan_json,
        "cdp_url": cdp_url,
        "output_dir": output_dir,
        "fill_visible_fields": fill_visible_fields,
        "capture_screenshots": capture_screenshots,
        "stop_before_submit": stop_before_submit,
    })

    return attach_documents_to_live_browser(payload)


def get_v47_3_status():
    try:
        return get_live_browser_attach_status()
    except Exception as exc:
        return {
            "status": "error",
            "service_version": "V47_3_LIVE_BROWSER_ATTACH",
            "message": "Could not load live browser attach status.",
            "error": str(exc),
        }
