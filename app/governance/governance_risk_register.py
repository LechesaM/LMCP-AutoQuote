from __future__ import annotations

from typing import Any, Dict, List

from app.persistence.persistence_health import validate_persistence_health

from ._shared import now_iso
from .access_review_engine import build_access_review_report
from .audit_chain_validator import build_audit_chain_validation
from .compliance_controls import build_compliance_controls
from .retention_enforcement import build_retention_enforcement_report


def build_governance_risk_register() -> Dict[str, Any]:
    controls = build_compliance_controls()
    access_review = build_access_review_report()
    audit = build_audit_chain_validation()
    retention = build_retention_enforcement_report()
    persistence = validate_persistence_health()
    risks: List[Dict[str, Any]] = []
    if controls.get("blockers"):
        risks.append({"risk": "compliance_blocker", "severity": "critical", "description": controls.get("blockers", [])})
    if access_review.get("stale_access_warnings", 0):
        risks.append({"risk": "access_drift", "severity": "high", "description": "Stale access sessions require review."})
    if audit.get("integrity_score", 0) < 90:
        risks.append({"risk": "audit_gap", "severity": "high", "description": "Audit integrity requires review."})
    if retention.get("blocked_by_legal_hold"):
        risks.append({"risk": "retention_hold", "severity": "medium", "description": "Legal holds protect some retention categories."})
    if persistence.get("status") != "healthy":
        risks.append({"risk": "persistence_risk", "severity": "high", "description": persistence.get("warnings", [])})
    summary = {
        "low": len([risk for risk in risks if risk["severity"] == "low"]),
        "medium": len([risk for risk in risks if risk["severity"] == "medium"]),
        "high": len([risk for risk in risks if risk["severity"] == "high"]),
        "critical": len([risk for risk in risks if risk["severity"] == "critical"]),
    }
    return {
        "status": "ok" if not [risk for risk in risks if risk["severity"] == "critical"] else "degraded",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "risks": risks,
        "summary": summary,
        "warnings": [risk["description"] for risk in risks],
        "blockers": controls.get("blockers", []),
    }

