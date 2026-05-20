from __future__ import annotations

from typing import Any, Dict

from ._shared import now_iso
from .audit_chain_validator import build_audit_chain_validation


def build_audit_integrity_monitor(limit: int = 500) -> Dict[str, Any]:
    payload = build_audit_chain_validation(limit=limit)
    return {
        "status": payload.get("status", "ok"),
        "generated_at": now_iso(),
        "data_source": payload.get("data_source", "runtime"),
        "monitor": payload,
        "integrity_score": payload.get("integrity_score", 0),
        "warnings": payload.get("warnings", []),
        "blockers": payload.get("blockers", []),
    }

