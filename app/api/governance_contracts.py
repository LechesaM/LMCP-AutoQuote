from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.governance import (
    build_access_review_report,
    build_audit_chain_validation,
    build_audit_integrity_monitor,
    build_audit_snapshot,
)
from app.governance.compliance_reporting import build_compliance_report
from app.governance.governance_attestations import build_governance_attestation
from app.governance.governance_risk_register import build_governance_risk_register
from app.governance.legal_hold_manager import build_legal_hold_summary
from app.governance.policy_acknowledgements import build_policy_acknowledgement_report
from app.governance.policy_registry import build_policy_registry
from app.governance.policy_versioning import build_policy_version_history
from app.governance.regulatory_export_service import build_regulatory_export_bundle
from app.governance.retention_enforcement import build_retention_enforcement_report
from app.governance.compliance_controls import build_compliance_controls


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wrap(payload: Dict[str, Any], *, default_status: str = "ok") -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return {
        "status": payload.get("status", default_status),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "runtime"),
        **payload,
    }


def build_policies_response() -> Dict[str, Any]:
    return _wrap(build_policy_registry())


def build_compliance_controls_response() -> Dict[str, Any]:
    return _wrap(build_compliance_controls())


def build_access_review_response() -> Dict[str, Any]:
    return _wrap(build_access_review_report())


def build_attestations_response() -> Dict[str, Any]:
    return _wrap(build_governance_attestation())


def build_audit_integrity_response() -> Dict[str, Any]:
    return _wrap(build_audit_integrity_monitor())


def build_retention_status_response() -> Dict[str, Any]:
    return _wrap(build_retention_enforcement_report())


def build_legal_holds_response() -> Dict[str, Any]:
    return _wrap(build_legal_hold_summary())


def build_risk_register_response() -> Dict[str, Any]:
    return _wrap(build_governance_risk_register())


def build_compliance_report_response() -> Dict[str, Any]:
    return _wrap(build_compliance_report())


def build_regulatory_export_response() -> Dict[str, Any]:
    return _wrap(build_regulatory_export_bundle())


def build_legal_hold_register_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _wrap(payload)


def build_legal_hold_release_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _wrap(payload)


def build_attestation_generate_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _wrap(payload)
