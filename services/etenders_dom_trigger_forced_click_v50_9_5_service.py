"""
LMCP V50.9.5 - eTenders DOM Trigger + Forced Click Injection Engine

Purpose:
- V50.9.4 confirmed CDP, authenticated browser reuse, and DataTables capture works.
- But the document request never fired.
- V50.9.5 removes manual-click dependency by:
    1. attaching to live Chrome CDP
    2. opening eTenders opportunities
    3. dismissing modals/overlays
    4. searching DataTables
    5. expanding candidate rows
    6. enumerating anchors/buttons/forms/onclick handlers
    7. hooking window.open, fetch, XHR, iframe src mutations
    8. force-dispatching click/pointer/mouse events
    9. capturing all document-trigger URLs and downloads

Routes:
    GET  /v50-9-5-dom-trigger-forced-click/status
    POST /v50-9-5-dom-trigger-forced-click/capture

Drop-in:
    app/services/etenders_dom_trigger_forced_click_v50_9_5_service.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


SERVICE_VERSION = "V50.9.5_ETENDERS_DOM_TRIGGER_FORCED_CLICK"

DEFAULT_CDP_URL = "http://host.docker.internal:9222"
DEFAULT_OUTPUT_DIR = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "playwright" / "downloads")
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


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
        "tenderdetails", "supportdocument", "attachment"
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
    search_text = _clean(payload.get("search_text") or payload.get("title") or "DIGITAL BOOK")
    tender_url = _clean(payload.get("tender_url") or ETENDERS_OPPORTUNITIES)

    return {
        "tender_id": tender_id,
        "support_document_id": support_document_id,
        "filename": filename,
        "search_text": search_text,
        "tender_url": tender_url,
    }


async def _install_js_hooks(page) -> None:
    await page.add_init_script(
        """
        (() => {
          window.__lmcpCapturedTriggers = window.__lmcpCapturedTriggers || [];
          window.__lmcpCapture = function(kind, data) {
            try {
              window.__lmcpCapturedTriggers.push({
                kind,
                data,
                href: location.href,
                ts: new Date().toISOString()
              });
            } catch(e) {}
          };

          const originalOpen = window.open;
          window.open = function(...args) {
            window.__lmcpCapture('window.open', {args: args.map(String)});
            return originalOpen.apply(this, args);
          };

          const originalFetch = window.fetch;
          window.fetch = function(...args) {
            try {
              window.__lmcpCapture('fetch', {
                url: String(args[0]),
                options: args[1] ? JSON.stringify(args[1]).slice(0, 2000) : null
              });
            } catch(e) {}
            return originalFetch.apply(this, args);
          };

          const OriginalXHR = window.XMLHttpRequest;
          window.XMLHttpRequest = function() {
            const xhr = new OriginalXHR();
            const originalOpenXHR = xhr.open;
            const originalSendXHR = xhr.send;
            xhr.open = function(method, url, ...rest) {
              this.__lmcpMethod = method;
              this.__lmcpUrl = url;
              window.__lmcpCapture('xhr.open', {method, url: String(url)});
              return originalOpenXHR.call(this, method, url, ...rest);
            };
            xhr.send = function(body) {
              window.__lmcpCapture('xhr.send', {
                method: this.__lmcpMethod,
                url: String(this.__lmcpUrl),
                body: body ? String(body).slice(0, 2000) : null
              });
              return originalSendXHR.call(this, body);
            };
            return xhr;
          };

          const obs = new MutationObserver((mutations) => {
            for (const m of mutations) {
              for (const node of m.addedNodes || []) {
                if (!node || !node.querySelectorAll) continue;
                const items = [];
                node.querySelectorAll('iframe,a,form').forEach((el) => {
                  items.push({
                    tag: el.tagName,
                    href: el.href || el.getAttribute('href') || '',
                    src: el.src || el.getAttribute('src') || '',
                    action: el.action || el.getAttribute('action') || '',
                    text: (el.innerText || el.textContent || '').slice(0, 200)
                  });
                });
                if (items.length) window.__lmcpCapture('mutation.clickables', items);
              }
            }
          });
          obs.observe(document.documentElement, {childList: true, subtree: true});
        })();
        """
    )


async def _dismiss_modals(page) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    texts = ["Accept", "I Accept", "OK", "Ok", "Close", "Continue", "Proceed", "Got it", "Agree", "Dismiss", "×", "x"]
    for text in texts:
        for selector in [f"button:has-text('{text}')", f"a:has-text('{text}')", f"input[value='{text}']", f"text={text}"]:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                if count:
                    await loc.first.click(timeout=1200, force=True)
                    actions.append({"action": "clicked", "selector": selector, "count": count})
                    await page.wait_for_timeout(400)
            except Exception:
                pass

    try:
        removed = await page.evaluate(
            """
            () => {
              const out = [];
              for (const sel of ['.modal-backdrop','.modal','.overlay','#cookieConsent','#consent','[role="dialog"]']) {
                document.querySelectorAll(sel).forEach(el => {
                  out.push({selector: sel, text: (el.innerText || el.textContent || '').slice(0,200)});
                  el.style.display='none';
                  el.style.visibility='hidden';
                  el.setAttribute('data-lmcp-hidden','1');
                });
              }
              document.body.classList.remove('modal-open');
              document.body.style.overflow='auto';
              return out;
            }
            """
        )
        if removed:
            actions.append({"action": "hid_overlays", "items": removed[:30]})
    except Exception as exc:
        actions.append({"action": "hide_error", "error": str(exc)})

    return actions


async def _search_and_expand(page, search_text: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    await page.wait_for_timeout(4000)

    selectors = ["input[type='search']", ".dataTables_filter input", "#tenderList_filter input", "input[aria-controls]", "input[placeholder*='Search']"]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "search_selector", "selector": selector, "count": count})
            if count:
                await loc.first.fill(search_text, timeout=3000)
                await loc.first.press("Enter", timeout=3000)
                actions.append({"action": "search_filled", "selector": selector, "search_text": search_text})
                await page.wait_for_timeout(5000)
                break
        except Exception as exc:
            actions.append({"action": "search_error", "selector": selector, "error": str(exc)})

    try:
        injected = await page.evaluate(
            """
            (term) => {
              let ok = false;
              if (window.jQuery) {
                window.jQuery('table').each(function(){
                  try {
                    const dt = window.jQuery(this).DataTable();
                    dt.search(term).draw();
                    ok = true;
                  } catch(e) {}
                });
              }
              return ok;
            }
            """,
            search_text,
        )
        actions.append({"action": "datatables_search", "ok": injected})
        await page.wait_for_timeout(5000)
    except Exception as exc:
        actions.append({"action": "datatables_search_error", "error": str(exc)})

    expand_selectors = [
        "td.details-control",
        "td.dtr-control",
        "img[src*='plus']",
        "tr:has-text('DIGITAL BOOK') td:first-child",
        "tr:has-text('JDAMARK') td:first-child",
        "tr:has-text('DIGITAL') td:first-child",
        "button:has-text('+')",
        "a:has-text('View')",
        "button:has-text('View')",
    ]

    for selector in expand_selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "expand_selector", "selector": selector, "count": count})
            for i in range(min(count, 8)):
                try:
                    await loc.nth(i).click(timeout=2500, force=True)
                    actions.append({"action": "expanded", "selector": selector, "index": i})
                    await page.wait_for_timeout(1500)
                except Exception as exc:
                    actions.append({"action": "expand_error", "selector": selector, "index": i, "error": str(exc)})
        except Exception as exc:
            actions.append({"action": "expand_selector_error", "selector": selector, "error": str(exc)})

    return actions


async def _enumerate_dom(page) -> Dict[str, Any]:
    return await page.evaluate(
        """
        () => {
          const out = [];
          const all = Array.from(document.querySelectorAll('a,button,input,form,iframe,img,[onclick],[role="button"],td,span,i'));
          all.forEach((el, i) => {
            const txt = (el.innerText || el.textContent || el.alt || el.title || '').trim();
            const href = el.href || el.getAttribute('href') || '';
            const src = el.src || el.getAttribute('src') || '';
            const onclick = el.getAttribute('onclick') || '';
            const action = el.action || el.getAttribute('action') || '';
            const cls = typeof el.className === 'string' ? el.className : '';
            const id = el.id || '';
            const json = JSON.stringify({txt,href,src,onclick,action,cls,id}).toLowerCase();
            if (/download|document|support|file|pdf|tender|jdamark|digital|plus|detail|view|e7904db8|155559/.test(json)) {
              const rect = el.getBoundingClientRect();
              out.push({
                index: i,
                tag: el.tagName,
                text: txt.slice(0,300),
                href,
                src,
                onclick,
                action,
                cls,
                id,
                title: el.title || '',
                alt: el.alt || '',
                visible: !!(rect.width || rect.height),
                rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height}
              });
            }
          });
          return {
            url: location.href,
            title: document.title,
            total_elements: all.length,
            hits: out.slice(0, 300),
            lmcpCapturedTriggers: window.__lmcpCapturedTriggers || []
          };
        }
        """
    )


async def _force_click_candidates(page, dom_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    hits = dom_snapshot.get("hits") or []

    # Prioritize actual links/buttons with document-like metadata.
    def score(hit: Dict[str, Any]) -> int:
        blob = json.dumps(hit).lower()
        s = 0
        for word, pts in [
            ("e7904db8", 100), ("155559", 60), ("pdf", 50), ("support", 40), ("download", 35),
            ("document", 30), ("file", 20), ("jdamark", 15), ("digital", 15), ("view", 10),
        ]:
            if word in blob:
                s += pts
        if hit.get("href"):
            s += 10
        if hit.get("onclick"):
            s += 15
        if hit.get("visible"):
            s += 5
        return s

    ranked = sorted(hits, key=score, reverse=True)[:80]
    actions.append({"action": "ranked_candidates", "items": ranked[:50]})

    # Click by JS index because normal selectors may miss dynamic/hidden controls.
    for hit in ranked[:40]:
        idx = hit.get("index")
        try:
            result = await page.evaluate(
                """
                (targetIndex) => {
                  const all = Array.from(document.querySelectorAll('a,button,input,form,iframe,img,[onclick],[role="button"],td,span,i'));
                  const el = all[targetIndex];
                  if (!el) return {ok:false, error:'not_found'};
                  try { el.scrollIntoView({block:'center', inline:'center'}); } catch(e) {}
                  const before = {
                    href: el.href || el.getAttribute('href') || '',
                    src: el.src || el.getAttribute('src') || '',
                    onclick: el.getAttribute('onclick') || '',
                    text: (el.innerText || el.textContent || el.alt || el.title || '').slice(0,200),
                    tag: el.tagName
                  };
                  const events = ['pointerdown','mousedown','mouseup','pointerup','click'];
                  for (const ev of events) {
                    try {
                      el.dispatchEvent(new MouseEvent(ev, {bubbles:true, cancelable:true, view:window}));
                    } catch(e) {}
                  }
                  try { el.click(); } catch(e) {}
                  return {ok:true, before};
                }
                """,
                idx,
            )
            actions.append({"action": "forced_click", "index": idx, "score": score(hit), "hit": hit, "result": result})
            await page.wait_for_timeout(2500)
        except Exception as exc:
            actions.append({"action": "forced_click_error", "index": idx, "hit": hit, "error": str(exc)})

    return actions


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
    wait_seconds = int(payload.get("wait_seconds") or 60)

    cdp_resolution = _resolve_cdp_endpoint(cdp_url)
    network_events: List[Dict[str, Any]] = []
    download_events: List[Dict[str, Any]] = []
    console_events: List[Dict[str, Any]] = []
    page_errors: List[str] = []
    screenshots: List[str] = []
    triggered_pages: List[Dict[str, Any]] = []

    playwright = None

    try:
        playwright = await async_playwright().start()

        if not cdp_resolution.get("ok"):
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "CDP resolution failed.",
                "cdp_resolution": cdp_resolution,
                "safe_to_process": False,
            }

        browser = await playwright.chromium.connect_over_cdp(cdp_resolution["resolved_websocket_url"])
        context = browser.contexts[0] if browser.contexts else await browser.new_context(accept_downloads=True)
        page = context.pages[0] if context.pages else await context.new_page()
        context.set_default_timeout(wait_seconds * 1000)

        async def attach_page_handlers(p):
            async def on_request(request):
                try:
                    if _looks_relevant_url(request.url):
                        network_events.append({
                            "type": "request",
                            "page_url": p.url,
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
                            "page_url": p.url,
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

            p.on("request", on_request)
            p.on("response", on_response)
            p.on("download", on_download)
            p.on("console", lambda msg: console_events.append({"type": msg.type, "text": msg.text[:500]}))
            p.on("pageerror", lambda exc: page_errors.append(str(exc)))
            await _install_js_hooks(p)

        async def on_page(new_page):
            triggered_pages.append({"url": new_page.url, "created_at": _now()})
            await attach_page_handlers(new_page)
            try:
                await new_page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

        context.on("page", lambda p: asyncio.create_task(on_page(p)))

        await attach_page_handlers(page)
        await page.goto(data["tender_url"], wait_until="domcontentloaded", timeout=wait_seconds * 1000)
        await page.wait_for_timeout(3000)

        modal_actions = await _dismiss_modals(page)
        search_expand_actions = await _search_and_expand(page, data["search_text"])
        await _dismiss_modals(page)

        dom_before = await _enumerate_dom(page)
        forced_click_actions = await _force_click_candidates(page, dom_before)

        # Wait after force-clicks for downloads/new pages/XHRs.
        await page.wait_for_timeout(wait_seconds * 1000)

        # Inspect all pages after clicks for PDF/blob/document URLs.
        page_snapshots = []
        for p in context.pages:
            try:
                snap = {
                    "url": p.url,
                    "title": await p.title(),
                    "lmcp_triggers": await p.evaluate("() => window.__lmcpCapturedTriggers || []"),
                }
                page_snapshots.append(snap)
            except Exception as exc:
                page_snapshots.append({"url": getattr(p, "url", ""), "error": str(exc)})

        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            screenshot_path = output_dir / f"ETENDERS_{data['tender_id']}__v50_9_5_page.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            screenshots.append(str(screenshot_path))
        except Exception:
            pass

        verified_downloads = [d for d in download_events if d.get("exists") and int(d.get("size") or 0) > 0]

        trigger_urls = []
        for snap in page_snapshots:
            for trig in snap.get("lmcp_triggers") or []:
                blob = json.dumps(trig)
                if any(x in blob.lower() for x in ["download", "document", "support", "pdf", "file", "155559", "e7904db8"]):
                    trigger_urls.append(trig)

        log_path = output_dir / f"ETENDERS_{data['tender_id']}__v50_9_5_capture.json"
        log_payload = {
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": data,
            "cdp_resolution": cdp_resolution,
            "modal_actions": modal_actions,
            "search_expand_actions": search_expand_actions,
            "dom_before": dom_before,
            "forced_click_actions": forced_click_actions,
            "network_events": network_events,
            "download_events": download_events,
            "triggered_pages": triggered_pages,
            "page_snapshots": page_snapshots,
            "trigger_urls": trigger_urls,
            "console_events": console_events[-200:],
            "page_errors": page_errors,
            "screenshots": screenshots,
        }
        log_path.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2))

        # Status: OK if actual download; useful if trigger URLs or relevant network found.
        relevant_network = [
            e for e in network_events
            if any(x in json.dumps(e).lower() for x in ["download", "document", "support", "pdf", "file", "155559", "e7904db8"])
        ]

        status = "ok" if verified_downloads else ("trigger_captured_needs_replay" if (trigger_urls or relevant_network) else "needs_dom_review")

        return {
            "status": status,
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": data,
            "cdp_resolution": cdp_resolution,
            "verified_download_count": len(verified_downloads),
            "verified_downloads": verified_downloads,
            "network_event_count": len(network_events),
            "relevant_network_count": len(relevant_network),
            "relevant_network_events": relevant_network[-120:],
            "download_events": download_events,
            "trigger_url_count": len(trigger_urls),
            "trigger_urls": trigger_urls[-100:],
            "dom_hit_count": len(dom_before.get("hits") or []),
            "dom_hits_top": (dom_before.get("hits") or [])[:80],
            "forced_click_count": len([a for a in forced_click_actions if a.get("action") == "forced_click"]),
            "forced_click_actions": forced_click_actions[:120],
            "modal_actions": modal_actions,
            "search_expand_actions": search_expand_actions,
            "triggered_pages": triggered_pages,
            "page_snapshots": page_snapshots,
            "console_events": console_events[-40:],
            "page_errors": page_errors,
            "screenshots": screenshots,
            "capture_log": str(log_path),
            "safe_to_process": bool(verified_downloads),
            "notes": [
                "V50.9.5 hooks window.open, fetch, XHR, and DOM mutations before forced clicks.",
                "If status is trigger_captured_needs_replay, build V50.9.6 replay downloader from trigger_urls/relevant_network_events.",
                "If status is needs_dom_review, inspect dom_hits_top and forced_click_actions for missing selectors.",
            ],
        }

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Forced-click capture failed.",
            "error": str(exc),
            "input": data,
            "cdp_resolution": cdp_resolution,
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


def capture_dom_trigger_forced_click(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return asyncio.run(_capture(payload or {}))


def get_v50_9_5_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_cdp_url": DEFAULT_CDP_URL,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "cdp_host_header_resolution",
            "window_open_hook",
            "fetch_hook",
            "xhr_hook",
            "iframe_mutation_capture",
            "dom_clickable_enumeration",
            "forced_pointer_mouse_click_dispatch",
            "datatable_search_and_row_expansion",
            "download_event_capture",
            "trigger_url_capture",
            "capture_log_generation",
        ],
    }
