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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


SERVICE_VERSION = "V50.9.4_ETENDERS_DOM_MODAL_AUTOCLICK"

DEFAULT_CDP_URL = "http://host.docker.internal:9222"
DEFAULT_OUTPUT_DIR = "runtime/playwright/downloads"
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"


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
    cdp_url = (cdp_url or DEFAULT_CDP_URL).rstrip("/")

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
    search_text = _clean(payload.get("search_text") or payload.get("title") or "DIGITAL BOOK JDA")
    tender_url = _clean(payload.get("tender_url") or ETENDERS_OPPORTUNITIES)

    return {
        "tender_id": tender_id,
        "support_document_id": support_document_id,
        "filename": filename,
        "search_text": search_text,
        "tender_url": tender_url,
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
              return {
                source,
                body_text_preview: text.slice(0, 2500),
                body_html_preview: html.slice(0, 12000),
                controls,
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
            "error": str(exc),
        }


async def _activate_best_candidate_row(page, data: Dict[str, str], seed_diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    target_terms = seed_diagnostics.get("target_terms_used") or _build_target_terms(data)
    best_candidate = seed_diagnostics.get("best_candidate_row")
    actions: List[Dict[str, Any]] = []

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

    candidate_text = _clean((best_candidate or {}).get("text_preview") or data.get("search_text") or data.get("tender_id"))
    candidate_norm = _normalise_match_text(candidate_text)
    min_score = 0.72 if candidate_norm else 0.0

    try:
        activation = await page.evaluate(
            """({candidateText, candidateNorm, targetTerms, minScore}) => {
              const norm = (value) => String(value || '')
                .toUpperCase()
                .replace(/[\\/-]+/g, ' ')
                .replace(/[^A-Z0-9]+/g, ' ')
                .replace(/\\s+/g, ' ')
                .trim();
              const tokens = (value) => norm(value).split(' ').filter(token => token.length >= 2);
              const targetTokens = Array.from(new Set([].concat(...targetTerms.map(tokens))));
              const scoreRow = (text) => {
                const rowNorm = norm(text);
                const rowTokens = new Set(tokens(text));
                const matchedTokens = targetTokens.filter(token => rowTokens.has(token));
                const matchedTerms = targetTerms.filter(term => {
                  const termNorm = norm(term);
                  return termNorm && (rowNorm.includes(termNorm) || termNorm.includes(rowNorm));
                });
                const tokenScore = matchedTokens.length / Math.max(targetTokens.length, 1);
                const termScore = matchedTerms.length / Math.max(targetTerms.filter(term => norm(term)).length, 1);
                const exactBonus = candidateNorm && (rowNorm.includes(candidateNorm) || candidateNorm.includes(rowNorm)) ? 1 : 0;
                return {
                  score: Math.max(tokenScore, termScore, exactBonus),
                  matchedTerms,
                  matchedTokens,
                  rowNorm
                };
              };

              const rows = Array.from(document.querySelectorAll('table tbody tr, table tr, [role="row"], .dataTables_wrapper tr'));
              let best = null;
              rows.forEach((row, index) => {
                const text = (row.innerText || row.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!text || text.length < 20) return;
                const rect = row.getBoundingClientRect();
                const style = window.getComputedStyle(row);
                const visible = !!(rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden');
                if (!visible) return;
                const scored = scoreRow(text);
                if (!best || scored.score > best.score) {
                  best = {
                    index,
                    score: scored.score,
                    matchedTerms: scored.matchedTerms,
                    matchedTokens: scored.matchedTokens,
                    textPreview: text.slice(0, 700)
                  };
                }
              });

              if (!best || best.score < minScore) {
                return {ok: false, reason: 'no_row_over_threshold', best};
              }

              const row = rows[best.index];
              row.scrollIntoView({block: 'center', inline: 'center'});
              row.click();

              const expanders = [
                'td.details-control',
                'td.dtr-control',
                'td:first-child',
                'button[aria-expanded]',
                'a[aria-expanded]',
                'button:has(i)',
                'a:has(i)',
                'button',
                'a'
              ];
              let expanded = false;
              let expanderSelector = '';
              for (const selector of expanders) {
                const ctl = row.querySelector(selector);
                if (!ctl) continue;
                try {
                  ctl.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, cancelable: true, view: window}));
                  ctl.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                  ctl.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                  ctl.click();
                  expanded = true;
                  expanderSelector = selector;
                  break;
                } catch(e) {}
              }

              return {ok: true, rowClicked: true, rowExpanded: expanded, expanderSelector, best};
            }""",
            {
                "candidateText": candidate_text,
                "candidateNorm": candidate_norm,
                "targetTerms": target_terms,
                "minScore": min_score,
            },
        )
        await page.wait_for_timeout(3000)
        actions.append({"action": "active_matched_row_activation", "result": activation})
    except Exception as exc:
        activation = {"ok": False, "reason": "activation_exception", "error": str(exc)}
        actions.append({"action": "active_matched_row_activation_error", "error": str(exc)})

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
            "text_preview": best.get("textPreview") or candidate_text,
            "expander_selector": activation.get("expanderSelector") or "",
        }

    expanded = await _capture_expanded_dom_state(page, "active_matched_row_execution")
    result["expanded_dom"] = expanded
    result["expanded_dom_detected"] = bool(expanded.get("expanded_dom_detected"))
    result["tender_detail_detected"] = bool(expanded.get("tender_detail_detected"))
    result["upload_controls_detected"] = bool(expanded.get("upload_controls_detected"))
    result["download_controls_detected"] = bool(expanded.get("download_controls_detected"))
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
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Playwright not installed or unavailable.",
            "error": str(exc),
            "safe_to_process": False,
        }

    data = _extract_payload(payload)
    cdp_url = _clean(payload.get("cdp_url") or DEFAULT_CDP_URL)
    output_dir = Path(str(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    wait_seconds = int(payload.get("wait_seconds") or 45)

    cdp_resolution = _resolve_cdp_endpoint(cdp_url)
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
    }

    playwright = None

    try:
        playwright = await async_playwright().start()

        if not cdp_resolution.get("ok"):
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "CDP resolution failed.",
                "cdp_resolution": cdp_resolution,
                "cdp_resolved": cdp_resolution,
                "matched_row": matched_row,
                "target_terms_used": row_diagnostics.get("target_terms_used") or [],
                "all_visible_row_previews_scanned": row_diagnostics.get("all_visible_row_previews_scanned") or [],
                "pagination_rounds_attempted": row_diagnostics.get("pagination_rounds_attempted") or 0,
                "best_candidate_row": row_diagnostics.get("best_candidate_row"),
                "row_clicked": active_row_execution.get("row_clicked", False),
                "row_expanded": active_row_execution.get("row_expanded", False),
                "expanded_dom_detected": active_row_execution.get("expanded_dom_detected", False),
                "tender_detail_detected": active_row_execution.get("tender_detail_detected", False),
                "upload_controls_detected": active_row_execution.get("upload_controls_detected", False),
                "safe_to_process": False,
            }

        browser = await playwright.chromium.connect_over_cdp(cdp_resolution["resolved_websocket_url"])

        context = browser.contexts[0] if browser.contexts else await browser.new_context(accept_downloads=True)
        page = context.pages[0] if context.pages else await context.new_page()
        context.set_default_timeout(wait_seconds * 1000)

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

        await page.goto(data["tender_url"], wait_until="domcontentloaded", timeout=wait_seconds * 1000)
        await page.wait_for_timeout(3000)

        modal_actions = await _dismiss_modals(page)

        # Force eTenders back to Currently Advertised before searching.
        # Browser sessions can persist Closed/Awarded tab state from previous runs.
        forced_tab_actions = await _force_currently_advertised_tab(page)
        pre_search_row_diagnostics = await _snapshot_row_diagnostics(
            page,
            data,
            "pre_search_currently_advertised",
        )
        active_row_execution = await _activate_best_candidate_row(page, data, pre_search_row_diagnostics)
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
            row_diagnostics = {
                "target_terms_used": pre_search_row_diagnostics.get("target_terms_used") or [],
                "all_visible_row_previews_scanned": pre_search_row_diagnostics.get("all_visible_row_previews_scanned") or [],
                "pagination_rounds_attempted": 1,
                "best_candidate_row": pre_search_row_diagnostics.get("best_candidate_row"),
            }
        else:
            search_actions = forced_tab_actions + await _search_opportunities(page, data["search_text"])
            modal_actions_2 = await _dismiss_modals(page)
            click_actions = (active_row_execution.get("actions") or []) + await _expand_and_click_documents(page, data)
            matched_row = _extract_matched_row(click_actions)
            row_diagnostics = _extract_row_diagnostics(click_actions)

        if not row_diagnostics.get("all_visible_row_previews_scanned"):
            row_diagnostics["all_visible_row_previews_scanned"] = (
                pre_search_row_diagnostics.get("all_visible_row_previews_scanned") or []
            )
        if not row_diagnostics.get("best_candidate_row"):
            row_diagnostics["best_candidate_row"] = pre_search_row_diagnostics.get("best_candidate_row")
        if not row_diagnostics.get("target_terms_used"):
            row_diagnostics["target_terms_used"] = pre_search_row_diagnostics.get("target_terms_used") or []
        if not matched_row and active_row_execution.get("matched_row"):
            matched_row = active_row_execution.get("matched_row")

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
            "row_clicked": active_row_execution.get("row_clicked", False),
            "row_expanded": active_row_execution.get("row_expanded", False),
            "expanded_dom_detected": active_row_execution.get("expanded_dom_detected", False),
            "tender_detail_detected": active_row_execution.get("tender_detail_detected", False),
            "upload_controls_detected": active_row_execution.get("upload_controls_detected", False),
            "download_controls_detected": active_row_execution.get("download_controls_detected", False),
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
            "capture_log": str(log_path),
            "safe_to_process": bool(verified_downloads),
            "notes": [
                "V50.9.4 auto-dismisses modals, searches the table, expands rows and clicks likely document controls.",
                "If no verified download appears, review click_actions.dom_relevant_clickables and capture_log.",
                "This engine does not bypass CAPTCHA or access controls.",
            ],
        }

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "DOM modal autoclick capture failed.",
            "error": str(exc),
            "input": data,
            "cdp_resolution": cdp_resolution,
            "cdp_resolved": cdp_resolution,
            "matched_row": matched_row,
            "target_terms_used": row_diagnostics.get("target_terms_used") or [],
            "all_visible_row_previews_scanned": row_diagnostics.get("all_visible_row_previews_scanned") or [],
            "pagination_rounds_attempted": row_diagnostics.get("pagination_rounds_attempted") or 0,
            "best_candidate_row": row_diagnostics.get("best_candidate_row"),
            "row_clicked": active_row_execution.get("row_clicked", False),
            "row_expanded": active_row_execution.get("row_expanded", False),
            "expanded_dom_detected": active_row_execution.get("expanded_dom_detected", False),
            "tender_detail_detected": active_row_execution.get("tender_detail_detected", False),
            "upload_controls_detected": active_row_execution.get("upload_controls_detected", False),
            "network_events": network_events[-80:],
            "download_events": download_events,
            "safe_to_process": False,
        }

    finally:
        try:
            if playwright:
                await playwright.stop()
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
