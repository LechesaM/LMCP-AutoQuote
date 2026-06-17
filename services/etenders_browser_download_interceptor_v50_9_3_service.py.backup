"""
LMCP V50.9.3 - Browser Session Download Interceptor

Purpose:
- V50.9.2 proved supportDocument metadata is correct but guessed endpoints mostly 404.
- This engine attaches to a live Chrome/Playwright CDP session and captures the real
  network request when eTenders downloads a support document.
- It can:
    1. attach to a browser over CDP
    2. open the tender details page
    3. watch network responses/download events
    4. identify PDF/Office/ZIP downloads
    5. save downloaded files to runtime/playwright/downloads
    6. record useful request/response metadata for replay in later engines

Important:
- This does NOT bypass CAPTCHA or access controls.
- It only observes a user/operator-controlled browser session.

Routes:
    GET  /v50-9-3-browser-download-interceptor/status
    POST /v50-9-3-browser-download-interceptor/capture

Drop-in:
    app/services/etenders_browser_download_interceptor_v50_9_3_service.py
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SERVICE_VERSION = "V50.9.3_ETENDERS_BROWSER_DOWNLOAD_INTERCEPTOR"

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

    tender_url = _clean(payload.get("tender_url") or "")
    if not tender_url and tender_id:
        tender_url = f"{ETENDERS_BASE}/Home/TenderDetails?id={tender_id}"

    return {
        "tender_id": tender_id,
        "support_document_id": support_document_id,
        "filename": filename,
        "tender_url": tender_url,
    }


async def _capture_with_playwright(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
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
    wait_seconds = int(payload.get("wait_seconds") or 25)
    click_text = _clean(payload.get("click_text") or "")
    auto_click = bool(payload.get("auto_click", True))
    headless_fallback = bool(payload.get("headless_fallback", False))

    safe_name = _safe_filename(data["filename"] or f"tender_{data['tender_id']}_document.pdf")
    output_path = output_dir / f"ETENDERS_{data['tender_id']}__{safe_name}"

    network_events: List[Dict[str, Any]] = []
    download_events: List[Dict[str, Any]] = []
    console_events: List[Dict[str, Any]] = []
    page_errors: List[str] = []
    screenshots: List[str] = []

    browser = None
    context = None
    page = None
    playwright = None

    try:
        playwright = await async_playwright().start()

        try:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            attach_mode = "cdp"
        except Exception as cdp_exc:
            if not headless_fallback:
                return {
                    "status": "error",
                    "service_version": SERVICE_VERSION,
                    "message": "Could not attach to live Chrome CDP session.",
                    "cdp_url": cdp_url,
                    "error": str(cdp_exc),
                    "how_to_start_chrome": (
                        'open -na "Google Chrome" --args --remote-debugging-port=9222 '
                        '--user-data-dir="/tmp/lmcp-chrome-cdp"'
                    ),
                    "safe_to_process": False,
                }

            browser = await playwright.chromium.launch(headless=True, accept_downloads=True)
            attach_mode = "headless_fallback"

        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = await browser.new_context(accept_downloads=True)

        # Ensure downloads are accepted where possible.
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

        # Open the tender details URL. If the operator already has eTenders open,
        # this still gives us the target page and uses the same browser session.
        if data["tender_url"]:
            try:
                await page.goto(data["tender_url"], wait_until="domcontentloaded", timeout=wait_seconds * 1000)
            except Exception as exc:
                network_events.append({"type": "goto_warning", "error": str(exc), "url": data["tender_url"]})

        # Screenshot for debugging.
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
            # Try targeted click by filename, then common document/download text.
            selectors = []
            if data["filename"]:
                selectors += [
                    f"text={data['filename']}",
                    f"a:has-text('{data['filename'][:30]}')",
                ]

            if click_text:
                selectors.append(f"text={click_text}")

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
                "button:has-text('Download')",
                "button:has-text('Documents')",
            ]

            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    count = await page.locator(selector).count()
                    click_attempts.append({"selector": selector, "count": count})
                    if count > 0:
                        # Use expect_download first, but do not fail if click triggers XHR instead.
                        try:
                            async with page.expect_download(timeout=6000) as download_info:
                                await locator.click(timeout=6000)
                            download = await download_info.value
                            await on_download(download)
                            clicked = True
                            break
                        except Exception:
                            try:
                                await locator.click(timeout=6000)
                                clicked = True
                                await page.wait_for_timeout(4000)
                                break
                            except Exception as click_exc:
                                click_attempts[-1]["click_error"] = str(click_exc)
                except Exception as exc:
                    click_attempts.append({"selector": selector, "error": str(exc)})

        # Wait for operator/manual click or background download/network events.
        await page.wait_for_timeout(wait_seconds * 1000)

        # If a verified download happened, return success.
        verified_downloads = [d for d in download_events if d.get("exists") and int(d.get("size") or 0) > 0]

        # Save network capture log.
        output_dir.mkdir(parents=True, exist_ok=True)
        capture_log = output_dir / f"ETENDERS_{data['tender_id']}__v50_9_3_capture.json"
        capture_log.write_text(json.dumps({
            "service_version": SERVICE_VERSION,
            "captured_at": _now(),
            "input": data,
            "attach_mode": attach_mode,
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
            "clicked": clicked,
            "verified_download_count": len(verified_downloads),
            "verified_downloads": verified_downloads,
            "network_event_count": len(network_events),
            "relevant_network_events": network_events[-80:],
            "download_events": download_events,
            "click_attempts": click_attempts[:80],
            "console_events": console_events[-20:],
            "page_errors": page_errors,
            "screenshots": screenshots,
            "capture_log": str(capture_log),
            "safe_to_process": bool(verified_downloads),
            "notes": [
                "If verified_download_count is 0, open the browser attached to CDP and manually click the document link while this endpoint is running.",
                "The capture_log stores request headers, URLs, and POST data for building a replay downloader.",
                "This engine does not bypass CAPTCHA or access controls.",
            ],
        }

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Browser download capture failed.",
            "error": str(exc),
            "input": data,
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
            "network_request_interception",
            "download_event_capture",
            "download_file_storage",
            "request_header_capture",
            "post_body_capture",
            "operator_assisted_document_click",
            "capture_log_generation",
        ],
    }
