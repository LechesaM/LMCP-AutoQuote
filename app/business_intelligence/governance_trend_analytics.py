from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.operator_ops.operator_actions_service import get_operator_actions
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from ._shared import now_iso, safe_float, safe_int


def build_governance_trend_analytics(limit: int = 100) -> Dict[str, Any]:
    actions = get_operator_actions(limit=limit).get("actions", [])
    pilot = build_pilot_readiness_report(limit=limit)
    final_submission_attempts = safe_int(pilot.get("governance_audit_summary", {}).get("final_submission_attempts", 0))
    proof_gaps = safe_int(pilot.get("governance_audit_summary", {}).get("proof_capture_compliance_count", 0))
    bypass_attempts = sum(1 for action in actions if str(action.get("action")) in {"reopen_review", "archive_rfq"})
    audit_completeness = safe_float(pilot.get("manual_governance_integrity_score", 0.0))
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if actions else "fallback",
        "summary": {
            "governance_incidents": safe_int(pilot.get("incident_summary", {}).get("audit_failures", 0) + pilot.get("incident_summary", {}).get("workflow_failures", 0)),
            "review_bypass_attempts": bypass_attempts,
            "stale_evidence_trend": safe_int(pilot.get("qualification_summary", {}).get("stale_quote_warnings", 0)),
            "proof_capture_gaps": proof_gaps,
            "escalation_trend": safe_int(pilot.get("governance_audit_summary", {}).get("manual_submission_confirmation_count", 0)),
            "audit_completeness_trend": audit_completeness,
        },
        "governance_incidents": [
            {"name": "final_submission_attempts", "count": final_submission_attempts},
            {"name": "bypass_attempts", "count": bypass_attempts},
        ],
        "review_bypass_attempts": bypass_attempts,
        "stale_evidence_trends": [
            {"label": "stale_quote_warnings", "count": safe_int(pilot.get("qualification_summary", {}).get("stale_quote_warnings", 0))}
        ],
        "proof_capture_gaps": proof_gaps,
        "audit_completeness_trends": [
            {"label": "manual_governance_integrity_score", "value": audit_completeness}
        ],
    }

