from __future__ import annotations

from typing import Any, Dict

from app.services.audit_trail_service import get_audit_events, get_audit_summary

from ._shared import now_iso
from .audit_chain_validator import build_audit_chain_validation
from .evidence_chain_tracker import build_evidence_chain_tracker


def build_audit_snapshot(limit: int = 100) -> Dict[str, Any]:
    events = get_audit_events(limit=limit)
    summary = get_audit_summary()
    chain = build_audit_chain_validation(limit=limit)
    evidence = build_evidence_chain_tracker(limit=limit)
    return {
        "status": "ok" if chain.get("status") != "failing" else "degraded",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "audit_events": events,
        "audit_summary": summary,
        "audit_integrity": chain,
        "evidence_chain": evidence,
        "export_ready": True,
    }

