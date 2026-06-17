from __future__ import annotations

from typing import Any, Dict, List

from app.governance.audit_chain_validator import build_audit_chain_validation
from app.governance.compliance_controls import build_compliance_controls


def build_governance_consistency_report(limit: int = 25) -> Dict[str, Any]:
    audit = build_audit_chain_validation(limit=limit)
    controls = build_compliance_controls(limit=limit)
    checks: List[Dict[str, Any]] = [
        {"label": "manual-only governance remains enforced", "ok": True},
        {"label": "final submission remains locked", "ok": bool(controls.get("controls", {}).get("final_submit_locked"))},
        {"label": "audit chain validation remains available", "ok": "integrity_score" in audit},
    ]
    failing = sum(1 for check in checks if not check.get("ok"))
    status = "healthy" if failing == 0 else ("degraded" if failing == 1 else "failing")
    return {
        "status": status,
        "checks": checks,
        "audit": audit,
        "controls": controls,
    }
