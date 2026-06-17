# app/services/autonomous_scheduler_service.py

import asyncio
from datetime import datetime
from app.services.tender_harvester import run_national_tender_radar
from app.services.production_lock_service import assert_production_submission_allowed
from app.services.portal_submission_service import auto_submit_portal

RUN_INTERVAL_SECONDS = 21600  # 30 minutes


async def run_cycle():
    print(f"[AUTONOMOUS] Cycle started at {datetime.utcnow().isoformat()}")

    tenders = run_national_tender_radar(max_total=10, enable_auto_quote=False)

    for tender in tenders:
        decision = assert_production_submission_allowed(tender)

        if not decision.get("allowed"):
            print(f"[SKIP] Blocked by production lock: {tender.get('buyer_rfq_number')}")
            continue

        try:
            result = await auto_submit(tender)
            print(f"[SUBMIT] {tender.get('buyer_rfq_number')} -> {result.get('submission_status')}")
        except Exception as e:
            print(f"[ERROR] Submission failed: {e}")

    print(f"[AUTONOMOUS] Cycle completed")


async def start_scheduler():
    while True:
        await run_cycle()
        await asyncio.sleep(RUN_INTERVAL_SECONDS)
