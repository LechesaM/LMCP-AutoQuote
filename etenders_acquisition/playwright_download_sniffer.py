#!/usr/bin/env python3
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/Users/cash/Documents/runtime/browser_download_capture.json")

TARGET = "https://www.etenders.gov.za/Home/opportunities?id=1"

captures = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    context = browser.new_context(
        accept_downloads=True
    )

    page = context.new_page()

    def handle_request(req):
        url = req.url.lower()

        if any(x in url for x in [
            "download",
            "document",
            "supportdocument",
            "file",
            "pdf",
            "xlsx",
            "docx"
        ]):
            captures.append({
                "type": "request",
                "url": req.url,
                "method": req.method,
                "headers": dict(req.headers),
                "post_data": req.post_data
            })

    def handle_response(res):
        url = res.url.lower()

        if any(x in url for x in [
            "download",
            "document",
            "supportdocument",
            "file"
        ]):
            captures.append({
                "type": "response",
                "url": res.url,
                "status": res.status,
                "headers": dict(res.headers),
            })

    page.on("request", handle_request)
    page.on("response", handle_response)

    print("OPENING PORTAL...")
    page.goto(TARGET, wait_until="domcontentloaded")

    print("WAITING FOR MANUAL ACTION...")
    print("")
    print("MANUALLY:")
    print("1. Click any tender")
    print("2. Open tender detail")
    print("3. Click any PDF/document download")
    print("4. Wait 10 seconds")
    print("5. Press ENTER here")

    input()

    OUT.write_text(json.dumps(captures, indent=2))

    print(f"\nSaved: {OUT}")
    print(f"Captured entries: {len(captures)}")

    browser.close()
