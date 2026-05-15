"""
LMCP V50.9.9 - Runtime Browser Download Interceptor

Purpose:
- V50.9.8 proved static replay can discover download families, but the real support-document
  endpoint appears to be runtime/session generated.
- V50.9.9 attaches to live Chrome over CDP and captures the actual browser runtime:
    - requests
    - responses
    - downloads
    - new tabs/pages
    - cookies
    - local/session storage
    - screenshots
    - runtime JS hooks for fetch/XHR/window.open/blob/object URLs
    - binary response saving
    - HAR-style audit log

Routes:
    GET  /v50-9-9-runtime-download-interceptor/status
    POST /v50-9-9-runtime-download-interceptor/capture

Drop-in:
    app/services/etenders_runtime_download_interceptor_v50_9_9.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests


SERVICE_VERSION = "V50.9.9_RUNTIME_BROWSER_DOWNLOAD_INTERCEPTOR"

DEFAULT_CDP_URL = "http://host.docker.internal:9222"
DEFAULT_OUTPUT_DIR = "runtime/playwright/runtime_download_intercepts"
DEFAULT_TENDER_URL = "https://www.etenders.gov.za/Home/opportunities"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_filename(filename: str, fallback: str = "download.bin") -> str:
    name = _clean(filename) or fallback
    name = name.replace("\\", "_").replace("/", "_").replace(":", "_")
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip().strip(". ")
    if not name:
        name = fallback
    if len(name) > 180:
        stem = Path(name).stem[:145]
        suffix = Path(name).suffix or ".bin"
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


def _important_url(url: str) -> bool:
    low = (url or "").lower()
    return any(x in low for x in [
        "download", "document", "attachment", "file", "support", "bid", "tender",
        "blob:", ".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", "sharepoint",
        "downloadspec", "tenderdetails", "paginatedtenderopportunities",
    ])


def _binary_like(headers: Dict[str, str], body_prefix: bytes = b"") -> bool:
    ctype = str(headers.get("content-type") or headers.get("Content-Type") or "").lower()
    cdisp = str(headers.get("content-disposition") or headers.get("Content-Disposition") or "").lower()
    if "attachment" in cdisp or "filename" in cdisp:
        return True
    if any(x in ctype for x in [
        "application/pdf",
        "application/octet-stream",
        "application/zip",
        "application/vnd",
        "application/msword",
        "image/",
    ]):
        return True
    return body_prefix.startswith(b"%PDF") or body_prefix.startswith(b"PK")


def _extension_from_headers(headers: Dict[str, str]) -> str:
    ctype = str(headers.get("content-type") or headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if "pdf" in ctype:
        return ".pdf"
    if "zip" in ctype:
        return ".zip"
    if "spreadsheetml" in ctype:
        return ".xlsx"
    if "wordprocessingml" in ctype:
        return ".docx"
    if "msword" in ctype:
        return ".doc"
    guessed = mimetypes.guess_extension(ctype or "")
    return guessed or ".bin"


def _filename_from_content_disposition(headers: Dict[str, str]) -> str:
    value = headers.get("content-disposition") or headers.get("Content-Disposition") or ""
    if not value:
        return ""
    m = re.search(r"filename\*=UTF-8''([^;]+)", value, re.I)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1)).strip('" ')
    m = re.search(r'filename="?([^";]+)"?', value, re.I)
    if m:
        return m.group(1).strip()
    return ""


async def _install_runtime_hooks(page) -> None:
    await page.add_init_script(
        """
        (() => {
          window.__lmcpRuntimeEvents = window.__lmcpRuntimeEvents || [];
          const cap = (kind, data) => {
            try {
              window.__lmcpRuntimeEvents.push({
                kind,
                data,
                href: location.href,
                ts: new Date().toISOString()
              });
            } catch(e) {}
          };

          const originalOpen = window.open;
          window.open = function(...args) {
            cap('window.open', {args: args.map(String)});
            return originalOpen.apply(this, args);
          };

          const originalCreateObjectURL = URL.createObjectURL;
          URL.createObjectURL = function(obj) {
            const url = originalCreateObjectURL.call(URL, obj);
            try {
              cap('URL.createObjectURL', {
                objectType: obj && obj.constructor ? obj.constructor.name : typeof obj,
                size: obj && obj.size ? obj.size : null,
                type: obj && obj.type ? obj.type : null,
                url
              });
            } catch(e) {}
            return url;
          };

          const originalFetch = window.fetch;
          window.fetch = function(...args) {
            try {
              cap('fetch.call', {
                url: String(args[0]),
                options: args[1] ? JSON.stringify(args[1]).slice(0, 3000) : null
              });
            } catch(e) {}
            return originalFetch.apply(this, args).then(async (res) => {
              try {
                cap('fetch.response', {
                  url: res.url,
                  status: res.status,
                  type: res.type,
                  headers: Array.from(res.headers.entries()).slice(0, 80)
                });
              } catch(e) {}
              return res;
            });
          };

          const OriginalXHR = window.XMLHttpRequest;
          window.XMLHttpRequest = function() {
            const xhr = new OriginalXHR();
            const oopen = xhr.open;
            const osend = xhr.send;
            xhr.open = function(method, url, ...rest) {
              this.__lmcpMethod = method;
              this.__lmcpUrl = url;
              cap('xhr.open', {method, url: String(url)});
              return oopen.call(this, method, url, ...rest);
            };
            xhr.send = function(body) {
              cap('xhr.send', {
                method: this.__lmcpMethod,
                url: String(this.__lmcpUrl),
                body: body ? String(body).slice(0, 3000) : null
              });
              this.addEventListener('load', function() {
                try {
                  cap('xhr.load', {
                    method: this.__lmcpMethod,
                    url: String(this.__lmcpUrl),
                    status: this.status,
                    responseURL: this.responseURL,
                    responseType: this.responseType,
                    textPreview: this.responseText ? this.responseText.slice(0, 1000) : null
                  });
                } catch(e) {}
              });
              return osend.call(this, body);
            };
            return xhr;
          };

          const obs = new MutationObserver((mutations) => {
            for (const m of mutations) {
              for (const node of m.addedNodes || []) {
                if (!node || !node.querySelectorAll) continue;
                const items = [];
                node.querySelectorAll('a,button,iframe,form,[onclick],[href],[src]').forEach((el) => {
                  const txt = (el.innerText || el.textContent || el.alt || el.title || '').trim();
                  const blob = JSON.stringify({
                    tag: el.tagName,
                    text: txt,
                    href: el.href || el.getAttribute('href') || '',
                    src: el.src || el.getAttribute('src') || '',
                    action: el.action || el.getAttribute('action') || '',
                    onclick: el.getAttribute('onclick') || '',
                    cls: el.className || '',
                    id: el.id || ''
                  });
                  if (/download|document|attachment|file|support|bid|tender|pdf|zip|sharepoint/i.test(blob)) {
                    items.push(JSON.parse(blob));
                  }
                });
                if (items.length) cap('mutation.relevant', items.slice(0, 100));
              }
            }
          });
          obs.observe(document.documentElement, {childList: true, subtree: true});
        })();
        """
    )


async def _dismiss_common_overlays(page) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    texts = ["Accept", "I Accept", "OK", "Ok", "Close", "Continue", "Proceed", "Agree", "Dismiss", "×", "x"]
    for text in texts:
        for selector in [f"button:has-text('{text}')", f"a:has-text('{text}')", f"input[value='{text}']", f"text={text}"]:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                if count:
                    await loc.first.click(timeout=1200, force=True)
                    actions.append({"selector": selector, "count": count, "action": "clicked"})
                    await page.wait_for_timeout(300)
            except Exception:
                pass
    try:
        hidden = await page.evaluate(
            """
            () => {
              const out = [];
              for (const sel of ['.modal-backdrop','.modal','.overlay','#cookieConsent','#consent','[role="dialog"]']) {
                document.querySelectorAll(sel).forEach(el => {
                  out.push({selector: sel, text: (el.innerText || el.textContent || '').slice(0,160)});
                  el.style.display = 'none';
                  el.style.visibility = 'hidden';
                });
              }
              document.body.classList.remove('modal-open');
              document.body.style.overflow = 'auto';
              return out;
            }
            """
        )
        if hidden:
            actions.append({"action": "hidden_overlays", "items": hidden[:50]})
    except Exception as exc:
        actions.append({"action": "hide_overlay_error", "error": str(exc)})
    return actions


async def _auto_interact(page, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    search_text = _clean(payload.get("search_text") or payload.get("tender_no") or payload.get("title") or "DIGITAL BOOK")

    # Search boxes
    for selector in ["input[type='search']", ".dataTables_filter input", "#tenderList_filter input", "input[aria-controls]", "input[placeholder*='Search']"]:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            actions.append({"action": "search_selector", "selector": selector, "count": count})
            if count:
                await loc.first.fill(search_text[:80], timeout=2500)
                await loc.first.press("Enter", timeout=2500)
                await page.wait_for_timeout(3500)
                actions.append({"action": "searched", "selector": selector, "value": search_text[:80]})
                break
        except Exception as exc:
            actions.append({"action": "search_error", "selector": selector, "error": str(exc)})

    # Relevant click selectors
    selectors = [
        "td.details-control",
        "td.dtr-control",
        "button:has-text('Download')",
        "a:has-text('Download')",
        "button:has-text('Document')",
        "a:has-text('Document')",
        "button:has-text('Documents')",
        "a:has-text('Documents')",
        "button:has-text('Bid')",
        "a:has-text('Bid')",
        "button:has-text('View')",
        "a:has-text('View')",
        "a[href*='Download']",
        "a[href*='download']",
        "a[href*='Document']",
        "a[href*='document']",
        "a[href*='Support']",
        "a[href*='support']",
        "a[href*='file']",
        "a[href*='File']",
        "[onclick*='Download']",
        "[onclick*='download']",
        "[onclick*='Document']",
        "[onclick*='document']",
        "[onclick*='Support']",
        "[onclick*='support']",
        ".fa-download",
        ".download",
        "i",
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            if count:
                actions.append({"action": "candidate_selector", "selector": selector, "count": count})
            for i in range(min(count, 5)):
                try:
                    await loc.nth(i).click(timeout=1800, force=True)
                    actions.append({"action": "clicked", "selector": selector, "index": i})
                    await page.wait_for_timeout(1600)
                except Exception as exc:
                    actions.append({"action": "click_error", "selector": selector, "index": i, "error": str(exc)})
        except Exception as exc:
            actions.append({"action": "selector_error", "selector": selector, "error": str(exc)})

    # JS forced click every relevant DOM element
    try:
        forced = await page.evaluate(
            """
            async () => {
              const out = [];
              const all = Array.from(document.querySelectorAll('a,button,input,td,span,i,[onclick],[href],[src],[role="button"]'));
              const relevant = all.map((el, index) => {
                const txt = (el.innerText || el.textContent || el.alt || el.title || '').trim();
                const info = {
                  index,
                  tag: el.tagName,
                  text: txt.slice(0,180),
                  href: el.href || el.getAttribute('href') || '',
                  src: el.src || el.getAttribute('src') || '',
                  onclick: el.getAttribute('onclick') || '',
                  cls: el.className || '',
                  id: el.id || ''
                };
                const blob = JSON.stringify(info);
                return /download|document|attachment|file|support|bid|tender|pdf|zip|sharepoint|jdamark|digital/i.test(blob) ? info : null;
              }).filter(Boolean).slice(0, 80);
              for (const item of relevant) {
                const el = all[item.index];
                try { el.scrollIntoView({block:'center', inline:'center'}); } catch(e) {}
                for (const ev of ['pointerdown','mousedown','mouseup','pointerup','click']) {
                  try { el.dispatchEvent(new MouseEvent(ev, {bubbles:true, cancelable:true, view:window})); } catch(e) {}
                }
                try { el.click(); } catch(e) {}
                out.push(item);
                await new Promise(r => setTimeout(r, 350));
              }
              return out;
            }
            """
        )
        actions.append({"action": "forced_relevant_dom_clicks", "items": forced[:80]})
    except Exception as exc:
        actions.append({"action": "forced_dom_error", "error": str(exc)})

    return actions


async def _capture(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return {"status": "error", "service_version": SERVICE_VERSION, "message": "Playwright unavailable", "error": str(exc), "safe_to_process": False}

    cdp_url = _clean(payload.get("cdp_url") or DEFAULT_CDP_URL)
    tender_id = _clean(payload.get("tender_id") or "UNKNOWN")
    target_url = _clean(payload.get("tender_url") or DEFAULT_TENDER_URL)
    output_dir = Path(_clean(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    wait_seconds = int(payload.get("wait_seconds") or 90)
    auto_click = bool(payload.get("auto_click", True))

    run_id = f"{tender_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    run_dir = output_dir / f"ETENDERS_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cdp = _resolve_cdp_endpoint(cdp_url)
    if not cdp.get("ok"):
        return {"status": "error", "service_version": SERVICE_VERSION, "message": "Could not resolve CDP endpoint", "cdp_resolution": cdp, "safe_to_process": False}

    network_events: List[Dict[str, Any]] = []
    download_events: List[Dict[str, Any]] = []
    binary_saves: List[Dict[str, Any]] = []
    page_errors: List[str] = []
    console_events: List[Dict[str, Any]] = []
    screenshots: List[str] = []
    runtime_events: List[Dict[str, Any]] = []
    pages_seen: List[Dict[str, Any]] = []

    playwright = None

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(cdp["resolved_websocket_url"])
        context = browser.contexts[0] if browser.contexts else await browser.new_context(accept_downloads=True)
        context.set_default_timeout(wait_seconds * 1000)

        async def attach_handlers(page):
            pages_seen.append({"url": page.url, "attached_at": _now()})
            await _install_runtime_hooks(page)

            async def on_request(request):
                try:
                    if _important_url(request.url):
                        network_events.append({
                            "kind": "request",
                            "page_url": page.url,
                            "url": request.url,
                            "method": request.method,
                            "headers": await request.all_headers(),
                            "post_data": request.post_data,
                            "ts": _now(),
                        })
                except Exception as exc:
                    network_events.append({"kind": "request_error", "error": str(exc), "ts": _now()})

            async def on_response(response):
                try:
                    headers = await response.all_headers()
                    url = response.url
                    important = _important_url(url) or _binary_like(headers)
                    if important:
                        event = {
                            "kind": "response",
                            "page_url": page.url,
                            "url": url,
                            "status": response.status,
                            "headers": headers,
                            "request_method": response.request.method,
                            "request_headers": await response.request.all_headers(),
                            "post_data": response.request.post_data,
                            "ts": _now(),
                        }

                        # Try save binary body for important/binary responses.
                        try:
                            body = await response.body()
                            event["body_size"] = len(body or b"")
                            event["body_prefix_b64"] = base64.b64encode((body or b"")[:80]).decode("ascii")
                            if _binary_like(headers, (body or b"")[:20]) and body:
                                filename = _filename_from_content_disposition(headers)
                                if not filename:
                                    parsed = urlparse(url)
                                    stem = Path(parsed.path).name or "runtime_response"
                                    ext = Path(stem).suffix or _extension_from_headers(headers)
                                    filename = stem if Path(stem).suffix else f"{stem}{ext}"
                                filename = _safe_filename(filename)
                                path = run_dir / f"RESPONSE__{len(binary_saves)+1:03d}__{filename}"
                                path.write_bytes(body)
                                saved = {
                                    "url": url,
                                    "saved_path": str(path),
                                    "filename": filename,
                                    "size": path.stat().st_size,
                                    "headers": headers,
                                }
                                binary_saves.append(saved)
                                event["saved_binary"] = saved
                        except Exception as body_exc:
                            event["body_error"] = str(body_exc)

                        network_events.append(event)
                except Exception as exc:
                    network_events.append({"kind": "response_error", "error": str(exc), "ts": _now()})

            async def on_download(download):
                try:
                    suggested = download.suggested_filename or "download.bin"
                    filename = _safe_filename(suggested)
                    path = run_dir / f"DOWNLOAD__{len(download_events)+1:03d}__{filename}"
                    await download.save_as(str(path))
                    download_events.append({
                        "url": download.url,
                        "suggested_filename": suggested,
                        "saved_path": str(path),
                        "size": path.stat().st_size if path.exists() else 0,
                        "ts": _now(),
                    })
                except Exception as exc:
                    download_events.append({"error": str(exc), "ts": _now()})

            page.on("request", on_request)
            page.on("response", on_response)
            page.on("download", on_download)
            page.on("console", lambda msg: console_events.append({"type": msg.type, "text": msg.text[:700], "ts": _now()}))
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        async def on_new_page(new_page):
            await attach_handlers(new_page)
            try:
                await new_page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass

        context.on("page", lambda p: asyncio.create_task(on_new_page(p)))

        page = context.pages[0] if context.pages else await context.new_page()
        await attach_handlers(page)

        await page.goto(target_url, wait_until="domcontentloaded", timeout=wait_seconds * 1000)
        await page.wait_for_timeout(4000)
        overlays = await _dismiss_common_overlays(page)

        interactions = []
        if auto_click:
            interactions = await _auto_interact(page, payload)

        # Also allow manual operator clicking during wait.
        await page.wait_for_timeout(wait_seconds * 1000)

        # Collect runtime JS events from all pages.
        for p in context.pages:
            try:
                ev = await p.evaluate("() => window.__lmcpRuntimeEvents || []")
                runtime_events.extend(ev)
            except Exception:
                pass
            try:
                path = run_dir / f"SCREENSHOT__{len(screenshots)+1:03d}.png"
                await p.screenshot(path=str(path), full_page=True)
                screenshots.append(str(path))
            except Exception:
                pass

        # Cookies and storage snapshot
        cookies = []
        storage = []
        try:
            cookies = await context.cookies()
        except Exception:
            pass

        for p in context.pages:
            try:
                storage.append({
                    "url": p.url,
                    "localStorage": await p.evaluate("() => Object.assign({}, window.localStorage || {})"),
                    "sessionStorage": await p.evaluate("() => Object.assign({}, window.sessionStorage || {})"),
                })
            except Exception:
                pass

        log = {
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": payload,
            "cdp_resolution": cdp,
            "run_dir": str(run_dir),
            "pages_seen": pages_seen,
            "overlays": overlays,
            "interactions": interactions,
            "network_events": network_events,
            "download_events": download_events,
            "binary_saves": binary_saves,
            "runtime_events": runtime_events,
            "cookies": cookies,
            "storage": storage,
            "console_events": console_events[-300:],
            "page_errors": page_errors,
            "screenshots": screenshots,
        }
        log_path = run_dir / "runtime_intercept_log.json"
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2))

        return {
            "status": "download_captured" if (download_events or binary_saves) else ("runtime_events_captured" if (network_events or runtime_events) else "needs_manual_click"),
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "tender_id": tender_id,
            "target_url": target_url,
            "run_dir": str(run_dir),
            "cdp_resolution": cdp,
            "network_event_count": len(network_events),
            "important_network_events": network_events[-120:],
            "download_count": len(download_events),
            "download_events": download_events,
            "binary_save_count": len(binary_saves),
            "binary_saves": binary_saves,
            "runtime_event_count": len(runtime_events),
            "runtime_events_preview": runtime_events[-120:],
            "screenshots": screenshots,
            "log_path": str(log_path),
            "safe_to_process": bool(download_events or binary_saves),
            "notes": [
                "V50.9.9 captures the live browser runtime, not only static replay.",
                "If no binary was captured, open the same Chrome window and manually click the document while capture is running.",
                "This layer is portal-generic and can be reused for SANRAL/Eskom/municipal portals.",
            ],
        }

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Runtime capture failed.",
            "error": str(exc),
            "cdp_resolution": cdp,
            "network_event_count": len(network_events),
            "download_count": len(download_events),
            "binary_save_count": len(binary_saves),
            "safe_to_process": False,
        }
    finally:
        try:
            if playwright:
                await playwright.stop()
        except Exception:
            pass


def capture_runtime_downloads(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return asyncio.run(_capture(payload or {}))


def get_v50_9_9_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_cdp_url": DEFAULT_CDP_URL,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "live_chrome_cdp_attach",
            "request_response_interception",
            "download_event_capture",
            "binary_response_saving",
            "fetch_xhr_window_open_blob_hooks",
            "new_page_interception",
            "cookie_storage_snapshot",
            "screenshot_capture",
            "har_style_runtime_log",
            "portal_generic_runtime_intelligence",
        ],
    }
