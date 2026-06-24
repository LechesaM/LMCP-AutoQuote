from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "app/services/compliance_regulatory_governance_service.py",
    "docs/COMPLIANCE_REGULATORY_GOVERNANCE_REPORT.md",
    "tests/test_compliance_regulatory_governance_service.py",
    "tests/test_compliance_regulatory_governance_api.py",
    "tests/test_compliance_regulatory_package_validation.py",
    "k8s/base/compliance-regulatory/regulatory-framework-placeholder.yaml",
    "k8s/base/compliance-regulatory/procurement-compliance-placeholder.yaml",
    "k8s/base/compliance-regulatory/audit-retention-placeholder.yaml",
    "k8s/base/compliance-regulatory/evidence-completeness-placeholder.yaml",
    "k8s/base/compliance-regulatory/policy-exception-escalation-placeholder.yaml",
    "k8s/base/compliance-regulatory/review-supervision-placeholder.yaml",
    "k8s/base/compliance-regulatory/regulatory-blocker-visibility-placeholder.yaml",
]

REQUIRED_SERVICE_TERMS = [
    "regulatory_framework_readiness",
    "procurement_compliance_readiness",
    "audit_retention_readiness",
    "governance_evidence_completeness",
    "policy_exception_escalation_readiness",
    "compliance_review_supervision",
    "regulatory_blocker_visibility",
    "dry_run_enforced",
    "human_supervision_required",
    "autonomous_approvals_enabled",
    "production_authority_enabled",
    "live_regulator_integrations_present",
    "governance_history",
    "recovery_state_history",
    "recovery_rationale",
    "blocker_sources",
]


def test_required_files_exist() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    assert not missing, f"Missing compliance regulatory governance files: {missing}"


def test_service_contains_required_governance_terms() -> None:
    service = (ROOT / "app/services/compliance_regulatory_governance_service.py").read_text(encoding="utf-8")
    missing = [term for term in REQUIRED_SERVICE_TERMS if term not in service]
    assert not missing, f"Missing compliance regulatory governance terms: {missing}"


def test_no_live_or_autonomous_regulatory_controls() -> None:
    service = (ROOT / "app/services/compliance_regulatory_governance_service.py").read_text(encoding="utf-8")

    forbidden = [
        "autonomous_approvals_enabled=True",
        "production_authority_enabled=True",
        "live_regulator_integrations_present=True",
    ]

    violations = [term for term in forbidden if term in service]
    assert not violations, f"Unsafe compliance regulatory configuration found: {violations}"


if __name__ == "__main__":
    test_required_files_exist()
    test_service_contains_required_governance_terms()
    test_no_live_or_autonomous_regulatory_controls()
    print("Compliance regulatory governance package validation passed.")
