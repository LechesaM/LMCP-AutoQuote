"""
LMCP V50.9.3 PATCHED - Browser Session Download Interceptor

Patch purpose:
- Docker can reach Chrome CDP at http://host.docker.internal:9222/json/version
  only when Host header is overridden to localhost:9222.
- Chrome returns webSocketDebuggerUrl as ws://localhost:9222/...
- Inside Docker that must be rewritten to ws://host.docker.internal:9222/...
- This patched service resolves CDP WebSocket URL manually before attaching.

Drop-in replacement:
    app/services/etenders_browser_download_interceptor_v50_9_3_service.py
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


SERVICE_VERSION = "V50.9.3_ETENDERS_BROWSER_DOWNLOAD_INTERCEPTOR_CDP_PATCH"

DEFAULT_CDP_URL = "http://host.docker.internal:9222"
DEFAULT_OUTPUT_DIR = "runtime/playwright/downloads"
ETENDERS_BASE = "https://www.etenders.gov.za"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_filename(filename: str, fallback: str = "etenders_browser_download.pdf") -> str:
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


def _looks_relevant_url(url: str) -> bool:
    low = (url or "").lower()
    return any(
        marker in low
        for marker in [
            "download",
            "document",
            "support",
            "file",
            "sharepoint",
            ".pdf",
            ".doc",
            ".xls",
            ".zip",
        ]
    )


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
    search_text = _clean(payload.get("search_text") or payload.get("searchText") or payload.get("click_text") or "")

    tender_url = _clean(payload.get("tender_url") or "")
    if not tender_url and tender_id:
        tender_url = f"{ETENDERS_BASE}/Home/TenderDetails?id={tender_id}"

    return {
        "tender_id": tender_id,
        "support_document_id": support_document_id,
        "filename": filename,
        "search_text": search_text,
        "tender_url": tender_url,
    }


async def _dismiss_obstructive_ui(page) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    for selector in [
        "#educationalPopup button",
        "#educationalPopup .close",
        "#educationalPopup [data-dismiss='modal']",
        "#TempPopupModal button",
        "#TempPopupModal .close",
        "#TempPopupModal [data-dismiss='modal']",
        "#genericModal button",
        "#genericModal .close",
        "#genericModal [data-dismiss='modal']",
        ".modal button.close",
        ".modal [data-dismiss='modal']",
        "[role='dialog'] button.close",
        "[role='dialog'] [data-dismiss='modal']",
    ]:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            if count:
                for idx in range(min(count, 3)):
                    try:
                        await loc.nth(idx).click(timeout=1500, force=True)
                        actions.append({"action": "clicked_close_selector", "selector": selector, "index": idx})
                        await page.wait_for_timeout(300)
                    except Exception as exc:
                        actions.append({"action": "close_click_error", "selector": selector, "index": idx, "error": str(exc)})
        except Exception as exc:
            actions.append({"action": "close_selector_error", "selector": selector, "error": str(exc)})

    for text in ["Got it, Thanks!", "Got it", "Close", "Next", "OK", "Ok", "Dismiss", "×", "x"]:
        for selector in [
            f"button:has-text('{text}')",
            f"a:has-text('{text}')",
            f"text={text}",
        ]:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                if count:
                    try:
                        await loc.first.click(timeout=1500, force=True)
                        actions.append({"action": "clicked_text", "selector": selector, "count": count})
                        await page.wait_for_timeout(300)
                    except Exception as exc:
                        actions.append({"action": "text_click_error", "selector": selector, "count": count, "error": str(exc)})
            except Exception as exc:
                actions.append({"action": "text_selector_error", "selector": selector, "error": str(exc)})

    try:
        removed = await page.evaluate(
            """
            () => {
              const out = [];
              const selectors = [
                '#educationalPopup',
                '#TempPopupModal',
                '#genericModal',
                '.modal-backdrop',
                '.modal-open',
                '.overlay',
                '[role="dialog"]'
              ];
              for (const sel of selectors) {
                document.querySelectorAll(sel).forEach(el => {
                  out.push({selector: sel, text: (el.innerText || el.textContent || '').slice(0, 200)});
                  if (el.classList && el.classList.contains('modal-open')) {
                    el.classList.remove('modal-open');
                  }
                  el.style.display = 'none';
                  el.style.visibility = 'hidden';
                  el.style.pointerEvents = 'none';
                  el.setAttribute('data-lmcp-hidden', '1');
                });
              }
              document.body.classList.remove('modal-open');
              document.body.style.overflow = 'auto';
              document.body.style.pointerEvents = 'auto';
              return out;
            }
            """
        )
        if removed:
            actions.append({"action": "hid_obstructive_ui", "items": removed[:30]})
    except Exception as exc:
        actions.append({"action": "hide_error", "error": str(exc)})

    return actions


def _resolve_cdp_endpoint(cdp_url: str) -> Dict[str, Any]:
    """
    Resolve Chrome CDP endpoint in Docker-safe way.

    Chrome rejects:
        Host: host.docker.internal:9222

    But accepts:
        Host: localhost:9222

    It then returns:
        ws://localhost:9222/devtools/browser/...

    Docker must use:
        ws://host.docker.internal:9222/devtools/browser/...
    """
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
        response = requests.get(
            version_url,
            headers={"Host": "localhost:9222"},
            timeout=8,
        )
        result["status_code"] = response.status_code

        if response.status_code != 200:
            result["error"] = f"cdp_version_status_{response.status_code}:{response.text[:300]}"
            return result

        data = response.json()
        raw_ws = data.get("webSocketDebuggerUrl") or ""
        resolved_ws = raw_ws

        # Replace localhost target returned by Chrome with the Docker-reachable host.
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


async def _capture_with_playwright(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Playwright is not installed or not available in this environment.",
            "error": str(exc),
            "safe_to_process": False,
        }

    data = _extract_payload(payload)
    cdp_url = _clean(payload.get("cdp_url") or DEFAULT_CDP_URL)
    output_dir = Path(str(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    wait_seconds = int(payload.get("wait_seconds") or 30)
    click_text = _clean(payload.get("click_text") or "")
    auto_click = bool(payload.get("auto_click", True))
    headless_fallback = bool(payload.get("headless_fallback", False))

    safe_name = _safe_filename(data["filename"] or f"tender_{data['tender_id']}_document.pdf")
    network_events: List[Dict[str, Any]] = []
    download_events: List[Dict[str, Any]] = []
    console_events: List[Dict[str, Any]] = []
    page_errors: List[str] = []
    screenshots: List[str] = []

    browser = None
    context = None
    page = None
    playwright = None
    cdp_resolution = _resolve_cdp_endpoint(cdp_url)

    if data["tender_url"].rstrip("/").endswith("/Home/opportunities"):
        data["tender_url"] = f"{ETENDERS_BASE}/Home/opportunities?id=1"

    try:
        playwright = await async_playwright().start()

        try:
            if not cdp_resolution.get("ok"):
                raise RuntimeError(f"CDP resolution failed: {cdp_resolution}")

            browser = await playwright.chromium.connect_over_cdp(cdp_resolution["resolved_websocket_url"])
            attach_mode = "cdp_resolved_websocket"
        except Exception as cdp_exc:
            if not headless_fallback:
                return {
                    "status": "error",
                    "service_version": SERVICE_VERSION,
                    "message": "Could not attach to live Chrome CDP session.",
                    "cdp_url": cdp_url,
                    "cdp_resolution": cdp_resolution,
                    "error": str(cdp_exc),
                    "how_to_start_chrome": (
                        'open -na "Google Chrome" --args --remote-debugging-address=0.0.0.0 '
                        '--remote-debugging-port=9222 --user-data-dir="/tmp/lmcp-chrome-cdp"'
                    ),
                    "safe_to_process": False,
                }

            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            attach_mode = "headless_fallback"

        if not context:
            if browser.contexts:
                context = browser.contexts[0]
            else:
                context = await browser.new_context(accept_downloads=True)

        try:
            context.set_default_timeout(wait_seconds * 1000)
        except Exception:
            pass

        if context.pages:
            page = context.pages[0]
        else:
            page = await context.new_page()

        async def on_response(response):
            try:
                headers = await response.all_headers()
                url = response.url
                if _looks_relevant_response(headers, url):
                    network_events.append({
                        "type": "response",
                        "url": url,
                        "status": response.status,
                        "headers": headers,
                        "request_method": response.request.method,
                        "request_headers": await response.request.all_headers(),
                        "post_data": response.request.post_data,
                    })
            except Exception as exc:
                network_events.append({"type": "response_error", "error": str(exc)})

        async def on_request(request):
            try:
                url = request.url
                if _looks_relevant_url(url):
                    network_events.append({
                        "type": "request",
                        "url": url,
                        "method": request.method,
                        "headers": await request.all_headers(),
                        "post_data": request.post_data,
                    })
            except Exception as exc:
                network_events.append({"type": "request_error", "error": str(exc)})

        async def on_download(download):
            try:
                suggested = download.suggested_filename
                dl_name = _safe_filename(suggested or safe_name)
                dl_path = output_dir / f"ETENDERS_{data['tender_id']}__{dl_name}"
                output_dir.mkdir(parents=True, exist_ok=True)
                await download.save_as(str(dl_path))
                download_events.append({
                    "url": download.url,
                    "suggested_filename": suggested,
                    "saved_path": str(dl_path),
                    "exists": dl_path.exists(),
                    "size": dl_path.stat().st_size if dl_path.exists() else 0,
                })
            except Exception as exc:
                download_events.append({"error": str(exc)})

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("download", on_download)
        page.on("console", lambda msg: console_events.append({"type": msg.type, "text": msg.text[:500]}))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        if data["tender_url"]:
            try:
                await page.goto(data["tender_url"], wait_until="domcontentloaded", timeout=wait_seconds * 1000)
            except Exception as exc:
                network_events.append({"type": "goto_warning", "error": str(exc), "url": data["tender_url"]})

        tab_clicked = False
        for selector in [
            "#Search",
            "text=Currently Advertised",
            "button:has-text('Currently Advertised')",
            "a:has-text('Currently Advertised')",
        ]:
            try:
                loc = page.locator(selector)
                if await loc.count():
                    await loc.first.click(timeout=1500, force=True)
                    network_events.append({"type": "clicked_tab", "selector": selector})
                    tab_clicked = True
                    await page.wait_for_timeout(1500)
                    break
            except Exception as exc:
                network_events.append({"type": "tab_click_error", "selector": selector, "error": str(exc)})

        if not tab_clicked:
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
                network_events.append({"type": "clicked_tab_dom", "clicked": bool(clicked)})
                if clicked:
                    tab_clicked = True
                    await page.wait_for_timeout(2500)
            except Exception as exc:
                network_events.append({"type": "tab_click_dom_error", "error": str(exc)})

        await _dismiss_obstructive_ui(page)
        try:
            await page.wait_for_timeout(1000)
        except Exception:
            pass

        if data["search_text"]:
            for selector in ["#my-text-input", "input#my-text-input"]:
                try:
                    loc = page.locator(selector)
                    if await loc.count():
                        field = loc.first
                        await field.click(timeout=1500, force=True)
                        await field.fill(data["search_text"], timeout=1500)
                        network_events.append({"type": "filled_search_input", "selector": selector, "value": data["search_text"][:160]})
                        break
                except Exception as exc:
                    network_events.append({"type": "search_input_error", "selector": selector, "error": str(exc)})

            for selector in ["#btnSearch", "button#btnSearch", "button.search"]:
                try:
                    loc = page.locator(selector)
                    if await loc.count():
                        await loc.first.click(timeout=2000, force=True)
                        network_events.append({"type": "clicked_search_button", "selector": selector})
                        await page.wait_for_timeout(2500)
                        break
                except Exception as exc:
                    network_events.append({"type": "search_button_error", "selector": selector, "error": str(exc)})

            for selector in [
                "input[placeholder*='Quick' i]",
                "input[placeholder*='Search' i]",
                "input[type='search']",
                "input[name*='search' i]",
                "input[id*='quick' i]",
                "input[id*='search' i]",
            ]:
                try:
                    loc = page.locator(selector)
                    if await loc.count():
                        field = loc.first
                        await field.click(timeout=1500, force=True)
                        await field.fill(data["search_text"], timeout=1500)
                        await field.press("Enter", timeout=1500)
                        network_events.append({"type": "filled_search", "selector": selector, "value": data["search_text"][:160]})
                        await page.wait_for_timeout(2000)
                        break
                except Exception as exc:
                    network_events.append({"type": "search_fill_error", "selector": selector, "error": str(exc)})

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            shot = output_dir / f"ETENDERS_{data['tender_id']}__v50_9_3_page.png"
            await page.screenshot(path=str(shot), full_page=True)
            screenshots.append(str(shot))
        except Exception:
            pass

        clicked = False
        click_attempts: List[Dict[str, Any]] = []

        if auto_click:
            await _dismiss_obstructive_ui(page)
            selectors = []
            if data["filename"]:
                selectors += [
                    f"text={data['filename']}",
                    f"a:has-text('{data['filename'][:30]}')",
                ]

            if click_text:
                selectors.append(f"text={click_text}")
            if data["search_text"]:
                selectors.extend([
                    f"text={data['search_text']}",
                    f"a:has-text('{data['search_text'][:60]}')",
                ])

            selectors += [
                "text=Download",
                "text=download",
                "text=Documents",
                "text=documents",
                "text=Support Document",
                "text=View",
                "a[href*='Download']",
                "a[href*='download']",
                "a[href*='Document']",
                "a[href*='document']",
                "button:has-text('Download')",
                "button:has-text('Documents')",
            ]

            for selector in selectors:
                try:
                    locator_collection = page.locator(selector)
                    count = await locator_collection.count()
                    click_attempts.append({"selector": selector, "count": count})
                    if count > 0:
                        locator = locator_collection.first
                        try:
                            async with page.expect_download(timeout=7000) as download_info:
                                await locator.click(timeout=7000)
                            download = await download_info.value
                            await on_download(download)
                            clicked = True
                            break
                        except Exception:
                            try:
                                await locator.click(timeout=7000)
                                clicked = True
                                await page.wait_for_timeout(5000)
                                break
                            except Exception as click_exc:
                                click_attempts[-1]["click_error"] = str(click_exc)
                except Exception as exc:
                    click_attempts.append({"selector": selector, "error": str(exc)})

        await page.wait_for_timeout(wait_seconds * 1000)

        verified_downloads = [
            d for d in download_events
            if d.get("exists") and int(d.get("size") or 0) > 0
        ]

        output_dir.mkdir(parents=True, exist_ok=True)
        capture_log = output_dir / f"ETENDERS_{data['tender_id']}__v50_9_3_capture.json"
        capture_log.write_text(json.dumps({
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": data,
            "attach_mode": attach_mode,
            "cdp_resolution": cdp_resolution,
            "network_events": network_events,
            "download_events": download_events,
            "click_attempts": click_attempts,
            "console_events": console_events[-50:],
            "page_errors": page_errors,
            "screenshots": screenshots,
        }, ensure_ascii=False, indent=2))

        return {
            "status": "ok" if verified_downloads else "needs_operator_or_next_pattern",
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": data,
            "attach_mode": attach_mode,
            "cdp_url": cdp_url,
            "cdp_resolution": cdp_resolution,
            "clicked": clicked,
            "verified_download_count": len(verified_downloads),
            "verified_downloads": verified_downloads,
            "network_event_count": len(network_events),
            "relevant_network_events": network_events[-100:],
            "download_events": download_events,
            "click_attempts": click_attempts[:100],
            "console_events": console_events[-20:],
            "page_errors": page_errors,
            "screenshots": screenshots,
            "capture_log": str(capture_log),
            "safe_to_process": bool(verified_downloads),
            "notes": [
                "CDP Host-header patch is active.",
                "If verified_download_count is 0, manually click the document link in Chrome while this endpoint is running.",
                "The capture_log stores request headers, URLs, and POST data for replay.",
            ],
        }

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Browser download capture failed.",
            "error": str(exc),
            "input": data,
            "cdp_resolution": cdp_resolution,
            "network_events": network_events[-40:],
            "download_events": download_events,
            "safe_to_process": False,
        }

    finally:
        try:
            if playwright:
                await playwright.stop()
        except Exception:
            pass


def capture_browser_download(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    return asyncio.run(_capture_with_playwright(payload))


def get_v50_9_3_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_cdp_url": DEFAULT_CDP_URL,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "live_chrome_cdp_attach",
            "docker_host_header_cdp_resolution",
            "websocket_url_rewrite",
            "network_request_interception",
            "download_event_capture",
            "download_file_storage",
            "request_header_capture",
            "post_body_capture",
            "operator_assisted_document_click",
            "capture_log_generation",
        ],
    }
