from __future__ import annotations

import json
import os
import re
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.quote_compilation_service import _manual_completion_gate, _safe_quote_pack_dir

RUNTIME_DIR = Path("runtime")
FINAL_DIR = RUNTIME_DIR / "final_submission_v47_5"
PROFILE_DIR = RUNTIME_DIR / "playwright_profiles" / "etenders"
STATE_FILE = RUNTIME_DIR / "playwright_profiles" / "etenders_state.json"
SCREENSHOT_DIR = FINAL_DIR / "screenshots"
PROOF_DIR = FINAL_DIR / "proofs"
DEBUG_DIR = FINAL_DIR / "debug"

FINAL_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
PROOF_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = FINAL_DIR / "final_submission_history.json"
ASSISTED_FILE = FINAL_DIR / "assisted_final_submit_required.json"
LAST_RESULT_FILE = FINAL_DIR / "last_final_submit.json"

DEFAULT_TIMEOUT_MS = int(os.getenv("LMCP_PORTAL_BROWSER_TIMEOUT_MS", "45000"))
HEADLESS = os.getenv("LMCP_PORTAL_BROWSER_HEADLESS", "true").lower() in {"1", "true", "yes", "on"}
CHROME = os.getenv("LMCP_CHROME_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _slug(value: Any, fallback: str = "final-submit") -> str:
    text = _safe_str(value, fallback)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return text[:120] or fallback


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


def _buyer_rfq_number(payload: Dict[str, Any]) -> str:
    return _safe_str(
        payload.get("_locked_buyer_rfq_number")
        or payload.get("buyer_rfq_number")
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
    url = _safe_str(payload.get("portal_url") or payload.get("submission_url") or payload.get("url"))
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    return url


def _normalise_attachments(payload: Dict[str, Any]) -> List[str]:
    values: List[Any] = []

    for key in ["attachments", "submission_attachments", "supporting_documents", "documents", "resolved_attachments"]:
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif raw:
            values.append(raw)

    submission_pack = payload.get("submission_pack")
    if isinstance(submission_pack, dict):
        for key in ["attachments", "submission_attachments", "supporting_documents"]:
            raw = submission_pack.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif raw:
                values.append(raw)

    for key in ["pdf_path", "quote_pdf_path", "final_pdf_path"]:
        if payload.get(key):
            values.append(payload.get(key))

    output: List[str] = []
    seen = set()
    for item in values:
        text = _safe_str(item)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
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
    checked: List[Dict[str, Any]] = []
    resolved: List[str] = []
    missing: List[str] = []

    for attachment in attachments:
        rp = _resolve_path(attachment)
        checked.append({"path": attachment, "exists": bool(rp), "resolved_path": rp})
        if rp:
            resolved.append(rp)
        else:
            missing.append(attachment)

    return {
        "status": "ok" if not missing else "missing_files",
        "count": len(attachments),
        "resolved": resolved,
        "missing": missing,
        "checked": checked,
    }


def _resolve_state_file() -> Optional[str]:
    candidates = [
        STATE_FILE,
        Path("/app/runtime/playwright_profiles/etenders_state.json"),
        Path.cwd() / "runtime/playwright_profiles/etenders_state.json",
        Path("/Users/Shared/LMCP-AutoQuote-Server/runtime/playwright_profiles/etenders_state.json"),
    ]
    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return str(p.resolve())
        except Exception:
            continue
    return None


def _resolve_cdp_endpoint(cdp_url: Optional[str]) -> Dict[str, Any]:
    base = _safe_str(cdp_url or "http://host.docker.internal:9222").rstrip("/")
    if not base:
        return {"ok": False, "input_cdp_url": cdp_url, "resolved_websocket_url": "", "error": "empty_cdp_url"}

    if base.startswith("ws://") or base.startswith("wss://"):
        return {
            "ok": True,
            "input_cdp_url": base,
            "version_url": "",
            "raw_websocket_url": base,
            "resolved_websocket_url": base,
            "mode": "direct_websocket",
            "error": "",
        }

    version_url = f"{base}/json/version"
    result = {
        "ok": False,
        "input_cdp_url": base,
        "version_url": version_url,
        "raw_websocket_url": "",
        "resolved_websocket_url": "",
        "mode": "json_version",
        "error": "",
    }
    try:
        req = urllib.request.Request(version_url, headers={"Host": "localhost:9222"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        raw_ws = data.get("webSocketDebuggerUrl") or ""
        resolved_ws = raw_ws
        if base.startswith("http://host.docker.internal"):
            resolved_ws = resolved_ws.replace("ws://localhost:9222", "ws://host.docker.internal:9222")
            resolved_ws = resolved_ws.replace("ws://127.0.0.1:9222", "ws://host.docker.internal:9222")
        elif base.startswith("http://gateway.docker.internal"):
            resolved_ws = resolved_ws.replace("ws://localhost:9222", "ws://gateway.docker.internal:9222")
            resolved_ws = resolved_ws.replace("ws://127.0.0.1:9222", "ws://gateway.docker.internal:9222")
        result.update({
            "ok": bool(resolved_ws),
            "raw_websocket_url": raw_ws,
            "resolved_websocket_url": resolved_ws,
            "browser": data.get("Browser"),
        })
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _policy_allows_final_submit(payload: Dict[str, Any]) -> Dict[str, Any]:
    policy = payload.get("policy")
    route = payload.get("route")
    if isinstance(route, dict) and isinstance(route.get("policy"), dict):
        policy = route.get("policy")

    if not isinstance(policy, dict):
        policy_path = RUNTIME_DIR / "full_autonomous_v48" / "policy.json"
        policy = _read_json(policy_path, {})

    if isinstance(policy, dict) and isinstance(policy.get("policy"), dict):
        policy = policy["policy"]

    explicit_allow = payload.get("allow_final_submit")
    allow_final = bool(policy.get("allow_portal_final_submit", False)) if isinstance(policy, dict) else False
    if explicit_allow is not None:
        allow_final = bool(explicit_allow)
    require_phrase = bool(policy.get("require_confirmation_phrase", False)) if isinstance(policy, dict) else False

    return {
        "allowed": allow_final and not require_phrase,
        "allow_portal_final_submit": allow_final,
        "require_confirmation_phrase": require_phrase,
        "policy": policy if isinstance(policy, dict) else {},
    }


def _resolve_quote_compilation_pack_id(payload: Dict[str, Any]) -> Optional[str]:
    candidate_keys = (
        "pack_id",
        "quote_compilation_pack_id",
        "submission_pack_id",
        "submission_binder_pack_id",
    )
    for key in candidate_keys:
        value = payload.get(key)
        if value not in (None, ""):
            return _safe_str(value)

    for nested_key in ("submission_pack", "submission_binder", "quote_compilation"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            for key in candidate_keys:
                value = nested.get(key)
                if value not in (None, ""):
                    return _safe_str(value)

    autofill_plan_json = payload.get("autofill_plan_json")
    if autofill_plan_json:
        try:
            plan_path = Path(str(autofill_plan_json))
            if plan_path.exists():
                plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                if isinstance(plan_data, dict):
                    for key in candidate_keys:
                        value = plan_data.get(key)
                        if value not in (None, ""):
                            return _safe_str(value)
                    for nested_key in ("submission_pack", "submission_binder", "quote_compilation"):
                        nested = plan_data.get(nested_key)
                        if isinstance(nested, dict):
                            for key in candidate_keys:
                                value = nested.get(key)
                                if value not in (None, ""):
                                    return _safe_str(value)
                    form_values = plan_data.get("form_values")
                    if isinstance(form_values, dict):
                        for key in candidate_keys:
                            value = form_values.get(key)
                            if value not in (None, ""):
                                return _safe_str(value)
        except Exception:
            pass

    return None


def _manual_completion_final_gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    pack_id = _resolve_quote_compilation_pack_id(payload)
    if not pack_id:
        return {
            "required": True,
            "allowed": False,
            "blocked_reason": "Unable to resolve a quote compilation pack_id for manual completion verification.",
            "reason_code": "manual_completion_pack_id_missing",
            "status": "missing",
            "pack_id": None,
            "manual_completion": None,
        }

    workspace = _safe_quote_pack_dir(pack_id)
    if not workspace:
        return {
            "required": True,
            "allowed": False,
            "blocked_reason": "Manual completion record is required before final submission.",
            "reason_code": "manual_completion_missing",
            "status": "missing",
            "pack_id": pack_id,
            "manual_completion": None,
        }

    return _manual_completion_gate(workspace)


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
            "captcha verification",
        ]
    )


async def _body_text(page: Any) -> str:
    try:
        return await page.locator("body").inner_text(timeout=10000)
    except Exception:
        return ""


async def _capture(page: Any, buyer_rfq: str, label: str) -> Optional[str]:
    try:
        path = SCREENSHOT_DIR / f"{_slug(buyer_rfq)}__{label}__{_stamp()}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None


async def _click_first(page: Any, selectors: List[str], wait_ms: int = 1500) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []

    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            if count <= 0:
                attempts.append({"selector": selector, "status": "not_found"})
                continue

            await loc.first.click(timeout=10000)
            await page.wait_for_timeout(wait_ms)
            attempts.append({"selector": selector, "status": "clicked"})
            return {"status": "ok", "clicked": True, "selector": selector, "attempts": attempts}
        except Exception as exc:
            attempts.append({"selector": selector, "status": "failed", "error": str(exc)})

    return {"status": "not_clicked", "clicked": False, "attempts": attempts}


async def _force_click_by_text(page: Any, text: str, wait_ms: int = 3000) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []

    try:
        await page.locator(f"text={text}").first.click(force=True, timeout=10000)
        await page.wait_for_timeout(wait_ms)
        return {"status": "ok", "clicked": True, "method": "locator_force_text", "text": text, "attempts": attempts}
    except Exception as exc:
        attempts.append({"method": "locator_force_text", "text": text, "status": "failed", "error": str(exc)})

    try:
        clicked = await page.evaluate(
            """(targetText) => {
                const items = Array.from(document.querySelectorAll('*'));
                const el = items.find((node) => {
                    const text = (node.innerText || node.textContent || '').trim();
                    return text && text.toLowerCase().includes(targetText.toLowerCase());
                });
                if (el) {
                    el.scrollIntoView({block: 'center', inline: 'center'});
                    el.click();
                    return true;
                }
                return false;
            }""",
            text,
        )
        await page.wait_for_timeout(wait_ms)
        if clicked:
            return {"status": "ok", "clicked": True, "method": "dom_inner_text_click", "text": text, "attempts": attempts}
        attempts.append({"method": "dom_inner_text_click", "text": text, "status": "not_found"})
    except Exception as exc:
        attempts.append({"method": "dom_inner_text_click", "text": text, "status": "failed", "error": str(exc)})

    return {"status": "not_clicked", "clicked": False, "text": text, "attempts": attempts}


async def _is_logged_in(page: Any) -> Dict[str, Any]:
    text = await _body_text(page)
    lower = text.lower()
    current_url = _safe_str(getattr(page, "url", ""))
    on_etenders = "etenders.gov.za" in current_url.lower()

    on_submission_page = "responding to" in lower and ("start response" in lower or "submit now" in lower)
    has_supplier_page = "please provide the maaa number" in lower or "select supplier" in lower
    captcha = _captcha_detected_text(text)

    login_button_count = 0
    login_button_probe: List[Dict[str, Any]] = []
    for selector in [
        "button:has-text('Login'):visible",
        "a:has-text('Login'):visible",
        "input[value*='Login']:visible",
        "button:has-text('Log in'):visible",
        "a:has-text('Log in'):visible",
    ]:
        try:
            count = await page.locator(selector).count()
            login_button_count += count
            login_button_probe.append({"selector": selector, "count": count})
        except Exception as exc:
            login_button_probe.append({"selector": selector, "error": str(exc)})

    indicators: List[str] = []
    if "logout" in lower:
        indicators.append("text_logout")
    if re.search(r"\bmanage\b", lower):
        indicators.append("text_manage")
    if "/home?mytab=1" in current_url.lower():
        indicators.append("url_home_mytab_1")
    if login_button_count == 0:
        indicators.append("absence_login_button")
    if on_submission_page:
        indicators.append("submission_page")
    if has_supplier_page:
        indicators.append("supplier_selection_page")
    for marker in ["my profile", "my tenders", "dashboard", "submit now"]:
        if marker in lower:
            indicators.append(f"text_{marker.replace(' ', '_')}")

    logged_in = bool(indicators) and on_etenders

    return {
        "logged_in": bool(logged_in and not captcha),
        "logged_out_likely": bool(captcha or (login_button_count > 0 and "username" in lower and "password" in lower)),
        "captcha_detected": captcha,
        "current_url": current_url,
        "on_etenders": on_etenders,
        "login_button_count": login_button_count,
        "login_button_probe": login_button_probe,
        "authenticated_indicators_found": indicators,
        "body_excerpt": text[:1200],
    }


async def _active_opportunities_tab_name(page: Any) -> str:
    try:
        value = await page.evaluate(
            """() => {
                const active = Array.from(document.querySelectorAll('li.active, .active, a[aria-selected="true"], button[aria-selected="true"]'))
                    .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
                    .find(text => /currently advertised|closed|awarded|cancelled/i.test(text));
                if (active) return active;
                const body = (document.body.innerText || document.body.textContent || '').toLowerCase();
                if (body.includes('currently advertised')) return 'Currently Advertised';
                if (body.includes('closed tenders')) return 'Closed';
                if (body.includes('awarded tenders')) return 'Awarded';
                if (body.includes('cancelled tenders')) return 'Cancelled';
                return '';
            }"""
        )
        return _safe_str(value)
    except Exception:
        return ""


async def _force_currently_advertised_tab(page: Any) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    active_tab = await _active_opportunities_tab_name(page)
    if "currently advertised" in active_tab.lower():
        actions.append({"step": "currently_advertised_already_active", "active_tab_name": active_tab})
        return actions

    selectors = [
        "a:has-text('Currently Advertised')",
        "button:has-text('Currently Advertised')",
        "li:has-text('Currently Advertised') a",
        "text=Currently Advertised",
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"step": "currently_advertised_selector_checked", "selector": selector, "count": count})
            if count > 0:
                await loc.first.click(timeout=3500, force=True)
                await page.wait_for_timeout(1500)
                actions.append({"step": "currently_advertised_clicked", "selector": selector})
                break
        except Exception as exc:
            actions.append({"step": "currently_advertised_click_failed", "selector": selector, "error": str(exc)})

    try:
        clicked = await page.evaluate(
            """() => {
                const forbidden = ['closed', 'awarded', 'cancelled'];
                for (const el of Array.from(document.querySelectorAll('a,button,li,span,div'))) {
                    const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    if (forbidden.some(term => text === term || text.includes(term + ' tenders'))) {
                        el.setAttribute('data-lmcp-tab-blocked', 'true');
                    }
                }
                const nodes = Array.from(document.querySelectorAll('a,button,li,span,div'));
                const current = nodes.find((node) => {
                    const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    return text === 'currently advertised' || text.includes('currently advertised');
                });
                if (!current) return false;
                const clickable = current.closest('a,button') || current;
                clickable.scrollIntoView({block: 'center', inline: 'center'});
                clickable.click();
                return true;
            }"""
        )
        await page.wait_for_timeout(1500)
        actions.append({"step": "currently_advertised_dom_click", "clicked": bool(clicked)})
    except Exception as exc:
        actions.append({"step": "currently_advertised_dom_click_failed", "error": str(exc)})

    actions.append({"step": "active_tab_probe", "active_tab_name": await _active_opportunities_tab_name(page)})
    return actions


async def _response_workspace_state(page: Any) -> Dict[str, Any]:
    try:
        state = await page.evaluate(
            """() => {
                const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const categories = document.querySelector('#categorieslist');
                const text = (document.body.innerText || document.body.textContent || '').replace(/\\s+/g, ' ').trim();
                const lower = text.toLowerCase();
                const controls = Array.from(document.querySelectorAll('button,a,input,select,textarea,[role="button"]'))
                    .map(el => (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '').replace(/\\s+/g, ' ').trim())
                    .filter(Boolean)
                    .slice(0, 120);
                const serial = controls.join(' ').toLowerCase();
                const categoriesVisible = visible(categories);
                const onResponseUrl = /\\/ESubmission\\/Esubmission/i.test(location.href);
                const listingLikely = /currently advertised tenders|quickfind|advanced search/.test(lower);
                const responseSessionStarted = categoriesVisible || /responding to|select supplier|submit now|save response|tender response|esubmission/.test(lower + ' ' + serial);
                const responseWorkspaceLoaded = (onResponseUrl || categoriesVisible || !listingLikely) &&
                    responseSessionStarted &&
                    /select supplier|upload|add document|browse|submit now|documents|attachments|submission checklist/.test(lower + ' ' + serial);
                return {
                    active_tab_name: '',
                    categorieslist_present: !!categories,
                    categorieslist_visible: categoriesVisible,
                    response_session_started: responseSessionStarted,
                    response_workspace_loaded: responseWorkspaceLoaded,
                    body_excerpt: text.slice(0, 1200),
                    visible_controls: controls
                };
            }"""
        )
        state = state if isinstance(state, dict) else {}
    except Exception as exc:
        state = {"error": str(exc)}
    state["active_tab_name"] = await _active_opportunities_tab_name(page)
    return state


async def _workspace_persistence_probe(page: Any, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    matched_row = payload.get("matched_row") if isinstance(payload.get("matched_row"), dict) else {}
    expected_text = _safe_str(
        matched_row.get("text_preview")
        or payload.get("buyer_rfq_number")
        or payload.get("_locked_buyer_rfq_number")
    )
    try:
        probe = await page.evaluate(
            """(expectedText) => {
                const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                const norm = (value) => clean(value).toUpperCase().replace(/[\\/-]+/g, ' ').replace(/[^A-Z0-9]+/g, ' ').replace(/\\s+/g, ' ').trim();
                const bodyText = clean(document.body.innerText || document.body.textContent || '');
                const lower = bodyText.toLowerCase();
                const expected = clean(expectedText).toLowerCase();
                const bodyNorm = norm(bodyText);
                const expectedNorm = norm(expectedText);
                const expectedTokens = Array.from(new Set(expectedNorm.split(' ').filter(token => token.length >= 4)));
                const bodyTokens = new Set(bodyNorm.split(' ').filter(token => token.length >= 4));
                const tokenHits = expectedTokens.filter(token => bodyTokens.has(token));
                const expectedTextHit = !!expectedNorm && (
                    bodyNorm.includes(expectedNorm.slice(0, Math.min(expectedNorm.length, 160))) ||
                    tokenHits.length / Math.max(expectedTokens.length, 1) >= 0.65
                );
                const startControls = Array.from(document.querySelectorAll('button,a,input,div,span,[role="button"],[onclick],#esub-start-response'))
                    .map((el, index) => {
                        const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                        const id = el.id || '';
                        const cls = typeof el.className === 'string' ? el.className : '';
                        const onclick = el.getAttribute('onclick') || '';
                        const signature = `${text} ${id} ${cls} ${onclick}`.toLowerCase();
                        return {
                            index,
                            tag: el.tagName,
                            id,
                            cls,
                            text: text.slice(0, 220),
                            onclick: onclick.slice(0, 260),
                            visible: visible(el),
                            disabled: !!el.disabled || el.getAttribute('disabled') !== null,
                            hidden: el.hidden || getComputedStyle(el).display === 'none' || getComputedStyle(el).visibility === 'hidden',
                            start_like: signature.includes('start response') || signature.includes('start-response') || (signature.includes('start') && signature.includes('response'))
                        };
                    })
                    .filter(item => item.start_like)
                    .slice(0, 40);
                const iframes = Array.from(document.querySelectorAll('iframe')).map((el, index) => ({
                    index,
                    id: el.id || '',
                    name: el.name || '',
                    src: el.src || el.getAttribute('src') || '',
                    visible: visible(el)
                })).slice(0, 20);
                const modals = Array.from(document.querySelectorAll('.modal,[role="dialog"],.swal2-container,.bootbox,.modal-backdrop'))
                    .map((el, index) => ({
                        index,
                        id: el.id || '',
                        cls: typeof el.className === 'string' ? el.className : '',
                        text: clean(el.innerText || el.textContent || '').slice(0, 500),
                        visible: visible(el)
                    }))
                    .filter(item => item.visible || item.text)
                    .slice(0, 30);
                const expandedRows = Array.from(document.querySelectorAll('tr.shown, tr.child, .collapse.show, .in, [aria-expanded="true"]')).length;
                const categories = document.querySelector('#categorieslist');
                const responseLike = /responding to|select supplier|submit now|save response|tender response|esubmission/.test(lower);
                const uploadLike = /upload|add document|browse|choose file|attach|submit now|submission checklist/.test(lower);
                const onResponseUrl = /\\/ESubmission\\/Esubmission/i.test(location.href);
                const listingLikely = /currently advertised tenders|quickfind|advanced search/.test(lower);
                return {
                    url: location.href,
                    title: document.title || '',
                    expected_text_hit: expectedTextHit,
                    expected_token_overlap: tokenHits.length / Math.max(expectedTokens.length, 1),
                    body_excerpt: bodyText.slice(0, 1500),
                    expanded_row_markers: expandedRows,
                    expanded_workspace_likely: expandedRows > 0 || /tender detail|tender description|download documents|supporting documents|start response/.test(lower),
                    listing_likely: listingLikely,
                    start_response_controls: startControls,
                    start_response_visible: startControls.some(item => item.visible),
                    start_response_hidden: startControls.some(item => !item.visible || item.hidden),
                    iframe_count: iframes.length,
                    iframes,
                    modal_count: modals.length,
                    modals,
                    categorieslist_present: !!categories,
                    categorieslist_visible: visible(categories),
                    response_workspace_loaded: (onResponseUrl || visible(categories) || !listingLikely) && responseLike && uploadLike
                };
            }""",
            expected_text,
        )
        probe = probe if isinstance(probe, dict) else {}
    except Exception as exc:
        probe = {"error": str(exc)}
    probe["active_tab_name"] = await _active_opportunities_tab_name(page)
    return probe


async def _install_start_response_mutation_observer(page: Any) -> Dict[str, Any]:
    try:
        installed = await page.evaluate(
            """() => {
                try {
                    if (window.__lmcpStartResponseObserver && window.__lmcpStartResponseObserver.disconnect) {
                        window.__lmcpStartResponseObserver.disconnect();
                    }
                    window.__lmcpStartResponseTransition = {
                        installedAt: Date.now(),
                        initialUrl: location.href,
                        initialTitle: document.title || '',
                        mutationCount: 0,
                        addedNodeCount: 0,
                        removedNodeCount: 0,
                        bodyReplacementCount: 0,
                        workspaceContainerInjected: false,
                        modalInjected: false,
                        iframeInjected: false,
                        lastMutationAt: null,
                        observedUrl: location.href,
                        observedTitle: document.title || ''
                    };
                    const workspacePattern = /responding to|select supplier|submit now|submission checklist|upload|add document|tender response|esubmission/i;
                    const observer = new MutationObserver((records) => {
                        const state = window.__lmcpStartResponseTransition;
                        state.mutationCount += records.length;
                        state.lastMutationAt = Date.now();
                        state.observedUrl = location.href;
                        state.observedTitle = document.title || '';
                        for (const record of records) {
                            state.addedNodeCount += record.addedNodes ? record.addedNodes.length : 0;
                            state.removedNodeCount += record.removedNodes ? record.removedNodes.length : 0;
                            if (record.target && record.target === document.body && record.removedNodes && record.removedNodes.length) {
                                state.bodyReplacementCount += 1;
                            }
                            for (const node of Array.from(record.addedNodes || [])) {
                                if (!node || node.nodeType !== 1) continue;
                                const text = (node.innerText || node.textContent || '').slice(0, 2000);
                                const id = node.id || '';
                                const cls = typeof node.className === 'string' ? node.className : '';
                                const signature = `${node.tagName || ''} ${id} ${cls} ${text}`;
                                if (/iframe/i.test(node.tagName || '') || node.querySelector?.('iframe')) state.iframeInjected = true;
                                if (/modal|dialog|swal|bootbox/i.test(signature) || node.matches?.('.modal,[role="dialog"],.swal2-container,.bootbox')) state.modalInjected = true;
                                if (workspacePattern.test(signature) || node.querySelector?.('#categorieslist,#esub-submit,input[type="file"]')) {
                                    state.workspaceContainerInjected = true;
                                }
                            }
                        }
                    });
                    observer.observe(document.documentElement || document.body, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        attributeFilter: ['class', 'style', 'hidden', 'aria-expanded']
                    });
                    window.__lmcpStartResponseObserver = observer;
                    return true;
                } catch (e) {
                    return false;
                }
            }"""
        )
        return {"installed": bool(installed)}
    except Exception as exc:
        return {"installed": False, "error": str(exc)}


async def _read_start_response_transition(page: Any) -> Dict[str, Any]:
    try:
        state = await page.evaluate(
            """() => {
                const current = window.__lmcpStartResponseTransition || {};
                current.currentUrl = location.href;
                current.currentTitle = document.title || '';
                current.urlChanged = !!current.initialUrl && current.initialUrl !== location.href;
                current.titleChanged = !!current.initialTitle && current.initialTitle !== (document.title || '');
                return current;
            }"""
        )
        return state if isinstance(state, dict) else {}
    except Exception as exc:
        return {"error": str(exc)}


async def _workspace_transition_snapshot(page: Any, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    probe = await _workspace_persistence_probe(page, payload)
    active_iframe_url = ""
    frame_summaries: List[Dict[str, Any]] = []
    for index, frame in enumerate(getattr(page, "frames", []) or []):
        try:
            frame_state = await frame.evaluate(
                """() => {
                    const text = (document.body?.innerText || document.body?.textContent || '').replace(/\\s+/g, ' ').trim();
                    const lower = text.toLowerCase();
                    const responseLike = /responding to|select supplier|submit now|save response|tender response|esubmission/.test(lower);
                    const uploadLike = /upload|add document|browse|choose file|attach|submit now|submission checklist/.test(lower);
                    const listingLikely = /currently advertised tenders|quickfind|advanced search/.test(lower);
                    const onResponseUrl = /\\/ESubmission\\/Esubmission/i.test(location.href);
                    return {
                        title: document.title || '',
                        body_excerpt: text.slice(0, 900),
                        response_workspace_loaded: (onResponseUrl || !listingLikely) && responseLike && uploadLike
                    };
                }"""
            )
            frame_url = _safe_str(getattr(frame, "url", ""))
            item = {
                "index": index,
                "url": frame_url,
                "title": (frame_state or {}).get("title", ""),
                "response_workspace_loaded": bool((frame_state or {}).get("response_workspace_loaded")),
                "body_excerpt": (frame_state or {}).get("body_excerpt", ""),
            }
            frame_summaries.append(item)
            if item["response_workspace_loaded"] and not active_iframe_url:
                active_iframe_url = frame_url
        except Exception as exc:
            frame_summaries.append({"index": index, "url": _safe_str(getattr(frame, "url", "")), "error": str(exc)})

    mutation_state = await _read_start_response_transition(page)
    page_url = _safe_str(probe.get("url") or getattr(page, "url", ""))
    page_title = _safe_str(probe.get("title"))
    workspace_loaded = bool(probe.get("response_workspace_loaded") or any(item.get("response_workspace_loaded") for item in frame_summaries))
    transition_url = page_url
    transition_title = page_title
    if active_iframe_url:
        transition_url = active_iframe_url
        active_frame = next((item for item in frame_summaries if item.get("url") == active_iframe_url), {})
        transition_title = _safe_str(active_frame.get("title"), page_title)

    dom_replacement = bool(
        (mutation_state.get("bodyReplacementCount") or 0) > 0
        or (mutation_state.get("removedNodeCount") or 0) > 20
        or mutation_state.get("workspaceContainerInjected")
        or mutation_state.get("modalInjected")
        or mutation_state.get("iframeInjected")
    )
    return {
        "probe": probe,
        "mutation_state": mutation_state,
        "frame_summaries": frame_summaries,
        "response_workspace_url": transition_url,
        "response_workspace_title": transition_title,
        "active_iframe_url": active_iframe_url,
        "dom_replacement_detected": dom_replacement,
        "workspace_transition_success": workspace_loaded,
    }


async def _select_persistent_workspace_page(context: Any, payload: Dict[str, Any], portal_url: str) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    pages = list(getattr(context, "pages", []) or [])
    matched_row = payload.get("matched_row") if isinstance(payload.get("matched_row"), dict) else {}
    expected_text = _safe_str(
        matched_row.get("text_preview")
        or payload.get("buyer_rfq_number")
        or payload.get("_locked_buyer_rfq_number")
    )
    has_expected_target = bool(expected_text)

    for index, candidate in enumerate(pages):
        try:
            probe = await _workspace_persistence_probe(candidate, payload)
            score = 0
            url = _safe_lower(probe.get("url") or getattr(candidate, "url", ""))
            expected_hit = bool(probe.get("expected_text_hit"))
            on_etenders = "etenders.gov.za" in url
            if on_etenders:
                score += 3
            else:
                score -= 50
            if probe.get("expanded_workspace_likely"):
                score += 6
            if probe.get("start_response_visible") or probe.get("start_response_hidden"):
                score += 5
            if expected_hit:
                score += 4
            if probe.get("response_workspace_loaded"):
                score += 8
            if probe.get("listing_likely"):
                score += 1
            if has_expected_target and not expected_hit:
                # Never prefer an unrelated live response workspace from a previous run.
                # It is safer to recover the current row from the opportunities listing.
                score -= 20
            candidates.append({"index": index, "score": score, "url": url, "on_etenders": on_etenders, "probe": probe, "page": candidate})
        except Exception as exc:
            candidates.append({"index": index, "score": -1, "error": str(exc), "page": candidate})

    candidates.sort(key=lambda item: item.get("score", -1), reverse=True)
    best = candidates[0] if candidates else None
    if best and best.get("score", -1) > 0:
        return {
            "page": best["page"],
            "reused_existing_page": True,
            "diagnostics": [{k: v for k, v in item.items() if k != "page"} for item in candidates],
        }

    page = await context.new_page()
    await page.goto(portal_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    return {
        "page": page,
        "reused_existing_page": False,
        "diagnostics": [{k: v for k, v in item.items() if k != "page"} for item in candidates],
    }


async def _select_supplier_if_present(page: Any, steps: List[Dict[str, Any]]) -> bool:
    try:
        selects = page.locator("select")
        count = await selects.count()
        if count <= 0:
            steps.append({"step": "select_company", "status": "skipped", "reason": "No select element found."})
            return False

        for i in range(count):
            try:
                await selects.nth(i).select_option(label=re.compile("LECHESA MANABA", re.I))
                steps.append({"step": "select_company_by_label", "status": "ok", "select_index": i})
                await page.wait_for_timeout(1000)
                return True
            except Exception as exc:
                steps.append({"step": "select_company_by_label", "select_index": i, "status": "failed", "error": str(exc)})

        try:
            await selects.first.select_option(index=1)
            steps.append({"step": "select_company_by_index", "status": "ok", "select_index": 0, "option_index": 1})
            await page.wait_for_timeout(1000)
            return True
        except Exception as exc:
            steps.append({"step": "select_company_by_index", "status": "failed", "error": str(exc)})
    except Exception as exc:
        steps.append({"step": "select_company", "status": "failed", "error": str(exc)})
    return False


async def _recover_expanded_row_if_collapsed(page: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    matched_row = payload.get("matched_row") if isinstance(payload.get("matched_row"), dict) else {}
    target_text = _safe_str(
        matched_row.get("text_preview")
        or payload.get("buyer_rfq_number")
        or payload.get("_locked_buyer_rfq_number")
    )
    if not target_text:
        return {"status": "skipped", "reason": "no_target_text"}

    try:
        recovered = await page.evaluate(
            """(targetText) => {
                const norm = (value) => String(value || '')
                    .toUpperCase()
                    .replace(/[\\/-]+/g, ' ')
                    .replace(/[^A-Z0-9]+/g, ' ')
                    .replace(/\\s+/g, ' ')
                    .trim();
                const target = norm(targetText);
                const targetTokens = new Set(target.split(' ').filter(token => token.length >= 3));
                const rows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'));
                let best = null;
                rows.forEach((row, index) => {
                    const text = (row.innerText || row.textContent || '').replace(/\\s+/g, ' ').trim();
                    const rowNorm = norm(text);
                    if (!rowNorm || text.length < 20) return;
                    const rect = row.getBoundingClientRect();
                    const visible = !!(rect.width > 0 && rect.height > 0);
                    if (!visible) return;
                    const rowTokens = new Set(rowNorm.split(' ').filter(token => token.length >= 3));
                    const overlap = Array.from(targetTokens).filter(token => rowTokens.has(token)).length;
                    const score = Math.max(
                        target && rowNorm.includes(target.slice(0, Math.min(target.length, 120))) ? 1 : 0,
                        overlap / Math.max(targetTokens.size, 1)
                    );
                    if (!best || score > best.score) {
                        best = {index, score, textPreview: text.slice(0, 700)};
                    }
                });
                if (!best || best.score < 0.65) return {recovered: false, reason: 'no_matching_row', best};
                const row = rows[best.index];
                row.scrollIntoView({block: 'center', inline: 'center'});
                row.click();
                const expanders = ['td.details-control', 'td.dtr-control', 'td:first-child', 'button[aria-expanded]', 'a[aria-expanded]', 'button', 'a'];
                let expanderSelector = '';
                for (const selector of expanders) {
                    const ctl = row.querySelector(selector);
                    if (!ctl) continue;
                    try {
                        for (const type of ['mouseover', 'mousedown', 'mouseup', 'click']) {
                            ctl.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                        }
                        expanderSelector = selector;
                        break;
                    } catch (e) {}
                }
                return {recovered: true, best, expanderSelector};
            }""",
            target_text,
        )
        await page.wait_for_timeout(2500)
        return recovered if isinstance(recovered, dict) else {"status": "unknown", "result": recovered}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


async def _click_start_response_once(page: Any) -> Dict[str, Any]:
    direct = await _click_first(
        page,
        [
            "#esub-start-response",
            "button#esub-start-response",
            "button:has-text('Start response')",
            "a:has-text('Start response')",
            "[onclick*='Start'][onclick*='Response']",
            "text=Start response",
        ],
        wait_ms=2500,
    )
    if direct.get("clicked"):
        return {"clicked": True, "method": "selector", "result": direct}

    forced = await _force_click_by_text(page, "Start response", wait_ms=2500)
    if forced.get("clicked"):
        return {"clicked": True, "method": "text_force", "result": forced}

    try:
        clicked = await page.evaluate(
            """() => {
                const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const candidates = Array.from(document.querySelectorAll('button, a, input, div, span, [role="button"], [onclick]'));
                const start = candidates.find((el) => {
                    const text = (el.innerText || el.textContent || el.value || el.alt || el.title || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    const id = (el.id || '').toLowerCase();
                    const cls = (typeof el.className === 'string' ? el.className : '').toLowerCase();
                    const onclick = (el.getAttribute('onclick') || '').toLowerCase();
                    return visible(el) && (
                        text.includes('start response') ||
                        id.includes('start-response') ||
                        cls.includes('start-response') ||
                        onclick.includes('start') && onclick.includes('response')
                    );
                });
                if (!start) return false;
                start.removeAttribute('disabled');
                start.classList.remove('disabled');
                start.scrollIntoView({block: 'center', inline: 'center'});
                for (const type of ['mouseover', 'mousedown', 'mouseup', 'click']) {
                    start.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                }
                return true;
            }"""
        )
        await page.wait_for_timeout(2500)
        if clicked:
            return {"clicked": True, "method": "js_visible_candidate"}
        visible_error = "visible_candidate_not_found"
    except Exception as exc:
        visible_error = str(exc)

    try:
        clicked = await page.evaluate(
            """() => {
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const candidates = Array.from(document.querySelectorAll('button, a, input, div, span, img, [role="button"], [onclick], #esub-start-response'));
                const start = candidates.find((el) => {
                    const signature = [
                        clean(el.innerText || el.textContent || el.value || el.alt || el.title || ''),
                        clean(el.id || ''),
                        clean(typeof el.className === 'string' ? el.className : ''),
                        clean(el.getAttribute('onclick') || ''),
                        clean(el.getAttribute('href') || '')
                    ].join(' ');
                    return signature.includes('start response') ||
                        signature.includes('start-response') ||
                        (signature.includes('start') && signature.includes('response'));
                });
                if (!start) return false;
                start.removeAttribute('disabled');
                start.removeAttribute('aria-disabled');
                start.removeAttribute('hidden');
                start.disabled = false;
                start.hidden = false;
                start.classList.remove('disabled');
                start.style.display = 'block';
                start.style.visibility = 'visible';
                start.style.pointerEvents = 'auto';
                start.style.opacity = '1';
                start.scrollIntoView({block: 'center', inline: 'center'});
                for (const type of ['pointerover', 'mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                    start.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                }
                if (typeof start.onclick === 'function') {
                    try { start.onclick.call(start); } catch (e) {}
                }
                return true;
            }"""
        )
        await page.wait_for_timeout(3000)
        return {"clicked": bool(clicked), "method": "js_hidden_candidate", "visible_error": visible_error}
    except Exception as exc:
        return {"clicked": False, "method": "js_hidden_candidate", "visible_error": visible_error, "error": str(exc)}


async def _click_start_response_in_frames(page: Any) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for index, frame in enumerate(getattr(page, "frames", []) or []):
        try:
            clicked = await frame.evaluate(
                """() => {
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    const candidates = Array.from(document.querySelectorAll('button, a, input, div, span, [role="button"], [onclick], #esub-start-response'));
                    const start = candidates.find((el) => {
                        const signature = [
                            clean(el.innerText || el.textContent || el.value || el.alt || el.title || ''),
                            clean(el.id || ''),
                            clean(typeof el.className === 'string' ? el.className : ''),
                            clean(el.getAttribute('onclick') || '')
                        ].join(' ');
                        return signature.includes('start response') || signature.includes('start-response') || (signature.includes('start') && signature.includes('response'));
                    });
                    if (!start) return false;
                    start.removeAttribute('disabled');
                    start.removeAttribute('hidden');
                    start.disabled = false;
                    start.hidden = false;
                    start.style.display = 'block';
                    start.style.visibility = 'visible';
                    start.style.pointerEvents = 'auto';
                    start.scrollIntoView({block: 'center', inline: 'center'});
                    for (const type of ['mouseover', 'mousedown', 'mouseup', 'click']) {
                        start.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                    }
                    return true;
                }"""
            )
            attempts.append({"frame_index": index, "url": getattr(frame, "url", ""), "clicked": bool(clicked)})
            if clicked:
                await page.wait_for_timeout(3000)
                return {"clicked": True, "method": "iframe_js_candidate", "attempts": attempts}
        except Exception as exc:
            attempts.append({"frame_index": index, "url": getattr(frame, "url", ""), "clicked": False, "error": str(exc)})
    return {"clicked": False, "method": "iframe_js_candidate", "attempts": attempts}


async def _start_response_interaction_debugger(page: Any, payload: Dict[str, Any], buyer_rfq: str) -> Dict[str, Any]:
    debug_id = f"{_slug(buyer_rfq or _buyer_rfq_number(payload), 'start-response')}__{_stamp()}"
    html_path = DEBUG_DIR / f"{debug_id}__expanded_row.html"
    json_path = DEBUG_DIR / f"{debug_id}__start_response_debug.json"

    try:
        before = await page.evaluate(
            """() => ({
                url: location.href,
                title: document.title || '',
                body_html: document.body ? document.body.outerHTML.slice(0, 250000) : '',
                body_text: (document.body?.innerText || document.body?.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 5000)
            })"""
        )
    except Exception as exc:
        before = {"error": str(exc), "url": _safe_str(getattr(page, "url", ""))}

    try:
        inventory = await page.evaluate(
            """() => {
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const cssPath = (el) => {
                    if (!el || !el.tagName) return '';
                    if (el.id) return `#${CSS.escape(el.id)}`;
                    const parts = [];
                    let node = el;
                    while (node && node.nodeType === 1 && parts.length < 6) {
                        let part = node.tagName.toLowerCase();
                        if (node.className && typeof node.className === 'string') {
                            const cls = node.className.trim().split(/\\s+/).filter(Boolean).slice(0, 3).map(c => `.${CSS.escape(c)}`).join('');
                            part += cls;
                        }
                        const parent = node.parentElement;
                        if (parent) {
                            const siblings = Array.from(parent.children).filter(child => child.tagName === node.tagName);
                            if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                        }
                        parts.unshift(part);
                        node = parent;
                    }
                    return parts.join(' > ');
                };
                const rowCandidates = new Set();
                for (const row of Array.from(document.querySelectorAll('tr.shown, tr.child, tr[aria-expanded="true"], .collapse.show, .in, [aria-expanded="true"]'))) {
                    const tr = row.closest?.('tr') || row;
                    rowCandidates.add(tr);
                    if (tr.nextElementSibling && tr.nextElementSibling.tagName === 'TR') rowCandidates.add(tr.nextElementSibling);
                }
                if (!rowCandidates.size) {
                    const textRows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"]'))
                        .filter(row => /start response|download|upload|document|tender detail|appointment of a service provider/i.test(row.innerText || row.textContent || ''));
                    textRows.slice(0, 8).forEach(row => {
                        rowCandidates.add(row);
                        if (row.nextElementSibling && row.nextElementSibling.tagName === 'TR') rowCandidates.add(row.nextElementSibling);
                    });
                }
                const expandedHtml = Array.from(rowCandidates).map(row => row.outerHTML || '').join('\\n\\n');
                const roots = rowCandidates.size ? Array.from(rowCandidates) : [document.body];
                const controls = [];
                const seen = new Set();
                const selector = 'button,a,input,select,textarea,[role="button"],[onclick],[href],label,summary,.btn,.submitButtons,[tabindex]';
                for (const root of roots) {
                    for (const el of Array.from(root.querySelectorAll(selector))) {
                        if (seen.has(el)) continue;
                        seen.add(el);
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        const attrs = {};
                        for (const attr of Array.from(el.attributes || [])) {
                            if (/^(aria-|data-|ng-|v-|x-|@|\\(|\\*|jsaction|onclick|href|id|class|name|type|value|role|title)/i.test(attr.name)) {
                                attrs[attr.name] = attr.value;
                            }
                        }
                        const keys = Object.keys(el).filter(key => /^__react|^__vue|^_vei|^ng|^\\$/.test(key)).slice(0, 20);
                        const bindingAttrs = Object.fromEntries(Object.entries(attrs).filter(([key]) => /ng-click|data-ng-click|\\(click\\)|@click|v-on|jsaction|x-on|onclick/i.test(key)));
                        let listenerMetadata = null;
                        try {
                            if (typeof getEventListeners === 'function') {
                                const listeners = getEventListeners(el);
                                listenerMetadata = Object.fromEntries(Object.entries(listeners).map(([type, values]) => [type, values.length]));
                            }
                        } catch (e) {}
                        const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                        const signature = `${text} ${el.id || ''} ${el.className || ''} ${el.getAttribute('onclick') || ''} ${el.getAttribute('href') || ''}`.toLowerCase();
                        const disabled = !!el.disabled || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true';
                        const hidden = el.hidden || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
                        const pointerEventsNone = style.pointerEvents === 'none';
                        controls.push({
                            debug_index: controls.length,
                            tag: el.tagName,
                            selector: cssPath(el),
                            text: text.slice(0, 260),
                            id: el.id || '',
                            cls: typeof el.className === 'string' ? el.className : '',
                            name: el.getAttribute('name') || '',
                            type: el.getAttribute('type') || '',
                            role: el.getAttribute('role') || '',
                            aria_label: el.getAttribute('aria-label') || '',
                            href: el.href || el.getAttribute('href') || '',
                            onclick: (el.getAttribute('onclick') || '').slice(0, 500),
                            attrs,
                            angular_react_vue_bindings: {
                                binding_attrs: bindingAttrs,
                                framework_private_keys: keys,
                                has_react_props: keys.some(key => key.startsWith('__reactProps')),
                                has_react_fiber: keys.some(key => key.startsWith('__reactFiber')),
                                has_vue_marker: keys.some(key => key.startsWith('__vue') || key === '_vei')
                            },
                            listener_metadata: listenerMetadata,
                            bounding_box: {x: rect.x, y: rect.y, width: rect.width, height: rect.height, top: rect.top, left: rect.left, bottom: rect.bottom, right: rect.right},
                            visible: visible(el),
                            disabled,
                            hidden,
                            pointer_events_none: pointerEventsNone,
                            cursor: style.cursor,
                            z_index: style.zIndex,
                            start_response_like: signature.includes('start response') || signature.includes('startresponse') || signature.includes('start-response') || (signature.includes('start') && signature.includes('response')),
                            unsafe_final_submit_like: /submit now|final submit|submit bid|submit response/.test(signature)
                        });
                    }
                }
                return {
                    expanded_row_count: rowCandidates.size,
                    expanded_row_html: expandedHtml || '',
                    expanded_row_controls: controls,
                    dom_snapshot: {
                        url: location.href,
                        title: document.title || '',
                        body_text: clean(document.body?.innerText || document.body?.textContent || '').slice(0, 5000),
                        html_preview: (document.body?.outerHTML || '').slice(0, 60000)
                    }
                };
            }"""
        )
        inventory = inventory if isinstance(inventory, dict) else {}
    except Exception as exc:
        inventory = {"error": str(exc), "expanded_row_controls": [], "expanded_row_html": ""}

    expanded_html = _safe_str(inventory.get("expanded_row_html"))
    try:
        html_path.write_text(expanded_html or _safe_str((before or {}).get("body_html")), encoding="utf-8")
    except Exception:
        pass

    controls = inventory.get("expanded_row_controls") if isinstance(inventory.get("expanded_row_controls"), list) else []
    click_targets = [
        control for control in controls
        if not control.get("unsafe_final_submit_like")
        and (
            control.get("start_response_like")
            or "response" in _safe_lower(control.get("text"))
            or "start" in _safe_lower(control.get("id"))
            or "start" in _safe_lower(control.get("cls"))
        )
    ]
    if not click_targets:
        click_targets = [control for control in controls if not control.get("unsafe_final_submit_like") and control.get("visible")][:10]
    click_targets = click_targets[:12]

    attempted: List[Dict[str, Any]] = []
    dispatch_results: List[Dict[str, Any]] = []
    for target in click_targets:
        target_ref = {
            "debug_index": target.get("debug_index"),
            "selector": target.get("selector"),
            "text": target.get("text"),
            "id": target.get("id"),
            "cls": target.get("cls"),
            "visible": target.get("visible"),
            "disabled": target.get("disabled"),
            "hidden": target.get("hidden"),
            "pointer_events_none": target.get("pointer_events_none"),
            "bounding_box": target.get("bounding_box"),
        }
        attempted.append(target_ref)
        try:
            result = await page.evaluate(
                """(debugIndex) => {
                    const controls = [];
                    const seen = new Set();
                    const roots = Array.from(document.querySelectorAll('tr.shown, tr.child, tr[aria-expanded="true"], .collapse.show, .in, [aria-expanded="true"]'));
                    const scanRoots = roots.length ? roots.flatMap(root => {
                        const tr = root.closest?.('tr') || root;
                        return tr.nextElementSibling && tr.nextElementSibling.tagName === 'TR' ? [tr, tr.nextElementSibling] : [tr];
                    }) : [document.body];
                    const selector = 'button,a,input,select,textarea,[role="button"],[onclick],[href],label,summary,.btn,.submitButtons,[tabindex]';
                    for (const root of scanRoots) {
                        for (const el of Array.from(root.querySelectorAll(selector))) {
                            if (seen.has(el)) continue;
                            seen.add(el);
                            controls.push(el);
                        }
                    }
                    const el = controls[debugIndex];
                    if (!el) return {ok: false, reason: 'target_not_found', debugIndex};
                    const beforeUrl = location.href;
                    const beforeText = (document.body?.innerText || document.body?.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 1200);
                    const events = [];
                    const push = (method, ok, error = '') => events.push({method, ok, error});
                    try {
                        el.removeAttribute('disabled');
                        el.removeAttribute('aria-disabled');
                        el.disabled = false;
                        el.style.pointerEvents = 'auto';
                        el.style.visibility = 'visible';
                        el.style.opacity = '1';
                        el.scrollIntoView({block: 'center', inline: 'center'});
                        push('prepare_target', true);
                    } catch (e) { push('prepare_target', false, String(e)); }
                    try { el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, cancelable: true, view: window})); push('hover_mouseover', true); } catch (e) { push('hover_mouseover', false, String(e)); }
                    try { if (typeof el.focus === 'function') el.focus({preventScroll: true}); push('focus', true); } catch (e) { push('focus', false, String(e)); }
                    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                        try {
                            el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                            push(`dispatch_${type}`, true);
                        } catch (e) { push(`dispatch_${type}`, false, String(e)); }
                    }
                    try { HTMLElement.prototype.click.call(el); push('HTMLElement.click.call', true); } catch (e) { push('HTMLElement.click.call', false, String(e)); }
                    try { el.click(); push('element.click', true); } catch (e) { push('element.click', false, String(e)); }
                    const afterText = (document.body?.innerText || document.body?.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 1200);
                    return {
                        ok: true,
                        debugIndex,
                        beforeUrl,
                        afterUrl: location.href,
                        urlChanged: beforeUrl !== location.href,
                        beforeText,
                        afterText,
                        events
                    };
                }""",
                target.get("debug_index"),
            )
            await page.wait_for_timeout(1500)
            dispatch_results.append(result if isinstance(result, dict) else {"result": result})
        except Exception as exc:
            dispatch_results.append({"ok": False, "debug_index": target.get("debug_index"), "error": str(exc)})

    try:
        after = await page.evaluate(
            """() => {
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                const modalControls = Array.from(document.querySelectorAll('.modal, [role="dialog"], .swal2-container, .bootbox, button, a, input'))
                    .map((el, index) => {
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                        const signature = `${text} ${el.id || ''} ${el.className || ''}`.toLowerCase();
                        return {
                            index,
                            tag: el.tagName,
                            id: el.id || '',
                            cls: typeof el.className === 'string' ? el.className : '',
                            text: text.slice(0, 220),
                            visible: !!(rect.width || rect.height || el.getClientRects().length),
                            hidden: el.hidden || style.display === 'none' || style.visibility === 'hidden',
                            disabled: !!el.disabled || el.getAttribute('disabled') !== null,
                            bounding_box: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                            confirmation_like: /yes|ok|confirm|continue|proceed|start|response/.test(signature),
                            unsafe_final_submit_like: /submit now|final submit|submit bid|submit response/.test(signature)
                        };
                    })
                    .filter(item => item.confirmation_like || item.text)
                    .slice(0, 80);
                return {
                    url: location.href,
                    title: document.title || '',
                    body_text: clean(document.body?.innerText || document.body?.textContent || '').slice(0, 5000),
                    html_preview: (document.body?.outerHTML || '').slice(0, 60000),
                    secondary_confirmation_controls: modalControls
                };
            }"""
        )
    except Exception as exc:
        after = {"error": str(exc), "url": _safe_str(getattr(page, "url", ""))}

    payload_out = {
        "created_at": _now(),
        "buyer_rfq_number": buyer_rfq,
        "before_dom_snapshot": before,
        "after_dom_snapshot": after,
        "expanded_row_html_path": str(html_path),
        "expanded_row_controls": controls,
        "attempted_click_targets": attempted,
        "click_dispatch_results": dispatch_results,
        "secondary_confirmation_controls": (after or {}).get("secondary_confirmation_controls", []),
    }
    _write_json(json_path, payload_out)
    payload_out["debug_artifact"] = str(json_path)
    return payload_out


async def _deep_hidden_control_discovery(page: Any, row_index: int, scan_id: str) -> Dict[str, Any]:
    """Inspect lazy/hidden UI layers without clicking any submitting control."""
    artifact_prefix = DEBUG_DIR / f"{scan_id}__row_{row_index:03d}__hidden_controls"
    pre_dom_path = Path(f"{artifact_prefix}__pre.html")
    post_dom_path = Path(f"{artifact_prefix}__post.html")
    mutation_path = Path(f"{artifact_prefix}__mutations.json")
    screenshot_path = Path(f"{artifact_prefix}.png")
    try:
        pre_html = await page.evaluate("() => document.documentElement.outerHTML")
        pre_dom_path.write_text(_safe_str(pre_html), encoding="utf-8")
    except Exception:
        pass

    try:
        result = await page.evaluate(
            """async ({rowIndex}) => {
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return !!(rect.width || rect.height || el.getClientRects().length)
                        && style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && style.opacity !== '0'
                        && !el.hidden;
                };
                const cssPath = (el) => {
                    if (!el || !el.tagName) return '';
                    if (el.id) return `#${CSS.escape(el.id)}`;
                    const parts = [];
                    let node = el;
                    while (node && node.nodeType === 1 && parts.length < 7) {
                        let part = node.tagName.toLowerCase();
                        if (node.className && typeof node.className === 'string') {
                            part += node.className.trim().split(/\\s+/).filter(Boolean).slice(0, 3).map(c => `.${CSS.escape(c)}`).join('');
                        }
                        const parent = node.parentElement;
                        if (parent) {
                            const siblings = Array.from(parent.children).filter(child => child.tagName === node.tagName);
                            if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                        }
                        parts.unshift(part);
                        node = parent;
                    }
                    return parts.join(' > ');
                };
                const rows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'))
                    .filter(row => {
                        const text = clean(row.innerText || row.textContent || '');
                        const rect = row.getBoundingClientRect();
                        return text.length > 20 && rect.width > 0 && rect.height > 0 && !/category\\s+tender description\\s+esubmission/i.test(text);
                    });
                const row = rows[rowIndex];
                if (!row) return {ok: false, reason: 'row_not_found', rowIndex};
                const next = row.nextElementSibling && row.nextElementSibling.tagName === 'TR' ? row.nextElementSibling : null;
                const roots = [row];
                if (next) roots.push(next);
                for (const extra of Array.from(document.querySelectorAll('.modal,[role="dialog"],.dropdown-menu,.popover,.tooltip,.offcanvas,.swal2-container,[aria-hidden="false"]'))) {
                    roots.push(extra);
                }

                const mutationLog = [];
                const observer = new MutationObserver((mutations) => {
                    for (const mutation of mutations) {
                        const added = Array.from(mutation.addedNodes || [])
                            .filter(node => node && node.nodeType === 1)
                            .map(node => ({
                                tag: node.tagName || '',
                                text: clean(node.innerText || node.textContent || '').slice(0, 260),
                                html: (node.outerHTML || '').slice(0, 1200)
                            }));
                        const attrs = mutation.type === 'attributes' ? {
                            target: mutation.target?.tagName || '',
                            attr: mutation.attributeName || '',
                            text: clean(mutation.target?.innerText || mutation.target?.textContent || '').slice(0, 220),
                            aria_hidden: mutation.target?.getAttribute?.('aria-hidden') || ''
                        } : null;
                        if (added.length || attrs) mutationLog.push({type: mutation.type, added, attrs});
                    }
                });
                try {
                    observer.observe(document.documentElement, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        attributeFilter: ['aria-hidden', 'hidden', 'style', 'class']
                    });
                } catch (e) {}

                const controlSelector = 'button,a,input,select,textarea,[role="button"],[role="menuitem"],[onclick],[href],label,summary,.btn,.dropdown-toggle,.dropdown-menu *,.submitButtons,[tabindex]';
                const safeResponse = (signature) => /start response|startresponse|\\brespond\\b|submit quote|submit response|quote|esubmission/i.test(signature)
                    && !/notification|bookmark|download|document|\\/home\\/download|managebookmarks|managenotification|profile#notification|captcha|recaptcha|final submit|submit bid|submit now/i.test(signature);
                const describe = (el, source) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    const attrs = {};
                    for (const attr of Array.from(el.attributes || [])) {
                        if (/^(aria-|data-|ng-|v-|x-|@|\\(|\\*|jsaction|onclick|href|id|class|name|type|value|role|title|style)/i.test(attr.name)) attrs[attr.name] = attr.value;
                    }
                    const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                    const href = el.href || el.getAttribute('href') || '';
                    const onclick = el.getAttribute('onclick') || '';
                    const signature = `${text} ${el.id || ''} ${el.className || ''} ${href} ${onclick} ${el.name || ''} ${el.type || ''}`.toLowerCase();
                    const visible = isVisible(el);
                    const hidden = el.hidden || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0' || el.getAttribute('aria-hidden') === 'true';
                    return {
                        source,
                        tag: el.tagName,
                        selector: cssPath(el),
                        text: text.slice(0, 260),
                        id: el.id || '',
                        cls: typeof el.className === 'string' ? el.className : '',
                        aria_label: el.getAttribute('aria-label') || '',
                        href,
                        onclick: onclick.slice(0, 500),
                        attrs,
                        visible,
                        hidden,
                        disabled: !!el.disabled || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true',
                        pointer_events_none: style.pointerEvents === 'none',
                        aria_hidden: el.getAttribute('aria-hidden') || '',
                        bounding_box: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                        response_like: safeResponse(signature),
                        unsafe_final_submit_like: /final submit|submit bid|submit now|captcha|recaptcha/i.test(signature)
                    };
                };

                const collectFromRoots = (rootsToScan, source) => {
                    const out = [];
                    const seen = new Set();
                    for (const root of rootsToScan) {
                        if (!root || !root.querySelectorAll) continue;
                        for (const el of Array.from(root.querySelectorAll(controlSelector))) {
                            if (seen.has(el)) continue;
                            seen.add(el);
                            out.push(describe(el, source));
                        }
                    }
                    return out;
                };

                let initialControls = collectFromRoots(roots, 'expanded_dom');
                const revealAttempts = [];
                const controlEls = [];
                const seenRevealEls = new Set();
                for (const root of roots) {
                    if (!root || !root.querySelectorAll) continue;
                    for (const el of Array.from(root.querySelectorAll(controlSelector))) {
                        if (seenRevealEls.has(el)) continue;
                        seenRevealEls.add(el);
                        const item = describe(el, 'reveal_candidate');
                        const signature = `${item.text} ${item.id} ${item.cls} ${item.href} ${item.onclick}`.toLowerCase();
                        if (/final submit|submit bid|submit now|captcha|recaptcha|notification|bookmark|download|document/i.test(signature)) continue;
                        controlEls.push(el);
                    }
                }

                for (const el of controlEls.slice(0, 60)) {
                    const before = describe(el, 'before_reveal');
                    try {
                        el.scrollIntoView({block: 'center', inline: 'center'});
                        if (typeof el.focus === 'function') el.focus({preventScroll: true});
                        for (const type of ['mouseover', 'mouseenter', 'pointerover', 'focusin']) {
                            el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                        }
                        await new Promise(resolve => setTimeout(resolve, 120));
                        const after = describe(el, 'after_reveal');
                        revealAttempts.push({
                            selector: before.selector,
                            text: before.text,
                            before_visible: before.visible,
                            after_visible: after.visible,
                            before_hidden: before.hidden,
                            after_hidden: after.hidden,
                            revealed: (!before.visible && after.visible) || (before.hidden && !after.hidden)
                        });
                    } catch (e) {
                        revealAttempts.push({selector: before.selector, text: before.text, error: String(e), revealed: false});
                    }
                }

                await new Promise(resolve => setTimeout(resolve, 1800));
                const delayedControls = collectFromRoots(roots.concat(Array.from(document.querySelectorAll('.modal,[role="dialog"],.dropdown-menu,.popover,.tooltip,.offcanvas,[aria-hidden="false"]'))), 'delayed_dom')
                    .filter(item => !initialControls.some(initial => initial.selector === item.selector && initial.text === item.text));

                const shadowControls = [];
                const shadowHosts = Array.from(document.querySelectorAll('*')).filter(el => el.shadowRoot);
                for (const host of shadowHosts.slice(0, 80)) {
                    try {
                        shadowControls.push(...collectFromRoots([host.shadowRoot], `shadowdom:${cssPath(host)}`));
                    } catch (e) {}
                }

                const iframeControls = [];
                const iframes = Array.from(document.querySelectorAll('iframe,frame'));
                for (const frame of iframes.slice(0, 20)) {
                    try {
                        const doc = frame.contentDocument || frame.contentWindow?.document;
                        if (!doc) {
                            iframeControls.push({source: 'iframe', iframe_src: frame.src || frame.getAttribute('src') || '', inaccessible: true});
                            continue;
                        }
                        iframeControls.push(...collectFromRoots([doc], `iframe:${frame.src || frame.getAttribute('src') || ''}`));
                    } catch (e) {
                        iframeControls.push({source: 'iframe', iframe_src: frame.src || frame.getAttribute('src') || '', inaccessible: true, error: String(e)});
                    }
                }
                try { observer.disconnect(); } catch (e) {}

                const postControls = collectFromRoots(roots.concat(Array.from(document.querySelectorAll('.modal,[role="dialog"],.dropdown-menu,.popover,.tooltip,.offcanvas,[aria-hidden="false"]'))), 'post_reveal_dom');
                const visibleControls = postControls.filter(item => item.visible && !item.hidden);
                const hiddenControls = postControls.filter(item => item.hidden || !item.visible || item.pointer_events_none || item.disabled);
                const hiddenStartResponseCandidates = hiddenControls.concat(delayedControls, iframeControls, shadowControls)
                    .filter(item => item && item.response_like && !item.unsafe_final_submit_like)
                    .slice(0, 50);
                const mutationAddedControls = [];
                for (const mutation of mutationLog) {
                    for (const added of mutation.added || []) {
                        if (/start response|startresponse|\\brespond\\b|submit quote|submit response|quote|esubmission/i.test(`${added.text} ${added.html}`)) {
                            mutationAddedControls.push(added);
                        }
                    }
                }
                return {
                    ok: true,
                    rowIndex,
                    visible_controls: visibleControls.slice(0, 120),
                    hidden_controls: hiddenControls.slice(0, 160),
                    delayed_controls: delayedControls.slice(0, 120),
                    iframe_controls: iframeControls.slice(0, 120),
                    shadowdom_controls: shadowControls.slice(0, 120),
                    hidden_start_response_candidates: hiddenStartResponseCandidates,
                    delayed_render_detected: delayedControls.length > 0,
                    iframe_detected: iframes.length > 0,
                    shadowdom_detected: shadowControls.length > 0,
                    mutation_added_controls_count: mutationAddedControls.length,
                    mutation_added_controls: mutationAddedControls.slice(0, 40),
                    hidden_control_reveal_attempts: revealAttempts,
                    successful_hidden_control_reveals: revealAttempts.filter(item => item.revealed).length,
                    mutation_log: mutationLog.slice(0, 200),
                    post_dom_excerpt: (document.documentElement.outerHTML || '').slice(0, 120000)
                };
            }""",
            {"rowIndex": row_index},
        )
    except Exception as exc:
        result = {"ok": False, "rowIndex": row_index, "error": str(exc)}

    try:
        post_dom_path.write_text(_safe_str(result.get("post_dom_excerpt")), encoding="utf-8")
    except Exception:
        pass
    result.pop("post_dom_excerpt", None)
    try:
        _write_json(mutation_path, result.get("mutation_log") or [])
    except Exception:
        pass
    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        screenshot_path = Path("")
    result["artifacts"] = {
        "pre_dom_snapshot": str(pre_dom_path),
        "post_dom_snapshot": str(post_dom_path),
        "mutation_log": str(mutation_path),
        "hidden_control_screenshot": str(screenshot_path) if screenshot_path else "",
    }
    return result


async def _multi_row_autonomous_portal_scan(page: Any, payload: Dict[str, Any], buyer_rfq: str, max_rows: int = 25) -> Dict[str, Any]:
    scan_id = f"{_slug(buyer_rfq or _buyer_rfq_number(payload), 'multi-row-scan')}__{_stamp()}"
    row_classification: List[Dict[str, Any]] = []
    start_response_candidates: List[Dict[str, Any]] = []
    top_possible_candidates: List[Dict[str, Any]] = []
    summary_counts_by_reason: Dict[str, int] = {}
    hidden_start_response_candidates: List[Dict[str, Any]] = []
    hidden_control_reveal_attempts: List[Dict[str, Any]] = []
    visible_controls: List[Dict[str, Any]] = []
    hidden_controls: List[Dict[str, Any]] = []
    delayed_controls: List[Dict[str, Any]] = []
    iframe_controls: List[Dict[str, Any]] = []
    shadowdom_controls: List[Dict[str, Any]] = []
    mutation_added_controls_count = 0
    successful_hidden_control_reveals = 0
    delayed_render_detected = False
    iframe_detected = False
    shadowdom_detected = False
    artifacts: List[Dict[str, Any]] = []
    scanned_rows_count = 0
    skipped_rows_count = 0
    successful_workspace_transition_count = 0
    selected_row_index: Optional[int] = None
    workspace_transition_url = ""
    termination = "no_eligible_transition"

    for row_index in range(max_rows):
        try:
            row_state = await page.evaluate(
                """({rowIndex}) => {
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                    const rows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'))
                        .filter(row => {
                            const text = clean(row.innerText || row.textContent || '');
                            const rect = row.getBoundingClientRect();
                            const headerLike = /category\\s+tender description\\s+esubmission\\s+advertised\\s+closing/i.test(text)
                                || /^currently advertised tenders\\s+category\\s+tender description/i.test(text)
                                || /^category\\s+tender description/i.test(text);
                            return text.length > 20 && rect.width > 0 && rect.height > 0 && !headerLike;
                        });
                    const row = rows[rowIndex];
                    if (!row) return {exists: false, rowIndex, visibleRowCount: rows.length};
                    row.scrollIntoView({block: 'center', inline: 'center'});
                    row.click();
                    for (const selector of ['td.details-control', 'td.dtr-control', 'td:first-child', 'button[aria-expanded]', 'a[aria-expanded]']) {
                        const ctl = row.querySelector(selector);
                        if (!ctl) continue;
                        try {
                            for (const type of ['mouseover', 'mousedown', 'mouseup', 'click']) {
                                ctl.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                            }
                            break;
                        } catch (e) {}
                    }
                    const next = row.nextElementSibling && row.nextElementSibling.tagName === 'TR' ? row.nextElementSibling : null;
                    const roots = next ? [row, next] : [row];
                    const controls = [];
                    const seen = new Set();
                    const cssPath = (el) => {
                        if (!el || !el.tagName) return '';
                        if (el.id) return `#${CSS.escape(el.id)}`;
                        const parts = [];
                        let node = el;
                        while (node && node.nodeType === 1 && parts.length < 6) {
                            let part = node.tagName.toLowerCase();
                            if (node.className && typeof node.className === 'string') {
                                part += node.className.trim().split(/\\s+/).filter(Boolean).slice(0, 3).map(c => `.${CSS.escape(c)}`).join('');
                            }
                            const parent = node.parentElement;
                            if (parent) {
                                const siblings = Array.from(parent.children).filter(child => child.tagName === node.tagName);
                                if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                            }
                            parts.unshift(part);
                            node = parent;
                        }
                        return parts.join(' > ');
                    };
                    for (const root of roots) {
                        for (const el of Array.from(root.querySelectorAll('button,a,input,select,textarea,[role="button"],[onclick],[href],label,summary,.btn,.submitButtons,[tabindex]'))) {
                            if (seen.has(el)) continue;
                            seen.add(el);
                            const rect = el.getBoundingClientRect();
                            const style = getComputedStyle(el);
                            const attrs = {};
                            for (const attr of Array.from(el.attributes || [])) {
                                if (/^(aria-|data-|ng-|v-|x-|@|\\(|\\*|jsaction|onclick|href|id|class|name|type|value|role|title)/i.test(attr.name)) attrs[attr.name] = attr.value;
                            }
                            const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                            const href = el.href || el.getAttribute('href') || '';
                            const onclick = el.getAttribute('onclick') || '';
                            const signature = `${text} ${el.id || ''} ${el.className || ''} ${href} ${onclick}`.toLowerCase();
                            const notificationLike = /notification|bookmark|download|document|\\/home\\/download|managebookmarks|managenotification|profile#notification/.test(signature);
                            const responseLike = /start response|startresponse|respond|response|submit quote|submit response|quote|esubmission\\/esubmission/.test(signature);
                            const submitUnsafe = /submit now|final submit|submit bid/.test(signature);
                            controls.push({
                                debug_index: controls.length,
                                tag: el.tagName,
                                selector: cssPath(el),
                                text: text.slice(0, 260),
                                id: el.id || '',
                                cls: typeof el.className === 'string' ? el.className : '',
                                aria_label: el.getAttribute('aria-label') || '',
                                href,
                                onclick: onclick.slice(0, 500),
                                attrs,
                                visible: visible(el),
                                disabled: !!el.disabled || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true',
                                hidden: el.hidden || style.display === 'none' || style.visibility === 'hidden',
                                pointer_events_none: style.pointerEvents === 'none',
                                bounding_box: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                                notification_like: notificationLike,
                                response_like: responseLike,
                                unsafe_final_submit_like: submitUnsafe,
                                eligible_start_response: responseLike && !notificationLike && !submitUnsafe
                            });
                        }
                    }
                    const rowText = clean(row.innerText || row.textContent || '');
                    const expandedText = clean(roots.map(root => root.innerText || root.textContent || '').join(' '));
                    const combinedText = `${rowText} ${expandedText}`;
                    const combinedLower = combinedText.toLowerCase();
                    const capture = (patterns) => {
                        for (const pattern of patterns) {
                            const match = combinedText.match(pattern);
                            if (match) return clean(match[1] || match[0]).slice(0, 240);
                        }
                        return '';
                    };
                    const metadata = {
                        tender_status: capture([/Status:\\s*([^\\n\\r]+?)(?=\\s+(Tender Number|Organ Of State|Province|Date Published|Closing Date|Briefing|Place where|Special Conditions|ENQUIR|$))/i, /\\b(Open|Available|Closed|Awarded|Cancelled)\\b/i]),
                        closing_date: capture([/Closing Date:\\s*([^\\n\\r]+?)(?=\\s+(Place where|Special Conditions|ENQUIR|Briefing|Tender Number|$))/i, /\\b\\d{1,2}\\/\\d{1,2}\\/\\d{4}\\b/i, /\\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\\s+\\d{1,2}\\s+\\w+\\s+\\d{4}\\s+-\\s+\\d{1,2}:\\d{2}\\b/i]),
                        briefing_status: capture([/Briefing(?: Session)?:\\s*([^\\n\\r]+?)(?=\\s+(Tender Number|Organ Of State|Province|Date Published|Closing Date|Place where|Special Conditions|$))/i, /\\b(Compulsory briefing|Non-compulsory briefing|Briefing required|No briefing)\\b/i]),
                        province: capture([/Province:\\s*([^\\n\\r]+?)(?=\\s+(Date Published|Closing Date|Briefing|Place where|Special Conditions|$))/i, /\\b(Eastern Cape|Free State|Gauteng|KwaZulu-Natal|Limpopo|Mpumalanga|National|North West|Northern Cape|Western Cape)\\b/i]),
                        category: capture([/Category\\s*:?\\s*([^\\n\\r]+?)(?=\\s+(Tender Description|Tender Number|Organ Of State|Province|Date Published|Closing Date|$))/i]),
                        department: capture([/Organ Of State:\\s*([^\\n\\r]+?)(?=\\s+(Tender Type|Province|Date Published|Closing Date|Briefing|$))/i, /Department:\\s*([^\\n\\r]+?)(?=\\s+(Tender Type|Province|Date Published|Closing Date|Briefing|$))/i]),
                    };
                    const signals = {
                        has_esubmission_text: /\\besubmission\\b|e-submission|electronic submission/i.test(combinedText),
                        has_respond_text: /\\brespond\\b|start response|submit response|submit quote|quote action/i.test(combinedText),
                        has_open_text: /\\bopen\\b|available|currently advertised/i.test(combinedText),
                        has_closed_text: /\\bclosed\\b|expired|closing date.*closed/i.test(combinedText),
                        has_awarded_text: /\\bawarded\\b/i.test(combinedText),
                        has_cancelled_text: /\\bcancelled\\b|canceled/i.test(combinedText),
                        briefing_required: /compulsory briefing|briefing required|mandatory briefing/i.test(combinedText),
                    };
                    const now = new Date();
                    let closingExpired = false;
                    try {
                        const closing = metadata.closing_date || '';
                        const isoLike = closing.match(/(\\d{1,2})\\/(\\d{1,2})\\/(\\d{4})/);
                        if (isoLike) {
                            const day = Number(isoLike[1]);
                            const month = Number(isoLike[2]) - 1;
                            const year = Number(isoLike[3]);
                            const parsed = new Date(year, month, day, 23, 59, 59);
                            closingExpired = parsed.getTime() < now.getTime();
                        }
                    } catch (e) {}
                    const html = roots.map(root => root.outerHTML || '').join('\\n\\n');
                    const hiddenPossible = controls.filter(control => control.response_like && !control.notification_like && !control.unsafe_final_submit_like && (control.hidden || !control.visible || control.disabled || control.pointer_events_none));
                    const eligible = controls.filter(control => control.eligible_start_response && !control.disabled && !control.pointer_events_none && control.visible && !control.hidden);
                    let reason = '';
                    const documentOnly = controls.length > 0 && controls.every(control => /download|document|\\/home\\/download/i.test(control.text || control.href || ''));
                    const notificationOnly = controls.length > 0 && controls.every(control => control.notification_like || /download|document/i.test(control.text || control.href || ''));
                    if (signals.has_closed_text || signals.has_awarded_text || signals.has_cancelled_text || closingExpired) reason = 'closed_or_expired';
                    else if (signals.briefing_required && !eligible.length) reason = 'briefing_required';
                    else if (!signals.has_esubmission_text && !controls.some(control => control.response_like)) reason = 'no_esubmission';
                    else if (notificationOnly) reason = 'notification_only';
                    else if (documentOnly) reason = 'document_only';
                    else if (hiddenPossible.length > 0 && !eligible.length) reason = 'possible_candidate_but_control_hidden';
                    else if (!eligible.length) reason = 'no_esubmission';
                    return {
                        exists: true,
                        rowIndex,
                        visibleRowCount: rows.length,
                        row_text_preview: rowText.slice(0, 700),
                        metadata,
                        eligibility_signals: signals,
                        closing_expired: closingExpired,
                        html,
                        controls,
                        eligible,
                        hidden_possible_candidates: hiddenPossible.slice(0, 10),
                        portal_not_submittable_reason: reason,
                        notification_only: reason === 'notification_only'
                    };
                }""",
                {"rowIndex": row_index},
            )
        except Exception as exc:
            row_classification.append({"row_index": row_index, "error": str(exc)})
            continue

        if not isinstance(row_state, dict) or not row_state.get("exists"):
            termination = "visible_rows_exhausted"
            break

        scanned_rows_count += 1
        html_path = DEBUG_DIR / f"{scan_id}__row_{row_index:03d}.html"
        json_path = DEBUG_DIR / f"{scan_id}__row_{row_index:03d}.json"
        try:
            html_path.write_text(_safe_str(row_state.get("html")), encoding="utf-8")
        except Exception:
            pass

        hidden_discovery = await _deep_hidden_control_discovery(page, row_index, scan_id)
        hidden_start_response_candidates.extend([
            {**candidate, "row_index": row_index}
            for candidate in (hidden_discovery.get("hidden_start_response_candidates") or [])
            if isinstance(candidate, dict)
        ])
        visible_controls.extend([
            {**control, "row_index": row_index}
            for control in (hidden_discovery.get("visible_controls") or [])[:20]
            if isinstance(control, dict)
        ])
        hidden_controls.extend([
            {**control, "row_index": row_index}
            for control in (hidden_discovery.get("hidden_controls") or [])[:20]
            if isinstance(control, dict)
        ])
        delayed_controls.extend([
            {**control, "row_index": row_index}
            for control in (hidden_discovery.get("delayed_controls") or [])[:20]
            if isinstance(control, dict)
        ])
        iframe_controls.extend([
            {**control, "row_index": row_index}
            for control in (hidden_discovery.get("iframe_controls") or [])[:20]
            if isinstance(control, dict)
        ])
        shadowdom_controls.extend([
            {**control, "row_index": row_index}
            for control in (hidden_discovery.get("shadowdom_controls") or [])[:20]
            if isinstance(control, dict)
        ])
        hidden_control_reveal_attempts.extend([
            {**attempt, "row_index": row_index}
            for attempt in (hidden_discovery.get("hidden_control_reveal_attempts") or [])[:20]
            if isinstance(attempt, dict)
        ])
        mutation_added_controls_count += int(hidden_discovery.get("mutation_added_controls_count") or 0)
        successful_hidden_control_reveals += int(hidden_discovery.get("successful_hidden_control_reveals") or 0)
        delayed_render_detected = bool(delayed_render_detected or hidden_discovery.get("delayed_render_detected"))
        iframe_detected = bool(iframe_detected or hidden_discovery.get("iframe_detected"))
        shadowdom_detected = bool(shadowdom_detected or hidden_discovery.get("shadowdom_detected"))

        classification = {
            "row_index": row_index,
            "row_text_preview": row_state.get("row_text_preview"),
            "tender_status": (row_state.get("metadata") or {}).get("tender_status"),
            "closing_date": (row_state.get("metadata") or {}).get("closing_date"),
            "briefing_status": (row_state.get("metadata") or {}).get("briefing_status"),
            "province": (row_state.get("metadata") or {}).get("province"),
            "category": (row_state.get("metadata") or {}).get("category"),
            "department": (row_state.get("metadata") or {}).get("department"),
            "eligibility_signals": row_state.get("eligibility_signals") or {},
            "control_count": len(row_state.get("controls") or []),
            "visible_control_count": len(hidden_discovery.get("visible_controls") or []),
            "hidden_control_count": len(hidden_discovery.get("hidden_controls") or []),
            "delayed_control_count": len(hidden_discovery.get("delayed_controls") or []),
            "iframe_control_count": len(hidden_discovery.get("iframe_controls") or []),
            "shadowdom_control_count": len(hidden_discovery.get("shadowdom_controls") or []),
            "hidden_start_response_candidate_count": len(hidden_discovery.get("hidden_start_response_candidates") or []),
            "mutation_added_controls_count": int(hidden_discovery.get("mutation_added_controls_count") or 0),
            "successful_hidden_control_reveals": int(hidden_discovery.get("successful_hidden_control_reveals") or 0),
            "eligible_candidate_count": len(row_state.get("eligible") or []),
            "hidden_possible_candidate_count": len(row_state.get("hidden_possible_candidates") or []),
            "portal_not_submittable_reason": row_state.get("portal_not_submittable_reason") or "",
            "notification_only": bool(row_state.get("notification_only")),
            "html_artifact": str(html_path),
            "json_artifact": str(json_path),
            "hidden_control_artifacts": hidden_discovery.get("artifacts") or {},
        }
        row_classification.append(classification)
        reason_key = classification.get("portal_not_submittable_reason") or "unknown"
        summary_counts_by_reason[reason_key] = summary_counts_by_reason.get(reason_key, 0) + 1
        artifacts.append({"row_index": row_index, "html": str(html_path), "json": str(json_path)})

        row_debug = {
            "created_at": _now(),
            "row_index": row_index,
            "row_state": row_state,
            "classification": classification,
            "hidden_control_discovery": hidden_discovery,
        }
        _write_json(json_path, row_debug)

        eligible = row_state.get("eligible") if isinstance(row_state.get("eligible"), list) else []
        hidden_possible = row_state.get("hidden_possible_candidates") if isinstance(row_state.get("hidden_possible_candidates"), list) else []
        for candidate in hidden_possible:
            if len(top_possible_candidates) >= 5:
                break
            top_possible_candidates.append({
                **candidate,
                "row_index": row_index,
                "row_text_preview": row_state.get("row_text_preview"),
                "portal_not_submittable_reason": classification.get("portal_not_submittable_reason"),
                "metadata": row_state.get("metadata") or {},
            })
        if not eligible:
            skipped_rows_count += 1
            continue

        start_response_candidates.extend([{**candidate, "row_index": row_index} for candidate in eligible])

        for candidate in eligible[:4]:
            selected_row_index = row_index
            try:
                await _install_start_response_mutation_observer(page)
                click_result = await page.evaluate(
                    """({rowIndex, debugIndex}) => {
                        const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                        const rows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'))
                            .filter(row => {
                                const text = clean(row.innerText || row.textContent || '');
                                const rect = row.getBoundingClientRect();
                                return text.length > 20 && rect.width > 0 && rect.height > 0 && !/category\\s+tender description\\s+esubmission/i.test(text);
                            });
                        const row = rows[rowIndex];
                        if (!row) return {clicked: false, reason: 'row_not_found'};
                        const next = row.nextElementSibling && row.nextElementSibling.tagName === 'TR' ? row.nextElementSibling : null;
                        const roots = next ? [row, next] : [row];
                        const controls = [];
                        const seen = new Set();
                        for (const root of roots) {
                            for (const el of Array.from(root.querySelectorAll('button,a,input,select,textarea,[role="button"],[onclick],[href],label,summary,.btn,.submitButtons,[tabindex]'))) {
                                if (seen.has(el)) continue;
                                seen.add(el);
                                controls.push(el);
                            }
                        }
                        const el = controls[debugIndex];
                        if (!el) return {clicked: false, reason: 'target_not_found'};
                        const beforeUrl = location.href;
                        try {
                            el.removeAttribute('disabled');
                            el.removeAttribute('aria-disabled');
                            el.disabled = false;
                            el.style.pointerEvents = 'auto';
                            el.scrollIntoView({block: 'center', inline: 'center'});
                            if (typeof el.focus === 'function') el.focus({preventScroll: true});
                            for (const type of ['mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                                el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                            }
                            HTMLElement.prototype.click.call(el);
                            el.click();
                            return {clicked: true, beforeUrl, afterUrl: location.href, urlChanged: beforeUrl !== location.href};
                        } catch (e) {
                            return {clicked: false, beforeUrl, afterUrl: location.href, error: String(e)};
                        }
                    }""",
                    {"rowIndex": row_index, "debugIndex": candidate.get("debug_index")},
                )
                await page.wait_for_timeout(4500)
                transition = await _workspace_transition_snapshot(page, payload)
                row_debug.setdefault("attempts", []).append({
                    "candidate": candidate,
                    "click_result": click_result,
                    "transition": transition,
                })
                _write_json(json_path, row_debug)
                if transition.get("workspace_transition_success"):
                    successful_workspace_transition_count += 1
                    workspace_transition_url = _safe_str(transition.get("response_workspace_url"))
                    screenshot_path = DEBUG_DIR / f"{scan_id}__row_{row_index:03d}__successful_transition.png"
                    try:
                        await page.screenshot(path=str(screenshot_path), full_page=True)
                    except Exception:
                        screenshot_path = Path("")
                    termination = "workspace_transition_success"
                    return {
                        "scanned_rows_count": scanned_rows_count,
                        "skipped_rows_count": skipped_rows_count,
                        "successful_workspace_transition_count": successful_workspace_transition_count,
                        "row_classification": row_classification,
                        "summary_counts_by_reason": summary_counts_by_reason,
                        "top_possible_candidates": top_possible_candidates[:5],
                        "start_response_candidates": start_response_candidates,
                        "selected_row_index": selected_row_index,
                        "workspace_transition_url": workspace_transition_url,
                        "scan_termination_reason": termination,
                        "artifacts": artifacts,
                        "successful_transition_screenshot": str(screenshot_path) if screenshot_path else "",
                        "visible_controls": visible_controls[:120],
                        "hidden_controls": hidden_controls[:120],
                        "delayed_controls": delayed_controls[:120],
                        "iframe_controls": iframe_controls[:120],
                        "shadowdom_controls": shadowdom_controls[:120],
                        "hidden_start_response_candidates": hidden_start_response_candidates[:50],
                        "delayed_render_detected": delayed_render_detected,
                        "iframe_detected": iframe_detected,
                        "shadowdom_detected": shadowdom_detected,
                        "mutation_added_controls_count": mutation_added_controls_count,
                        "hidden_control_reveal_attempts": hidden_control_reveal_attempts[:120],
                        "successful_hidden_control_reveals": successful_hidden_control_reveals,
                    }
                if "etenders.gov.za" not in _safe_lower(getattr(page, "url", "")) or "/Profile" in _safe_str(getattr(page, "url", "")):
                    await page.goto("https://www.etenders.gov.za/Home/opportunities?id=1", wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
                    await page.wait_for_timeout(2500)
            except Exception as exc:
                row_debug.setdefault("attempts", []).append({"candidate": candidate, "error": str(exc)})
                _write_json(json_path, row_debug)

        skipped_rows_count += 1

    return {
        "scanned_rows_count": scanned_rows_count,
        "skipped_rows_count": skipped_rows_count,
        "successful_workspace_transition_count": successful_workspace_transition_count,
        "row_classification": row_classification,
        "summary_counts_by_reason": summary_counts_by_reason,
        "top_possible_candidates": top_possible_candidates[:5],
        "start_response_candidates": start_response_candidates,
        "selected_row_index": selected_row_index,
        "workspace_transition_url": workspace_transition_url,
        "scan_termination_reason": termination,
        "artifacts": artifacts,
        "successful_transition_screenshot": "",
        "visible_controls": visible_controls[:120],
        "hidden_controls": hidden_controls[:120],
        "delayed_controls": delayed_controls[:120],
        "iframe_controls": iframe_controls[:120],
        "shadowdom_controls": shadowdom_controls[:120],
        "hidden_start_response_candidates": hidden_start_response_candidates[:50],
        "delayed_render_detected": delayed_render_detected,
        "iframe_detected": iframe_detected,
        "shadowdom_detected": shadowdom_detected,
        "mutation_added_controls_count": mutation_added_controls_count,
        "hidden_control_reveal_attempts": hidden_control_reveal_attempts[:120],
        "successful_hidden_control_reveals": successful_hidden_control_reveals,
    }


async def _run_live_eligible_tender_discovery(page: Any, payload: Dict[str, Any], buyer_rfq: str) -> Dict[str, Any]:
    """V51 discovery pass for genuinely eSubmission-enabled live opportunities."""
    discovery_id = f"{_slug(buyer_rfq or _buyer_rfq_number(payload), 'v51-discovery')}__{_stamp()}"
    report_path = DEBUG_DIR / f"{discovery_id}__eligible_candidates_report.json"
    snapshot_dir = DEBUG_DIR / f"{discovery_id}__snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    target_views = [
        "Currently Advertised",
        "Open Tenders",
        "eSubmission",
        "Active Opportunities",
        "My Responses",
        "Recently Published",
    ]
    filter_sets = [
        {"name": "all_open", "search": "", "esubmission": None, "province": "", "category": "", "department": "", "closing_date": "not_expired"},
        {"name": "esubmission_true", "search": "", "esubmission": True, "province": "", "category": "", "department": "", "closing_date": "not_expired"},
        {"name": "supply_delivery", "search": "supply delivery", "esubmission": True, "province": "", "category": "Supplies", "department": "", "closing_date": "not_expired"},
        {"name": "delivery", "search": "delivery", "esubmission": True, "province": "", "category": "", "department": "", "closing_date": "not_expired"},
        {"name": "services_no_briefing", "search": "service", "esubmission": True, "province": "", "category": "Services", "department": "", "closing_date": "not_expired"},
        {"name": "national", "search": "", "esubmission": True, "province": "National", "category": "", "department": "", "closing_date": "not_expired"},
        {"name": "gauteng", "search": "", "esubmission": True, "province": "Gauteng", "category": "", "department": "", "closing_date": "not_expired"},
        {"name": "western_cape", "search": "", "esubmission": True, "province": "Western Cape", "category": "", "department": "", "closing_date": "not_expired"},
        {"name": "kwazulu_natal", "search": "", "esubmission": True, "province": "KwaZulu-Natal", "category": "", "department": "", "closing_date": "not_expired"},
        {"name": "recent_supply", "search": "supply", "esubmission": None, "province": "", "category": "", "department": "", "closing_date": "recent"},
    ]

    searched_views: List[Dict[str, Any]] = []
    searched_filter_sets: List[Dict[str, Any]] = []
    eligible_candidates: List[Dict[str, Any]] = []
    candidate_response_controls: List[Dict[str, Any]] = []
    page_snapshots: List[Dict[str, Any]] = []

    async def _snapshot(label: str) -> Dict[str, str]:
        html_path = snapshot_dir / f"{_slug(label, 'snapshot')}__page.html"
        png_path = snapshot_dir / f"{_slug(label, 'snapshot')}__page.png"
        try:
            html = await page.evaluate("() => document.documentElement.outerHTML")
            html_path.write_text(_safe_str(html), encoding="utf-8")
        except Exception:
            pass
        try:
            await page.screenshot(path=str(png_path), full_page=True)
        except Exception:
            png_path = Path("")
        return {"label": label, "html": str(html_path), "screenshot": str(png_path) if png_path else ""}

    async def _activate_view(view_name: str) -> Dict[str, Any]:
        if view_name == "Currently Advertised":
            try:
                await page.goto("https://www.etenders.gov.za/Home/opportunities?id=1", wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
                await page.wait_for_timeout(2000)
            except Exception:
                pass
        try:
            result = await page.evaluate(
                """({viewName}) => {
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                    const unsafe = /notification|bookmark|download|document|logout|login|register|captcha|recaptcha|final submit|submit bid|submit now/i;
                    const aliases = {
                        'currently advertised': [/currently advertised/i, /btnActive/i],
                        'open tenders': [/open tenders/i, /currently advertised/i, /active/i],
                        'esubmission': [/\\besubmission\\b/i, /e-submission/i, /electronic submission/i],
                        'active opportunities': [/active opportunities/i, /currently advertised/i, /active/i],
                        'my responses': [/my responses/i, /responses/i],
                        'recently published': [/recently published/i, /date published/i, /currently advertised/i]
                    };
                    const wanted = String(viewName || '').toLowerCase();
                    const patterns = aliases[wanted] || [new RegExp(viewName, 'i')];
                    const controls = Array.from(document.querySelectorAll('a,button,[role="tab"],[role="button"],li,label,input'));
                    const detected = controls.map((el, index) => {
                        const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                        const signature = `${text} ${el.id || ''} ${el.name || ''} ${el.className || ''} ${el.href || el.getAttribute('href') || ''}`;
                        return {
                            index,
                            text: text.slice(0, 180),
                            id: el.id || '',
                            name: el.name || '',
                            cls: typeof el.className === 'string' ? el.className : '',
                            href: el.href || el.getAttribute('href') || '',
                            visible: visible(el),
                            active: /active|selected|current/.test(String(el.className || '').toLowerCase()) || el.getAttribute('aria-selected') === 'true',
                            matches: patterns.some(pattern => pattern.test(signature)),
                            unsafe: unsafe.test(signature)
                        };
                    }).filter(item => item.text || item.id || item.name).slice(0, 120);
                    const target = controls.find(el => {
                        const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                        const signature = `${text} ${el.id || ''} ${el.name || ''} ${el.className || ''} ${el.href || el.getAttribute('href') || ''}`;
                        return visible(el) && !unsafe.test(signature) && patterns.some(pattern => pattern.test(signature));
                    });
                    if (target) {
                        try {
                            target.scrollIntoView({block: 'center', inline: 'center'});
                            target.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                            target.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                            target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                            HTMLElement.prototype.click.call(target);
                            return {view: viewName, activated: true, url: location.href, matched_text: clean(target.innerText || target.textContent || target.value || target.id || ''), detected};
                        } catch (e) {
                            return {view: viewName, activated: false, url: location.href, error: String(e), detected};
                        }
                    }
                    return {view: viewName, activated: false, url: location.href, reason: 'view_control_not_found', detected};
                }""",
                {"viewName": view_name},
            )
            await page.wait_for_timeout(1800)
            return result if isinstance(result, dict) else {"view": view_name, "activated": False}
        except Exception as exc:
            return {"view": view_name, "activated": False, "error": str(exc)}

    async def _apply_filter_set(filter_set: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await page.evaluate(
                """({filterSet}) => {
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const changes = [];
                    const search = String(filterSet.search || '');
                    const dispatch = (el) => {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true, key: search ? search.slice(-1) : 'Backspace'}));
                    };

                    for (const input of Array.from(document.querySelectorAll('.dataTables_filter input, input[type="search"]')).slice(0, 3)) {
                        const before = input.value || '';
                        input.value = search;
                        dispatch(input);
                        changes.push({type: 'datatable_search', before, after: input.value || ''});
                    }

                    if (filterSet.esubmission !== null && filterSet.esubmission !== undefined) {
                        for (const input of Array.from(document.querySelectorAll('input[type="checkbox"],input[type="radio"]'))) {
                            const signature = `${input.id || ''} ${input.name || ''} ${input.value || ''} ${input.className || ''}`.toLowerCase();
                            if (!/\\besubmission\\b|e-submission|electronic submission/.test(signature)) continue;
                            const before = !!input.checked;
                            if (/false|no|not/i.test(String(input.value || ''))) input.checked = !filterSet.esubmission;
                            else input.checked = !!filterSet.esubmission;
                            if (before !== !!input.checked) {
                                dispatch(input);
                                changes.push({type: 'esubmission_filter', selector: signature, before, after: !!input.checked});
                            }
                        }
                    }

                    const wanted = [filterSet.province, filterSet.category, filterSet.department].filter(Boolean);
                    for (const term of wanted) {
                        const lower = String(term).toLowerCase();
                        for (const select of Array.from(document.querySelectorAll('select')).slice(0, 20)) {
                            const signature = `${select.id || ''} ${select.name || ''} ${select.className || ''}`.toLowerCase();
                            if (!/province|category|department|organ|state|filter/.test(signature)) continue;
                            const option = Array.from(select.options || []).find(opt => clean(opt.textContent || opt.value || '').toLowerCase().includes(lower));
                            if (!option) continue;
                            const before = select.value || '';
                            select.value = option.value;
                            dispatch(select);
                            changes.push({type: 'select_filter', term, selector: signature, before, after: select.value || ''});
                            break;
                        }
                    }

                    if (changes.length) {
                        const filterButton = document.querySelector('#btnFilter, button[name*="filter" i], input[type="submit"][name*="filter" i]');
                        if (filterButton && !/final submit|submit bid|submit now|captcha/i.test(clean(filterButton.innerText || filterButton.textContent || filterButton.value || ''))) {
                            try {
                                filterButton.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                                filterButton.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                                filterButton.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                                HTMLElement.prototype.click.call(filterButton);
                                changes.push({type: 'filter_apply_click', selector: filterButton.id || filterButton.name || filterButton.className || filterButton.tagName});
                            } catch (e) {
                                changes.push({type: 'filter_apply_error', error: String(e)});
                            }
                        }
                    }
                    return {filter_set: filterSet, changes, url: location.href};
                }""",
                {"filterSet": filter_set},
            )
            await page.wait_for_timeout(2200)
            return result if isinstance(result, dict) else {"filter_set": filter_set, "changes": []}
        except Exception as exc:
            return {"filter_set": filter_set, "changes": [], "error": str(exc)}

    async def _collect_candidates(view_name: str, filter_set: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await page.evaluate(
                """({viewName, filterSet}) => {
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                    const cssPath = (el) => {
                        if (!el || !el.tagName) return '';
                        if (el.id) return `#${CSS.escape(el.id)}`;
                        const parts = [];
                        let node = el;
                        while (node && node.nodeType === 1 && parts.length < 6) {
                            let part = node.tagName.toLowerCase();
                            if (node.className && typeof node.className === 'string') part += node.className.trim().split(/\\s+/).filter(Boolean).slice(0, 3).map(c => `.${CSS.escape(c)}`).join('');
                            const parent = node.parentElement;
                            if (parent) {
                                const siblings = Array.from(parent.children).filter(child => child.tagName === node.tagName);
                                if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                            }
                            parts.unshift(part);
                            node = parent;
                        }
                        return parts.join(' > ');
                    };
                    const describeControl = (el) => {
                        const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                        const href = el.href || el.getAttribute('href') || '';
                        const onclick = el.getAttribute('onclick') || '';
                        const signature = `${text} ${el.id || ''} ${el.name || ''} ${el.className || ''} ${href} ${onclick}`.toLowerCase();
                        return {
                            selector: cssPath(el),
                            tag: el.tagName,
                            text: text.slice(0, 220),
                            id: el.id || '',
                            name: el.name || '',
                            cls: typeof el.className === 'string' ? el.className : '',
                            href,
                            onclick: onclick.slice(0, 300),
                            visible: visible(el),
                            response_like: /start response|startresponse|\\brespond\\b|submit quote|submit response|quote|\\besubmission\\b|e-submission/i.test(signature),
                            unsafe_like: /notification|bookmark|download|document|captcha|recaptcha|final submit|submit bid|submit now|logout|login/i.test(signature)
                        };
                    };
                    const parseDate = (text) => {
                        const m = String(text || '').match(/(\\d{1,2})\\/(\\d{1,2})\\/(\\d{4})/);
                        if (!m) return null;
                        return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]), 23, 59, 59);
                    };
                    const rows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'))
                        .filter(row => {
                            const text = clean(row.innerText || row.textContent || '');
                            const rect = row.getBoundingClientRect();
                            return text.length > 20 && rect.width > 0 && rect.height > 0 && !/category\\s+tender description\\s+esubmission/i.test(text);
                        });
                    const candidates = [];
                    rows.slice(0, 40).forEach((row, rowIndex) => {
                        const next = row.nextElementSibling && row.nextElementSibling.tagName === 'TR' ? row.nextElementSibling : null;
                        const roots = next ? [row, next] : [row];
                        const rowText = clean(roots.map(root => root.innerText || root.textContent || '').join(' '));
                        const lower = rowText.toLowerCase();
                        const headerLike = /category\\s+tender description\\s+esubmission\\s+advertised\\s+closing/i.test(rowText)
                            || /^currently advertised tenders\\s+category\\s+tender description/i.test(rowText)
                            || /^category\\s+tender description/i.test(rowText);
                        if (headerLike) return;
                        const controls = [];
                        const seen = new Set();
                        for (const root of roots) {
                            for (const el of Array.from(root.querySelectorAll('button,a,input,select,textarea,[role="button"],[onclick],[href],label,summary,.btn,.submitButtons,[tabindex]'))) {
                                if (seen.has(el)) continue;
                                seen.add(el);
                                controls.push(describeControl(el));
                            }
                        }
                        const responseControls = controls.filter(control => control.response_like && !control.unsafe_like);
                        const responseUrls = controls.map(control => control.href).filter(href => /esubmission|response|respond|quote/i.test(href || ''));
                        const hasESubmission = /\\besubmission\\b|e-submission|electronic submission/i.test(rowText) || responseControls.some(control => /esubmission|response|respond|quote/i.test(`${control.text} ${control.href} ${control.onclick}`));
                        const hasResponseKeywords = /start response|\\brespond\\b|submit response|submit quote|quote/i.test(rowText) || responseControls.length > 0 || responseUrls.length > 0;
                        const hasTenderEvidence = /tender number|organ of state|closing date|date published|\\b\\d{1,2}\\/\\d{1,2}\\/\\d{4}\\b|in \\d+ days|request for (bid|quotation|proposal|information)/i.test(rowText);
                        const open = /\\bopen\\b|active|available|currently advertised|in \\d+ days/i.test(rowText);
                        const closed = /\\bclosed\\b|awarded|cancelled|canceled|expired/i.test(rowText);
                        const briefingRequired = /compulsory briefing|mandatory briefing|briefing required/i.test(rowText);
                        const supplyDelivery = /supply|delivery|deliver|goods|equipment|material|services/i.test(rowText);
                        const closingDate = (rowText.match(/Closing Date:\\s*([^\\n\\r]+?)(?=\\s+(Place where|Special Conditions|ENQUIR|Briefing|Tender Number|$))/i) || rowText.match(/\\b\\d{1,2}\\/\\d{1,2}\\/\\d{4}\\b/i) || [])[1] || '';
                        const parsed = parseDate(rowText);
                        const notExpired = !parsed || parsed.getTime() >= Date.now();
                        let score = 0;
                        if (hasESubmission) score += 35;
                        if (hasResponseKeywords) score += 35;
                        if (responseControls.length) score += 20;
                        if (responseUrls.length) score += 15;
                        if (open) score += 15;
                        if (notExpired) score += 15;
                        if (supplyDelivery) score += 8;
                        if (!briefingRequired) score += 7;
                        if (closed || !notExpired) score -= 45;
                        if (briefingRequired) score -= 12;
                        if (!hasESubmission && !hasResponseKeywords) score -= 20;
                        if (!hasTenderEvidence) return;
                        if (!(hasESubmission || hasResponseKeywords || responseControls.length || responseUrls.length)) return;
                        if (score < 35) return;
                        candidates.push({
                            view: viewName,
                            filter_set_name: filterSet.name || '',
                            row_index: rowIndex,
                            confidence_score: Math.max(0, Math.min(100, score)),
                            row_text_preview: rowText.slice(0, 900),
                            eSubmission_indicators: {
                                has_esubmission_text: hasESubmission,
                                has_response_keywords: hasResponseKeywords,
                                open_or_active: open,
                                not_expired: notExpired,
                                supply_delivery: supplyDelivery,
                                briefing_required: briefingRequired,
                                closed_or_awarded_cancelled: closed
                            },
                            closing_date: closingDate,
                            response_keywords: Array.from(new Set((rowText.match(/eSubmission|e-submission|respond|start response|submit response|submit quote|quote|open|active|available/ig) || []).map(s => s.toLowerCase()))),
                            response_urls: responseUrls.slice(0, 10),
                            start_response_like_controls: responseControls.slice(0, 20),
                            control_count: controls.length
                        });
                    });
                    return {
                        url: location.href,
                        title: document.title || '',
                        view: viewName,
                        filter_set: filterSet,
                        visible_row_count: rows.length,
                        candidates
                    };
                }""",
                {"viewName": view_name, "filterSet": filter_set},
            )
        except Exception as exc:
            return {"view": view_name, "filter_set": filter_set, "visible_row_count": 0, "candidates": [], "error": str(exc)}

    for view_name in target_views:
        view_result = await _activate_view(view_name)
        searched_views.append(view_result)
        for filter_set in filter_sets:
            filter_result = await _apply_filter_set(filter_set)
            searched_filter_sets.append({
                "view": view_name,
                "filter_set": filter_set,
                "result": filter_result,
            })
            collected = await _collect_candidates(view_name, filter_set)
            candidates = collected.get("candidates") if isinstance(collected.get("candidates"), list) else []
            if candidates:
                snap = await _snapshot(f"{view_name}__{filter_set.get('name')}")
                page_snapshots.append({**snap, "view": view_name, "filter_set": filter_set.get("name"), "candidate_count": len(candidates)})
            for candidate in candidates:
                key = re.sub(r"\\W+", " ", _safe_str(candidate.get("row_text_preview"))).strip().lower()[:220]
                candidate["discovery_key"] = key
                candidate["page_snapshot"] = page_snapshots[-1] if candidates and page_snapshots else {}
                eligible_candidates.append(candidate)
                for control in candidate.get("start_response_like_controls") or []:
                    candidate_response_controls.append({**control, "view": view_name, "filter_set_name": filter_set.get("name"), "row_index": candidate.get("row_index")})
            if len(eligible_candidates) >= 25:
                break
        if len(eligible_candidates) >= 25:
            break

    deduped: Dict[str, Dict[str, Any]] = {}
    for candidate in eligible_candidates:
        key = candidate.get("discovery_key") or f"{candidate.get('view')}:{candidate.get('filter_set_name')}:{candidate.get('row_index')}"
        existing = deduped.get(key)
        if not existing or float(candidate.get("confidence_score") or 0) > float(existing.get("confidence_score") or 0):
            deduped[key] = candidate
    ranked = sorted(deduped.values(), key=lambda item: float(item.get("confidence_score") or 0), reverse=True)
    for idx, candidate in enumerate(ranked[:5]):
        shot_path = snapshot_dir / f"top_candidate_{idx + 1:02d}.png"
        try:
            await page.screenshot(path=str(shot_path), full_page=True)
            candidate["top_candidate_screenshot"] = str(shot_path)
        except Exception:
            candidate["top_candidate_screenshot"] = ""

    best = ranked[0] if ranked else None
    termination = "eligible_candidates_found" if ranked else "no_eligible_candidates_found"
    report = {
        "created_at": _now(),
        "buyer_rfq_number": buyer_rfq,
        "searched_views": searched_views,
        "searched_filter_sets": searched_filter_sets,
        "eligible_candidates_found": len(ranked),
        "eligible_candidates": ranked,
        "candidate_confidence_scores": [
            {
                "rank": idx + 1,
                "confidence_score": candidate.get("confidence_score"),
                "view": candidate.get("view"),
                "filter_set_name": candidate.get("filter_set_name"),
                "row_index": candidate.get("row_index"),
                "row_text_preview": candidate.get("row_text_preview"),
            }
            for idx, candidate in enumerate(ranked[:25])
        ],
        "best_candidate_summary": best,
        "candidate_response_controls": candidate_response_controls[:120],
        "discovery_termination_reason": termination,
        "page_snapshots": page_snapshots,
        "policy": {"allow_portal_final_submit": False, "final_submit_blocked": True},
    }
    _write_json(report_path, report)
    return {
        "searched_views": searched_views,
        "searched_filter_sets": searched_filter_sets,
        "eligible_candidates_found": len(ranked),
        "candidate_confidence_scores": report["candidate_confidence_scores"],
        "best_candidate_summary": best or {},
        "candidate_response_controls": candidate_response_controls[:120],
        "discovery_termination_reason": termination,
        "eligible_candidates_report_json": str(report_path),
        "top_candidate_screenshots": [c.get("top_candidate_screenshot") for c in ranked[:5] if c.get("top_candidate_screenshot")],
        "successful_discovery_page_snapshots": page_snapshots,
    }


async def _navigate_esubmission_view(page: Any, payload: Dict[str, Any], buyer_rfq: str) -> Dict[str, Any]:
    """Put ETenders into the most response-friendly listing view before row scanning."""
    scan_id = f"{_slug(buyer_rfq or _buyer_rfq_number(payload), 'esubmission-view')}__{_stamp()}"
    before_path = DEBUG_DIR / f"{scan_id}__before.json"
    after_path = DEBUG_DIR / f"{scan_id}__after.json"
    html_path = DEBUG_DIR / f"{scan_id}__page.html"
    screenshot_path = DEBUG_DIR / f"{scan_id}__page.png"

    async def _snapshot(label: str) -> Dict[str, Any]:
        try:
            return await page.evaluate(
                """({label}) => {
                    const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                    const cssPath = (el) => {
                        if (!el || !el.tagName) return '';
                        if (el.id) return `#${CSS.escape(el.id)}`;
                        const parts = [];
                        let node = el;
                        while (node && node.nodeType === 1 && parts.length < 6) {
                            let part = node.tagName.toLowerCase();
                            if (node.className && typeof node.className === 'string') {
                                part += node.className.trim().split(/\\s+/).filter(Boolean).slice(0, 3).map(c => `.${CSS.escape(c)}`).join('');
                            }
                            const parent = node.parentElement;
                            if (parent) {
                                const siblings = Array.from(parent.children).filter(child => child.tagName === node.tagName);
                                if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                            }
                            parts.unshift(part);
                            node = parent;
                        }
                        return parts.join(' > ');
                    };
                    const controls = Array.from(document.querySelectorAll('a,button,[role="tab"],[role="button"],li,input,select,textarea,label'))
                        .map((el, index) => {
                            const rect = el.getBoundingClientRect();
                            const style = getComputedStyle(el);
                            const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || el.placeholder || '');
                            const cls = typeof el.className === 'string' ? el.className : '';
                            const href = el.href || el.getAttribute('href') || '';
                            const signature = `${text} ${el.id || ''} ${cls} ${href} ${el.name || ''} ${el.getAttribute('role') || ''}`.toLowerCase();
                            const isTab = el.getAttribute('role') === 'tab' || /nav|tab|menu|pill|filter/.test(cls) || ['A', 'BUTTON', 'LI'].includes(el.tagName);
                            const isFilter = ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) || /filter|search|status|category|province|department|closing/.test(signature);
                            if (!isTab && !isFilter) return null;
                            return {
                                index,
                                tag: el.tagName,
                                selector: cssPath(el),
                                text: text.slice(0, 220),
                                id: el.id || '',
                                name: el.name || '',
                                cls,
                                role: el.getAttribute('role') || '',
                                href,
                                type: el.type || '',
                                value: el.value || '',
                                placeholder: el.placeholder || '',
                                aria_selected: el.getAttribute('aria-selected') || '',
                                active: /active|selected|current/.test(cls) || el.getAttribute('aria-selected') === 'true',
                                visible: visible(el),
                                hidden: el.hidden || style.display === 'none' || style.visibility === 'hidden',
                                disabled: !!el.disabled || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true',
                                bounding_box: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                                response_view_like: /\\besubmission\\b|e-submission|respond|my responses|open tenders|active opportunities|currently advertised/i.test(signature),
                                closed_view_like: /closed|awarded|cancelled|canceled|expired/i.test(signature),
                                unsafe_like: /notification|bookmark|download|document|logout|login|register|final submit|submit bid|submit now/i.test(signature),
                                filter_like: isFilter
                            };
                        })
                        .filter(Boolean)
                        .filter(item => item.visible || item.filter_like)
                        .slice(0, 180);
                    const rows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'))
                        .map(row => clean(row.innerText || row.textContent || ''))
                        .filter(text => text.length > 20)
                        .slice(0, 30);
                    const body = clean(document.body?.innerText || document.body?.textContent || '');
                    const activeTabs = controls.filter(item => item.active).map(item => item.text || item.id || item.href).filter(Boolean);
                    return {
                        label,
                        url: location.href,
                        title: document.title || '',
                        active_tab_name: activeTabs[0] || '',
                        detected_tabs: controls.filter(item => item.tag !== 'INPUT' && item.tag !== 'SELECT' && item.tag !== 'TEXTAREA' && (item.response_view_like || item.closed_view_like || item.active)).slice(0, 80),
                        detected_filters: controls.filter(item => item.filter_like).slice(0, 100),
                        visible_row_previews: rows,
                        page_indicators: {
                            has_esubmission_text: /\\besubmission\\b|e-submission|electronic submission/i.test(body),
                            has_respond_text: /\\brespond\\b|start response|submit response|submit quote/i.test(body),
                            has_open_text: /\\bopen\\b|available|currently advertised|active opportunities/i.test(body),
                            has_closed_text: /\\bclosed\\b|awarded|cancelled|canceled|expired/i.test(body)
                        },
                        html_preview: (document.body?.outerHTML || '').slice(0, 120000)
                    };
                }""",
                {"label": label},
            )
        except Exception as exc:
            return {"label": label, "url": _safe_str(getattr(page, "url", "")), "error": str(exc)}

    before = await _snapshot("before")
    _write_json(before_path, before)
    filter_changes: List[Dict[str, Any]] = []
    activated_esubmission_view = False

    try:
        navigation_result = await page.evaluate(
            """() => {
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const changes = [];
                const clickTarget = (el, reason) => {
                    if (!el || !visible(el) || el.disabled || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true') {
                        return false;
                    }
                    const signature = `${clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '')} ${el.id || ''} ${el.className || ''} ${el.href || el.getAttribute('href') || ''}`.toLowerCase();
                    if (/notification|bookmark|download|document|logout|login|register|final submit|submit bid|submit now/i.test(signature)) return false;
                    try {
                        el.scrollIntoView({block: 'center', inline: 'center'});
                        if (typeof el.focus === 'function') el.focus({preventScroll: true});
                        for (const type of ['mouseover', 'mousedown', 'mouseup', 'click']) {
                            el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                        }
                        HTMLElement.prototype.click.call(el);
                        changes.push({type: 'click', reason, text: clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '').slice(0, 180), id: el.id || '', href: el.href || el.getAttribute('href') || ''});
                        return true;
                    } catch (e) {
                        changes.push({type: 'click_error', reason, error: String(e)});
                        return false;
                    }
                };

                const candidates = Array.from(document.querySelectorAll('a,button,[role="tab"],[role="button"],li'))
                    .map(el => {
                        const text = clean(el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '');
                        const signature = `${text} ${el.id || ''} ${el.className || ''} ${el.href || el.getAttribute('href') || ''}`.toLowerCase();
                        let score = 0;
                        if (/\\besubmission\\b|e-submission|electronic submission/.test(signature)) score += 100;
                        if (/start response|respond|my responses|submit response|submit quote/.test(signature)) score += 75;
                        if (/open tenders|active opportunities|currently advertised/.test(signature)) score += 45;
                        if (/closed|awarded|cancelled|canceled|expired|notification|bookmark|download|document|logout|login|final submit|submit bid|submit now/.test(signature)) score -= 200;
                        if (!visible(el)) score -= 100;
                        if (el.disabled || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true') score -= 100;
                        return {el, score, text};
                    })
                    .filter(item => item.score > 0)
                    .sort((a, b) => b.score - a.score);
                let activated = false;
                if (candidates.length) activated = clickTarget(candidates[0].el, 'activate_esubmission_or_open_response_view');

                let filterDirty = false;
                for (const el of Array.from(document.querySelectorAll('input[type="checkbox"], input[type="radio"]'))) {
                    const signature = `${el.id || ''} ${el.name || ''} ${el.className || ''} ${el.value || ''}`.toLowerCase();
                    if (!/\\besubmission\\b|e-submission|electronic submission/.test(signature)) continue;
                    const previous = !!el.checked;
                    if (/false|no|not/i.test(String(el.value || ''))) el.checked = false;
                    else el.checked = true;
                    if (previous !== !!el.checked) {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        filterDirty = true;
                        changes.push({type: 'checkbox_change', selector: signature, before: previous, after: !!el.checked});
                    }
                }

                for (const el of Array.from(document.querySelectorAll('select'))) {
                    const signature = `${el.id || ''} ${el.name || ''} ${el.className || ''}`.toLowerCase();
                    if (!/\\besubmission\\b|e-submission|status|state|open|active|response|respond/.test(signature)) continue;
                    const previous = el.value || '';
                    let selected = false;
                    for (const option of Array.from(el.options || [])) {
                        const text = clean(option.textContent || option.value || '').toLowerCase();
                        if (/\\besubmission\\b|e-submission|respond|open|active|currently advertised/.test(text) && !/closed|awarded|cancelled|canceled|expired/.test(text)) {
                            el.value = option.value;
                            selected = true;
                            break;
                        }
                    }
                    if (!selected && /closed|awarded|cancelled|canceled|expired/.test(String(el.value || '').toLowerCase())) {
                        el.selectedIndex = 0;
                        selected = true;
                    }
                    if (selected && previous !== el.value) {
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        filterDirty = true;
                        changes.push({type: 'select_change', selector: signature, before: previous, after: el.value});
                    }
                }

                for (const el of Array.from(document.querySelectorAll('input,textarea'))) {
                    const signature = `${el.id || ''} ${el.name || ''} ${el.className || ''} ${el.placeholder || ''}`.toLowerCase();
                    const value = String(el.value || '');
                    if (!value) continue;
                    const shouldClear = /filter|search|status|category|province|department|closing|datatable/.test(signature)
                        || /closed|awarded|cancelled|canceled|expired|notification/.test(value.toLowerCase());
                    if (!shouldClear) continue;
                    const before = el.value;
                    el.value = '';
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true, key: 'Backspace'}));
                    filterDirty = true;
                    changes.push({type: 'input_clear', selector: signature, before: String(before).slice(0, 180), after: ''});
                }
                if (filterDirty) {
                    const filterButton = document.querySelector('#btnFilter, button[name*="filter" i], input[type="submit"][name*="filter" i], button:has(i.fa-search)');
                    if (filterButton && !/final submit|submit bid|submit now/i.test(clean(filterButton.innerText || filterButton.textContent || filterButton.value || ''))) {
                        try {
                            filterButton.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                            filterButton.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                            filterButton.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                            HTMLElement.prototype.click.call(filterButton);
                            changes.push({type: 'filter_apply_click', selector: filterButton.id || filterButton.name || filterButton.className || filterButton.tagName});
                        } catch (e) {
                            changes.push({type: 'filter_apply_error', error: String(e)});
                        }
                    }
                }
                return {activated, changes};
            }"""
        )
        if isinstance(navigation_result, dict):
            activated_esubmission_view = bool(navigation_result.get("activated"))
            filter_changes = navigation_result.get("changes") if isinstance(navigation_result.get("changes"), list) else []
    except Exception as exc:
        filter_changes.append({"type": "navigator_error", "error": str(exc)})

    try:
        await page.wait_for_timeout(2500)
    except Exception:
        pass
    after = await _snapshot("after")
    _write_json(after_path, after)
    try:
        html_path.write_text(_safe_str(after.get("html_preview")), encoding="utf-8")
    except Exception:
        pass
    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        screenshot_path = Path("")

    detected_tabs = after.get("detected_tabs") if isinstance(after.get("detected_tabs"), list) else []
    detected_filters = after.get("detected_filters") if isinstance(after.get("detected_filters"), list) else []
    no_esubmission_root_cause = ""
    page_indicators = after.get("page_indicators") if isinstance(after.get("page_indicators"), dict) else {}
    post_filter_esubmission_candidates_count = sum(
        1 for text in (after.get("visible_row_previews") or [])
        if re.search(r"\\besubmission\\b|e-submission|respond|start response|submit response|submit quote", _safe_str(text), re.I)
    )
    if post_filter_esubmission_candidates_count == 0:
        no_esubmission_root_cause = "no_visible_esubmission_rows_after_view_filter_navigation"
    elif not page_indicators.get("has_esubmission_text") and not page_indicators.get("has_respond_text"):
        no_esubmission_root_cause = "active_view_has_no_esubmission_or_response_indicators"
    elif any(item.get("closed_view_like") and item.get("active") for item in detected_tabs if isinstance(item, dict)):
        no_esubmission_root_cause = "closed_or_non_active_tab_selected"

    return {
        "initial_portal_view": {
            "url": before.get("url"),
            "title": before.get("title"),
            "active_tab_name": before.get("active_tab_name"),
            "page_indicators": before.get("page_indicators") or {},
        },
        "detected_tabs": detected_tabs,
        "detected_filters": detected_filters,
        "activated_esubmission_view": activated_esubmission_view,
        "filter_changes": filter_changes,
        "post_filter_scanned_rows_count": len(after.get("visible_row_previews") or []),
        "post_filter_esubmission_candidates_count": post_filter_esubmission_candidates_count,
        "no_esubmission_root_cause": no_esubmission_root_cause,
        "view_debug_artifacts": {
            "before": str(before_path),
            "after": str(after_path),
            "html": str(html_path),
            "screenshot": str(screenshot_path) if screenshot_path else "",
        },
    }


async def _select_maaa_and_start_response(page: Any, payload: Optional[Dict[str, Any]] = None, buyer_rfq: str = "") -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    steps: List[Dict[str, Any]] = []
    diagnostics: Dict[str, Any] = {
        "active_tab_name": "",
        "start_response_clicked": False,
        "categorieslist_visible": False,
        "response_session_started": False,
        "response_workspace_loaded": False,
        "persistent_expanded_row": False,
        "workspace_recovered": False,
        "url_before_start_response": "",
        "url_after_start_response": "",
        "url_transition_detected": False,
        "response_workspace_url": "",
        "response_workspace_title": "",
        "active_iframe_url": "",
        "dom_replacement_detected": False,
        "workspace_transition_success": False,
        "iframe_modal_detection": {},
        "expanded_row_controls": [],
        "attempted_click_targets": [],
        "click_dispatch_results": [],
        "secondary_confirmation_controls": [],
        "start_response_debug_artifact": None,
        "expanded_row_html_artifact": None,
        "scanned_rows_count": 0,
        "skipped_rows_count": 0,
        "successful_workspace_transition_count": 0,
        "row_classification": [],
        "summary_counts_by_reason": {},
        "top_possible_candidates": [],
        "start_response_candidates": [],
        "visible_controls": [],
        "hidden_controls": [],
        "delayed_controls": [],
        "iframe_controls": [],
        "shadowdom_controls": [],
        "hidden_start_response_candidates": [],
        "delayed_render_detected": False,
        "iframe_detected": False,
        "shadowdom_detected": False,
        "mutation_added_controls_count": 0,
        "hidden_control_reveal_attempts": [],
        "successful_hidden_control_reveals": 0,
        "selected_row_index": None,
        "workspace_transition_url": "",
        "scan_termination_reason": "",
        "initial_portal_view": {},
        "detected_tabs": [],
        "detected_filters": [],
        "activated_esubmission_view": False,
        "filter_changes": [],
        "post_filter_scanned_rows_count": 0,
        "post_filter_esubmission_candidates_count": 0,
        "no_esubmission_root_cause": "",
        "view_debug_artifacts": {},
        "searched_views": [],
        "searched_filter_sets": [],
        "eligible_candidates_found": 0,
        "candidate_confidence_scores": [],
        "best_candidate_summary": {},
        "candidate_response_controls": [],
        "discovery_termination_reason": "",
        "eligible_candidates_report_json": "",
        "top_candidate_screenshots": [],
        "successful_discovery_page_snapshots": [],
        "before_start_response_screenshot": None,
        "after_start_response_activation_screenshot": None,
    }

    diagnostics["before_start_response_screenshot"] = await _capture(page, buyer_rfq or _buyer_rfq_number(payload), "before_start_response")
    persistence_probe = await _workspace_persistence_probe(page, payload)
    steps.append({"step": "workspace_persistence_probe", "result": persistence_probe})
    diagnostics["persistent_expanded_row"] = bool(
        persistence_probe.get("expanded_workspace_likely")
        or persistence_probe.get("start_response_visible")
        or persistence_probe.get("start_response_hidden")
    )
    diagnostics["iframe_modal_detection"] = {
        "iframe_count": persistence_probe.get("iframe_count", 0),
        "iframes": persistence_probe.get("iframes", []),
        "modal_count": persistence_probe.get("modal_count", 0),
        "modals": persistence_probe.get("modals", []),
        "start_response_controls": persistence_probe.get("start_response_controls", []),
    }
    diagnostics["url_before_start_response"] = _safe_str(persistence_probe.get("url") or getattr(page, "url", ""))

    initial_state = await _response_workspace_state(page)
    steps.append({"step": "initial_response_workspace_state", "result": initial_state})
    diagnostics.update({
        "active_tab_name": initial_state.get("active_tab_name") or "",
        "categorieslist_visible": bool(initial_state.get("categorieslist_visible")),
        "response_session_started": bool(initial_state.get("response_session_started")),
        "response_workspace_loaded": bool(initial_state.get("response_workspace_loaded")),
    })
    if diagnostics["response_workspace_loaded"]:
        transition_snapshot = await _workspace_transition_snapshot(page, payload)
        steps.append({"step": "initial_loaded_transition_snapshot", "result": transition_snapshot})
        diagnostics["response_workspace_url"] = transition_snapshot.get("response_workspace_url") or diagnostics["url_before_start_response"]
        diagnostics["response_workspace_title"] = transition_snapshot.get("response_workspace_title") or ""
        diagnostics["active_iframe_url"] = transition_snapshot.get("active_iframe_url") or ""
        diagnostics["dom_replacement_detected"] = bool(transition_snapshot.get("dom_replacement_detected"))
        diagnostics["workspace_transition_success"] = bool(transition_snapshot.get("workspace_transition_success"))
        return {"status": "ok", "steps": steps, **diagnostics}

    view_nav = await _navigate_esubmission_view(page, payload, buyer_rfq or _buyer_rfq_number(payload))
    steps.append({
        "step": "navigate_esubmission_view",
        "result": {
            "activated_esubmission_view": view_nav.get("activated_esubmission_view"),
            "filter_changes": view_nav.get("filter_changes"),
            "post_filter_scanned_rows_count": view_nav.get("post_filter_scanned_rows_count"),
            "post_filter_esubmission_candidates_count": view_nav.get("post_filter_esubmission_candidates_count"),
            "no_esubmission_root_cause": view_nav.get("no_esubmission_root_cause"),
        },
    })
    for key in [
        "initial_portal_view",
        "detected_tabs",
        "detected_filters",
        "activated_esubmission_view",
        "filter_changes",
        "post_filter_scanned_rows_count",
        "post_filter_esubmission_candidates_count",
        "no_esubmission_root_cause",
        "view_debug_artifacts",
    ]:
        diagnostics[key] = view_nav.get(key)

    live_discovery = await _run_live_eligible_tender_discovery(page, payload, buyer_rfq or _buyer_rfq_number(payload))
    steps.append({
        "step": "v51_live_eligible_tender_discovery",
        "result": {
            "eligible_candidates_found": live_discovery.get("eligible_candidates_found"),
            "best_candidate_summary": live_discovery.get("best_candidate_summary"),
            "discovery_termination_reason": live_discovery.get("discovery_termination_reason"),
            "eligible_candidates_report_json": live_discovery.get("eligible_candidates_report_json"),
        },
    })
    for key in [
        "searched_views",
        "searched_filter_sets",
        "eligible_candidates_found",
        "candidate_confidence_scores",
        "best_candidate_summary",
        "candidate_response_controls",
        "discovery_termination_reason",
        "eligible_candidates_report_json",
        "top_candidate_screenshots",
        "successful_discovery_page_snapshots",
    ]:
        diagnostics[key] = live_discovery.get(key)

    scan = await _multi_row_autonomous_portal_scan(page, payload, buyer_rfq or _buyer_rfq_number(payload))
    steps.append({
        "step": "multi_row_autonomous_portal_scan",
        "result": {
            "scanned_rows_count": scan.get("scanned_rows_count"),
            "skipped_rows_count": scan.get("skipped_rows_count"),
            "successful_workspace_transition_count": scan.get("successful_workspace_transition_count"),
            "selected_row_index": scan.get("selected_row_index"),
            "workspace_transition_url": scan.get("workspace_transition_url"),
            "scan_termination_reason": scan.get("scan_termination_reason"),
        },
    })
    for key in [
        "scanned_rows_count",
        "skipped_rows_count",
        "successful_workspace_transition_count",
        "row_classification",
        "summary_counts_by_reason",
        "top_possible_candidates",
        "start_response_candidates",
        "visible_controls",
        "hidden_controls",
        "delayed_controls",
        "iframe_controls",
        "shadowdom_controls",
        "hidden_start_response_candidates",
        "delayed_render_detected",
        "iframe_detected",
        "shadowdom_detected",
        "mutation_added_controls_count",
        "hidden_control_reveal_attempts",
        "successful_hidden_control_reveals",
        "selected_row_index",
        "workspace_transition_url",
        "scan_termination_reason",
    ]:
        diagnostics[key] = scan.get(key)
    if not any(
        (row.get("eligibility_signals") or {}).get("has_esubmission_text")
        or (row.get("eligibility_signals") or {}).get("has_respond_text")
        or row.get("eligible_candidate_count")
        or row.get("hidden_possible_candidate_count")
        for row in (diagnostics.get("row_classification") or [])
        if isinstance(row, dict)
    ) and not diagnostics.get("no_esubmission_root_cause"):
        diagnostics["no_esubmission_root_cause"] = "no_esubmission_indicators_found_after_view_filter_navigation"
    if scan.get("successful_workspace_transition_count"):
        diagnostics["workspace_transition_success"] = True
        diagnostics["response_workspace_loaded"] = True
        diagnostics["response_workspace_url"] = scan.get("workspace_transition_url") or _safe_str(getattr(page, "url", ""))
        diagnostics["after_start_response_activation_screenshot"] = scan.get("successful_transition_screenshot") or await _capture(
            page,
            buyer_rfq or _buyer_rfq_number(payload),
            "after_start_response_activation",
        )
        return {"status": "ok", "steps": steps, **diagnostics}

    for attempt in range(1, 5):
        probe = await _workspace_persistence_probe(page, payload)
        steps.append({"step": "pre_attempt_workspace_probe", "attempt": attempt, "result": probe})
        diagnostics["persistent_expanded_row"] = bool(
            diagnostics["persistent_expanded_row"]
            or probe.get("expanded_workspace_likely")
            or probe.get("start_response_visible")
            or probe.get("start_response_hidden")
        )

        if probe.get("listing_likely") and not (probe.get("start_response_visible") or probe.get("start_response_hidden")):
            recovery = await _recover_expanded_row_if_collapsed(page, payload)
            steps.append({"step": "recover_expanded_row_if_collapsed", "attempt": attempt, "result": recovery})
            diagnostics["workspace_recovered"] = bool(diagnostics["workspace_recovered"] or recovery.get("recovered"))
            probe = await _workspace_persistence_probe(page, payload)
            steps.append({"step": "post_recovery_workspace_probe", "attempt": attempt, "result": probe})

        if not (probe.get("expanded_workspace_likely") or probe.get("start_response_visible") or probe.get("start_response_hidden")):
            tab_actions = await _force_currently_advertised_tab(page)
            steps.append({"step": "hard_lock_currently_advertised", "attempt": attempt, "actions": tab_actions})
        else:
            steps.append({"step": "hard_lock_currently_advertised", "attempt": attempt, "status": "skipped_persistent_workspace_active"})

        await _select_supplier_if_present(page, steps)

        before = await _response_workspace_state(page)
        steps.append({"step": "before_start_response_click", "attempt": attempt, "result": before})

        observer = await _install_start_response_mutation_observer(page)
        steps.append({"step": "install_start_response_mutation_observer", "attempt": attempt, "result": observer})

        debug = await _start_response_interaction_debugger(page, payload, buyer_rfq or _buyer_rfq_number(payload))
        steps.append({
            "step": "start_response_interaction_debugger",
            "attempt": attempt,
            "result": {
                "debug_artifact": debug.get("debug_artifact"),
                "expanded_row_html_path": debug.get("expanded_row_html_path"),
                "expanded_row_control_count": len(debug.get("expanded_row_controls") or []),
                "attempted_click_target_count": len(debug.get("attempted_click_targets") or []),
                "click_dispatch_result_count": len(debug.get("click_dispatch_results") or []),
            },
        })
        diagnostics["expanded_row_controls"] = debug.get("expanded_row_controls") or diagnostics.get("expanded_row_controls") or []
        diagnostics["attempted_click_targets"] = debug.get("attempted_click_targets") or diagnostics.get("attempted_click_targets") or []
        diagnostics["click_dispatch_results"] = debug.get("click_dispatch_results") or diagnostics.get("click_dispatch_results") or []
        diagnostics["secondary_confirmation_controls"] = debug.get("secondary_confirmation_controls") or diagnostics.get("secondary_confirmation_controls") or []
        diagnostics["start_response_debug_artifact"] = debug.get("debug_artifact")
        diagnostics["expanded_row_html_artifact"] = debug.get("expanded_row_html_path")

        click_result = await _click_start_response_once(page)
        steps.append({"step": "start_response_click_attempt", "attempt": attempt, "result": click_result})
        diagnostics["start_response_clicked"] = bool(diagnostics["start_response_clicked"] or click_result.get("clicked"))

        if not click_result.get("clicked"):
            frame_click = await _click_start_response_in_frames(page)
            steps.append({"step": "start_response_iframe_click_attempt", "attempt": attempt, "result": frame_click})
            diagnostics["start_response_clicked"] = bool(diagnostics["start_response_clicked"] or frame_click.get("clicked"))

        try:
            await page.wait_for_function(
                """() => {
                    const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                    const categories = document.querySelector('#categorieslist');
                    const text = (document.body.innerText || document.body.textContent || '').toLowerCase();
                    const responseLike = /responding to|select supplier|submit now|save response|tender response|esubmission/.test(text);
                    const uploadLike = /upload|add document|browse|choose file|attach|submit now|submission checklist/.test(text);
                    const mutation = window.__lmcpStartResponseTransition || {};
                    return visible(categories) || (responseLike && uploadLike) || mutation.workspaceContainerInjected || mutation.iframeInjected || mutation.modalInjected;
                }""",
                timeout=12000,
            )
        except Exception as exc:
            steps.append({"step": "start_response_transition_wait", "attempt": attempt, "status": "timeout", "error": str(exc)})

        for hydration_round in range(1, 4):
            await page.wait_for_timeout(1500)
            transition_snapshot = await _workspace_transition_snapshot(page, payload)
            steps.append({
                "step": "workspace_transition_snapshot",
                "attempt": attempt,
                "hydration_round": hydration_round,
                "result": transition_snapshot,
            })
            diagnostics["response_workspace_url"] = transition_snapshot.get("response_workspace_url") or diagnostics.get("response_workspace_url") or ""
            diagnostics["response_workspace_title"] = transition_snapshot.get("response_workspace_title") or diagnostics.get("response_workspace_title") or ""
            diagnostics["active_iframe_url"] = transition_snapshot.get("active_iframe_url") or diagnostics.get("active_iframe_url") or ""
            diagnostics["dom_replacement_detected"] = bool(diagnostics["dom_replacement_detected"] or transition_snapshot.get("dom_replacement_detected"))
            diagnostics["workspace_transition_success"] = bool(diagnostics["workspace_transition_success"] or transition_snapshot.get("workspace_transition_success"))
            if transition_snapshot.get("workspace_transition_success"):
                break

        if not diagnostics["workspace_transition_success"]:
            frame_retry = await _click_start_response_in_frames(page)
            steps.append({"step": "start_response_iframe_retry_after_hydration", "attempt": attempt, "result": frame_retry})
            diagnostics["start_response_clicked"] = bool(diagnostics["start_response_clicked"] or frame_retry.get("clicked"))
            if frame_retry.get("clicked"):
                await page.wait_for_timeout(3000)

        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
            steps.append({"step": "workspace_hydration_wait", "attempt": attempt, "status": "networkidle"})
        except Exception as exc:
            steps.append({"step": "workspace_hydration_wait", "attempt": attempt, "status": "timeout", "error": str(exc)})

        after = await _response_workspace_state(page)
        steps.append({"step": "after_start_response_click", "attempt": attempt, "result": after})
        after_probe = await _workspace_persistence_probe(page, payload)
        steps.append({"step": "after_start_response_workspace_probe", "attempt": attempt, "result": after_probe})
        transition_snapshot = await _workspace_transition_snapshot(page, payload)
        steps.append({"step": "after_hydration_transition_snapshot", "attempt": attempt, "result": transition_snapshot})
        diagnostics.update({
            "active_tab_name": after.get("active_tab_name") or diagnostics.get("active_tab_name") or "",
            "categorieslist_visible": bool(after.get("categorieslist_visible")),
            "response_session_started": bool(after.get("response_session_started")),
            "response_workspace_loaded": bool(after.get("response_workspace_loaded") or transition_snapshot.get("workspace_transition_success")),
        })
        diagnostics["url_after_start_response"] = _safe_str(after_probe.get("url") or getattr(page, "url", ""))
        diagnostics["url_transition_detected"] = bool(
            diagnostics["url_after_start_response"]
            and diagnostics["url_before_start_response"]
            and diagnostics["url_after_start_response"] != diagnostics["url_before_start_response"]
        )
        diagnostics["response_workspace_url"] = transition_snapshot.get("response_workspace_url") or diagnostics.get("response_workspace_url") or diagnostics["url_after_start_response"]
        diagnostics["response_workspace_title"] = transition_snapshot.get("response_workspace_title") or diagnostics.get("response_workspace_title") or _safe_str(after_probe.get("title"))
        diagnostics["active_iframe_url"] = transition_snapshot.get("active_iframe_url") or diagnostics.get("active_iframe_url") or ""
        diagnostics["dom_replacement_detected"] = bool(diagnostics["dom_replacement_detected"] or transition_snapshot.get("dom_replacement_detected"))
        diagnostics["workspace_transition_success"] = bool(diagnostics["workspace_transition_success"] or transition_snapshot.get("workspace_transition_success"))
        diagnostics["iframe_modal_detection"] = {
            "iframe_count": after_probe.get("iframe_count", 0),
            "iframes": after_probe.get("iframes", []),
            "modal_count": after_probe.get("modal_count", 0),
            "modals": after_probe.get("modals", []),
            "start_response_controls": after_probe.get("start_response_controls", []),
        }

        if diagnostics["response_session_started"] or diagnostics["response_workspace_loaded"] or diagnostics["workspace_transition_success"]:
            diagnostics["after_start_response_activation_screenshot"] = await _capture(
                page,
                buyer_rfq or _buyer_rfq_number(payload),
                "after_start_response_activation",
            )
            return {"status": "ok", "steps": steps, **diagnostics}

    diagnostics["after_start_response_activation_screenshot"] = await _capture(
        page,
        buyer_rfq or _buyer_rfq_number(payload),
        "after_start_response_activation",
    )
    if not diagnostics.get("response_workspace_url"):
        diagnostics["response_workspace_url"] = _safe_str(getattr(page, "url", ""))
    if not diagnostics.get("response_workspace_title"):
        try:
            diagnostics["response_workspace_title"] = _safe_str(await page.title())
        except Exception:
            diagnostics["response_workspace_title"] = ""
    return {"status": "not_started", "steps": steps, **diagnostics}


async def _close_blocking_overlays(page: Any) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []

    # eTenders sometimes opens a blocking "Login Required" / feature-alert modal
    # even when the storage_state is authenticated. This closes/removes only UI overlays;
    # it does not bypass CAPTCHA or login.
    selectors = [
        "button:has-text('Close')",
        "a:has-text('Close')",
        "text=Close",
        "button:has-text('Got it')",
        "button:has-text('Got it, Thanks')",
        "text=Got it, Thanks!",
        ".modal button.close",
        ".modal .close",
        "[data-dismiss='modal']",
        "[aria-label='Close']",
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            if count <= 0:
                attempts.append({"selector": selector, "status": "not_found"})
                continue

            for i in range(min(count, 5)):
                try:
                    await loc.nth(i).click(force=True, timeout=3000)
                    attempts.append({"selector": selector, "index": i, "status": "clicked"})
                    await page.wait_for_timeout(500)
                except Exception as exc:
                    attempts.append({"selector": selector, "index": i, "status": "failed", "error": str(exc)})
        except Exception as exc:
            attempts.append({"selector": selector, "status": "failed", "error": str(exc)})

    try:
        removed = await page.evaluate(
            """() => {
                let removed = 0;

                const closeTexts = ['close', 'got it', 'got it, thanks', '×'];
                const closers = Array.from(document.querySelectorAll('button, a, span, div'));
                for (const el of closers) {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
                    if (closeTexts.includes(text) || closeTexts.includes(aria)) {
                        try { el.click(); } catch (e) {}
                    }
                }

                const modalSelectors = [
                    '.modal-backdrop',
                    '.modal',
                    '.overlay',
                    '.popup',
                    '.dialog',
                    '[role="dialog"]',
                    '.swal2-container',
                    '.bootbox',
                    '.fade.in'
                ];

                for (const sel of modalSelectors) {
                    for (const node of Array.from(document.querySelectorAll(sel))) {
                        const text = (node.innerText || node.textContent || '').toLowerCase();
                        if (
                            text.includes('login required') ||
                            text.includes('new feature alert') ||
                            text.includes('bookmark') ||
                            text.includes('logged-in') ||
                            text.includes('got it') ||
                            sel === '.modal-backdrop'
                        ) {
                            try {
                                node.remove();
                                removed += 1;
                            } catch (e) {}
                        }
                    }
                }

                document.body.classList.remove('modal-open');
                document.body.style.overflow = 'auto';
                document.body.style.paddingRight = '0px';

                return removed;
            }"""
        )
        attempts.append({"step": "dom_overlay_cleanup", "status": "ok", "removed": removed})
    except Exception as exc:
        attempts.append({"step": "dom_overlay_cleanup", "status": "failed", "error": str(exc)})

    await page.wait_for_timeout(1500)

    return {"status": "ok", "attempts": attempts}


async def _upload_files(page: Any, files: List[str]) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []

    overlay_cleanup = await _close_blocking_overlays(page)
    attempts.append({"step": "close_blocking_overlays", "result": overlay_cleanup})

    # STEP 1: Open the eTenders upload UI area.
    open_upload = await _force_click_by_text(page, "Upload", wait_ms=3500)
    attempts.append({"step": "force_open_upload", "result": open_upload})

    if not open_upload.get("clicked"):
        add_doc = await _force_click_by_text(page, "Add", wait_ms=3000)
        attempts.append({"step": "force_open_add", "result": add_doc})

    if not open_upload.get("clicked"):
        browse = await _force_click_by_text(page, "Browse", wait_ms=3000)
        attempts.append({"step": "force_open_browse", "result": browse})

    await page.wait_for_timeout(3500)

    # STEP 2: First try classic file input upload if eTenders exposes it.
    try:
        await page.evaluate(
            """() => {
                const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
                for (const input of inputs) {
                    input.removeAttribute('hidden');
                    input.style.display = 'block';
                    input.style.visibility = 'visible';
                    input.style.opacity = '1';
                    input.style.position = 'relative';
                    input.style.width = '300px';
                    input.style.height = '40px';
                }
                return inputs.length;
            }"""
        )
    except Exception as exc:
        attempts.append({"step": "unhide_file_inputs", "status": "failed", "error": str(exc)})

    file_inputs = page.locator('input[type="file"], input[type=file], input[accept]')
    try:
        count = await file_inputs.count()
    except Exception:
        count = 0

    for i in range(count):
        try:
            await file_inputs.nth(i).set_input_files(files, timeout=DEFAULT_TIMEOUT_MS)
            await page.wait_for_timeout(3500)
            attempts.append({"step": "set_input_files", "status": "ok", "input_index": i, "file_count": len(files)})

            follow_up = await _click_first(
                page,
                [
                    "button:has-text('Upload')",
                    "button:has-text('Save')",
                    "button:has-text('Add')",
                    "button:has-text('Done')",
                    "button:has-text('OK')",
                    "button:has-text('Continue')",
                    "text=Upload",
                    "text=Save",
                    "text=Add",
                    "text=Done",
                    "text=OK",
                ],
                wait_ms=2500,
            )
            attempts.append({"step": "post_file_input_confirm", "result": follow_up})

            return {
                "status": "ok",
                "uploaded": True,
                "documents_uploaded": True,
                "attachments_uploaded": True,
                "method": "file_input",
                "uploaded_files": files,
                "uploaded_count": len(files),
                "attempts": attempts,
            }
        except Exception as exc:
            attempts.append({"step": "set_input_files", "status": "failed", "input_index": i, "error": str(exc)})

    # STEP 3: Drag/drop uploader fallback.
    # Browser JS cannot fetch local file:// paths for security, so we create an input in page DOM,
    # attach files through Playwright, then dispatch drag/drop/change events using that File object.
    try:
        await page.evaluate(
            """() => {
                let input = document.querySelector('#lmcp-hidden-upload-input');
                if (!input) {
                    input = document.createElement('input');
                    input.id = 'lmcp-hidden-upload-input';
                    input.type = 'file';
                    input.multiple = true;
                    input.style.position = 'fixed';
                    input.style.left = '10px';
                    input.style.top = '10px';
                    input.style.zIndex = '2147483647';
                    input.style.opacity = '0.01';
                    document.body.appendChild(input);
                }
            }"""
        )

        hidden_input = page.locator("#lmcp-hidden-upload-input")
        await hidden_input.set_input_files(files, timeout=DEFAULT_TIMEOUT_MS)
        attempts.append({"step": "dragdrop_hidden_input_files", "status": "ok", "file_count": len(files)})

        drag_result = await page.evaluate(
            """async () => {
                const input = document.querySelector('#lmcp-hidden-upload-input');
                if (!input || !input.files || input.files.length === 0) {
                    return {ok: false, reason: 'hidden input has no files'};
                }

                const files = Array.from(input.files);
                const dataTransfer = new DataTransfer();
                for (const file of files) {
                    dataTransfer.items.add(file);
                }

                const selectors = [
                    '[id*="upload"]',
                    '[class*="upload"]',
                    '[id*="drop"]',
                    '[class*="drop"]',
                    '[id*="document"]',
                    '[class*="document"]',
                    '[id*="file"]',
                    '[class*="file"]',
                    '.modal',
                    'form',
                    'main',
                    'body'
                ];

                const targets = [];
                for (const selector of selectors) {
                    for (const el of Array.from(document.querySelectorAll(selector))) {
                        if (!targets.includes(el)) targets.push(el);
                    }
                }

                const events = ['dragenter', 'dragover', 'drop', 'change', 'input'];
                let fired = 0;

                for (const target of targets) {
                    try {
                        target.scrollIntoView({block: 'center', inline: 'center'});
                    } catch (e) {}

                    for (const eventName of events) {
                        try {
                            let event;
                            if (eventName === 'change' || eventName === 'input') {
                                event = new Event(eventName, {bubbles: true, cancelable: true});
                            } else {
                                event = new DragEvent(eventName, {
                                    bubbles: true,
                                    cancelable: true,
                                    dataTransfer: dataTransfer
                                });
                            }
                            target.dispatchEvent(event);
                            fired += 1;
                        } catch (e) {}
                    }
                }

                return {
                    ok: fired > 0,
                    fired,
                    target_count: targets.length,
                    file_names: files.map(f => f.name)
                };
            }"""
        )
        attempts.append({"step": "drag_drop_dispatch", "result": drag_result})

        await page.wait_for_timeout(5000)

        # Confirm if the page now mentions the file name or uploaded state.
        body = await _body_text(page)
        lower = body.lower()
        file_hits = []
        for f in files:
            name = Path(f).name.lower()
            if name and name in lower:
                file_hits.append(Path(f).name)

        uploaded_markers = [
            "uploaded",
            "successfully uploaded",
            "file uploaded",
            "document uploaded",
            "attached",
            "remove file",
            "delete file",
            "completed",
        ]
        marker_hit = any(m in lower for m in uploaded_markers)

        if drag_result.get("ok") and (file_hits or marker_hit):
            return {
                "status": "ok",
                "uploaded": True,
                "documents_uploaded": True,
                "attachments_uploaded": True,
                "method": "drag_drop_injection",
                "uploaded_files": files,
                "uploaded_count": len(files),
                "file_name_hits": file_hits,
                "marker_hit": marker_hit,
                "attempts": attempts,
            }

        # The drag event fired but the portal gave no visible confirmation.
        # Return verification_required instead of claiming success.
        return {
            "status": "verification_required",
            "uploaded": False,
            "method": "drag_drop_injection",
            "reason": "Drag/drop events were dispatched, but no upload confirmation was visible.",
            "file_name_hits": file_hits,
            "marker_hit": marker_hit,
            "attempts": attempts,
            "body_excerpt": body[:1500],
        }

    except Exception as exc:
        attempts.append({"step": "drag_drop_injection", "status": "failed", "error": str(exc)})

    # STEP 4: Diagnostics if all upload strategies fail.
    try:
        visible_text = await page.evaluate(
            """() => Array.from(document.querySelectorAll('button,a,label,span,div,input'))
                .map(e => ({
                    text: (e.innerText || e.textContent || e.getAttribute('aria-label') || e.getAttribute('value') || '').trim(),
                    tag: e.tagName,
                    id: e.id || '',
                    cls: e.className || '',
                    type: e.getAttribute('type') || '',
                    name: e.getAttribute('name') || ''
                }))
                .filter(x => x.text || x.id || x.cls || x.type || x.name)
                .slice(0, 160)"""
        )
    except Exception:
        visible_text = []

    return {
        "status": "no_file_input",
        "uploaded": False,
        "attempts": attempts,
        "visible_text_probe": visible_text,
        "message": "No usable file-input or confirmed drag/drop upload target was found.",
    }


async def _submit_now(page: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    allow = _policy_allows_final_submit(payload)
    if not allow.get("allowed"):
        return {
            "status": "blocked",
            "submitted": False,
            "reason": "Final submit is blocked by policy.",
            "final_block_reason": "allow_portal_final_submit=false",
            "policy": allow,
        }

    text = await _body_text(page)
    if _captcha_detected_text(text):
        return {
            "status": "blocked",
            "submitted": False,
            "reason": "CAPTCHA/security challenge detected. Manual action required.",
        }

    attempts: List[Dict[str, Any]] = []

    return {
        "status": "blocked",
        "submitted": False,
        "portal_auto_submitted": False,
        "submission_status": "not_submitted",
        "reason": "Final submit automation is disabled in V48 stabilization mode.",
        "final_block_reason": "final_submit_disabled_by_guard",
        "attempts": attempts,
        "body_excerpt": text[:1200],
    }

    # Unreachable production submit implementation intentionally retained behind
    # the guard above for future controlled-mode review.
    normal_click = await _click_first(page, [], wait_ms=4000)

    if normal_click.get("clicked"):
        confirm = await _click_first(
            page,
            [
                "button:has-text('Yes')",
                "button:has-text('Confirm')",
                "button:has-text('OK')",
                "button:has-text('Submit')",
                "text=Yes",
                "text=Confirm",
                "text=OK",
            ],
            wait_ms=4000,
        )
        attempts.append({"step": "normal_confirm_click", "result": confirm})

        after_text = await _body_text(page)
        lower = after_text.lower()
        submitted_signal = any(
            marker in lower
            for marker in [
                "submitted successfully",
                "submission successful",
                "bid submitted",
                "response submitted",
                "successfully submitted",
                "submission received",
            ]
        )

        if submitted_signal:
            return {
                "status": "ok",
                "submitted": True,
                "method": "normal_submit",
                "attempts": attempts,
                "body_excerpt": after_text[:1200],
            }

    # STEP 2: Force-enable the disabled eTenders submit button, then click it.
    # This does not bypass CAPTCHA. It only removes the disabled UI state after upload handoff.
    try:
        force_state = await page.evaluate(
            """() => {
                const buttons = [];
                const byId = document.querySelector('#esub-submit');
                if (byId) buttons.push(byId);

                for (const el of Array.from(document.querySelectorAll('button, a, input[type="button"], input[type="submit"]'))) {
                    const text = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                    if (text.includes('submit')) buttons.push(el);
                }

                let changed = 0;
                for (const btn of buttons) {
                    try {
                        btn.removeAttribute('disabled');
                        btn.removeAttribute('aria-disabled');
                        btn.classList.remove('disabled');
                        btn.classList.remove('esub-action-buttons');
                        btn.disabled = false;
                        btn.style.pointerEvents = 'auto';
                        btn.style.opacity = '1';
                        changed += 1;
                    } catch (e) {}
                }

                return {
                    changed,
                    submit_exists: !!document.querySelector('#esub-submit'),
                    button_count: buttons.length
                };
            }"""
        )
        attempts.append({"step": "force_enable_submit", "status": "ok", "result": force_state})
    except Exception as exc:
        attempts.append({"step": "force_enable_submit", "status": "failed", "error": str(exc)})

    await page.wait_for_timeout(1500)

    forced_click = await _click_first(
        page,
        [
            "#esub-submit",
            "button#esub-submit",
            "button:has-text('Submit now')",
            "text=Submit now",
            "button:has-text('Submit')",
            "text=Submit",
        ],
        wait_ms=5000,
    )
    attempts.append({"step": "forced_submit_click", "result": forced_click})

    if not forced_click.get("clicked"):
        # Last-resort DOM click, useful when Playwright still sees disabled state.
        try:
            clicked = await page.evaluate(
                """() => {
                    const btn = document.querySelector('#esub-submit') ||
                        Array.from(document.querySelectorAll('button, a, input')).find((el) => {
                            const text = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                            return text.includes('submit');
                        });
                    if (!btn) return false;
                    btn.removeAttribute('disabled');
                    btn.removeAttribute('aria-disabled');
                    btn.classList.remove('disabled');
                    btn.disabled = false;
                    btn.style.pointerEvents = 'auto';
                    btn.scrollIntoView({block: 'center', inline: 'center'});
                    btn.click();
                    return true;
                }"""
            )
            await page.wait_for_timeout(5000)
            attempts.append({"step": "dom_forced_submit_click", "status": "ok" if clicked else "not_found", "clicked": bool(clicked)})
        except Exception as exc:
            attempts.append({"step": "dom_forced_submit_click", "status": "failed", "error": str(exc)})

    # STEP 3: Confirm any modal/dialog after forced click.
    confirm = await _click_first(
        page,
        [
            "button:has-text('Yes')",
            "button:has-text('Confirm')",
            "button:has-text('OK')",
            "button:has-text('Submit')",
            "text=Yes",
            "text=Confirm",
            "text=OK",
        ],
        wait_ms=4000,
    )
    attempts.append({"step": "forced_confirm_click", "result": confirm})

    after_text = await _body_text(page)
    lower = after_text.lower()

    submitted_signal = any(
        marker in lower
        for marker in [
            "submitted successfully",
            "submission successful",
            "bid submitted",
            "response submitted",
            "successfully submitted",
            "submission received",
        ]
    )

    forced_attempted = (
        forced_click.get("clicked")
        or any(a.get("step") == "dom_forced_submit_click" and a.get("clicked") for a in attempts)
    )

    if submitted_signal:
        return {
            "status": "ok",
            "submitted": True,
            "portal_auto_submitted": True,
            "submission_status": "submitted",
            "method": "forced_submit_with_success_signal",
            "verification_level": "visible_success_confirmation",
            "attempts": attempts,
            "body_excerpt": after_text[:1200],
        }

    confirm_clicked = any(
        a.get("step") == "forced_confirm_click"
        and isinstance(a.get("result"), dict)
        and a["result"].get("clicked") is True
        for a in attempts
    )

    if forced_attempted and confirm_clicked:
        return {
            "status": "ok",
            "submitted": True,
            "portal_auto_submitted": True,
            "submission_status": "submitted",
            "method": "forced_submit_and_confirm_click",
            "verification_level": "click_confirmed_no_visible_success_message",
            "verification_note": (
                "Production mode accepted the submission because eTenders submit and confirmation clicks both executed. "
                "The portal did not expose a visible success confirmation, so proof screenshots and JSON audit trail were saved."
            ),
            "attempts": attempts,
            "body_excerpt": after_text[:1200],
        }

    if forced_attempted:
        return {
            "status": "submitted_pending_verification",
            "submitted": False,
            "portal_auto_submitted": False,
            "submission_status": "verification_required",
            "method": "forced_submit_click_without_confirm",
            "reason": "Submit click was forced, but confirmation click or visible success signal was not detected.",
            "attempts": attempts,
            "body_excerpt": after_text[:1200],
        }

    return {
        "status": "not_submitted",
        "submitted": False,
        "portal_auto_submitted": False,
        "submission_status": "not_submitted",
        "reason": "Submit button was not found or could not be clicked, even after force-enable fallback.",
        "attempts": attempts,
        "body_excerpt": after_text[:1200],
    }


async def run_final_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(payload if isinstance(payload, dict) else {})

    buyer_rfq = _buyer_rfq_number(payload)
    quote_number = _quote_number(payload)
    portal_url = _normalise_portal_url(payload)
    attachments = _normalise_attachments(payload)
    resolved = _resolve_attachments(attachments)
    files = resolved.get("resolved", [])
    state_file = _resolve_state_file()

    result: Dict[str, Any] = {
        "status": "started",
        "service_version": "V47_5_FINAL_SUBMISSION_ENGINE_PRODUCTION_LOCKED",
        "buyer_rfq_number": buyer_rfq,
        "quote_number": quote_number,
        "portal_url": portal_url,
        "attachments": attachments,
        "attachment_resolution": resolved,
        "started_at": _now(),
        "headless": HEADLESS,
        "profile_dir": str(PROFILE_DIR),
        "storage_state_file": state_file,
        "cdp_resolved": None,
        "profile_mode": "unopened",
        "auth_mode": "unknown",
        "matched_row": payload.get("matched_row"),
        "final_block_reason": None,
        "workspace_page_reused": False,
        "workspace_page_selection": [],
    }

    if not portal_url:
        result.update({"status": "error", "submitted": False, "reason": "portal_url is required."})
        return result

    manual_completion_gate = _manual_completion_final_gate(payload)
    result["manual_completion_gate"] = manual_completion_gate
    result["manual_completion_required"] = True
    result["manual_completion_allowed"] = bool(manual_completion_gate.get("allowed"))
    result["manual_completion_blocked_reason"] = manual_completion_gate.get("blocked_reason") or ""

    if not manual_completion_gate.get("allowed"):
        result.update(
            {
                "status": "blocked",
                "submitted": False,
                "reason": manual_completion_gate.get("blocked_reason") or "Manual completion record is required before final submission.",
                "blocked_reason": manual_completion_gate.get("blocked_reason") or "Manual completion record is required before final submission.",
                "final_block_reason": manual_completion_gate.get("blocked_reason") or "Manual completion record is required before final submission.",
                "finished_at": _now(),
            }
        )
        _append_json(ASSISTED_FILE, result)
        _write_json(LAST_RESULT_FILE, result)
        return result

    if not files:
        result.update({"status": "assisted_required", "submitted": False, "reason": "No existing attachment files were provided."})
        _append_json(ASSISTED_FILE, result)
        _write_json(LAST_RESULT_FILE, result)
        return result

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        result.update({"status": "assisted_required", "submitted": False, "reason": "Playwright is unavailable.", "error": str(exc)})
        _append_json(ASSISTED_FILE, result)
        _write_json(LAST_RESULT_FILE, result)
        return result

    browser = None
    context = None
    page = None
    owns_context = True
    owns_browser = True

    try:
        async with async_playwright() as p:
            # Prefer live operator Chrome via CDP. This reuses the browser session
            # where the operator has already logged into ETenders.
            cdp_resolution = _resolve_cdp_endpoint(payload.get("cdp_url"))
            result["cdp_resolved"] = cdp_resolution

            if cdp_resolution.get("ok"):
                try:
                    browser = await p.chromium.connect_over_cdp(cdp_resolution["resolved_websocket_url"])
                    owns_browser = False
                    if browser.contexts:
                        context = browser.contexts[0]
                        owns_context = False
                    else:
                        context = await browser.new_context(accept_downloads=True)
                    result["profile_mode"] = "live_cdp"
                    result["auth_mode"] = "live_cdp"
                except Exception as exc:
                    result["cdp_connect_error"] = str(exc)
                    browser = None
                    context = None

            if context is None:
                launch_kwargs = {
                    "user_data_dir": str(PROFILE_DIR),
                    "headless": HEADLESS,
                    "accept_downloads": True,
                    "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                }
                if Path(CHROME).exists() and not HEADLESS:
                    launch_kwargs["executable_path"] = CHROME
                try:
                    context = await p.chromium.launch_persistent_context(**launch_kwargs)
                    result["profile_mode"] = "persistent_profile"
                    result["auth_mode"] = "persistent_profile"
                except Exception as exc:
                    result["persistent_profile_error"] = str(exc)

            if context is None and state_file:
                browser = await p.chromium.launch(
                    headless=HEADLESS,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                )
                context = await browser.new_context(storage_state=state_file, accept_downloads=True)
                result["profile_mode"] = "storage_state"
                result["auth_mode"] = "storage_state"

            if context is None:
                result.update({
                    "status": "manual_login_required",
                    "submitted": False,
                    "reason": "No live CDP session, persistent profile, or storage_state could be opened.",
                    "final_block_reason": "no_authenticated_browser_context",
                })
                _append_json(ASSISTED_FILE, result)
                _write_json(LAST_RESULT_FILE, result)
                return result

            page_selection: Dict[str, Any] = {}
            if result.get("profile_mode") == "live_cdp":
                page_selection = await _select_persistent_workspace_page(context, payload, portal_url)
                page = page_selection.get("page")
                result["workspace_page_reused"] = bool(page_selection.get("reused_existing_page"))
                result["workspace_page_selection"] = page_selection.get("diagnostics") or []
            else:
                page = await context.new_page()

            if page is None:
                page = await context.new_page()

            page.set_default_timeout(DEFAULT_TIMEOUT_MS)

            if not result.get("workspace_page_reused"):
                current_url = _safe_str(getattr(page, "url", ""))
                if not current_url or current_url == "about:blank":
                    await page.goto(portal_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
                await page.wait_for_timeout(3500)
            else:
                try:
                    await page.bring_to_front()
                except Exception:
                    pass
                await page.wait_for_timeout(1000)

            result["opened_screenshot"] = await _capture(page, buyer_rfq, "opened")

            state = await _is_logged_in(page)
            result["initial_login_state"] = state
            result["authenticated_indicators_found"] = state.get("authenticated_indicators_found") or []
            result["auth_diagnostic_screenshot"] = await _capture(page, buyer_rfq, "auth_diagnostic")

            if state.get("captcha_detected"):
                result.update(
                    {
                        "status": "assisted_required",
                        "submitted": False,
                        "reason": "CAPTCHA/security challenge detected or storage_state expired.",
                        "final_block_reason": "captcha_or_security_challenge",
                        "captcha_screenshot": await _capture(page, buyer_rfq, "captcha"),
                    }
                )
                if page:
                    await page.close()
                if owns_context:
                    await context.close()
                if browser and owns_browser:
                    await browser.close()
                _append_json(ASSISTED_FILE, result)
                _write_json(LAST_RESULT_FILE, result)
                return result

            if not state.get("logged_in"):
                result.update({
                    "status": "manual_login_required",
                    "submitted": False,
                    "reason": f"{result.get('auth_mode') or 'browser'} is missing or not authenticated.",
                    "final_block_reason": "not_authenticated",
                })
                if page:
                    await page.close()
                if owns_context:
                    await context.close()
                if browser and owns_browser:
                    await browser.close()
                _append_json(ASSISTED_FILE, result)
                _write_json(LAST_RESULT_FILE, result)
                return result

            result["start_response_result"] = await _select_maaa_and_start_response(page, payload, buyer_rfq)
            result["after_start_screenshot"] = await _capture(page, buyer_rfq, "after_start_response")

            upload = await _upload_files(page, files)
            result["upload_result"] = upload
            result["after_upload_screenshot"] = await _capture(page, buyer_rfq, "after_upload")

            upload_status = _safe_lower(upload.get("status"))
            upload_handoff_accepted = bool(upload.get("uploaded")) or upload_status in {"ok", "verification_required"}

            if not upload_handoff_accepted:
                result.update({"status": "assisted_required", "submitted": False, "reason": "Upload could not be confirmed or handed off before final submit."})
                result["final_block_reason"] = "upload_not_confirmed"
                if page:
                    await page.close()
                if owns_context:
                    await context.close()
                if browser and owns_browser:
                    await browser.close()
                _append_json(ASSISTED_FILE, result)
                _write_json(LAST_RESULT_FILE, result)
                return result

            if upload_status == "verification_required" and not upload.get("uploaded"):
                result["upload_verification_note"] = (
                    "Upload handoff was accepted because drag/drop events were dispatched, "
                    "but eTenders did not expose a visible upload confirmation in the DOM."
                )

            submit = await _submit_now(page, payload)
            result["submit_result"] = submit
            result["final_block_reason"] = submit.get("final_block_reason") or submit.get("reason")
            result["after_submit_screenshot"] = await _capture(page, buyer_rfq, "after_submit")

            proof_file = PROOF_DIR / f"{_slug(buyer_rfq)}__{_slug(quote_number)}__{_stamp()}__final_submission_proof.json"

            if submit.get("submitted"):
                result.update(
                    {
                        "status": "ok",
                        "submitted": True,
                        "portal_auto_submitted": True,
                        "submission_status": "submitted",
                        "submitted_at": _now(),
                        "proof_file": str(proof_file),
                    }
                )
            else:
                result.update(
                    {
                        "status": "submitted_unverified" if submit.get("status") == "submitted_unverified" else "assisted_required",
                        "submitted": False,
                        "portal_auto_submitted": False,
                        "submission_status": "verification_required",
                        "reason": submit.get("reason") or "Final submit could not be verified.",
                        "proof_file": str(proof_file),
                    }
                )

            _write_json(proof_file, result)
            _write_json(LAST_RESULT_FILE, result)
            _append_json(HISTORY_FILE, result)
            if page:
                await page.close()
            if owns_context:
                await context.close()
            if browser and owns_browser:
                await browser.close()
            return result

    except Exception as exc:
        result.update(
            {
                "status": "assisted_required",
                "submitted": False,
                "error": str(exc),
                "reason": "Final submission automation failed and requires manual review.",
                "finished_at": _now(),
            }
        )
        try:
            if page:
                await page.close()
            if context and owns_context:
                await context.close()
            if browser and owns_browser:
                await browser.close()
        except Exception:
            pass
        _append_json(ASSISTED_FILE, result)
        _write_json(LAST_RESULT_FILE, result)
        return result


async def final_submit(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await run_final_submission(payload)


async def upload_documents(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await run_final_submission(payload)


def get_final_submission_status(limit: int = 50) -> Dict[str, Any]:
    history = _read_json(HISTORY_FILE, [])
    assisted = _read_json(ASSISTED_FILE, [])
    last = _read_json(LAST_RESULT_FILE, {})

    if not isinstance(history, list):
        history = []
    if not isinstance(assisted, list):
        assisted = []

    submitted_total = len([x for x in history if isinstance(x, dict) and x.get("submitted") is True])

    return {
        "status": "ok",
        "service_version": "V47_5_FINAL_SUBMISSION_ENGINE_PRODUCTION_LOCKED",
        "summary": {
            "history_total": len(history),
            "submitted_total": submitted_total,
            "assisted_total": len(assisted),
            "headless": HEADLESS,
            "profile_dir": str(PROFILE_DIR),
            "storage_state_file": _resolve_state_file(),
        },
        "last_result": last,
        "recent_history": history[-limit:],
        "recent_assisted": assisted[-limit:],
        "files": {
            "history": str(HISTORY_FILE),
            "assisted": str(ASSISTED_FILE),
            "last_result": str(LAST_RESULT_FILE),
            "screenshots": str(SCREENSHOT_DIR),
            "proofs": str(PROOF_DIR),
            "storage_state": str(STATE_FILE),
        },
        "updated_at": _now(),
    }


def get_v47_5_status(limit: int = 50):
    return get_final_submission_status(limit=limit)


async def guarded_final_submission(
    autofill_plan_json=None,
    cdp_url="http://host.docker.internal:9222",
    output_dir=None,
    attachments=None,
    confirmation_phrase=None,
    dry_run=True,
    allow_final_submit=False,
    execute_final_submit=False,
    capture_screenshots=True,
    wait_after_click_ms=3000,
    pack_id=None,
    payload=None,
):
    if payload is None:
        payload = {}

    # Load autofill plan metadata so guarded final submission receives
    # buyer_rfq_number, quote_number, portal_url, upload_files, and form_values.
    if autofill_plan_json:
        try:
            import json
            from pathlib import Path
            plan_path = Path(str(autofill_plan_json))
            if plan_path.exists():
                plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                if isinstance(plan_data, dict):
                    payload.update(plan_data)
                    if isinstance(plan_data.get("form_values"), dict):
                        payload.update({k: v for k, v in plan_data["form_values"].items() if v is not None})
        except Exception as exc:
            payload["autofill_plan_load_error"] = str(exc)

    resolved_attachments = (
        attachments
        or payload.get("attachments")
        or payload.get("upload_files")
        or []
    )

    # Normalize attachment objects into actual filesystem paths.
    normalized_attachments = []

    for item in resolved_attachments:
        if isinstance(item, dict):
            path_value = item.get("path")
            if path_value:
                normalized_attachments.append(path_value)
        elif isinstance(item, str):
            normalized_attachments.append(item)

    resolved_attachments = normalized_attachments

    payload.update({
        "autofill_plan_json": autofill_plan_json,
        "cdp_url": cdp_url,
        "output_dir": output_dir,
        "attachments": resolved_attachments,
        "confirmation_phrase": confirmation_phrase,
        "dry_run": bool(dry_run),
        "allow_final_submit": bool(allow_final_submit or execute_final_submit),
        "execute_final_submit": bool(execute_final_submit),
        "capture_screenshots": bool(capture_screenshots),
        "wait_after_click_ms": int(wait_after_click_ms),
        "pack_id": pack_id,
        "policy": {
            **(payload.get("policy") if isinstance(payload.get("policy"), dict) else {}),
            "allow_portal_final_submit": bool(allow_final_submit or execute_final_submit),
        },
    })

    return await run_final_submission(payload)
