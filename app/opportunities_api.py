from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter

from app.tasks import manual_harvest, run_harvest_only

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


def _normalize_manual_harvest_result(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "status": "ok",
            "source": "manual_harvest",
            "updated_at": None,
            "count": 0,
            "items": [],
        }

    items: List[Dict[str, Any]] = []

    raw_items = result.get("items")
    if isinstance(raw_items, list):
        items = [item for item in raw_items if isinstance(item, dict)]

    if not items:
        raw_opportunities = result.get("opportunities")
        if isinstance(raw_opportunities, list):
            items = [item for item in raw_opportunities if isinstance(item, dict)]

    count = result.get("count")
    if not isinstance(count, int):
        count = result.get("opportunities_found")
    if not isinstance(count, int):
        count = len(items)

    return {
        "status": result.get("status", "ok"),
        "source": result.get("source", "manual_harvest"),
        "updated_at": result.get("updated_at"),
        "count": count,
        "items": items,
    }


def _get_live_store_items() -> Dict[str, Any]:
    from app.services.live_rfq_store import LiveRFQStore

    live_data = LiveRFQStore.get_all()
    if not isinstance(live_data, dict):
        return {
            "status": "ok",
            "source": "live_rfq_store",
            "updated_at": None,
            "count": 0,
            "items": [],
        }

    live_items = live_data.get("items", [])
    if not isinstance(live_items, list):
        live_items = []

    return {
        "status": "ok",
        "source": "live_rfq_store",
        "updated_at": live_data.get("updated_at"),
        "count": len(live_items),
        "items": live_items,
    }


@router.post("/harvest", summary="Trigger RFQ Harvest into Live Store (ASYNC)")
def harvest_opportunities() -> Dict[str, Any]:
    """
    Trigger background harvest via Celery and return immediately.
    This prevents Swagger/UI from blocking on long harvest runs.
    """
    try:
        task = run_harvest_only.delay()
        return {
            "status": "started",
            "message": "RFQ harvest started in background",
            "task_id": task.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("Failed to trigger async harvest")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": 0,
            "items": [],
        }


@router.get("/live", summary="Get Current Live RFQs")
def get_live_opportunities() -> Dict[str, Any]:
    """
    Returns current live RFQs from the live store.
    Falls back to synchronous manual harvest only if the live store is empty.
    """
    try:
        live_response = _get_live_store_items()
        if live_response["items"]:
            return live_response
    except Exception:
        logger.exception("Failed reading LiveRFQStore in get_live_opportunities")

    try:
        result = manual_harvest()
        normalized = _normalize_manual_harvest_result(result)
        normalized["source"] = "fallback_manual_harvest"
        return normalized
    except Exception as e:
        logger.exception("Failed to fetch live opportunities")
        return {
            "status": "error",
            "message": str(e),
            "count": 0,
            "items": [],
        }


@router.get("/harvest/status", summary="Harvest Status")
def harvest_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "message": "Harvest service available",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("", summary="Get Opportunities")
@router.get("/", summary="Get Opportunities")
def get_opportunities() -> Dict[str, Any]:
    """
    Returns current live RFQs.
    Falls back to synchronous manual harvest only if the live store is empty.
    """
    try:
        live_response = _get_live_store_items()
        if live_response["items"]:
            return live_response
    except Exception:
        logger.exception("Failed reading LiveRFQStore in get_opportunities")

    try:
        result = manual_harvest()
        normalized = _normalize_manual_harvest_result(result)
        normalized["source"] = "fallback_manual_harvest"
        return normalized
    except Exception as e:
        logger.exception("get_opportunities failed")
        return {
            "status": "error",
            "message": str(e),
            "count": 0,
            "items": [],
        }


@router.get("/health", summary="Opportunities API Health")
def opportunities_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "opportunities_api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
