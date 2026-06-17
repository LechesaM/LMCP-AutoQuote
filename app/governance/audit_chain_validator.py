from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services import immutable_submission_lock_service


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def load_audit_events(limit: int = 100) -> List[Dict[str, Any]]:
    records = immutable_submission_lock_service._read_records()  # type: ignore[attr-defined]
    if not records:
        return []
    events = []
    for record in records[-max(1, int(limit or 100)) :]:
        events.append(
            {
                "id": record.get("record_hash") or "",
                "event_type": record.get("kind") or "",
                "created_at": record.get("timestamp") or "",
                "source": record.get("source_service") or "",
                "severity": "info",
                "payload": record.get("payload") if isinstance(record.get("payload"), dict) else {},
            }
        )
    return events


def build_audit_chain_validation(limit: int = 100) -> Dict[str, Any]:
    events = list(load_audit_events(limit=limit) or [])
    missing_required_fields = 0
    timestamps = []
    seen_ids = set()
    duplicate_ids = 0
    orphaned_actions: List[Dict[str, Any]] = []
    for event in events:
        event_id = _safe_text(event.get("id"))
        event_type = _safe_text(event.get("event_type"))
        created_at = _safe_text(event.get("created_at"))
        if not event_id or not event_type or not created_at:
            missing_required_fields += 1
        if event_id:
            if event_id in seen_ids:
                duplicate_ids += 1
            seen_ids.add(event_id)
        if created_at:
            timestamps.append(created_at)
        if "action" in event_type and not isinstance(event.get("payload"), dict):
            orphaned_actions.append(event)
        if "action" in event_type and not event.get("payload"):
            orphaned_actions.append(event)
    timestamps_sorted = timestamps == sorted(timestamps)
    penalties = (missing_required_fields * 20) + (duplicate_ids * 15) + (len(orphaned_actions) * 20) + (0 if timestamps_sorted else 10)
    integrity_score = max(0, 100 - penalties)
    status = "healthy" if integrity_score >= 90 else ("degraded" if integrity_score >= 60 else "failing")
    return {
        "status": status,
        "validated_at": _now_iso(),
        "append_only_assumed": True,
        "timestamps_sorted": timestamps_sorted,
        "missing_required_fields": missing_required_fields,
        "duplicate_ids": duplicate_ids,
        "orphaned_actions": orphaned_actions,
        "integrity_score": integrity_score,
        "defensibility_report": {
            "event_count": len(events),
            "manual_only_governance": True,
            "append_only_chain_expected": True,
        },
        "events_sample": events[-max(0, min(len(events), 10)) :],
    }
