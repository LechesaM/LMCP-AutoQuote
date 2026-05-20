from __future__ import annotations

from typing import Any, Dict

from ._shared import now_iso
from .access_review_engine import build_access_review_report
from .audit_chain_validator import build_audit_chain_validation
from .audit_integrity_monitor import build_audit_integrity_monitor
from .audit_snapshot_service import build_audit_snapshot
from .compliance_controls import build_compliance_controls
from .governance_attestations import build_governance_attestation
from .governance_risk_register import build_governance_risk_register
from .legal_hold_manager import build_legal_hold_summary
from .policy_acknowledgements import build_policy_acknowledgement_report
from .policy_registry import build_policy_registry
from .policy_versioning import build_policy_version_history
from .regulatory_export_service import build_regulatory_export_bundle
from .retention_enforcement import build_retention_enforcement_report


def build_compliance_report(limit: int = 100) -> Dict[str, Any]:
    policies = build_policy_registry()
    version_history = build_policy_version_history()
    controls = build_compliance_controls(limit=limit)
    access_review = build_access_review_report()
    attestation = build_governance_attestation()
    audit_validation = build_audit_chain_validation(limit=limit)
    audit_monitor = build_audit_integrity_monitor(limit=limit)
    audit_snapshot = build_audit_snapshot(limit=limit)
    retention = build_retention_enforcement_report()
    legal_holds = build_legal_hold_summary()
    risk_register = build_governance_risk_register()
    acknowledgements = build_policy_acknowledgement_report()
    regulatory_export = build_regulatory_export_bundle(limit=limit)
    return {
        "status": controls.get("status", "ok"),
        "generated_at": now_iso(),
        "data_source": "runtime",
        "policies": policies,
        "policy_versions": version_history,
        "controls": controls,
        "access_review": access_review,
        "attestations": attestation,
        "audit_validation": audit_validation,
        "audit_monitor": audit_monitor,
        "audit_snapshot": audit_snapshot,
        "retention": retention,
        "legal_holds": legal_holds,
        "risk_register": risk_register,
        "policy_acknowledgements": acknowledgements,
        "regulatory_export": regulatory_export,
        "export_ready": True,
        "manualGovernanceOnly": True,
        "manual_governance_only": True,
    }
