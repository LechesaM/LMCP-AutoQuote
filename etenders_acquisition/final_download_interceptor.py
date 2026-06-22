#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

OUT = Path("/Users/cash/Documents/runtime/final_download_interceptor_capture.json")
DOWNLOAD_DIR = Path("/Users/cash/Documents/runtime/final_download_interceptor_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "https://www.etenders.gov.za/Home/opportunities?id=1"

captures = []


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def save_capture():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(captures, indent=2), encoding="utf-8")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    context = browser.new_context(
        accept_downloads=True,
        viewport={"width": 1500, "height": 950},
    )

    page = context.new_page()

    def request_handler(req):
        url = req.url.lower()

        if any(x in url for x in [
            "download",
            "document",
            "support",
            "file",
            "attachment",
            "blob",
            "azure",
            "storage",
            "pdf",
            "docx",
            "xlsx",
            "xls",
            "zip",
        ]):
            captures.append({
                "captured_at": now_iso(),
                "type": "request",
                "url": req.url,
                "method": req.method,
                "headers": dict(req.headers),
                "post_data": req.post_data,
            })
            save_capture()
            print("REQ:", req.method, req.url)

    def response_handler(res):
        url = res.url.lower()

        if any(x in url for x in [
            "download",
            "document",
            "support",
            "file",
            "attachment",
            "blob",
            "azure",
            "storage",
        ]):
            try:
                headers = dict(res.headers)
            except Exception:
                headers = {}

            captures.append({
                "captured_at": now_iso(),
                "type": "response",
                "url": res.url,
                "status": res.status,
                "headers": headers,
            })
            save_capture()
            print("RES:", res.status, res.url)

    def download_handler(download):
        try:
            suggested = download.suggested_filename or "download.bin"
            path = DOWNLOAD_DIR / suggested
            download.save_as(str(path))

            captures.append({
                "captured_at": now_iso(),
                "type": "download",
                "url": download.url,
                "suggested_filename": suggested,
                "saved_path": str(path),
            })
            save_capture()
            print("DOWNLOAD:", suggested, path)
        except Exception as e:
            captures.append({
                "captured_at": now_iso(),
                "type": "download_error",
                "error": str(e),
            })
            save_capture()

    page.on("request", request_handler)
    page.on("response", response_handler)
    page.on("download", download_handler)

    print("Opening eTenders...")
    page.goto(TARGET, wait_until="domcontentloaded")
    page.wait_for_timeout(8000)

    print("")
    print("MANUAL STEPS:")
    print("1. Click Advanced Search if needed.")
    print("2. Search tender: Table 01")
    print("3. Open/view the Table 01 tender row.")
    print("4. Click the actual attachment: RFQ number Tables 01.docx")
    print("5. Wait until download finishes.")
    print("6. Come back to terminal and press ENTER.")
    print("")
    print(f"Capture file updating live: {OUT}")
    print(f"Downloads folder: {DOWNLOAD_DIR}")
    print("")

    input("Press ENTER after you have downloaded one real document... ")

    save_capture()

    print("")
    print(f"Saved capture: {OUT}")
    print(f"Captured entries: {len(captures)}")
    print(f"Downloads saved in: {DOWNLOAD_DIR}")

    context.close()
    browser.close()
