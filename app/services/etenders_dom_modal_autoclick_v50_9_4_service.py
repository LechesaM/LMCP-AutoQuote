"""
LMCP V50.9.4 - eTenders DOM + Modal Auto-Dismiss + Attachment Auto-Click Engine

Purpose:
- V50.9.3 solved Docker -> Chrome CDP connectivity and network interception.
- The remaining issue is that eTenders can show modals/overlays and the table may not be
  searched/expanded/clicked during the capture window.
- This engine attaches to live Chrome CDP, opens eTenders opportunities, dismisses modals,
  searches for the RFQ, expands matching rows, clicks likely document/attachment anchors,
  captures download/network events, and saves files/logs.

Routes:
    GET  /v50-9-4-dom-modal-autoclick/status
    POST /v50-9-4-dom-modal-autoclick/capture

Drop-in:
    app/services/etenders_dom_modal_autoclick_v50_9_4_service.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urljoin, urlparse

import requests


SERVICE_VERSION = "V50.9.4_ETENDERS_DOM_MODAL_AUTOCLICK"

DEFAULT_CDP_URL = "http://host.docker.internal:9222"
DEFAULT_OUTPUT_DIR = "runtime/playwright/downloads"
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"
DEFAULT_PLAYWRIGHT_CHROMIUM_EXECUTABLE = "/Users/cash/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
DEFAULT_PLAYWRIGHT_HEADLESS_SHELL_EXECUTABLE = "/Users/cash/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-arm64/chrome-headless-shell"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalise_match_text(value: Any) -> str:
    text = str(value or "").upper()
    text = text.replace("/", " ").replace("-", " ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _match_tokens(value: Any) -> List[str]:
    return [token for token in _normalise_match_text(value).split() if len(token) >= 2]


def _build_target_terms(data: Dict[str, str]) -> List[str]:
    raw_values = [
        data.get("tender_id", ""),
        data.get("search_text", ""),
        data.get("filename", ""),
        data.get("support_document_id", ""),
    ]

    terms: List[str] = []
    for raw in raw_values:
        value = _clean(raw)
        if value and value not in terms:
            terms.append(value)
        for part in re.split(r"[\s/\\,_:;|()-]+", value):
            part = part.strip()
            if len(part) >= 4 and part not in terms:
                terms.append(part)

    compact = re.sub(r"[^A-Za-z0-9]+", "", " ".join(raw_values)).upper()
    tender_id = _clean(data.get("tender_id", ""))
    if tender_id.upper() == "JDAMARK-DIGITALBOOK-05-2026" or "JDAMARKDIGITALBOOK052026" in compact:
        for term in ["JDAMARK", "DIGITALBOOK", "DIGITAL BOOK", "05/2026", "05-2026"]:
            if term not in terms:
                terms.append(term)

    return terms


def _score_row_text(row_text: str, target_terms: List[str]) -> Dict[str, Any]:
    row_norm = _normalise_match_text(row_text)
    row_tokens = set(_match_tokens(row_text))
    target_tokens = set()
    matched_terms: List[str] = []

    for term in target_terms:
        term_norm = _normalise_match_text(term)
        if not term_norm:
            continue
        tokens = set(_match_tokens(term))
        target_tokens.update(tokens)
        if term_norm in row_norm or row_norm in term_norm:
            matched_terms.append(term)

    matched_tokens = sorted(token for token in target_tokens if token in row_tokens)
    token_overlap = len(matched_tokens) / max(len(target_tokens), 1)
    term_score = len(matched_terms) / max(len([t for t in target_terms if _normalise_match_text(t)]), 1)
    score = max(token_overlap, term_score)

    return {
        "score": round(score, 4),
        "matched_terms": matched_terms,
        "matched_tokens": matched_tokens,
        "row_normalized": row_norm[:500],
        "target_tokens": sorted(target_tokens),
    }


def _safe_filename(filename: str, fallback: str = "etenders_document.pdf") -> str:
    name = _clean(filename) or fallback
    name = name.replace("\\", "_").replace("/", "_").replace(":", "_")
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip().strip(". ")
    if not name:
        name = fallback
    if len(name) > 180:
        stem = Path(name).stem[:150]
        suffix = Path(name).suffix or ".pdf"
        name = f"{stem}{suffix}"
    return name


def _resolve_cdp_endpoint(cdp_url: str) -> Dict[str, Any]:
    cdp_url = _clean(cdp_url).rstrip("/")

    if not cdp_url:
        return {
            "ok": False,
            "input_cdp_url": "",
            "version_url": "",
            "status_code": 0,
            "raw_websocket_url": "",
            "resolved_websocket_url": "",
            "json": None,
            "error": "empty_cdp_url",
        }

    # Accept a direct websocket endpoint as already resolved.
    if cdp_url.startswith("ws://") or cdp_url.startswith("wss://"):
        return {
            "ok": True,
            "input_cdp_url": cdp_url,
            "version_url": "",
            "status_code": 200,
            "raw_websocket_url": cdp_url,
            "resolved_websocket_url": cdp_url,
            "json": None,
            "error": "",
            "mode": "direct_websocket",
        }

    version_url = f"{cdp_url}/json/version"
    result = {
        "ok": False,
        "input_cdp_url": cdp_url,
        "version_url": version_url,
        "status_code": 0,
        "raw_websocket_url": "",
        "resolved_websocket_url": "",
        "json": None,
        "error": "",
    }

    try:
        response = requests.get(version_url, headers={"Host": "localhost:9222"}, timeout=8)
        result["status_code"] = response.status_code
        if response.status_code != 200:
            result["error"] = f"cdp_version_status_{response.status_code}:{response.text[:300]}"
            return result

        data = response.json()
        raw_ws = data.get("webSocketDebuggerUrl") or ""
        resolved_ws = raw_ws

        if cdp_url.startswith("http://host.docker.internal"):
            resolved_ws = resolved_ws.replace("ws://localhost:9222", "ws://host.docker.internal:9222")
            resolved_ws = resolved_ws.replace("ws://127.0.0.1:9222", "ws://host.docker.internal:9222")
        elif cdp_url.startswith("http://gateway.docker.internal"):
            resolved_ws = resolved_ws.replace("ws://localhost:9222", "ws://gateway.docker.internal:9222")
            resolved_ws = resolved_ws.replace("ws://127.0.0.1:9222", "ws://gateway.docker.internal:9222")

        result.update({
            "ok": bool(resolved_ws),
            "raw_websocket_url": raw_ws,
            "resolved_websocket_url": resolved_ws,
            "json": data,
        })
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    if not text:
        return bool(default)
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return bool(default)


def _looks_relevant_url(url: str) -> bool:
    low = (url or "").lower()
    return any(x in low for x in [
        "download", "document", "support", "file", "sharepoint", "tender",
        ".pdf", ".doc", ".xls", ".zip", "paginatedtenderopportunities",
    ])


def _looks_relevant_response(headers: Dict[str, str], url: str = "") -> bool:
    ctype = str(headers.get("content-type") or headers.get("Content-Type") or "").lower()
    cdisp = str(headers.get("content-disposition") or headers.get("Content-Disposition") or "").lower()
    return (
        "application/pdf" in ctype
        or "application/octet-stream" in ctype
        or "application/zip" in ctype
        or "application/vnd" in ctype
        or "application/msword" in ctype
        or "attachment" in cdisp
        or "filename" in cdisp
        or _looks_relevant_url(url)
    )


def _extract_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    tender_id = _clean(payload.get("tender_id") or payload.get("tenderId") or payload.get("id"))
    support_document_id = _clean(
        payload.get("supportDocumentID")
        or payload.get("support_document_id")
        or payload.get("document_guid")
        or payload.get("documentGuid")
        or payload.get("guid")
    )
    filename = _clean(payload.get("filename") or payload.get("fileName") or payload.get("document_name"))
    tender_title = _clean(payload.get("tender_title") or payload.get("title"))
    buyer = _clean(payload.get("buyer") or payload.get("buyer_name") or payload.get("procuring_entity"))
    reference_number = _clean(
        payload.get("reference_number")
        or payload.get("rfq_number")
        or payload.get("tender_number")
        or payload.get("tender_no")
    )
    search_text = _clean(payload.get("search_text") or tender_title or reference_number or tender_id or "DIGITAL BOOK JDA")
    detail_page_url = _clean(payload.get("detail_page_url") or payload.get("detailUrl"))
    opportunities_url = _clean(payload.get("opportunities_url") or payload.get("opportunitiesUrl"))
    tender_url = _clean(payload.get("tender_url") or detail_page_url or opportunities_url or ETENDERS_OPPORTUNITIES)

    return {
        "tender_id": tender_id,
        "support_document_id": support_document_id,
        "filename": filename,
        "search_text": search_text,
        "title": tender_title,
        "buyer": buyer,
        "buyer_name": buyer,
        "reference_number": reference_number,
        "detail_page_url": detail_page_url,
        "opportunities_url": opportunities_url,
        "tender_url": tender_url,
    }


def _is_etenders_detail_url(url: str) -> bool:
    cleaned = _clean(url).lower()
    return "etenders.gov.za" in cleaned and "/home/tenderdetails" in cleaned


def _is_etenders_opportunities_url(url: str) -> bool:
    cleaned = _clean(url).lower()
    return "etenders.gov.za" in cleaned and "/home/opportunities" in cleaned


def _resolve_helper_urls(data: Dict[str, str]) -> Dict[str, Any]:
    detail_page_url = _clean(data.get("detail_page_url"))
    opportunities_url = _clean(data.get("opportunities_url"))
    tender_url = _clean(data.get("tender_url"))

    if not detail_page_url and _is_etenders_detail_url(tender_url):
        detail_page_url = tender_url
    if not opportunities_url and _is_etenders_opportunities_url(tender_url):
        opportunities_url = tender_url
    if not opportunities_url:
        opportunities_url = ETENDERS_OPPORTUNITIES

    helper_input_url = detail_page_url or opportunities_url or tender_url or ETENDERS_OPPORTUNITIES
    helper_preserved_query_params = bool(
        (detail_page_url and urlparse(detail_page_url).query)
        or (opportunities_url and urlparse(opportunities_url).query)
    )

    return {
        "detail_page_url": detail_page_url,
        "opportunities_url": opportunities_url,
        "helper_input_url": helper_input_url,
        "detail_page_url_available": bool(detail_page_url),
        "opportunities_url_available": bool(opportunities_url),
        "helper_preserved_query_params": helper_preserved_query_params,
    }


async def _dismiss_modals(page) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    # Try common modal/cookie/overlay buttons.
    button_texts = [
        "Accept", "I Accept", "OK", "Ok", "Close", "Continue", "Proceed",
        "Got it", "Agree", "Dismiss", "No thanks", "×", "x",
    ]

    for text in button_texts:
        selectors = [
            f"button:has-text('{text}')",
            f"a:has-text('{text}')",
            f"input[value='{text}']",
            f"text={text}",
        ]
        for selector in selectors:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                if count > 0:
                    await loc.first.click(timeout=1500, force=True)
                    actions.append({"action": "clicked_modal_button", "selector": selector, "count": count})
                    await page.wait_for_timeout(500)
            except Exception as exc:
                pass

    # Hide stubborn overlays if visible. This is UI cleanup only, not bypassing auth/captcha.
    hide_script = """
    () => {
      const removed = [];
      const selectors = [
        '.modal-backdrop', '.modal', '.overlay', '.cookie', '.cookies',
        '#cookieConsent', '#consent', '[role="dialog"]'
      ];
      for (const sel of selectors) {
        document.querySelectorAll(sel).forEach((el) => {
          const txt = (el.innerText || el.textContent || '').slice(0, 200);
          el.style.display = 'none';
          el.style.visibility = 'hidden';
          removed.push({selector: sel, text: txt});
        });
      }
      document.body.classList.remove('modal-open');
      document.body.style.overflow = 'auto';
      return removed;
    }
    """
    try:
        removed = await page.evaluate(hide_script)
        if removed:
            actions.append({"action": "hid_overlays", "items": removed[:20]})
    except Exception:
        pass

    return actions


async def _search_opportunities(page, search_text: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    # First open eTenders QuickFind panel if available.
    for quick_selector in [
        "button:has-text('QuickFind')",
        "a:has-text('QuickFind')",
        "text=QuickFind",
        "button:has-text('Quick Find')",
        "a:has-text('Quick Find')",
        "text=Quick Find",
    ]:
        try:
            q = page.locator(quick_selector)
            if await q.count() > 0:
                await q.first.click(timeout=3000, force=True)
                await page.wait_for_timeout(1200)
                actions.append({"action": "quickfind_clicked", "selector": quick_selector})
                break
        except Exception as exc:
            actions.append({"action": "quickfind_click_error", "selector": quick_selector, "error": str(exc)})

    search_selectors = [
        "input[type='search']:visible",
        "input[aria-controls*='tender']:visible",
        "input[aria-controls]:visible",
        "#tenderList_filter input:visible",
        ".dataTables_filter input:visible",
        "input[placeholder*='Search']",
        "input[placeholder*='search']",
        "input[placeholder*='Type']",
        "input[placeholder*='type']",
        "input[type='text']:visible",
        ".modal input[type='text']",
        ".modal input",
    ]

    search_terms = []
    base = (search_text or "").strip()
    if base:
        search_terms.append(base)

    # Relaxed fallback terms for eTenders matching.
    for term in [
        base.replace("/", " ").replace("-", " "),
        "DIGITALBOOK",
        "JDAMARK",
        "DIGITAL BOOK",
        "BOOK",
    ]:
        term = (term or "").strip()
        if term and term not in search_terms:
            search_terms.append(term)

    for selector in search_selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "search_selector_checked", "selector": selector, "count": count})
            if count > 0:
                for term in search_terms:
                    try:
                        await loc.first.fill("", timeout=3000)
                        await page.wait_for_timeout(300)
                        await loc.first.fill(term, timeout=3000)
                        await loc.first.evaluate(
                            """(input, value) => {
                              input.value = value;
                              input.dispatchEvent(new Event('input', { bubbles: true }));
                              input.dispatchEvent(new Event('change', { bubbles: true }));
                              input.dispatchEvent(new KeyboardEvent('keyup', {
                                key: 'Enter',
                                code: 'Enter',
                                bubbles: true
                              }));
                            }""",
                            term,
                        )
                        await loc.first.press("Enter", timeout=3000)
                        await page.wait_for_timeout(4500)
                        body_text = await page.locator("body").inner_text(timeout=3000)
                        hit = term.lower() in body_text.lower()
                        actions.append({
                            "action": "search_filled",
                            "selector": selector,
                            "search_text": term,
                            "body_hit": hit,
                            "body_preview": body_text[:500],
                        })
                        if hit:
                            return actions
                    except Exception as exc:
                        actions.append({"action": "search_term_error", "selector": selector, "search_text": term, "error": str(exc)})
                return actions
        except Exception as exc:
            actions.append({"action": "search_error", "selector": selector, "error": str(exc)})

    # Fallback DataTables search injection using relaxed terms too.
    for term in search_terms:
        try:
            injected = await page.evaluate(
                """
                (term) => {
                  let done = false;
                  if (window.jQuery && window.jQuery.fn && window.jQuery.fn.dataTable) {
                    window.jQuery('table').each(function(){
                      try {
                        const dt = window.jQuery(this).DataTable();
                        dt.search(term).draw();

                        const searchInputs = document.querySelectorAll(
                          "input[type='search'], .dataTables_filter input"
                        );

                        searchInputs.forEach(inp => {
                          inp.value = term;
                          inp.dispatchEvent(new Event('input', { bubbles:true }));
                          inp.dispatchEvent(new Event('change', { bubbles:true }));
                          inp.dispatchEvent(new KeyboardEvent('keyup', {
                            key:'Enter',
                            code:'Enter',
                            bubbles:true
                          }));
                        });

                        done = true;
                      } catch(e) {}
                    });
                  }
                  return done;
                }
                """,
                term,
            )
            await page.wait_for_timeout(4500)
            body_text = await page.locator("body").inner_text(timeout=3000)
            hit = term.lower() in body_text.lower()
            actions.append({
                "action": "datatables_search_injected",
                "done": injected,
                "search_text": term,
                "body_hit": hit,
                "body_preview": body_text[:500],
            })
            if injected and hit:
                break
        except Exception as exc:
            actions.append({"action": "datatables_search_error", "search_text": term, "error": str(exc)})

    return actions


async def _force_currently_advertised_tab(page) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    active_tab = await _active_opportunities_tab_name(page)
    if "currently advertised" in active_tab.lower():
        actions.append({"action": "currently_advertised_already_active", "active_tab_name": active_tab})
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
            actions.append({"action": "currently_advertised_selector_checked", "selector": selector, "count": count})
            if count > 0:
                await loc.first.click(timeout=4000, force=True)
                await page.wait_for_timeout(4000)
                actions.append({"action": "forced_currently_advertised_tab", "selector": selector})
                return actions
        except Exception as exc:
            actions.append({"action": "forced_currently_advertised_tab_error", "selector": selector, "error": str(exc)})

    try:
        clicked = await page.evaluate(
            """() => {
              const nodes = Array.from(document.querySelectorAll('a,button,li,span,div'));
              const el = nodes.find((node) => {
                const text = (node.innerText || node.textContent || '').trim().toLowerCase();
                return text === 'currently advertised' || text.includes('currently advertised');
              });
              if (!el) return false;
              const clickable = el.closest('a,button') || el;
              clickable.scrollIntoView({ block: 'center', inline: 'center' });
              clickable.click();
              return true;
            }"""
        )
        await page.wait_for_timeout(4000)
        actions.append({"action": "forced_currently_advertised_tab_dom", "clicked": bool(clicked)})
    except Exception as exc:
        actions.append({"action": "forced_currently_advertised_tab_dom_error", "error": str(exc)})
    return actions


async def _active_opportunities_tab_name(page) -> str:
    try:
        name = await page.evaluate(
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
        return _clean(name)
    except Exception:
        return ""


async def _force_browse_currently_advertised(page, tender_url: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    for selector in [
        "a:has-text('Browse Opportunities')",
        "button:has-text('Browse Opportunities')",
        "a:has-text('Opportunities')",
        "text=Browse Opportunities",
    ]:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "browse_opportunities_selector_checked", "selector": selector, "count": count})
            if count > 0:
                await loc.first.click(timeout=4000, force=True)
                await page.wait_for_timeout(2500)
                actions.append({"action": "browse_opportunities_clicked", "selector": selector})
                break
        except Exception as exc:
            actions.append({"action": "browse_opportunities_click_error", "selector": selector, "error": str(exc)})

    try:
        current = str(getattr(page, "url", "") or "")
        if "/Home/opportunities" not in current:
            await page.goto(tender_url or ETENDERS_OPPORTUNITIES, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2500)
            actions.append({"action": "browse_opportunities_goto", "url": tender_url or ETENDERS_OPPORTUNITIES})
    except Exception as exc:
        actions.append({"action": "browse_opportunities_goto_error", "error": str(exc)})

    actions.extend(await _force_currently_advertised_tab(page))
    actions.append({"action": "active_tab_after_force", "active_tab_name": await _active_opportunities_tab_name(page)})

    try:
        await page.wait_for_function(
            """() => Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"]'))
              .some(row => (row.innerText || row.textContent || '').trim().length > 20)""",
            timeout=30000,
        )
        actions.append({"action": "datatable_tbody_rows_ready", "ready": True})
    except Exception as exc:
        actions.append({"action": "datatable_tbody_rows_ready", "ready": False, "error": str(exc)})

    return actions


async def _capture_expanded_dom_state(page, source: str = "active_row") -> Dict[str, Any]:
    try:
        state = await page.evaluate(
            """(source) => {
              const text = (document.body.innerText || document.body.textContent || '').replace(/\\s+/g, ' ').trim();
              const html = document.body.outerHTML || '';
              const anchors = Array.from(document.querySelectorAll('a[href]'));
              const anchorSummaries = anchors.map((el) => ({
                href: el.href || el.getAttribute('href') || '',
                text: (el.innerText || el.textContent || el.getAttribute('aria-label') || el.title || '').replace(/\\s+/g, ' ').trim().slice(0, 220),
              }));
              const blobLinks = Array.from(document.querySelectorAll('a[href], button, input, [onclick], [data-href], [data-url], [data-download-url], [formaction]'))
                .map((el, index) => {
                  const rawHref = el.getAttribute('href') || el.getAttribute('data-href') || el.getAttribute('data-url') || el.getAttribute('data-download-url') || el.getAttribute('formaction') || '';
                  const onclick = el.getAttribute('onclick') || '';
                  const href = el.href || rawHref || '';
                  const candidate = href || rawHref || onclick;
                  if (!candidate) return null;
                  const lower = candidate.toLowerCase();
                  if (lower.indexOf('blobname=') === -1 && lower.indexOf('/home/download') === -1 && lower.indexOf('download/?blobname=') === -1) {
                    return null;
                  }
                  let absolute = href || rawHref || '';
                  try {
                    if (absolute) {
                      absolute = new URL(absolute, document.baseURI).toString();
                    }
                  } catch (e) {}
                  const finalHref = absolute || href || rawHref || candidate;
                  let blobName = '';
                  let downloadedFileName = '';
                  try {
                    const params = new URL(finalHref, document.baseURI).searchParams;
                    blobName = params.get('blobName') || params.get('BlobName') || params.get('blobname') || '';
                    downloadedFileName = params.get('downloadedFileName') || params.get('DownloadedFileName') || params.get('downloaded_filename') || '';
                  } catch (e) {}
                  return {
                    index,
                    tag: el.tagName,
                    text: (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '').replace(/\\s+/g, ' ').trim().slice(0, 220),
                    href: finalHref,
                    blobName,
                    downloadedFileName,
                    onclick,
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                  };
                })
                .filter(item => item && item.href)
                .slice(0, 40);
              const controls = Array.from(document.querySelectorAll('a,button,input,select,textarea,[onclick],[role="button"]'))
                .map((el, index) => ({
                  index,
                  tag: el.tagName,
                  id: el.id || '',
                  cls: typeof el.className === 'string' ? el.className : '',
                  text: (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.title || '').replace(/\\s+/g, ' ').trim().slice(0, 220),
                  href: el.href || el.getAttribute('href') || '',
                  onclick: el.getAttribute('onclick') || '',
                  type: el.getAttribute('type') || '',
                  visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                }))
                .filter(item => item.text || item.href || item.onclick || item.id || item.cls)
                .slice(0, 160);
              const serial = JSON.stringify(controls).toLowerCase();
              const lowerText = text.toLowerCase();
              const anchorHrefList = anchorSummaries.map((item) => item.href).filter(Boolean);
              const anchorTextList = anchorSummaries.map((item) => item.text).filter(Boolean);
              return {
                source,
                body_text_preview: text.slice(0, 2500),
                body_html_preview: html.slice(0, 12000),
                visible_text_limited: text.slice(0, 2500),
                tender_documents_text_limited: /tender documents/i.test(text) ? text.slice(0, 2500) : '',
                document_anchor_count: anchorSummaries.length,
                all_anchor_hrefs_limited: anchorHrefList.slice(0, 40),
                all_anchor_texts_limited: anchorTextList.slice(0, 40),
                download_like_anchor_count: anchorHrefList.filter((href) => /download|blobname|document/i.test(String(href).toLowerCase())).length,
                blob_like_string_count: (html.match(/blobName|downloadedFileName|\/Home\/Download|\/home\/Download/gi) || []).length,
                controls,
                blob_links: blobLinks,
                blob_link_count: blobLinks.length,
                documents_section_found: blobLinks.length > 0 || /tender documents|documents|supporting documents|document links?|attachments?/i.test(lowerText + ' ' + serial),
                expanded_dom_detected: /download|document|tender detail|tenderdescription|briefing|closing|contact|support/i.test(text + ' ' + serial),
                tender_detail_detected: /tender detail|tender description|briefing|closing date|enquiries|buyer|department|contact/i.test(lowerText),
                upload_controls_detected: /upload|browse|choose file|add document|attach|drop/i.test(lowerText + ' ' + serial),
                download_controls_detected: /download|document|support|attachment|file/i.test(lowerText + ' ' + serial)
              };
            }""",
            source,
        )
        return state if isinstance(state, dict) else {}
    except Exception as exc:
        return {
            "source": source,
            "expanded_dom_detected": False,
            "tender_detail_detected": False,
            "upload_controls_detected": False,
            "download_controls_detected": False,
            "documents_section_found": False,
            "tender_documents_text_limited": "",
            "document_anchor_count": 0,
            "all_anchor_hrefs_limited": [],
            "all_anchor_texts_limited": [],
            "download_like_anchor_count": 0,
            "blob_like_string_count": 0,
            "visible_text_limited": "",
            "post_click_wait_ms": 0,
            "row_selector_used": "",
            "row_click_target_used": "",
            "blob_links": [],
            "blob_link_count": 0,
            "error": str(exc),
        }


def _limit_snippet(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _v50_9_4_empty_capture_result(data: Dict[str, Any], cdp_resolution: Dict[str, Any], *, status: str, message: str, error: str = "", helper_error_type: str = "", helper_error_message: str = "") -> Dict[str, Any]:
    helper_error_message_limited = _limit_snippet(helper_error_message or error or "", 240)
    return {
        "status": status,
        "service_version": SERVICE_VERSION,
        "message": message,
        "error": error,
        "helper_error_type": helper_error_type,
        "helper_error_message_limited": helper_error_message_limited,
        "input": data,
        "cdp_resolution": cdp_resolution,
        "cdp_resolved": cdp_resolution,
        "matched_row": None,
        "target_terms_used": [],
        "all_visible_row_previews_scanned": [],
        "pagination_rounds_attempted": 0,
        "best_candidate_row": None,
        "table_container_found": False,
        "datatables_processing_seen": False,
        "datatables_processing_finished": False,
        "main_response_status": 0,
        "body_text_length": 0,
        "body_html_length": 0,
        "body_text_preview_limited": "",
        "visible_row_count": 0,
        "page_text_limited_before_row_search": "",
        "table_count": 0,
        "row_count_by_selector": {},
        "first_rows_text_limited": [],
        "visible_links_limited": [],
        "helper_input_url": "",
        "helper_resolved_url": "",
        "helper_used_detail_page": False,
        "helper_used_opportunities_page": False,
        "helper_preserved_query_params": False,
        "detail_page_url_available": False,
        "opportunities_url_available": False,
        "page_url_after_load": "",
        "page_title": "",
        "screenshot_path": "",
        "browser_mode": "failed",
        "row_found": False,
        "row_clicked": False,
        "row_expanded": False,
        "row_match_strategy": "",
        "row_match_text": "",
        "matched_row_text_limited": "",
        "expanded_dom_detected": False,
        "tender_detail_detected": False,
        "upload_controls_detected": False,
        "download_controls_detected": False,
        "documents_section_found": False,
        "row_selector_used": "",
        "row_click_target_used": "",
        "post_click_wait_ms": 0,
        "tender_documents_text_limited": "",
        "document_anchor_count": 0,
        "all_anchor_hrefs_limited": [],
        "all_anchor_texts_limited": [],
        "download_like_anchor_count": 0,
        "blob_like_string_count": 0,
        "interactive_blob_candidates_count": 0,
        "blob_links": [],
        "visible_text_limited": "",
        "expanded_dom": None,
        "active_tab_name": "",
        "verified_download_count": 0,
        "verified_downloads": [],
        "network_event_count": 0,
        "relevant_network_events": [],
        "download_events": [],
        "modal_actions": [],
        "search_actions": [],
        "click_actions": [],
        "console_events": [],
        "page_errors": [],
        "screenshots": [],
        "screenshot_path": "",
        "capture_log": "",
        "safe_to_process": False,
        "notes": [],
    }


def _unique_compact(values: List[Any], limit: int = 20) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        text = _clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _normalize_partial_title(title: str) -> str:
    tokens = [token for token in _normalise_match_text(title).split() if len(token) >= 4]
    return " ".join(tokens[:6]).strip()


async def _v50_9_4_wait_for_etenders_table_ready(page, data: Dict[str, str], timeout_ms: int = 9000, main_response_status: int = 0) -> Dict[str, Any]:
    container_selectors = ["#tendeList", "table#tendeList", ".dataTables_wrapper", ".dataTables_scroll", "table"]
    row_selectors = [
        "#tendeList tbody tr",
        "table#tendeList tbody tr",
        ".dataTables_wrapper tbody tr",
        "tr[role='row']",
        "td.sorting_1",
    ]
    processing_selectors = [".dataTables_processing", ".dataTables_processing:visible"]
    link_selectors = ["a[href]"]

    result: Dict[str, Any] = {
        "table_container_found": False,
        "datatables_processing_seen": False,
        "datatables_processing_finished": False,
        "main_response_status": int(main_response_status or 0),
        "body_text_length": 0,
        "body_html_length": 0,
        "body_text_preview_limited": "",
        "visible_row_count": 0,
        "page_text_limited_before_row_search": "",
        "table_count": 0,
        "row_count_by_selector": {},
        "first_rows_text_limited": [],
        "visible_links_limited": [],
        "page_url_after_load": _clean(getattr(page, "url", "")),
        "page_title": "",
        "screenshot_path": "",
        "row_texts": [],
    }

    try:
        result["page_title"] = _clean(await page.title())
    except Exception:
        pass

    try:
        body_text = await page.locator("body").inner_text(timeout=min(timeout_ms, 3000))
        result["body_text_length"] = len(body_text or "")
        result["page_text_limited_before_row_search"] = _limit_snippet(body_text, 1400)
        result["body_text_preview_limited"] = _limit_snippet(body_text, 500)
    except Exception:
        pass

    try:
        body_html = await page.content()
        result["body_html_length"] = len(body_html or "")
    except Exception:
        pass

    try:
        output_dir_raw = _clean(data.get("output_dir") or "")
        if output_dir_raw:
            output_dir = Path(output_dir_raw).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = output_dir / f"ETENDERS_{_clean(data.get('tender_id') or 'capture')}__v50_9_4_pre_table.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            result["screenshot_path"] = str(screenshot_path)
    except Exception:
        pass

    deadline = time.monotonic() + max(timeout_ms, 1000) / 1000.0
    while True:
        container_found = False
        processing_seen = False
        visible_rows: List[Dict[str, Any]] = []
        row_count_by_selector: Dict[str, int] = {}
        table_count = 0

        for selector in container_selectors:
            try:
                count = int(await page.locator(selector).count())
            except Exception:
                count = 0
            if count > 0:
                container_found = True
                table_count += count

        for selector in processing_selectors:
            try:
                if int(await page.locator(selector).count()) > 0:
                    processing_seen = True
            except Exception:
                pass

        for selector in row_selectors:
            try:
                loc = page.locator(selector)
                count = int(await loc.count())
            except Exception:
                count = 0
            row_count_by_selector[selector] = count
            if count <= 0:
                continue
            visible_rows.append({"selector": selector, "index": 0, "text": ""})
            for idx in range(min(count, 6)):
                try:
                    row = loc.nth(idx)
                    text = _limit_snippet(await row.inner_text(timeout=min(timeout_ms, 2000)), 260)
                    if text:
                        visible_rows.append({"selector": selector, "index": idx, "text": text})
                except Exception:
                    continue

        visible_row_count = len([row for row in visible_rows if _clean(row.get("text"))])
        result.update({
            "table_container_found": container_found,
            "datatables_processing_seen": processing_seen,
            "datatables_processing_finished": container_found and not processing_seen,
            "visible_row_count": visible_row_count,
            "table_count": table_count,
            "row_count_by_selector": row_count_by_selector,
            "first_rows_text_limited": [row.get("text") for row in visible_rows if row.get("text")][:10],
            "row_texts": [row for row in visible_rows if row.get("text")],
        })

        try:
            anchor_count = int(await page.locator("a[href]").count())
        except Exception:
            anchor_count = 0
        visible_links: List[str] = []
        for idx in range(min(anchor_count, 20)):
            try:
                href = _clean(await page.locator("a[href]").nth(idx).get_attribute("href"))
            except Exception:
                href = ""
            if href:
                visible_links.append(href)
        result["visible_links_limited"] = _unique_compact(visible_links, limit=20)

        if container_found and visible_row_count > 0 and not processing_seen:
            break
        if time.monotonic() >= deadline:
            break
        try:
            await page.wait_for_timeout(250)
        except Exception:
            break

    return result


def _v50_9_4_match_etenders_row_texts(row_texts: List[Dict[str, Any]], data: Dict[str, str]) -> Dict[str, Any]:
    title = _clean(data.get("title") or data.get("search_text") or "")
    tender_id = _clean(data.get("tender_id") or "")
    buyer = _clean(data.get("buyer_name") or data.get("buyer") or data.get("procuring_entity") or "")
    reference = _clean(
        data.get("reference_number")
        or data.get("rfq_number")
        or data.get("tender_number")
        or data.get("tender_no")
        or ""
    )
    partial_title = _normalize_partial_title(title)

    strategy_terms = [
        ("tender_id", [tender_id]),
        ("exact_title", [title]),
        ("normalized_partial_title", [partial_title]),
        ("buyer_name", [buyer]),
        ("reference_number", [reference]),
    ]

    for strategy, terms in strategy_terms:
        usable_terms = [term for term in terms if _clean(term)]
        if not usable_terms:
            continue
        best: Optional[Dict[str, Any]] = None
        for row in row_texts:
            row_text = _clean(row.get("text"))
            if not row_text:
                continue
            row_norm = _normalise_match_text(row_text)
            term_norms = [_normalise_match_text(term) for term in usable_terms]
            matched = False
            matched_term = ""
            if strategy == "tender_id":
                matched = any(term in row_text for term in usable_terms)
                matched_term = usable_terms[0] if matched else ""
            elif strategy == "exact_title":
                matched = any(term_norm and (term_norm in row_norm or row_norm in term_norm) for term_norm in term_norms)
                matched_term = usable_terms[0] if matched else ""
            elif strategy == "normalized_partial_title":
                matched = any(term_norm and term_norm in row_norm for term_norm in term_norms)
                matched_term = usable_terms[0] if matched else ""
            else:
                matched = any(term_norm and term_norm in row_norm for term_norm in term_norms)
                matched_term = usable_terms[0] if matched else ""
            if not matched:
                continue
            scored = _score_row_text(row_text, usable_terms)
            row_match = {
                "row_found": True,
                "row_match_strategy": strategy,
                "row_match_text": matched_term,
                "matched_row_text_limited": _limit_snippet(row_text, 320),
                "matched_row_index": int(row.get("index") or 0),
                "matched_row_selector": _clean(row.get("selector") or ""),
                "score": scored.get("score") or 0,
                "matched_terms": scored.get("matched_terms") or [],
                "matched_tokens": scored.get("matched_tokens") or [],
            }
            if best is None or float(row_match["score"]) > float(best["score"]):
                best = row_match
        if best:
            return best

    return {
        "row_found": False,
        "row_match_strategy": "",
        "row_match_text": "",
        "matched_row_text_limited": "",
        "matched_row_index": -1,
        "matched_row_selector": "",
        "score": 0,
        "matched_terms": [],
        "matched_tokens": [],
    }


async def _activate_best_candidate_row(page, data: Dict[str, str], seed_diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    target_terms = seed_diagnostics.get("target_terms_used") or _build_target_terms(data)
    best_candidate = seed_diagnostics.get("best_candidate_row")
    actions: List[Dict[str, Any]] = []
    main_response_status = int(data.get("main_response_status") or 0)

    result: Dict[str, Any] = {
        "row_clicked": False,
        "row_expanded": False,
        "expanded_dom_detected": False,
        "tender_detail_detected": False,
        "upload_controls_detected": False,
        "download_controls_detected": False,
        "active_tab_name": "",
        "matched_row": None,
        "best_candidate_row": best_candidate,
        "row_selector_used": "table tbody tr, table tr, [role=\"row\"], .dataTables_wrapper tr",
        "row_click_target_used": "",
        "post_click_wait_ms": 0,
        "documents_section_found": False,
        "tender_documents_text_limited": "",
        "document_anchor_count": 0,
        "all_anchor_hrefs_limited": [],
        "all_anchor_texts_limited": [],
        "download_like_anchor_count": 0,
        "blob_like_string_count": 0,
        "visible_text_limited": "",
        "helper_error_type": "",
        "helper_error_message_limited": "",
        "actions": actions,
    }

    nav_actions = await _force_browse_currently_advertised(page, data.get("tender_url") or ETENDERS_OPPORTUNITIES)
    actions.extend(nav_actions)
    result["active_tab_name"] = await _active_opportunities_tab_name(page)

    if not best_candidate:
        fresh = await _snapshot_row_diagnostics(page, data, "active_pre_click")
        best_candidate = fresh.get("best_candidate_row")
        result["best_candidate_row"] = best_candidate
        actions.append({"action": "active_best_candidate_refreshed", "best_candidate_row": best_candidate})

    try:
        table_snapshot = await _v50_9_4_wait_for_etenders_table_ready(page, data, timeout_ms=9000, main_response_status=main_response_status)
    except Exception as exc:
        table_snapshot = {
            "table_container_found": False,
            "datatables_processing_seen": False,
            "datatables_processing_finished": False,
            "main_response_status": main_response_status,
            "body_text_length": 0,
            "body_html_length": 0,
            "body_text_preview_limited": "",
            "visible_row_count": 0,
            "page_text_limited_before_row_search": "",
            "table_count": 0,
            "row_count_by_selector": {},
            "first_rows_text_limited": [],
            "visible_links_limited": [],
            "page_url_after_load": _clean(getattr(page, "url", "")),
            "page_title": "",
            "screenshot_path": "",
            "row_texts": [],
            "helper_error_type": type(exc).__name__,
            "helper_error_message_limited": _limit_snippet(str(exc), 240),
        }
        result["helper_error_type"] = type(exc).__name__
        result["helper_error_message_limited"] = _limit_snippet(str(exc), 240)
    result["table_container_found"] = bool(table_snapshot.get("table_container_found"))
    result["datatables_processing_seen"] = bool(table_snapshot.get("datatables_processing_seen"))
    result["datatables_processing_finished"] = bool(table_snapshot.get("datatables_processing_finished"))
    result["main_response_status"] = int(table_snapshot.get("main_response_status") or 0)
    result["body_text_length"] = int(table_snapshot.get("body_text_length") or 0)
    result["body_html_length"] = int(table_snapshot.get("body_html_length") or 0)
    result["body_text_preview_limited"] = _clean(table_snapshot.get("body_text_preview_limited"))
    result["visible_row_count"] = int(table_snapshot.get("visible_row_count") or 0)
    result["table_count"] = int(table_snapshot.get("table_count") or 0)
    result["row_count_by_selector"] = table_snapshot.get("row_count_by_selector") or {}
    result["first_rows_text_limited"] = table_snapshot.get("first_rows_text_limited") or []
    result["visible_links_limited"] = table_snapshot.get("visible_links_limited") or []
    result["page_text_limited_before_row_search"] = _clean(table_snapshot.get("page_text_limited_before_row_search"))
    result["page_url_after_load"] = _clean(table_snapshot.get("page_url_after_load"))
    result["page_title"] = _clean(table_snapshot.get("page_title"))
    result["screenshot_path"] = _clean(table_snapshot.get("screenshot_path"))
    result["actions"].append({
        "action": "etenders_table_snapshot",
        "summary": {
            "table_container_found": result["table_container_found"],
            "datatables_processing_seen": result["datatables_processing_seen"],
            "datatables_processing_finished": result["datatables_processing_finished"],
            "visible_row_count": result["visible_row_count"],
            "table_count": result["table_count"],
            "page_url_after_load": result["page_url_after_load"],
            "page_title": result["page_title"],
        },
    })

    try:
        match = _v50_9_4_match_etenders_row_texts(table_snapshot.get("row_texts") or [], data)
    except Exception as exc:
        match = {
            "row_found": False,
            "row_match_strategy": "",
            "row_match_text": "",
            "matched_row_text_limited": "",
            "matched_row_index": -1,
            "matched_row_selector": "",
            "score": 0,
            "matched_terms": [],
            "matched_tokens": [],
        }
        result["helper_error_type"] = result.get("helper_error_type") or type(exc).__name__
        result["helper_error_message_limited"] = result.get("helper_error_message_limited") or _limit_snippet(str(exc), 240)
    result["row_found"] = bool(match.get("row_found"))
    result["row_match_strategy"] = _clean(match.get("row_match_strategy"))
    result["row_match_text"] = _clean(match.get("row_match_text"))
    result["matched_row_text_limited"] = _clean(match.get("matched_row_text_limited"))
    result["matched_row"] = {
        "source": "table_snapshot_match",
        "index": int(match.get("matched_row_index") or -1),
        "score": match.get("score"),
        "matched_terms": match.get("matched_terms") or [],
        "matched_tokens": match.get("matched_tokens") or [],
        "text_preview": _clean(match.get("matched_row_text_limited")),
        "selector": _clean(match.get("matched_row_selector")),
    } if result["row_found"] else None

    if not result["row_found"]:
        result["failure_reason"] = "row_not_found|page_state_no_table" if not result.get("table_container_found") else "row_not_found"
        actions.append({
            "action": "row_not_found",
            "table_container_found": result["table_container_found"],
            "visible_row_count": result["visible_row_count"],
            "row_count_by_selector": result["row_count_by_selector"],
            "first_rows_text_limited": result["first_rows_text_limited"],
            "visible_links_limited": result["visible_links_limited"],
            "page_url_after_load": result["page_url_after_load"],
            "page_title": result["page_title"],
            "row_match_strategy": "",
            "row_match_text": "",
        })
        expanded = {
            "expanded_dom_detected": False,
            "tender_detail_detected": False,
            "upload_controls_detected": False,
            "download_controls_detected": False,
            "documents_section_found": False,
            "tender_documents_text_limited": "",
            "document_anchor_count": 0,
            "all_anchor_hrefs_limited": [],
            "all_anchor_texts_limited": [],
            "download_like_anchor_count": 0,
            "blob_like_string_count": 0,
            "visible_text_limited": "",
            "post_click_wait_ms": 0,
            "row_selector_used": _clean(result.get("row_selector_used")),
            "row_click_target_used": "",
        }
        result["expanded_dom"] = expanded
        result["actions"] = actions
        return result

    try:
        matched_selector = _clean(match.get("matched_row_selector") or "")
        matched_index = int(match.get("matched_row_index") or 0)
        row_selector = matched_selector or "#tendeList tbody tr"
        row_locator = page.locator(row_selector)
        row_count = int(await row_locator.count())
        if row_count <= matched_index and row_count > 0:
            matched_index = max(0, row_count - 1)
        row = row_locator.nth(matched_index)
        await row.scroll_into_view_if_needed(timeout=3000)
        await row.click(timeout=4000, force=True)
        row_click_target_used = "row"
        row_selector_used = row_selector
        expanders = [
            "td.details-control",
            "td.dtr-control",
            "td.sorting_1",
            "td:first-child",
            "button[aria-expanded]",
            "a[aria-expanded]",
            "button:has(i)",
            "a:has(i)",
            "button",
            "a",
        ]
        expanded = False
        expander_selector = ""
        for selector in expanders:
            try:
                ctl = row.locator(selector).first
                if await ctl.count() > 0:
                    await ctl.click(timeout=3000, force=True)
                    expanded = True
                    expander_selector = selector
                    row_click_target_used = selector
                    break
            except Exception:
                continue
        wait_start = time.monotonic()
        try:
            await page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        try:
            await page.wait_for_function(
                """() => {
                  const text = (document.body.innerText || document.body.textContent || '').toLowerCase();
                  return text.includes('tender documents') || text.includes('documents');
                }""",
                timeout=6000,
            )
        except Exception:
            pass
        try:
            await page.wait_for_function(
                """() => Array.from(document.querySelectorAll('a[href]')).some((a) => {
                  const href = String(a.href || a.getAttribute('href') || '').toLowerCase();
                  return href.includes('.pdf') || href.includes('download') || href.includes('blobname=');
                })""",
                timeout=6000,
            )
        except Exception:
            pass
        await page.wait_for_timeout(1000)
        post_click_wait_ms = int((time.monotonic() - wait_start) * 1000)
        activation = {
            "ok": True,
            "rowClicked": True,
            "rowExpanded": expanded,
            "expanderSelector": expander_selector,
            "rowSelectorUsed": row_selector_used,
            "rowClickTargetUsed": row_click_target_used,
            "best": {
                "index": matched_index,
                "score": match.get("score") or 0,
                "matchedTerms": match.get("matched_terms") or [],
                "matchedTokens": match.get("matched_tokens") or [],
                "textPreview": match.get("matched_row_text_limited") or "",
            },
        }
        actions.append({"action": "active_matched_row_activation", "result": activation})
    except Exception as exc:
        activation = {"ok": False, "reason": "activation_exception", "error": str(exc)}
        actions.append({"action": "active_matched_row_activation_error", "error": str(exc)})
        post_click_wait_ms = 0

    post_expand_tab_actions = await _force_currently_advertised_tab(page)
    actions.extend({**item, "action": "post_expand_" + item.get("action", "tab_action")} for item in post_expand_tab_actions)
    result["active_tab_name"] = await _active_opportunities_tab_name(page)
    actions.append({"action": "active_tab_after_row_activation", "active_tab_name": result["active_tab_name"]})

    if isinstance(activation, dict) and activation.get("ok"):
        best = activation.get("best") or {}
        result["row_clicked"] = bool(activation.get("rowClicked"))
        result["row_expanded"] = bool(activation.get("rowExpanded"))
        result["matched_row"] = {
            "source": "active_matched_row_execution",
            "index": best.get("index"),
            "score": best.get("score"),
            "matched_terms": best.get("matchedTerms") or [],
            "matched_tokens": best.get("matchedTokens") or [],
            "text_preview": best.get("textPreview") or result.get("row_match_text") or "",
            "expander_selector": activation.get("expanderSelector") or "",
        }
        result["row_selector_used"] = activation.get("rowSelectorUsed") or "table tbody tr, table tr, [role=\"row\"], .dataTables_wrapper tr"
        result["row_click_target_used"] = activation.get("rowClickTargetUsed") or activation.get("expanderSelector") or "row"
        result["post_click_wait_ms"] = post_click_wait_ms

    expanded = await _capture_expanded_dom_state(page, "active_matched_row_execution")
    result["expanded_dom"] = expanded
    result["expanded_dom_detected"] = bool(expanded.get("expanded_dom_detected"))
    result["tender_detail_detected"] = bool(expanded.get("tender_detail_detected"))
    result["upload_controls_detected"] = bool(expanded.get("upload_controls_detected"))
    result["download_controls_detected"] = bool(expanded.get("download_controls_detected"))
    result["documents_section_found"] = bool(expanded.get("documents_section_found"))
    result["tender_documents_text_limited"] = _clean(expanded.get("tender_documents_text_limited"))
    result["document_anchor_count"] = int(expanded.get("document_anchor_count") or 0)
    result["all_anchor_hrefs_limited"] = expanded.get("all_anchor_hrefs_limited") or []
    result["all_anchor_texts_limited"] = expanded.get("all_anchor_texts_limited") or []
    result["download_like_anchor_count"] = int(expanded.get("download_like_anchor_count") or 0)
    result["blob_like_string_count"] = int(expanded.get("blob_like_string_count") or 0)
    result["visible_text_limited"] = _clean(expanded.get("visible_text_limited"))
    actions.append({"action": "expanded_dom_captured", "summary": {
        "expanded_dom_detected": result["expanded_dom_detected"],
        "tender_detail_detected": result["tender_detail_detected"],
        "upload_controls_detected": result["upload_controls_detected"],
        "download_controls_detected": result["download_controls_detected"],
    }})

    return result


async def _expand_and_click_documents(page, data: Dict[str, str]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    tokens = [
        data.get("support_document_id", ""),
        data.get("filename", ""),
        data.get("tender_id", ""),
        "JDAMARK",
        "DIGITAL BOOK",
        "Documents",
        "Download",
    ]
    tokens = [t for t in tokens if t]

    # Deep row discovery: scan visible rows and walk DataTables pagination/scroll before expansion.
    target_terms = _build_target_terms(data)
    target_terms_norm = [_normalise_match_text(term) for term in target_terms if _normalise_match_text(term)]
    all_row_previews: List[Dict[str, Any]] = []
    pagination_rounds_attempted = 0
    best_candidate: Optional[Dict[str, Any]] = None
    matched_row_found = False
    actions.append({
        "action": "target_terms_used",
        "terms": target_terms,
        "normalised_terms": target_terms_norm,
    })

    for page_round in range(0, 8):
        pagination_rounds_attempted = page_round + 1
        try:
            rows = page.locator("table tbody tr:visible")
            count = await rows.count()
            actions.append({"action": "deep_row_scan", "round": page_round, "row_count": count})

            if count <= 0:
                try:
                    dom_rows = await page.evaluate(
                        """() => {
                          const candidates = Array.from(document.querySelectorAll(
                            'table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'
                          ));
                          return candidates.map((row, index) => {
                            const rect = row.getBoundingClientRect();
                            const style = window.getComputedStyle(row);
                            const text = (row.innerText || row.textContent || '').replace(/\\s+/g, ' ').trim();
                            const visible = !!(
                              text &&
                              rect.width > 0 &&
                              rect.height > 0 &&
                              style.display !== 'none' &&
                              style.visibility !== 'hidden' &&
                              style.opacity !== '0'
                            );
                            return {
                              index,
                              visible,
                              rect: {width: rect.width, height: rect.height, top: rect.top, left: rect.left},
                              text: text.slice(0, 1000)
                            };
                          }).filter(row => row.text).slice(0, 200);
                        }"""
                    )
                    visible_dom_rows = [row for row in dom_rows if row.get("visible")]
                    actions.append({
                        "action": "dom_row_snapshot",
                        "round": page_round,
                        "row_count": len(dom_rows),
                        "visible_row_count": len(visible_dom_rows),
                    })

                    for row_info in visible_dom_rows:
                        row_text = row_info.get("text") or ""
                        score = _score_row_text(row_text, target_terms)
                        matched_terms = score.get("matched_terms") or []
                        row_preview = {
                            "round": page_round,
                            "index": row_info.get("index"),
                            "source": "dom_snapshot",
                            "score": score.get("score"),
                            "matched_terms": matched_terms,
                            "matched_tokens": score.get("matched_tokens") or [],
                            "text_preview": row_text[:500],
                        }
                        all_row_previews.append(row_preview)

                        if (
                            best_candidate is None
                            or float(row_preview.get("score") or 0) > float(best_candidate.get("score") or 0)
                        ):
                            best_candidate = dict(row_preview)

                        actions.append({
                            "action": "dom_row_seen",
                            "round": page_round,
                            "index": row_info.get("index"),
                            "score": score.get("score"),
                            "matched_terms": matched_terms,
                            "matched_tokens": score.get("matched_tokens") or [],
                            "text_preview": row_text[:300],
                        })

                        if matched_terms or float(score.get("score") or 0) >= 0.45:
                            clicked = await page.evaluate(
                                """(targetIndex) => {
                                  const rows = Array.from(document.querySelectorAll(
                                    'table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'
                                  ));
                                  const row = rows[targetIndex];
                                  if (!row) return false;
                                  row.scrollIntoView({block: 'center', inline: 'center'});
                                  row.click();
                                  const ctl = row.querySelector('td.details-control, td.dtr-control, button, a');
                                  if (ctl) ctl.click();
                                  return true;
                                }""",
                                row_info.get("index"),
                            )
                            await page.wait_for_timeout(1500)
                            matched_row_found = bool(clicked)
                            actions.append({
                                "action": "dom_row_matched_and_activated",
                                "round": page_round,
                                "index": row_info.get("index"),
                                "clicked": bool(clicked),
                                "score": score.get("score"),
                                "matched_terms": matched_terms,
                                "matched_tokens": score.get("matched_tokens") or [],
                                "text_preview": row_text[:500],
                            })
                            if clicked:
                                raise StopAsyncIteration
                except StopAsyncIteration:
                    raise
                except Exception as exc:
                    actions.append({"action": "dom_row_snapshot_error", "round": page_round, "error": str(exc)})

            for i in range(min(count, 25)):
                try:
                    row = rows.nth(i)
                    row_text = await row.inner_text(timeout=1500)
                    score = _score_row_text(row_text, target_terms)
                    matched_terms = score.get("matched_terms") or []
                    row_preview = {
                        "round": page_round,
                        "index": i,
                        "score": score.get("score"),
                        "matched_terms": matched_terms,
                        "matched_tokens": score.get("matched_tokens") or [],
                        "text_preview": row_text[:500],
                    }
                    all_row_previews.append(row_preview)

                    if (
                        best_candidate is None
                        or float(row_preview.get("score") or 0) > float(best_candidate.get("score") or 0)
                    ):
                        best_candidate = dict(row_preview)

                    actions.append({
                        "action": "deep_row_seen",
                        "round": page_round,
                        "index": i,
                        "score": score.get("score"),
                        "matched_terms": matched_terms,
                        "matched_tokens": score.get("matched_tokens") or [],
                        "text_preview": row_text[:300],
                    })

                    if matched_terms or float(score.get("score") or 0) >= 0.45:
                        await row.click(timeout=2500, force=True)
                        await page.wait_for_timeout(1000)
                        matched_row_found = True
                        actions.append({
                            "action": "deep_row_matched_and_activated",
                            "round": page_round,
                            "index": i,
                            "score": score.get("score"),
                            "matched_terms": matched_terms,
                            "matched_tokens": score.get("matched_tokens") or [],
                            "text_preview": row_text[:500],
                        })

                        try:
                            plus = row.locator("td.details-control, td.dtr-control").first
                            if await plus.count() > 0:
                                await plus.click(timeout=2500, force=True)
                                await page.wait_for_timeout(1500)
                                actions.append({"action": "deep_row_expanded", "round": page_round, "index": i})
                        except Exception as exc:
                            actions.append({"action": "deep_row_expand_error", "round": page_round, "index": i, "error": str(exc)})

                        # Stop pagination scan once a likely row is activated.
                        page_round = 999
                        raise StopAsyncIteration

                except StopAsyncIteration:
                    raise
                except Exception as exc:
                    actions.append({"action": "deep_row_error", "round": page_round, "index": i, "error": str(exc)})

            # Try DataTables next page.
            next_clicked = False
            for next_selector in [
                "a.paginate_button.next:not(.disabled)",
                "#tendeList_next:not(.disabled)",
                "#tenderList_next:not(.disabled)",
                "li.paginate_button.next:not(.disabled) a",
                "a:has-text('Next')",
            ]:
                try:
                    nxt = page.locator(next_selector)
                    if await nxt.count() > 0:
                        await nxt.first.click(timeout=2500, force=True)
                        await page.wait_for_timeout(2500)
                        actions.append({"action": "pagination_next_clicked", "round": page_round, "selector": next_selector})
                        next_clicked = True
                        break
                except Exception as exc:
                    actions.append({"action": "pagination_next_error", "round": page_round, "selector": next_selector, "error": str(exc)})

            if not next_clicked:
                try:
                    await page.mouse.wheel(0, 900)
                    await page.wait_for_timeout(1800)
                    actions.append({"action": "page_scrolled_for_more_rows", "round": page_round})
                except Exception as exc:
                    actions.append({"action": "page_scroll_error", "round": page_round, "error": str(exc)})
                    break

        except StopAsyncIteration:
            break
        except Exception as exc:
            actions.append({"action": "deep_row_scan_error", "round": page_round, "error": str(exc)})
            break

    if (
        not matched_row_found
        and best_candidate
        and float(best_candidate.get("score") or 0) > 0
        and best_candidate.get("source") != "dom_snapshot"
        and int(best_candidate.get("round") or -1) == pagination_rounds_attempted - 1
    ):
        try:
            rows = page.locator("table tbody tr:visible")
            candidate_index = int(best_candidate.get("index") or 0)
            if await rows.count() > candidate_index:
                row = rows.nth(candidate_index)
                await row.click(timeout=2500, force=True)
                await page.wait_for_timeout(1000)
                actions.append({
                    "action": "best_candidate_row_activated",
                    "round": best_candidate.get("round"),
                    "index": candidate_index,
                    "score": best_candidate.get("score"),
                    "matched_terms": best_candidate.get("matched_terms") or [],
                    "matched_tokens": best_candidate.get("matched_tokens") or [],
                    "text_preview": best_candidate.get("text_preview") or "",
                })
                matched_row_found = True
        except Exception as exc:
            actions.append({
                "action": "best_candidate_row_activation_error",
                "candidate": best_candidate,
                "error": str(exc),
            })
    elif not matched_row_found and best_candidate and float(best_candidate.get("score") or 0) > 0:
        actions.append({
            "action": "best_candidate_row_activation_skipped",
            "reason": "candidate_not_on_current_visible_page",
            "candidate": best_candidate,
        })

    actions.append({
        "action": "row_matching_diagnostics",
        "target_terms_used": target_terms,
        "all_visible_row_previews_scanned": all_row_previews,
        "pagination_rounds_attempted": pagination_rounds_attempted,
        "best_candidate_row": best_candidate,
    })

    # Activate only matching visible rows. Some eTenders buttons remain disabled until
    # a row is selected, but clicking unrelated rows causes wrong opportunity targeting.
    row_activation_selectors = [
        "table tbody tr:visible",
        "#tenderList tbody tr:visible",
        ".dataTables_wrapper table tbody tr:visible",
    ]

    for selector in row_activation_selectors:
        try:
            rows = page.locator(selector)
            count = await rows.count()
            actions.append({"action": "row_activation_selector_checked", "selector": selector, "count": count})
            for i in range(min(count, 10)):
                try:
                    row = rows.nth(i)
                    txt = await row.inner_text(timeout=1500)
                    score = _score_row_text(txt, target_terms)
                    matched_terms = score.get("matched_terms") or []
                    if matched_terms or float(score.get("score") or 0) >= 0.45:
                        await row.click(timeout=2500, force=True)
                        await page.wait_for_timeout(800)
                        actions.append({
                            "action": "row_activated",
                            "selector": selector,
                            "index": i,
                            "score": score.get("score"),
                            "matched_terms": matched_terms,
                            "matched_tokens": score.get("matched_tokens") or [],
                            "text_preview": txt[:400],
                        })
                except Exception as exc:
                    actions.append({"action": "row_activation_error", "selector": selector, "index": i, "error": str(exc)})
        except Exception as exc:
            actions.append({"action": "row_activation_selector_error", "selector": selector, "error": str(exc)})

    matched_already = any(
        action.get("action") in {
            "deep_row_matched_and_activated",
            "dom_row_matched_and_activated",
            "best_candidate_row_activated",
            "row_activated",
        }
        for action in actions
    )

    if not matched_already:
        actions.append({"action": "document_click_skipped", "reason": "no_matched_or_best_row_activated"})
        return actions

    actions.append({"action": "generic_expand_skipped", "reason": "matched_or_best_row_already_activated"})

    # Click document/download anchors/buttons.
    click_selectors = []
    for token in tokens:
        short = token[:40].replace("'", "\\'")
        click_selectors += [
            f"a:has-text('{short}')",
            f"button:has-text('{short}')",
            f"text={short}",
        ]

    click_selectors += [
        "a[href*='Download']",
        "a[href*='download']",
        "a[href*='Document']",
        "a[href*='document']",
        "a[href*='support']",
        "a[href*='Support']",
        "button:has-text('Download')",
        "button:has-text('Documents')",
        "button:has-text('Document')",
        "button:has-text('View')",
        "i.fa-download",
        ".fa-download",
        ".download",
    ]

    for selector in click_selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "click_selector_checked", "selector": selector, "count": count})
            if count > 0:
                for idx in range(min(count, 3)):
                    try:
                        async with page.expect_download(timeout=7000) as dl:
                            await loc.nth(idx).click(timeout=5000, force=True)
                        download = await dl.value
                        # Actual saving is handled by page download handler.
                        actions.append({"action": "download_triggered", "selector": selector, "index": idx, "url": download.url})
                        return actions
                    except Exception:
                        try:
                            await loc.nth(idx).click(timeout=5000, force=True)
                            actions.append({"action": "clicked", "selector": selector, "index": idx})
                            await page.wait_for_timeout(4000)
                        except Exception as exc:
                            actions.append({"action": "click_error", "selector": selector, "index": idx, "error": str(exc)})
        except Exception as exc:
            actions.append({"action": "click_selector_error", "selector": selector, "error": str(exc)})

    # Final fallback: inspect DOM for hrefs/buttons containing relevant words.
    try:
        dom_hits = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a,button')).map((el, i) => ({
              i,
              tag: el.tagName,
              text: (el.innerText || el.textContent || '').trim().slice(0, 200),
              href: el.href || el.getAttribute('href') || '',
              onclick: el.getAttribute('onclick') || '',
              cls: el.className || ''
            })).filter(x => /download|document|support|file|view|detail/i.test(JSON.stringify(x))).slice(0, 100)
            """
        )
        actions.append({"action": "dom_relevant_clickables", "items": dom_hits})
    except Exception as exc:
        actions.append({"action": "dom_relevant_clickables_error", "error": str(exc)})

    return actions


