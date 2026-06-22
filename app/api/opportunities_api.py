from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from app.tasks import run_harvest_only as run_harvest_only_task
from app.services.local_harvest_service import run_local_sprint7_harvest


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])

_FIXTURE_SOURCES = {"visible_bulk_validation", "seed_fixture", "Smoke Fixture eTenders"}
_HISTORICAL_MARKERS = {"manual_production", "pilot_wave", "simulation_runs", "submission_packages"}


def _parse_date(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt)
        except Exception:
            continue
    return None


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

    current_items = [item for item in live_items if isinstance(item, dict) and _is_current_live_candidate(item)]

    return {
        "status": "ok",
        "source": "live_rfq_store",
        "updated_at": live_data.get("updated_at"),
        "count": len(current_items),
        "items": current_items,
        "filter": {
            "closing_date": "today_or_later",
            "historical_sources_excluded": sorted(_HISTORICAL_MARKERS),
            "fixture_sources_excluded": sorted(_FIXTURE_SOURCES),
        },
    }


def _is_current_live_candidate(item: Dict[str, Any]) -> bool:
    closing_date = str(item.get("closing_date") or "").strip()
    if not closing_date:
        return False
    try:
        parsed = _parse_date(closing_date)
        if parsed is None or parsed.date() < datetime.now(timezone.utc).date():
            return False
    except Exception:
        return False

    source = (
        str(item.get("source") or "").strip()
        or str(item.get("data_source") or "").strip()
        or str((item.get("rfq_validation_report") or {}).get("source") or "").strip()
    )
    if source in _FIXTURE_SOURCES:
        return False

    blob = json.dumps(item, ensure_ascii=False).lower()
    if any(marker in blob for marker in _HISTORICAL_MARKERS):
        return False
    if any(source.lower() == marker.lower() for marker in _HISTORICAL_MARKERS):
        return False

    buyer_name = str(item.get("buyer_name") or "").strip()
    if not buyer_name:
        return False

    return True


@router.post("/harvest", summary="Trigger RFQ Harvest into Live Store (ASYNC)")
def harvest_opportunities() -> Dict[str, Any]:
    try:
        task = run_harvest_only_task.delay()
        return {
            "status": "started",
            "message": "RFQ harvest started in background",
            "task_id": task.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.exception("Failed to trigger async harvest")
        return {
            "status": "error",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": 0,
            "items": [],
        }


@router.post("/harvest-local", summary="Trigger RFQ Harvest into Live Store (LOCAL)")
def harvest_opportunities_local(
    max_total: int = 20,
    max_per_source: int = 5,
    max_sources_per_cycle: int = 10,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
    source_file: Optional[str] = None,
    source_name: str = "NECSA",
    include_bad_sources: bool = False,
    headless: bool = True,
    persist_to_live_store: bool = True,
    minimum_margin_pct: float = 25.0,
    minimum_profit: float = 30000.0,
) -> Dict[str, Any]:
    result = run_local_sprint7_harvest(
        max_total=max_total,
        max_per_source=max_per_source,
        max_sources_per_cycle=max_sources_per_cycle,
        source_file=source_file,
        source_name=source_name,
        include_bad_sources=include_bad_sources,
        headless=headless,
        persist_to_live_store=persist_to_live_store,
        minimum_margin_pct=minimum_margin_pct,
        minimum_profit=minimum_profit,
        source_timeout_seconds=source_timeout_seconds,
        playwright_timeout_ms=playwright_timeout_ms,
    )
    return {
        "status": "ok" if result.get("status") == "ok" else "failed",
        "message": "RFQ harvest completed locally",
        "source": "local_harvest",
        "source_name": source_name,
        "persist_to_live_store": persist_to_live_store,
        "source_file": result.get("source_file") or source_file,
        "count": len(result.get("items") if isinstance(result.get("items"), list) else []),
        "result": result,
    }


@router.get("/live", summary="Get Current Live RFQs")
def get_live_opportunities() -> Dict[str, Any]:
    try:
        return _get_live_store_items()
    except Exception as exc:
        logger.exception("Failed to fetch live opportunities")
        return {
            "status": "error",
            "message": str(exc),
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
    try:
        return _get_live_store_items()
    except Exception as exc:
        logger.exception("get_opportunities failed")
        return {
            "status": "error",
            "message": str(exc),
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
