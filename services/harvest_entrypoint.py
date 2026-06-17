from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.services.tender_harvester import harvest_tenders

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path("/app/runtime")
SNAPSHOT_FILE = SNAPSHOT_DIR / "last_harvest_result.json"


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


def _normalize_result(result: Dict[str, Any] | None) -> Dict[str, Any]:
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


def _write_snapshot(result: Dict[str, Any]) -> None:
    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Could not write harvest snapshot: %s", exc)


def _read_snapshot() -> Dict[str, Any] | None:
    try:
        if not SNAPSHOT_FILE.exists():
            return None

        data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return _normalize_result(data)
    except Exception as exc:
        logger.warning("Could not read harvest snapshot: %s", exc)

    return None


def run_canonical_harvest() -> Dict[str, Any]:
    """
    Single source of truth for harvesting.

    All callers should use this function instead of importing random harvester
    modules directly.

    Behaviour:
    - calls app.services.tender_harvester.harvest_tenders()
    - normalizes output shape
    - writes a last-good snapshot
    - falls back to snapshot if live harvesting fails
    """
    try:
        result = _normalize_result(harvest_tenders())
        _write_snapshot(result)
        return result

    except Exception as exc:
        logger.exception("Canonical harvest failed: %s", exc)

        snapshot = _read_snapshot()
        if snapshot:
            snapshot["message"] = (
                f"Using last good harvest snapshot because live harvest failed: {exc}"
            )
            snapshot["timestamp"] = utc_now_iso()
            snapshot["snapshot_fallback"] = True
            return snapshot

        return _default_result(f"Live harvest failed and no snapshot exists: {exc}")
