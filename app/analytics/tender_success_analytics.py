from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


class TenderOutcomeStatus(str, Enum):
    SUBMITTED = "submitted"
    AWARDED = "awarded"
    LOST = "lost"


def _log_path() -> Path:
    return get_runtime_paths().manual_production_dir / "tender_outcomes.jsonl"


def record_tender_outcome(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(record)
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
    return payload


def _items(limit: int = 20) -> List[Dict[str, Any]]:
    path = _log_path()
    items: List[Dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines()[-max(1, int(limit or 20)):]:
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                items.append(payload)
    return items


def build_tender_success_analytics(limit: int = 20) -> Dict[str, Any]:
    items = _items(limit)
    processed = len(items)
    submitted_manually = sum(1 for item in items if item.get("submitted_manually"))
    won = sum(1 for item in items if str(item.get("outcome_status")) == TenderOutcomeStatus.AWARDED.value)
    lost = sum(1 for item in items if str(item.get("outcome_status")) == TenderOutcomeStatus.LOST.value)
    quote_generated = sum(1 for item in items if item.get("quote_generated"))
    refusal_rate = (lost / processed) if processed else 0.0
    quote_conversion_rate = (quote_generated / processed) if processed else 0.0
    return {
        "status": "ok",
        "tender_outcome_summary": {
            "processed": processed,
            "submitted_manually": submitted_manually,
            "won": won,
            "lost": lost,
        },
        "refusal_rate": refusal_rate,
        "quote_conversion_rate": quote_conversion_rate,
    }
