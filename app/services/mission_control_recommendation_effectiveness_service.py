from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


_LOCK = Lock()
ALLOWED_EVENT_TYPES = {"generated", "opened", "acted", "completed"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text or default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_date(value: Any) -> datetime.date | None:
    text = _safe_str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _history_root() -> Path:
    explicit = _safe_str(os.getenv("LMCP_MISSION_CONTROL_TRACKING_DIR") or os.getenv("LMCP_MISSION_CONTROL_EFFECTIVENESS_DIR"))
    if explicit:
        return Path(explicit).expanduser().resolve()
    return get_runtime_paths().runtime_root / "mission_control"


def _event_log_path() -> Path:
    explicit = _safe_str(os.getenv("LMCP_MISSION_CONTROL_EFFECTIVENESS_LOG_PATH"))
    if explicit:
        return Path(explicit).expanduser().resolve()
    return _history_root() / "recommendation_effectiveness.jsonl"


def _dedupe_key(event: Dict[str, Any]) -> str:
    recommendation_id = _safe_str(event.get("recommendationId") or event.get("recommendation_id") or event.get("id"))
    event_type = _safe_str(event.get("eventType") or event.get("event_type") or "generated").lower()
    occurred_at = _safe_str(event.get("occurredAt") or event.get("occurred_at") or event.get("createdAt") or event.get("created_at"))
    date_key = _safe_date(occurred_at)
    return "|".join([recommendation_id, event_type, date_key.isoformat() if date_key else occurred_at[:10]])


def _normalise_event_type(value: Any) -> str:
    text = _safe_str(value, "generated").lower()
    if text in {"recommendation_generated", "generated"}:
        return "generated"
    if text in {"recommendation_opened", "opened"}:
        return "opened"
    if text in {"recommendation_acted", "acted", "actioned"}:
        return "acted"
    if text in {"recommendation_completed", "completed"}:
        return "completed"
    return "generated"


def _read_events() -> List[Dict[str, Any]]:
    path = _event_log_path()
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                events.append(payload)
    except Exception:
        return []
    return events


def _write_event(event: Dict[str, Any]) -> Dict[str, Any]:
    path = _event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    return event


def build_default_mission_control_recommendation_effectiveness(status: str = "insufficient_history") -> Dict[str, Any]:
    return {
        "status": status,
        "generatedAt": _now_iso(),
        "days": 30,
        "totals": {"events": 0, "generated": 0, "opened": 0, "acted": 0, "completed": 0},
        "byEventType": {"generated": 0, "opened": 0, "acted": 0, "completed": 0},
        "byRecommendationType": {},
        "byPriority": {},
        "recentEvents": [],
        "eventLogPath": str(_event_log_path()),
    }


def record_mission_control_recommendation_event(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(event)
    event_type = _normalise_event_type(payload.get("eventType") or payload.get("event_type"))
    occurred_at = _safe_str(payload.get("occurredAt") or payload.get("occurred_at") or _now_iso())
    recommendation_id = _safe_str(payload.get("recommendationId") or payload.get("recommendation_id") or payload.get("id") or _dedupe_key(payload))
    record = {
        "id": _safe_str(payload.get("id") or f"mc-rec-{len(_read_events()) + 1}"),
        "eventType": event_type,
        "recommendationId": recommendation_id,
        "recommendationType": _safe_str(payload.get("recommendationType") or payload.get("recommendation_type") or "unknown"),
        "priority": _safe_str(payload.get("priority") or "unknown"),
        "source": _safe_str(payload.get("source") or "unknown"),
        "targetRoute": _safe_str(payload.get("targetRoute") or payload.get("target_route") or ""),
        "relatedRfqId": _safe_str(payload.get("relatedRfqId") or payload.get("related_rfq_id") or ""),
        "score": _safe_float(payload.get("score") or 0),
        "estimatedProfit": _safe_float(payload.get("estimatedProfit") or payload.get("estimated_profit") or 0),
        "occurredAt": occurred_at,
        "metadata": _safe_dict(payload.get("metadata") or payload.get("payload")),
    }

    existing = _read_events()
    key = _dedupe_key(record)
    if any(_dedupe_key(item) == key for item in existing):
        return record
    return _write_event(record)


def build_mission_control_recommendation_effectiveness(days: int = 30) -> Dict[str, Any]:
    try:
        window_days = max(1, min(int(days or 30), 365))
    except Exception:
        window_days = 30

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=window_days - 1)
    events = [event for event in _read_events() if _safe_date(event.get("occurredAt") or event.get("occurred_at")) is not None]
    events = [event for event in events if _safe_date(event.get("occurredAt") or event.get("occurred_at")) >= cutoff]
    events.sort(key=lambda item: _safe_str(item.get("occurredAt") or item.get("occurred_at")), reverse=True)

    if not events:
        return build_default_mission_control_recommendation_effectiveness()

    totals = Counter(_normalise_event_type(event.get("eventType") or event.get("event_type")) for event in events)
    by_recommendation_type = Counter(_safe_str(event.get("recommendationType") or event.get("recommendation_type") or "unknown").lower() for event in events)
    by_priority = Counter(_safe_str(event.get("priority") or "unknown").lower() for event in events)

    recent_events = events[:20]
    return {
        "status": "configured" if totals else "insufficient_history",
        "generatedAt": _now_iso(),
        "days": window_days,
        "totals": {
            "events": len(events),
            "generated": totals.get("generated", 0),
            "opened": totals.get("opened", 0),
            "acted": totals.get("acted", 0),
            "completed": totals.get("completed", 0),
        },
        "byEventType": {key: totals.get(key, 0) for key in ("generated", "opened", "acted", "completed")},
        "byRecommendationType": dict(by_recommendation_type),
        "byPriority": dict(by_priority),
        "recentEvents": recent_events,
        "eventLogPath": str(_event_log_path()),
    }
