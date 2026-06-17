from __future__ import annotations

from typing import Any, Dict

from .audit_chain_validator import build_audit_chain_validation


def build_audit_integrity_monitor(limit: int = 100) -> Dict[str, Any]:
    validation = build_audit_chain_validation(limit=limit)
    return {
        "status": validation.get("status"),
        "integrity_score": validation.get("integrity_score"),
        "manual_governance_only": True,
        "validation": validation,
    }
