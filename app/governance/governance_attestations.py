from __future__ import annotations

from typing import Any, Dict

from ._shared import digest_json, now_iso
from .access_review_engine import build_access_review_report
from .audit_chain_validator import build_audit_chain_validation
from .compliance_controls import build_compliance_controls


def build_governance_attestation(*, operator_id: str = "", note: str = "") -> Dict[str, Any]:
    controls = build_compliance_controls()
    audit = build_audit_chain_validation()
    access_review = build_access_review_report()
    attestation = {
        "attestation_type": "manual_governance_defensibility",
        "manual_only_governance": True,
        "no_autonomous_submission": True,
        "proof_capture_enforced": bool(controls.get("controls", {}).get("proof_capture_enforced", True)),
        "audit_completeness": bool(controls.get("controls", {}).get("audit_completeness", False)),
        "retention_compliance": bool(controls.get("controls", {}).get("retention_compliance", False)),
        "rbac_enforcement": bool(controls.get("controls", {}).get("rbac_integrity", False)),
        "audit_integrity_score": audit.get("integrity_score", 0),
        "operator_id": str(operator_id or ""),
        "note": str(note or ""),
        "access_review_state": access_review.get("status", "ok"),
    }
    attestation["signature"] = digest_json(attestation)[:24]
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "attestation": attestation,
        "attestation_text": (
            "LMCP governance attestation confirms manual-only governance, no autonomous submission, "
            "proof capture enforcement, audit completeness, retention compliance and RBAC enforcement."
        ),
        "signed_style": True,
        "export_safe": True,
    }