def _extract_matched_row(actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for action in actions:
        if action.get("action") in {"deep_row_matched_and_activated", "dom_row_matched_and_activated"}:
            return {
                "round": action.get("round"),
                "index": action.get("index"),
                "source": "dom_snapshot" if action.get("action") == "dom_row_matched_and_activated" else "playwright_visible_row",
                "score": action.get("score"),
                "matched_terms": action.get("matched_terms") or [],
                "matched_tokens": action.get("matched_tokens") or [],
                "text_preview": action.get("text_preview") or "",
            }
    for action in actions:
        if action.get("action") in {"best_candidate_row_activated", "row_activated"}:
            return {
                "round": action.get("round"),
                "index": action.get("index"),
                "selector": action.get("selector"),
                "score": action.get("score"),
                "matched_terms": action.get("matched_terms") or [],
                "matched_tokens": action.get("matched_tokens") or [],
                "text_preview": action.get("text_preview") or "",
            }
    return None


def _extract_row_diagnostics(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    diagnostics = {
        "target_terms_used": [],
        "all_visible_row_previews_scanned": [],
        "pagination_rounds_attempted": 0,
        "best_candidate_row": None,
    }
    for action in actions:
        if action.get("action") == "row_matching_diagnostics":
            diagnostics.update({
                "target_terms_used": action.get("target_terms_used") or [],
                "all_visible_row_previews_scanned": action.get("all_visible_row_previews_scanned") or [],
                "pagination_rounds_attempted": action.get("pagination_rounds_attempted") or 0,
                "best_candidate_row": action.get("best_candidate_row"),
            })
            break
    if not diagnostics["target_terms_used"]:
        for action in actions:
            if action.get("action") == "target_terms_used":
                diagnostics["target_terms_used"] = action.get("terms") or []
                break
    return diagnostics


async def _snapshot_row_diagnostics(page, data: Dict[str, str], source: str) -> Dict[str, Any]:
    target_terms = _build_target_terms(data)
    previews: List[Dict[str, Any]] = []
    best_candidate: Optional[Dict[str, Any]] = None

    try:
        rows = await page.evaluate(
            """() => {
              const candidates = Array.from(document.querySelectorAll(
                'table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'
              ));
              return candidates.map((row, index) => {
                const rect = row.getBoundingClientRect();
                const style = window.getComputedStyle(row);
                const text = (row.innerText || row.textContent || '').replace(/\\s+/g, ' ').trim();
                const visible = !!(
                  text &&
                  rect.width > 0 &&
                  rect.height > 0 &&
                  style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  style.opacity !== '0'
                );
                return {
                  index,
                  visible,
                  rect: {width: rect.width, height: rect.height, top: rect.top, left: rect.left},
                  text: text.slice(0, 1000)
                };
              }).filter(row => row.text).slice(0, 200);
            }"""
        )
    except Exception as exc:
        return {
            "source": source,
            "target_terms_used": target_terms,
            "all_visible_row_previews_scanned": [],
            "best_candidate_row": None,
            "error": str(exc),
        }

    for row in rows:
        if not row.get("visible"):
            continue
        row_text = row.get("text") or ""
        score = _score_row_text(row_text, target_terms)
        preview = {
            "source": source,
            "index": row.get("index"),
            "score": score.get("score"),
            "matched_terms": score.get("matched_terms") or [],
            "matched_tokens": score.get("matched_tokens") or [],
            "text_preview": row_text[:500],
        }
        previews.append(preview)
        if best_candidate is None or float(preview.get("score") or 0) > float(best_candidate.get("score") or 0):
            best_candidate = dict(preview)

    return {
        "source": source,
        "target_terms_used": target_terms,
        "all_visible_row_previews_scanned": previews,
        "best_candidate_row": best_candidate,
    }


async def _capture(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return _v50_9_4_empty_capture_result(
            {},
            {},
            status="error",
            message="Playwright not installed or unavailable.",
            error=str(exc),
            helper_error_type=type(exc).__name__,
            helper_error_message=str(exc),
        )

    data = _extract_payload(payload)
    configured_cdp_url = _clean(payload.get("cdp_url") or os.getenv("ETENDERS_CDP_URL") or "")
    output_dir = Path(str(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    wait_seconds = _safe_int(payload.get("wait_seconds") or 45, 45)
    headless = _safe_bool(payload.get("headless"), _safe_bool(os.getenv("ETENDERS_HELPER_HEADLESS"), False))
    browser_launch_timeout_ms = _safe_int(
        payload.get("browser_launch_timeout_ms") or os.getenv("ETENDERS_HELPER_BROWSER_TIMEOUT_MS") or 45000,
        45000,
    )
    managed_executable_path = _clean(
        payload.get("chromium_executable_path")
        or os.getenv("ETENDERS_CHROMIUM_EXECUTABLE")
        or os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        or (
            DEFAULT_PLAYWRIGHT_HEADLESS_SHELL_EXECUTABLE
            if headless and Path(DEFAULT_PLAYWRIGHT_HEADLESS_SHELL_EXECUTABLE).exists()
            else ""
        )
        or (DEFAULT_PLAYWRIGHT_CHROMIUM_EXECUTABLE if Path(DEFAULT_PLAYWRIGHT_CHROMIUM_EXECUTABLE).exists() else "")
    )

    cdp_resolution = _resolve_cdp_endpoint(configured_cdp_url) if configured_cdp_url else {
        "ok": False,
        "input_cdp_url": "",
        "version_url": "",
        "status_code": 0,
        "raw_websocket_url": "",
        "resolved_websocket_url": "",
        "json": None,
        "error": "empty_cdp_url",
    }
    network_events: List[Dict[str, Any]] = []
    download_events: List[Dict[str, Any]] = []
    console_events: List[Dict[str, Any]] = []
    page_errors: List[str] = []
    screenshots: List[str] = []
    matched_row: Optional[Dict[str, Any]] = None
    row_diagnostics: Dict[str, Any] = {
        "target_terms_used": [],
        "all_visible_row_previews_scanned": [],
        "pagination_rounds_attempted": 0,
        "best_candidate_row": None,
    }
    active_row_execution: Dict[str, Any] = {
        "row_clicked": False,
        "row_expanded": False,
        "expanded_dom_detected": False,
        "tender_detail_detected": False,
        "upload_controls_detected": False,
        "download_controls_detected": False,
        "documents_section_found": False,
        "tender_documents_text_limited": "",
        "document_anchor_count": 0,
        "all_anchor_hrefs_limited": [],
        "all_anchor_texts_limited": [],
        "download_like_anchor_count": 0,
        "blob_like_string_count": 0,
        "visible_text_limited": "",
        "expanded_dom": None,
        "table_container_found": False,
        "datatables_processing_seen": False,
        "datatables_processing_finished": False,
        "main_response_status": 0,
        "body_text_length": 0,
        "body_html_length": 0,
        "body_text_preview_limited": "",
        "visible_row_count": 0,
        "page_text_limited_before_row_search": "",
        "table_count": 0,
        "row_count_by_selector": {},
        "first_rows_text_limited": [],
        "visible_links_limited": [],
        "page_url_after_load": "",
        "page_title": "",
        "screenshot_path": "",
        "helper_input_url": "",
        "helper_resolved_url": "",
        "helper_used_detail_page": False,
        "helper_used_opportunities_page": False,
        "helper_preserved_query_params": False,
        "detail_page_url_available": False,
        "opportunities_url_available": False,
        "helper_error_type": "",
        "helper_error_message_limited": "",
        "browser_mode": "failed",
    }

    playwright = None
    browser = None
    context = None
    managed_user_data_dir = ""
    helper_browser_mode = "failed"

    try:
        playwright = await async_playwright().start()
        browser_attach_error = ""

        if cdp_resolution.get("ok"):
            try:
                browser = await playwright.chromium.connect_over_cdp(cdp_resolution["resolved_websocket_url"])
                helper_browser_mode = "cdp_attach"
            except Exception as exc:
                browser_attach_error = str(exc)

        if helper_browser_mode != "cdp_attach":
            browser_launch_error = browser_attach_error or _clean(cdp_resolution.get("error") or cdp_resolution.get("message") or "")
            try:
                managed_user_data_dir = tempfile.mkdtemp(prefix=f"lmcp-etenders-helper-{data['tender_id'] or 'browser'}-")
                launch_headless_values = [headless]
                if headless is False:
                    launch_headless_values.append(True)
                elif headless is True:
                    launch_headless_values.append(False)

                last_launch_exc: Optional[Exception] = None
                for launch_headless in dict.fromkeys(launch_headless_values):
                    launch_kwargs: Dict[str, Any] = {
                        "headless": launch_headless,
                        "viewport": {"width": 1440, "height": 900},
                        "accept_downloads": True,
                        "timeout": browser_launch_timeout_ms,
                    }
                    if managed_executable_path:
                        launch_kwargs["executable_path"] = managed_executable_path
                    try:
                        context = await playwright.chromium.launch_persistent_context(
                            managed_user_data_dir,
                            **launch_kwargs,
                        )
                        last_launch_exc = None
                        break
                    except Exception as exc:
                        last_launch_exc = exc
                        context = None
                        continue

                if context is None:
                    raise last_launch_exc or RuntimeError("playwright_managed_launch_failed")
                browser = getattr(context, "browser", None)
                page = context.pages[0] if context.pages else await context.new_page()
                helper_browser_mode = "playwright_managed"
            except Exception as exc:
                helper_browser_mode = "failed"
                browser_launch_error = browser_launch_error or str(exc)
                return _v50_9_4_empty_capture_result(
                    data,
                    cdp_resolution,
                    status="error",
                    message="Browser launch failed.",
                    helper_error_type=type(exc).__name__,
                    helper_error_message=browser_launch_error,
                )
        else:
            context = browser.contexts[0] if browser and browser.contexts else await browser.new_context(accept_downloads=True)
            page = context.pages[0] if context.pages else await context.new_page()

        context.set_default_timeout(wait_seconds * 1000)
        active_row_execution["browser_mode"] = helper_browser_mode
        if helper_browser_mode == "playwright_managed":
            active_row_execution["helper_input_url"] = _clean(configured_cdp_url or data.get("tender_url") or ETENDERS_OPPORTUNITIES)

        async def on_request(request):
            try:
                if _looks_relevant_url(request.url):
                    network_events.append({
                        "type": "request",
                        "url": request.url,
                        "method": request.method,
                        "headers": await request.all_headers(),
                        "post_data": request.post_data,
                    })
            except Exception as exc:
                network_events.append({"type": "request_error", "error": str(exc)})

        async def on_response(response):
            try:
                headers = await response.all_headers()
                if _looks_relevant_response(headers, response.url):
                    network_events.append({
                        "type": "response",
                        "url": response.url,
                        "status": response.status,
                        "headers": headers,
                        "request_method": response.request.method,
                        "request_headers": await response.request.all_headers(),
                        "post_data": response.request.post_data,
                    })
            except Exception as exc:
                network_events.append({"type": "response_error", "error": str(exc)})

        async def on_download(download):
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                suggested = download.suggested_filename
                safe = _safe_filename(suggested or data["filename"] or "etenders_download.pdf")
                path = output_dir / f"ETENDERS_{data['tender_id']}__{safe}"
                await download.save_as(str(path))
                download_events.append({
                    "url": download.url,
                    "suggested_filename": suggested,
                    "saved_path": str(path),
                    "exists": path.exists(),
                    "size": path.stat().st_size if path.exists() else 0,
                })
            except Exception as exc:
                download_events.append({"error": str(exc)})

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("download", on_download)
        page.on("console", lambda msg: console_events.append({"type": msg.type, "text": msg.text[:500]}))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        routing = _resolve_helper_urls(data)
        helper_input_url = _clean(routing.get("helper_input_url") or data.get("tender_url") or ETENDERS_OPPORTUNITIES)
        helper_used_detail_page = False
        helper_used_opportunities_page = False
        search_actions: List[Dict[str, Any]] = []
        click_actions: List[Dict[str, Any]] = []
        modal_actions_2: List[Dict[str, Any]] = []

        async def _run_opportunities_flow(opportunities_url: str, main_status: int) -> None:
            nonlocal active_row_execution, matched_row, row_diagnostics, search_actions, click_actions, modal_actions_2, helper_used_opportunities_page
            helper_used_opportunities_page = True
            forced_tab_actions = await _force_currently_advertised_tab(page)
            pre_search_row_diagnostics = await _snapshot_row_diagnostics(
                page,
                {**data, "tender_url": opportunities_url},
                "pre_search_currently_advertised",
            )
            prior_row_execution = dict(active_row_execution)
            row_execution = await _activate_best_candidate_row(
                page,
                {**data, "tender_url": opportunities_url, "output_dir": str(output_dir), "main_response_status": str(main_status)},
                pre_search_row_diagnostics,
            )
            browser_mode = _clean(prior_row_execution.get("browser_mode") or helper_browser_mode or "failed")
            active_row_execution = {**prior_row_execution, **(row_execution or {}), "browser_mode": browser_mode}
            matched_row = active_row_execution.get("matched_row") or matched_row

            if active_row_execution.get("row_clicked"):
                search_actions = forced_tab_actions + [
                    {
                        "action": "search_skipped_after_active_matched_row",
                        "reason": "best_candidate_row_clicked",
                    }
                ]
                modal_actions_2 = await _dismiss_modals(page)
                click_actions = active_row_execution.get("actions") or []
                click_actions = click_actions + await _expand_and_click_documents(page, {**data, "tender_url": opportunities_url})
                row_diagnostics = {
                    "target_terms_used": pre_search_row_diagnostics.get("target_terms_used") or [],
                    "all_visible_row_previews_scanned": pre_search_row_diagnostics.get("all_visible_row_previews_scanned") or [],
                    "pagination_rounds_attempted": 1,
                    "best_candidate_row": pre_search_row_diagnostics.get("best_candidate_row"),
                }
            else:
                search_actions = forced_tab_actions + await _search_opportunities(page, data["search_text"])
                modal_actions_2 = await _dismiss_modals(page)
                click_actions = (active_row_execution.get("actions") or []) + await _expand_and_click_documents(page, {**data, "tender_url": opportunities_url})
                matched_row = _extract_matched_row(click_actions)
                row_diagnostics = _extract_row_diagnostics(click_actions)

        main_response_status = 0
        main_response = await page.goto(helper_input_url, wait_until="domcontentloaded", timeout=wait_seconds * 1000)
        main_response_status = int(getattr(main_response, "status", 0) or 0)
        await page.wait_for_timeout(3000)

        modal_actions = await _dismiss_modals(page)

        if _is_etenders_detail_url(helper_input_url):
            helper_used_detail_page = True
            detail_expanded = await _capture_expanded_dom_state(page, "detail_page_initial")
            page_title = ""
            try:
                page_title = _clean(await page.title())
            except Exception:
                pass
            active_row_execution.update({
                "row_clicked": False,
                "row_expanded": False,
                "expanded_dom_detected": bool(detail_expanded.get("expanded_dom_detected")),
                "tender_detail_detected": bool(detail_expanded.get("tender_detail_detected")),
                "upload_controls_detected": bool(detail_expanded.get("upload_controls_detected")),
                "download_controls_detected": bool(detail_expanded.get("download_controls_detected")),
                "documents_section_found": bool(detail_expanded.get("documents_section_found")),
                "tender_documents_text_limited": _clean(detail_expanded.get("tender_documents_text_limited")),
                "document_anchor_count": int(detail_expanded.get("document_anchor_count") or 0),
                "all_anchor_hrefs_limited": detail_expanded.get("all_anchor_hrefs_limited") or [],
                "all_anchor_texts_limited": detail_expanded.get("all_anchor_texts_limited") or [],
                "download_like_anchor_count": int(detail_expanded.get("download_like_anchor_count") or 0),
                "blob_like_string_count": int(detail_expanded.get("blob_like_string_count") or 0),
                "interactive_blob_candidates_count": len(detail_expanded.get("blob_links") or []),
                "blob_links": detail_expanded.get("blob_links") or [],
                "visible_text_limited": _clean(detail_expanded.get("visible_text_limited")),
                "expanded_dom": detail_expanded,
                "main_response_status": main_response_status,
                "page_url_after_load": _clean(getattr(page, "url", "")),
                "page_title": page_title,
            })
            detail_has_document_state = bool(
                detail_expanded.get("documents_section_found")
                or detail_expanded.get("download_controls_detected")
                or detail_expanded.get("blob_links")
                or int(detail_expanded.get("document_anchor_count") or 0) > 0
            )
            if not detail_has_document_state and _clean(routing.get("opportunities_url")):
                search_actions.append({
                    "action": "detail_page_fallback_to_opportunities",
                    "detail_page_url": helper_input_url,
                    "opportunities_url": _clean(routing.get("opportunities_url")),
                })
                opp_response = await page.goto(_clean(routing.get("opportunities_url")), wait_until="domcontentloaded", timeout=wait_seconds * 1000)
                main_response_status = int(getattr(opp_response, "status", 0) or main_response_status)
                await page.wait_for_timeout(3000)
                modal_actions_2 = await _dismiss_modals(page)
                await _run_opportunities_flow(_clean(routing.get("opportunities_url")), main_response_status)
        else:
            await _run_opportunities_flow(_clean(routing.get("opportunities_url") or helper_input_url), main_response_status)

        if not row_diagnostics.get("all_visible_row_previews_scanned"):
            row_diagnostics["all_visible_row_previews_scanned"] = row_diagnostics.get("all_visible_row_previews_scanned") or []
        if not row_diagnostics.get("best_candidate_row"):
            row_diagnostics["best_candidate_row"] = row_diagnostics.get("best_candidate_row")
        if not row_diagnostics.get("target_terms_used"):
            row_diagnostics["target_terms_used"] = row_diagnostics.get("target_terms_used") or []
        if not matched_row and active_row_execution.get("matched_row"):
            matched_row = active_row_execution.get("matched_row")

        helper_resolved_url = _clean(getattr(page, "url", ""))
        active_row_execution["interactive_blob_candidates_count"] = int(
            active_row_execution.get("interactive_blob_candidates_count")
            or len((active_row_execution.get("expanded_dom") or {}).get("blob_links") or [])
            or 0
        )
        active_row_execution["helper_input_url"] = helper_input_url
        active_row_execution["helper_resolved_url"] = helper_resolved_url
        active_row_execution["helper_used_detail_page"] = helper_used_detail_page
        active_row_execution["helper_used_opportunities_page"] = helper_used_opportunities_page
        active_row_execution["helper_preserved_query_params"] = bool(routing.get("helper_preserved_query_params"))
        active_row_execution["detail_page_url_available"] = bool(routing.get("detail_page_url_available"))
        active_row_execution["opportunities_url_available"] = bool(routing.get("opportunities_url_available"))
        active_row_execution["blob_links"] = active_row_execution.get("blob_links") or (active_row_execution.get("expanded_dom") or {}).get("blob_links") or []

        await page.wait_for_timeout(wait_seconds * 1000)

        output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = output_dir / f"ETENDERS_{data['tender_id']}__v50_9_4_page.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            screenshots.append(str(screenshot_path))
        except Exception:
            pass

        verified_downloads = [d for d in download_events if d.get("exists") and int(d.get("size") or 0) > 0]

        log_path = output_dir / f"ETENDERS_{data['tender_id']}__v50_9_4_capture.json"
        log_payload = {
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": data,
            "cdp_resolution": cdp_resolution,
            "cdp_resolved": cdp_resolution,
            "matched_row": matched_row,
            "target_terms_used": row_diagnostics.get("target_terms_used") or [],
            "all_visible_row_previews_scanned": row_diagnostics.get("all_visible_row_previews_scanned") or [],
            "pagination_rounds_attempted": row_diagnostics.get("pagination_rounds_attempted") or 0,
            "best_candidate_row": row_diagnostics.get("best_candidate_row"),
            "helper_input_url": active_row_execution.get("helper_input_url", ""),
            "helper_resolved_url": active_row_execution.get("helper_resolved_url", ""),
            "helper_used_detail_page": active_row_execution.get("helper_used_detail_page", False),
            "helper_used_opportunities_page": active_row_execution.get("helper_used_opportunities_page", False),
            "helper_preserved_query_params": active_row_execution.get("helper_preserved_query_params", False),
            "detail_page_url_available": active_row_execution.get("detail_page_url_available", False),
            "opportunities_url_available": active_row_execution.get("opportunities_url_available", False),
            "browser_mode": active_row_execution.get("browser_mode", "failed"),
            "interactive_blob_candidates_count": active_row_execution.get("interactive_blob_candidates_count", 0),
            "row_clicked": active_row_execution.get("row_clicked", False),
            "row_expanded": active_row_execution.get("row_expanded", False),
            "expanded_dom_detected": active_row_execution.get("expanded_dom_detected", False),
            "tender_detail_detected": active_row_execution.get("tender_detail_detected", False),
            "upload_controls_detected": active_row_execution.get("upload_controls_detected", False),
            "download_controls_detected": active_row_execution.get("download_controls_detected", False),
            "expanded_dom": active_row_execution.get("expanded_dom"),
            "active_tab_name": active_row_execution.get("active_tab_name"),
            "modal_actions": modal_actions + modal_actions_2,
            "search_actions": search_actions,
            "click_actions": click_actions,
            "network_events": network_events,
            "download_events": download_events,
            "console_events": console_events[-100:],
            "page_errors": page_errors,
            "screenshots": screenshots,
        }
        log_path.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2))

        return {
            "status": "ok" if verified_downloads else "needs_review_or_manual_click",
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": data,
            "cdp_resolution": cdp_resolution,
            "cdp_resolved": cdp_resolution,
            "matched_row": matched_row,
            "target_terms_used": row_diagnostics.get("target_terms_used") or [],
            "all_visible_row_previews_scanned": row_diagnostics.get("all_visible_row_previews_scanned") or [],
            "pagination_rounds_attempted": row_diagnostics.get("pagination_rounds_attempted") or 0,
            "best_candidate_row": row_diagnostics.get("best_candidate_row"),
            "helper_input_url": active_row_execution.get("helper_input_url", ""),
            "helper_resolved_url": active_row_execution.get("helper_resolved_url", ""),
            "helper_used_detail_page": active_row_execution.get("helper_used_detail_page", False),
            "helper_used_opportunities_page": active_row_execution.get("helper_used_opportunities_page", False),
            "helper_preserved_query_params": active_row_execution.get("helper_preserved_query_params", False),
            "detail_page_url_available": active_row_execution.get("detail_page_url_available", False),
            "opportunities_url_available": active_row_execution.get("opportunities_url_available", False),
            "browser_mode": active_row_execution.get("browser_mode", "failed"),
            "interactive_blob_candidates_count": active_row_execution.get("interactive_blob_candidates_count", 0),
            "table_container_found": active_row_execution.get("table_container_found", False),
            "datatables_processing_seen": active_row_execution.get("datatables_processing_seen", False),
            "datatables_processing_finished": active_row_execution.get("datatables_processing_finished", False),
            "main_response_status": active_row_execution.get("main_response_status", 0),
            "body_text_length": active_row_execution.get("body_text_length", 0),
            "body_html_length": active_row_execution.get("body_html_length", 0),
            "body_text_preview_limited": active_row_execution.get("body_text_preview_limited", ""),
            "visible_row_count": active_row_execution.get("visible_row_count", 0),
            "page_text_limited_before_row_search": active_row_execution.get("page_text_limited_before_row_search", ""),
            "table_count": active_row_execution.get("table_count", 0),
            "row_count_by_selector": active_row_execution.get("row_count_by_selector", {}),
            "first_rows_text_limited": active_row_execution.get("first_rows_text_limited", []),
            "visible_links_limited": active_row_execution.get("visible_links_limited", []),
            "page_url_after_load": active_row_execution.get("page_url_after_load", ""),
            "page_title": active_row_execution.get("page_title", ""),
            "screenshot_path": active_row_execution.get("screenshot_path", ""),
            "row_found": bool(active_row_execution.get("row_clicked") or active_row_execution.get("matched_row")),
            "row_clicked": active_row_execution.get("row_clicked", False),
            "row_expanded": active_row_execution.get("row_expanded", False),
            "row_match_strategy": active_row_execution.get("row_match_strategy", ""),
            "row_match_text": active_row_execution.get("row_match_text", ""),
            "matched_row_text_limited": active_row_execution.get("matched_row_text_limited", ""),
            "expanded_dom_detected": active_row_execution.get("expanded_dom_detected", False),
            "tender_detail_detected": active_row_execution.get("tender_detail_detected", False),
            "upload_controls_detected": active_row_execution.get("upload_controls_detected", False),
            "download_controls_detected": active_row_execution.get("download_controls_detected", False),
            "documents_section_found": active_row_execution.get("documents_section_found", False),
            "row_selector_used": active_row_execution.get("row_selector_used", ""),
            "row_click_target_used": active_row_execution.get("row_click_target_used", ""),
            "post_click_wait_ms": active_row_execution.get("post_click_wait_ms", 0),
            "tender_documents_text_limited": active_row_execution.get("tender_documents_text_limited", ""),
            "document_anchor_count": active_row_execution.get("document_anchor_count", 0),
            "all_anchor_hrefs_limited": active_row_execution.get("all_anchor_hrefs_limited", []),
            "all_anchor_texts_limited": active_row_execution.get("all_anchor_texts_limited", []),
            "download_like_anchor_count": active_row_execution.get("download_like_anchor_count", 0),
            "blob_like_string_count": active_row_execution.get("blob_like_string_count", 0),
            "interactive_blob_candidates_count": active_row_execution.get("interactive_blob_candidates_count", 0),
            "blob_links": active_row_execution.get("blob_links", []),
            "visible_text_limited": active_row_execution.get("visible_text_limited", ""),
            "helper_error_type": active_row_execution.get("helper_error_type", ""),
            "helper_error_message_limited": active_row_execution.get("helper_error_message_limited", ""),
            "expanded_dom": active_row_execution.get("expanded_dom"),
            "active_tab_name": active_row_execution.get("active_tab_name"),
            "verified_download_count": len(verified_downloads),
            "verified_downloads": verified_downloads,
            "network_event_count": len(network_events),
            "relevant_network_events": network_events[-120:],
            "download_events": download_events,
            "modal_actions": modal_actions + modal_actions_2,
            "search_actions": search_actions,
            "click_actions": click_actions[:150],
            "console_events": console_events[-30:],
            "page_errors": page_errors,
            "screenshots": screenshots,
            "screenshot_path": screenshots[-1] if screenshots else "",
            "capture_log": str(log_path),
            "safe_to_process": bool(verified_downloads),
            "notes": [
                "V50.9.4 auto-dismisses modals, searches the table, expands rows and clicks likely document controls.",
                "If no verified download appears, review click_actions.dom_relevant_clickables and capture_log.",
                "This engine does not bypass CAPTCHA or access controls.",
            ],
        }

    except Exception as exc:
        return _v50_9_4_empty_capture_result(
            data,
            cdp_resolution,
            status="error",
            message="DOM modal autoclick capture failed.",
            error=str(exc),
            helper_error_type=type(exc).__name__,
            helper_error_message=str(exc),
        )

    finally:
        try:
            if helper_browser_mode == "playwright_managed" and context is not None:
                await context.close()
        except Exception:
            pass
        try:
            if playwright:
                await playwright.stop()
        except Exception:
            pass
        if managed_user_data_dir:
            try:
                shutil.rmtree(managed_user_data_dir, ignore_errors=True)
            except Exception:
                pass


def capture_dom_modal_autoclick(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return asyncio.run(_capture(payload or {}))


def get_v50_9_4_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_cdp_url": DEFAULT_CDP_URL,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "cdp_host_header_resolution",
            "modal_auto_dismiss",
            "datatable_search",
            "row_expand_autoclick",
            "document_link_autoclick",
            "download_event_capture",
            "network_event_capture",
            "dom_clickable_discovery",
            "capture_log_generation",
        ],
    }
