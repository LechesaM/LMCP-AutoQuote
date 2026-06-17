# V47.6 Submission Verification Engine

import os
from playwright.sync_api import sync_playwright
from datetime import datetime
from pathlib import Path
import json

def verify_live_submission(
    buyer_rfq_number,
    quote_number=None,
    cdp_url="http://127.0.0.1:9222",
    capture_screenshots=True,
    navigate_to_profile_responses=False,
):

    workspace = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "submission_verification_v47_6" / f"{buyer_rfq_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    screenshots_dir = workspace / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "status": "unknown",
        "confidence": 0,
        "screenshots": [],
        "workspace": str(workspace)
    }

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        page = browser.contexts[0].pages[-1]

        if navigate_to_profile_responses:
            page.goto("https://www.etenders.gov.za/Profile#ResponsesSubmitted")

        page.wait_for_timeout(4000)

        text = page.inner_text("body")

        if capture_screenshots:
            path = screenshots_dir / "verification.png"
            page.screenshot(path=str(path), full_page=True)
            result["screenshots"].append(str(path))

        text_lower = text.lower()

        if "submitted" in text_lower or "successful" in text_lower:
            result["status"] = "confirmed_or_likely_submitted"
            result["confidence"] = 0.85

        elif "responses submitted" in text_lower:
            result["status"] = "pending_review_likely_submitted"
            result["confidence"] = 0.6

        elif "error" in text_lower or "failed" in text_lower:
            result["status"] = "not_confirmed"
            result["confidence"] = 0.3

        else:
            result["status"] = "unknown_review_required"
            result["confidence"] = 0.2

        browser.close()

    with open(workspace / "verification.json", "w") as f:
        json.dump(result, f, indent=2)

    return result
