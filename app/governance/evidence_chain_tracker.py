from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.services.audit_trail_service import load_audit_events

from ._shared import now_iso


def build_evidence_chain_tracker(limit: int = 500) -> Dict[str, Any]:
    events = load_audit_events()[-max(1, int(limit or 500)) :]
    evidence_events = [
        event
        for event in events
        if any(keyword in str(event.get("event_type") or "").lower() for keyword in ("proof", "evidence", "submission", "quote"))
        or any(keyword in str(event.get("message") or "").lower() for keyword in ("proof", "evidence", "quote"))
    ]
    chain_counts = Counter(str(event.get("event_type") or "unknown") for event in evidence_events)
    missing_references = [
        event
        for event in evidence_events
        if not (event.get("buyer_rfq_number") or event.get("quote_number") or event.get("payload"))
    ]
    return {
        "status": "ok" if not missing_references else "degraded",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "evidence_events": evidence_events,
        "evidence_event_count": len(evidence_events),
        "evidence_event_types": dict(chain_counts),
        "missing_references": missing_references,
        "evidence_chain_complete": len(missing_references) == 0,
    }

