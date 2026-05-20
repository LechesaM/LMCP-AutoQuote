from __future__ import annotations

from typing import Any, Dict

from ._shared import now_iso
from .access_review_engine import build_access_review_report
from .audit_export_packager import build_audit_export_package
from .audit_snapshot_service import build_audit_snapshot
from .compliance_controls import build_compliance_controls
from .governance_attestations import build_governance_attestation
from .legal_hold_manager import build_legal_hold_summary
from .retention_enforcement import build_retention_enforcement_report


def build_regulatory_export_bundle(limit: int = 100) -> Dict[str, Any]:
    audit_pack = build_audit_export_package(limit=limit)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "bundle": {
            "audit_pack": audit_pack,
            "controls": build_compliance_controls(limit=limit),
            "access_review": build_access_review_report(),
            "attestation": build_governance_attestation(),
            "retention": build_retention_enforcement_report(),
            "legal_holds": build_legal_hold_summary(),
            "audit_snapshot": build_audit_snapshot(limit=limit),
        },
        "manifest": {
            "json": True,
            "csv": True,
            "zip_manifest": audit_pack.get("zip_manifest", {}),
            "export_safe": True,
        },
        "export_safe": True,
        "no_secrets": True,
        "manual_governance_only": True,
    }

