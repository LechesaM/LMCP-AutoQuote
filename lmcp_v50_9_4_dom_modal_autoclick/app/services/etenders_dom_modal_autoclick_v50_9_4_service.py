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

    search_selectors = [
        "input[type='search']",
        "input[aria-controls*='tender']",
        "input[aria-controls]",
        "#tenderList_filter input",
        ".dataTables_filter input",
        "input[placeholder*='Search']",
        "input[placeholder*='search']",
    ]

    for selector in search_selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "search_selector_checked", "selector": selector, "count": count})
            if count > 0:
                await loc.first.fill(search_text, timeout=3000)
                await loc.first.press("Enter", timeout=3000)
                await page.wait_for_timeout(5000)
                actions.append({"action": "search_filled", "selector": selector, "search_text": search_text})
                return actions
        except Exception as exc:
            actions.append({"action": "search_error", "selector": selector, "error": str(exc)})

    # Fallback DataTables search injection.
    try:
        injected = await page.evaluate(
            """
            (term) => {
              let done = false;
              if (window.jQuery && window.jQuery.fn && window.jQuery.fn.dataTable) {
                const tables = window.jQuery('table').DataTable ? window.jQuery('table') : [];
                window.jQuery('table').each(function(){
                  try {
                    const dt = window.jQuery(this).DataTable();
                    dt.search(term).draw();
                    done = true;
                  } catch(e) {}
                });
              }
              return done;
            }
            """,
            search_text,
        )
        actions.append({"action": "datatables_search_injected", "done": injected, "search_text": search_text})
        await page.wait_for_timeout(5000)
    except Exception as exc:
        actions.append({"action": "datatables_search_error", "error": str(exc)})

    return actions


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

    # Expand visible row/details controls first.
    expand_selectors = [
        "td.details-control",
        "td.dtr-control",
        "tr:has-text('JDAMARK') td:first-child",
        "tr:has-text('DIGITAL BOOK') td:first-child",
        "button:has-text('+')",
        "a:has-text('View')",
        "a:has-text('Details')",
        "button:has-text('View')",
        "button:has-text('Details')",
    ]

    for selector in expand_selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "expand_selector_checked", "selector": selector, "count": count})
            for idx in range(min(count, 5)):
                try:
                    await loc.nth(idx).click(timeout=3000, force=True)
                    actions.append({"action": "expanded", "selector": selector, "index": idx})
                    await page.wait_for_timeout(1500)
                except Exception as exc:
                    actions.append({"action": "expand_click_error", "selector": selector, "index": idx, "error": str(exc)})
        except Exception as exc:
            actions.append({"action": "expand_selector_error", "selector": selector, "error": str(exc)})

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
        search_actions = await _search_opportunities(page, data["search_text"])
        modal_actions_2 = await _dismiss_modals(page)
        click_actions = await _expand_and_click_documents(page, data)

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
