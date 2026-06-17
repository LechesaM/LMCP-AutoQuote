from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .audit_chain_validator import load_audit_events


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def build_evidence_chain_tracker(limit: int = 100) -> Dict[str, Any]:
    events = list(load_audit_events(limit=limit) or [])
    evidence_events: List[Dict[str, Any]] = []
    for event in events:
        event_type = _safe_text(event.get("event_type")).lower()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if "proof" in event_type or "evidence" in event_type or payload.get("proof"):
            evidence_events.append(event)
    return {
        "status": "healthy" if evidence_events else "degraded",
        "generated_at": _now_iso(),
        "evidence_chain_complete": bool(evidence_events),
        "evidence_event_count": len(evidence_events),
        "events": evidence_events,
        "manual_governance_only": True,
    }
