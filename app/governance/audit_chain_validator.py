from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.audit_trail_service import load_audit_events

from ._shared import now_iso


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def build_audit_chain_validation(limit: int = 500) -> Dict[str, Any]:
    events = load_audit_events()[-max(1, int(limit or 500)) :]
    warnings: List[str] = []
    blockers: List[str] = []
    missing_required_fields = [event for event in events if not event.get("id") or not event.get("event_type") or not event.get("created_at")]
    parsed_times = [_parse_iso(event.get("created_at")) for event in events if _parse_iso(event.get("created_at"))]
    timestamps_sorted = all(parsed_times[index] <= parsed_times[index + 1] for index in range(len(parsed_times) - 1)) if parsed_times else True
    if missing_required_fields:
        warnings.append("Some audit events are missing required fields.")
    if not timestamps_sorted:
        warnings.append("Audit timestamps are not strictly ordered.")
    duplicate_ids = len({event.get("id") for event in events}) != len(events)
    if duplicate_ids:
        blockers.append("Duplicate audit event identifiers detected.")
    orphaned_actions = [
        event
        for event in events
        if str(event.get("event_type") or "").startswith("operator_") and not (event.get("buyer_rfq_number") or event.get("payload"))
    ]
    if orphaned_actions:
        warnings.append("Potential orphaned operator actions detected.")
    integrity_score = 100 - (15 * len(blockers)) - (5 * len(warnings))
    integrity_score = max(0, integrity_score)
    status = "healthy"
    if blockers:
        status = "failing"
    elif warnings:
        status = "degraded"
    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "total_events": len(events),
        "missing_required_fields": len(missing_required_fields),
        "timestamps_sorted": timestamps_sorted,
        "duplicate_ids": duplicate_ids,
        "orphaned_actions": orphaned_actions,
        "warnings": warnings,
        "blockers": blockers,
        "integrity_score": integrity_score,
        "append_only_assumed": True,
        "defensibility_report": {
            "continuity": timestamps_sorted and not duplicate_ids,
            "attribution": len(orphaned_actions) == 0,
            "export_ready": True,
        },
    }

