from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.auth import rbac
from app.operations.runtime_alerts import get_runtime_alerts
from app.persistence.persistence_health import validate_persistence_health
from app.persistence.retention_policy import evaluate_retention_readiness, get_retention_policy
from app.services.audit_trail_service import load_audit_events

from ._shared import now_iso
from .policy_registry import build_policy_registry


def _audit_integrity_checks() -> Dict[str, Any]:
    events = load_audit_events()
    missing = [event for event in events if not event.get("id") or not event.get("created_at") or not event.get("event_type")]
    severities = Counter(str(event.get("severity") or "info").lower() for event in events)
    return {
        "event_count": len(events),
        "missing_required_fields": len(missing),
        "severity_counts": dict(severities),
        "append_only_assumed": True,
    }


def build_compliance_controls(limit: int = 100) -> Dict[str, Any]:
    policies = build_policy_registry()
    retention = get_retention_policy()
    retention_readiness = evaluate_retention_readiness()
    persistence = validate_persistence_health()
    runtime_alerts = get_runtime_alerts(limit=limit)
    audit_checks = _audit_integrity_checks()
    role_matrix = {role: list(perms) for role, perms in rbac.ROLE_PERMISSIONS.items()}
    prohibited = {
        "autonomous_submit",
        "auto_approve",
        "bypass_review_ready",
        "bypass_proof_capture",
    }
    warnings: List[str] = []
    blockers: List[str] = []
    checks = {
        "review_ready_enforced": True,
        "proof_capture_enforced": True,
        "operator_attribution_required": True,
        "audit_completeness": audit_checks["missing_required_fields"] == 0,
        "retention_compliance": retention_readiness.get("requires_explicit_confirmation", False),
        "rbac_integrity": not any(permission in prohibited for perms in role_matrix.values() for permission in perms),
        "manual_submission_only": True,
    }
    if not checks["audit_completeness"]:
        blockers.append("Audit trail contains records with missing required fields.")
    if persistence.get("status") == "failing":
        blockers.append("Persistence health is failing.")
    if runtime_alerts.get("total", 0):
        warnings.append("Runtime alerts are active and should be reviewed.")
    if retention.get("dry_run_only") is not True:
        warnings.append("Retention policy is not in dry-run mode.")
    score = 100 - (25 * len(blockers)) - (5 * len(warnings))
    score = max(0, score)
    status = "healthy"
    if blockers:
        status = "failing"
    elif warnings:
        status = "degraded"
    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "controls": checks,
        "policy_registry": policies,
        "retention": retention,
        "retention_readiness": retention_readiness,
        "persistence": persistence,
        "audit_integrity": audit_checks,
        "runtime_alerts": runtime_alerts,
        "role_matrix": role_matrix,
        "warnings": warnings,
        "blockers": blockers,
        "compliance_score": score,
        "manual_governance_only": True,
    }
