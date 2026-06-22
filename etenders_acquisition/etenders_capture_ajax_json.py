#!/usr/bin/env python3

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/Users/cash/Documents/runtime/etenders_ajax_capture.json")

captures = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    def handle_response(response):
        url = response.url.lower()

        if "paginatedtenderopportunities" in url:
            try:
                body = response.text()

                captures.append({
                    "url": response.url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body[:500000]
                })

                print(f"Captured AJAX: {response.url}")

            except Exception as e:
                print("ERR:", e)

    page.on("response", handle_response)

    page.goto(
        "https://www.etenders.gov.za/Home/opportunities?id=1",
        wait_until="domcontentloaded"
    )

    print("\nWAITING 15 SECONDS FOR AJAX...")
    page.wait_for_timeout(15000)

    OUT.write_text(json.dumps(captures, indent=2))

    print(f"\nSaved: {OUT}")
    print(f"Captures: {len(captures)}")

    browser.close()
