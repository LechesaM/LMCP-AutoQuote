from __future__ import annotations

from typing import Any, Dict, List


def assess_submission_readiness(
    *,
    compliance_matrix: Dict[str, Any],
    submission_method: Dict[str, Any],
    quote_pack_ready: bool,
    pricing_schedule_ready: bool,
    risk_engine: Dict[str, Any],
    workflow_stage: str | None = None,
) -> Dict[str, Any]:
    method = str(submission_method.get("method") or "unknown")
    blockers: List[str] = []
    warnings: List[str] = []
    reason_chain: List[str] = []

    if risk_engine.get("risk_level") == "blocked" or risk_engine.get("disqualification_triggers"):
        state = "BLOCKED"
        blockers.extend([str(item) for item in risk_engine.get("disqualification_triggers", [])] or ["blocked risk"])
        reason_chain.append("risk engine blocked the RFQ")
    elif compliance_matrix.get("missing_required_count", 0) or not quote_pack_ready or not pricing_schedule_ready:
        state = "MISSING_DOCS"
        if compliance_matrix.get("missing_required_count", 0):
            blockers.extend([str(item) for item in compliance_matrix.get("blockers", [])])
        if not quote_pack_ready:
            blockers.append("quote pack not ready")
        if not pricing_schedule_ready:
            blockers.append("pricing schedule not ready")
        reason_chain.append("mandatory documentation is incomplete")
    elif method in {"physical_delivery", "courier_hand_delivery"}:
        state = "MANUAL_ONLY"
        warnings.append("physical or courier submission requires manual handling")
        reason_chain.append("physical submission path")
    elif method == "portal":
        state = "MANUAL_ONLY"
        warnings.append("portal submission remains supervised")
        reason_chain.append("portal submission path")
    elif risk_engine.get("risk_level") == "high":
        state = "HIGH_RISK"
        warnings.append("high risk RFQ requires operator review")
        reason_chain.append("high risk profile")
    elif method == "email" and quote_pack_ready and pricing_schedule_ready and risk_engine.get("risk_level") == "low":
        state = "READY"
        reason_chain.append("email submission with complete documentation and low risk")
    else:
        state = "HIGH_RISK" if risk_engine.get("risk_level") in {"medium", "high"} else "MANUAL_ONLY"
        warnings.append("operator review required")
        reason_chain.append("fallback to governed review path")

    if workflow_stage and workflow_stage not in {"quote_generated", "approval_required", "approved", "review_ready", "proof_recorded"}:
        warnings.append(f"workflow stage {workflow_stage} not yet eligible for submission")
        if state == "READY":
            state = "MANUAL_ONLY"

    next_operator_action = {
        "READY": "proceed with governed approval steps",
        "MISSING_DOCS": "close compliance gaps and regenerate missing documents",
        "HIGH_RISK": "perform manual review and validate risk triggers",
        "MANUAL_ONLY": "continue under manual supervision",
        "BLOCKED": "stop and resolve disqualification blockers",
    }[state]

    return {
        "readiness_state": state,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "reason_chain": reason_chain,
        "next_operator_action": next_operator_action,
        "manual_only": state in {"MANUAL_ONLY", "BLOCKED"},
        "go_candidate": state == "READY",
    }
