from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.auth import rbac
from app.governance.audit_chain_validator import build_audit_chain_validation
from app.governance.compliance_controls import build_compliance_controls
from app.governance.policy_registry import build_policy_registry
from app.governance.retention_enforcement import build_retention_enforcement_report
from app.persistence.persistence_health import validate_persistence_health
from app.services.audit_trail_service import load_audit_events

from ._shared import now_iso, safe_int


_AUDIT_EVENT_TYPES_REQUIRING_ATTRIBUTION = {
    "governance_legal_hold_registered",
    "governance_legal_hold_released",
    "governance_attestation_generated",
    "operator_action_created",
    "operator_assignment_created",
    "operator_timeline_event",
}


def build_governance_consistency_report(limit: int = 100) -> Dict[str, Any]:
    policy_registry = build_policy_registry()
    compliance_controls = build_compliance_controls(limit=limit)
    audit_chain = build_audit_chain_validation(limit=limit)
    retention = build_retention_enforcement_report()
    persistence = validate_persistence_health()
    events = load_audit_events()[-max(1, int(limit or 100)) :]
    permissions = {role: list(perms) for role, perms in rbac.ROLE_PERMISSIONS.items()}

    missing_attribution = [
        event
        for event in events
        if str(event.get("event_type") or "") in _AUDIT_EVENT_TYPES_REQUIRING_ATTRIBUTION
        and not (
            str(event.get("operator_id") or "").strip()
            or str(event.get("payload", {}).get("operator_id") or "").strip()
            or str(event.get("payload", {}).get("actor") or "").strip()
        )
    ]
    inconsistencies: List[str] = []
    if not bool(policy_registry.get("summary", {}).get("manualEnforcementOnly", policy_registry.get("summary", {}).get("manual_enforcement_only", True))):
        inconsistencies.append("Manual-only governance policy is not enabled.")
    if not compliance_controls.get("controls", {}).get("review_ready_enforced", False):
        inconsistencies.append("review_ready enforcement is inconsistent.")
    if not compliance_controls.get("controls", {}).get("proof_capture_enforced", False):
        inconsistencies.append("proof capture enforcement is inconsistent.")
    if compliance_controls.get("controls", {}).get("manual_submission_only") is not True:
        inconsistencies.append("Manual submission governance is inconsistent.")
    if compliance_controls.get("controls", {}).get("rbac_integrity") is not True:
        inconsistencies.append("RBAC integrity is inconsistent.")
    if audit_chain.get("integrity_score", 0) < 90:
        inconsistencies.append("Audit continuity requires review.")
    if missing_attribution:
        inconsistencies.append("Missing audit attribution detected.")
    if retention.get("dry_run_only") is not True:
        inconsistencies.append("Retention enforcement is not in dry-run mode.")
    if persistence.get("status") == "failing":
        inconsistencies.append("Persistence health is failing.")
    no_bypass_permissions = not any(
        permission in {"autonomous_submit", "auto_approve", "bypass_review_ready", "bypass_proof_capture"}
        for perms in permissions.values()
        for permission in perms
    )
    if not no_bypass_permissions:
        inconsistencies.append("Prohibited governance permissions are present.")

    severity = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }
    for item in compliance_controls.get("warnings", []):
        severity["medium"] += 1
    if inconsistencies:
        severity["high"] += len(inconsistencies)
    if persistence.get("status") == "failing":
        severity["critical"] += 1

    score = 100 - (severity["medium"] * 4) - (severity["high"] * 8) - (severity["critical"] * 20)
    score = max(0, min(100, score))
    status = "healthy"
    if persistence.get("status") == "failing" or severity["critical"]:
        status = "failing"
    elif inconsistencies or compliance_controls.get("warnings") or compliance_controls.get("blockers"):
        status = "degraded"

    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "consistency_score": score,
        "checks": [
            {
                "label": "manual-only governance",
                "status": "pass" if bool(policy_registry.get("summary", {}).get("manualEnforcementOnly", True)) else "fail",
                "passed": bool(policy_registry.get("summary", {}).get("manualEnforcementOnly", True)),
                "detail": "Manual-only governance policy is enabled.",
                "severity": "info",
            },
            {
                "label": "review_ready enforcement",
                "status": "pass" if compliance_controls.get("controls", {}).get("review_ready_enforced", False) else "fail",
                "passed": compliance_controls.get("controls", {}).get("review_ready_enforced", False),
                "detail": "review_ready enforcement must remain consistent.",
                "severity": "info",
            },
            {
                "label": "proof capture enforcement",
                "status": "pass" if compliance_controls.get("controls", {}).get("proof_capture_enforced", False) else "fail",
                "passed": compliance_controls.get("controls", {}).get("proof_capture_enforced", False),
                "detail": "Proof capture enforcement must remain consistent.",
                "severity": "info",
            },
            {
                "label": "manual submission only",
                "status": "pass" if compliance_controls.get("controls", {}).get("manual_submission_only", False) else "fail",
                "passed": compliance_controls.get("controls", {}).get("manual_submission_only", False),
                "detail": "Submission remains manual-only.",
                "severity": "info",
            },
            {
                "label": "rbac integrity",
                "status": "pass" if compliance_controls.get("controls", {}).get("rbac_integrity", False) else "fail",
                "passed": compliance_controls.get("controls", {}).get("rbac_integrity", False),
                "detail": "RBAC permissions remain governance-safe.",
                "severity": "info",
            },
            {
                "label": "audit continuity",
                "status": "pass" if audit_chain.get("append_only_assumed", False) and audit_chain.get("timestamps_sorted", True) else "fail",
                "passed": audit_chain.get("append_only_assumed", False) and audit_chain.get("timestamps_sorted", True),
                "detail": "Audit chain remains append-only and ordered.",
                "severity": "info",
            },
            {
                "label": "operator attribution",
                "status": "pass" if len(missing_attribution) == 0 else "fail",
                "passed": len(missing_attribution) == 0,
                "detail": "Operator attribution must remain present for governance events.",
                "severity": "info",
            },
            {
                "label": "retention dry run",
                "status": "pass" if retention.get("dry_run_only", False) else "fail",
                "passed": retention.get("dry_run_only", False),
                "detail": "Retention enforcement remains dry-run only by default.",
                "severity": "info",
            },
            {
                "label": "no prohibited permissions",
                "status": "pass" if no_bypass_permissions else "fail",
                "passed": no_bypass_permissions,
                "detail": "Autonomous and bypass permissions remain absent.",
                "severity": "info",
            },
        ],
        "inconsistencies": inconsistencies,
        "warnings": compliance_controls.get("warnings", []) + (["Audit attribution gaps detected."] if missing_attribution else []),
        "blockers": compliance_controls.get("blockers", []) + (["Persistence is failing."] if persistence.get("status") == "failing" else []),
        "audit_attribution_missing": len(missing_attribution),
        "role_distribution": Counter(event.get("role") or event.get("operator_role") or "unknown" for event in events).most_common(),
        "permissions": permissions,
    }
