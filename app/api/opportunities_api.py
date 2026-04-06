from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

from app.tasks import manual_harvest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.post("/harvest", summary="Trigger RFQ Harvest into Live Store (ASYNC)")
def harvest_opportunities() -> Dict[str, Any]:
    """
    🔥 NON-BLOCKING HARVEST

    - Triggers Celery background task
    - Returns immediately
    - Prevents Swagger/UI freezing
    """

    try:
        # 🚀 Trigger async harvest
        task = manual_harvest.delay()

        return {
            "status": "started",
            "message": "RFQ harvest started in background",
            "task_id": task.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.exception("❌ Failed to trigger async harvest")

        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/live", summary="Get Current Live RFQs")
def get_live_opportunities() -> Dict[str, Any]:
    """
    Returns current RFQs from live store.
    Falls back to manual harvest ONLY if empty.
    """

    try:
        from app.services.live_rfq_store import LiveRFQStore

        store = LiveRFQStore()
        data = store.get_all()

        if data:
            return {
                "status": "ok",
                "source": "live_store",
                "count": len(data),
                "items": data,
            }

        # ⚠️ Fallback (still synchronous but only if empty)
        logger.warning("⚠️ Live store empty → triggering fallback harvest")

        fallback = manual_harvest()

        return {
            "status": "ok",
            "source": "fallback_manual_harvest",
            "count": len(fallback.get("items", [])),
            "items": fallback.get("items", []),
        }

    except Exception as e:
        logger.exception("❌ Failed to fetch live opportunities")

        return {
            "status": "error",
            "message": str(e),
        }
