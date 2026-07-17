from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.tender_harvester import run_national_tender_radar

logger = logging.getLogger(__name__)

ENTRYPOINT_IDENTITY = (
    "app.services.harvest_entrypoint.run_canonical_harvest"
)
HARVESTER_IDENTITY = (
    "app.services.tender_harvester.run_national_tender_radar"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_result(message: str = "No harvest data available.") -> Dict[str, Any]:
    return {
        "status": "success",
        "summary": {
            "sources_used": 0,
            "items_found": 0,
            "top_item_supply_score": 0,
            "by_entity_type": {},
        },
        "sources": [],
        "items": [],
        "timestamp": utc_now_iso(),
        "message": message,
    }


def _normalize_result(
    result: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return _default_result("Harvester returned a non-dict result.")

    normalized = deepcopy(result)

    normalized.setdefault("status", "success")
    normalized.setdefault("summary", {})
    normalized.setdefault("sources", [])
    normalized.setdefault("items", [])
    normalized.setdefault("timestamp", utc_now_iso())
    normalized.setdefault("message", "Harvest completed successfully.")

    summary = normalized["summary"]
    if not isinstance(summary, dict):
        summary = {}

    summary.setdefault("sources_used", len(normalized.get("sources", []) or []))
    summary.setdefault("items_found", len(normalized.get("items", []) or []))
    summary.setdefault("top_item_supply_score", 0)
    summary.setdefault("by_entity_type", {})

    normalized["summary"] = summary

    if not isinstance(normalized.get("sources"), list):
        normalized["sources"] = []

    if not isinstance(normalized.get("items"), list):
        normalized["items"] = []

    return normalized


def run_canonical_harvest(
    *,
    max_total: int = 20,
    max_per_source: int = 3,
    persist_to_live_store: bool = False,
    persist_source_health: bool = False,
) -> Dict[str, Any]:
    """
    Single source of truth for harvesting.

    All callers should use this function instead of importing random harvester
    modules directly.

    Behaviour:
    - calls app.services.tender_harvester.run_national_tender_radar()
    - normalizes output shape
    - keeps auto-quote and autonomous downstream execution disabled
    - does not write runtime snapshots
    """
    try:
        raw_result = run_national_tender_radar(
            max_total=max_total,
            max_per_source=max_per_source,
            enable_auto_quote=False,
            persist_to_live_store=persist_to_live_store,
            persist_source_health=persist_source_health,
            headless=True,
            true_autonomous=False,
        )
        result = _normalize_result(raw_result)

        return {
            "status": "completed",
            "entrypoint": ENTRYPOINT_IDENTITY,
            "harvester": HARVESTER_IDENTITY,
            "max_total": max_total,
            "max_per_source": max_per_source,
            "persist_to_live_store": persist_to_live_store,
            "persist_source_health": persist_source_health,
            "auto_quote_enabled": False,
            "autonomous_downstream_enabled": False,
            "result": result,
        }

    except Exception as exc:
        logger.exception(
            "[HARVEST_ENTRYPOINT] Canonical harvest failed"
        )

        return {
            "status": "failed",
            "entrypoint": ENTRYPOINT_IDENTITY,
            "harvester": HARVESTER_IDENTITY,
            "max_total": max_total,
            "max_per_source": max_per_source,
            "persist_to_live_store": False,
            "persist_source_health": False,
            "auto_quote_enabled": False,
            "autonomous_downstream_enabled": False,
            "error": str(exc),
        }


canonical_harvest = run_canonical_harvest
