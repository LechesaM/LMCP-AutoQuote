from __future__ import annotations

import asyncio
import os
from typing import Dict, Any
from urllib.parse import urlparse
from pathlib import Path

from playwright.async_api import async_playwright

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "playwright_profiles" / "etenders")


async def run_etenders_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    portal_url = payload.get("portal_url")
    buyer_rfq_number = payload.get("buyer_rfq_number")
    quote_number = payload.get("quote_number")

    if not portal_url:
        return {"status": "error", "message": "portal_url required"}

    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                executable_path=CHROME,
                headless=False,
                args=["--start-maximized"],
                viewport=None,
            )

            page = context.pages[0] if context.pages else await context.new_page()

            await page.goto(portal_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # 🔍 STEP 1 — ensure logged in
            if "login" in page.url.lower():
                return {
                    "status": "manual_login_required",
                    "message": "User not logged in. Please login first.",
                    "current_url": page.url,
                }

            # 🔍 STEP 2 — select company (MAAA dropdown)
            try:
                await page.select_option("select", label="LECHESA MANABA CONSULTING AND PROJECTS")
            except:
                pass  # already selected

            await page.wait_for_timeout(1000)

            # 🔍 STEP 3 — click Start response
            try:
                await page.click("button:has-text('Start response')")
            except:
                return {
                    "status": "error",
                    "message": "Could not click Start response",
                    "url": page.url,
                }

            await page.wait_for_timeout(5000)

            return {
                "status": "ok",
                "stage": "response_started",
                "buyer_rfq_number": buyer_rfq_number,
                "quote_number": quote_number,
                "current_url": page.url,
                "message": "Start response clicked successfully",
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }
