from __future__ import annotations

from typing import Any, Dict, List

from ._shared import now_iso


POLICY_BLUEPRINTS = (
    {
        "policy_key": "review_governance",
        "title": "Review governance",
        "category": "workflow",
        "description": "Manual review, escalation and approval remain governed by operators.",
        "controls": ["review_ready", "manual_review", "escalation_chain"],
    },
    {
        "policy_key": "proof_capture",
        "title": "Proof capture",
        "category": "workflow",
        "description": "Proof capture remains mandatory before manual release or submission.",
        "controls": ["proof_required", "evidence_chain", "audit_reference"],
    },
    {
        "policy_key": "submission_governance",
        "title": "Submission governance",
        "category": "workflow",
        "description": "Submission remains manual-only and requires explicit human approval.",
        "controls": ["manual_submission_only", "approval_signoff", "supervised_live_only"],
    },
    {
        "policy_key": "retention_policy",
        "title": "Retention policy",
        "category": "records",
        "description": "Retention windows are enforced through dry-run first policy checks.",
        "controls": ["dry_run_first", "retention_windows", "legal_hold_override"],
    },
    {
        "policy_key": "operator_accountability",
        "title": "Operator accountability",
        "category": "access",
        "description": "All operator actions require attribution and auditable operator identity.",
        "controls": ["operator_id", "activity_feed", "audit_chain"],
    },
    {
        "policy_key": "audit_requirements",
        "title": "Audit requirements",
        "category": "audit",
        "description": "Audit trails remain append-only and defensible for export and review.",
        "controls": ["append_only", "integrity_check", "export_packaging"],
    },
)


def build_policy_catalog() -> List[Dict[str, Any]]:
    generated_at = now_iso()
    catalog: List[Dict[str, Any]] = []
    for blueprint in POLICY_BLUEPRINTS:
        catalog.append(
            {
                **blueprint,
                "version": "1.0.0",
                "status": "active",
                "effective_at": generated_at,
                "superseded_by": None,
                "approval_metadata": {
                    "approved_by_role": "governance",
                    "approved_by": "LMCP Governance",
                    "approved_at": generated_at,
                },
                "manual_enforcement_only": True,
                "effective_date": generated_at.split("T", 1)[0],
            }
        )
    return catalog


def get_policy_catalog() -> Dict[str, Any]:
    policies = build_policy_catalog()
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "policy_count": len(policies),
        "categories": sorted({item["category"] for item in policies}),
        "policies": policies,
    }


def get_policy_by_key(policy_key: str) -> Dict[str, Any]:
    normalized = str(policy_key or "").strip().lower()
    for policy in build_policy_catalog():
        if policy["policy_key"] == normalized:
            return policy
    return {}


def build_policy_registry() -> Dict[str, Any]:
    catalog = build_policy_catalog()
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime",
        "policies": catalog,
        "summary": {
            "policy_count": len(catalog),
            "active_count": len([item for item in catalog if item["status"] == "active"]),
            "categories": sorted({item["category"] for item in catalog}),
            "manualEnforcementOnly": True,
            "manual_enforcement_only": True,
        },
    }
