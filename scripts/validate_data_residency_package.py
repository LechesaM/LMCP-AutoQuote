from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "app/services/data_residency_governance_service.py",
    "docs/DATA_RESIDENCY_SOVEREIGNTY_GOVERNANCE_REPORT.md",
    "tests/test_data_residency_governance_service.py",
    "tests/test_data_residency_governance_api.py",
    "tests/test_data_residency_package_validation.py",
    "k8s/base/data-residency/residency-boundary-placeholder.yaml",
    "k8s/base/data-residency/sovereignty-policy-placeholder.yaml",
    "k8s/base/data-residency/restricted-region-placeholder.yaml",
    "k8s/base/data-residency/evidence-residency-placeholder.yaml",
    "k8s/base/data-residency/backup-residency-placeholder.yaml",
]

REQUIRED_SERVICE_TERMS = [
    "tenant_data_residency_ready",
    "jurisdiction_boundary_ready",
    "cross_region_movement_restricted",
    "backup_residency_aligned",
    "audit_log_residency_aligned",
    "evidence_storage_residency_aligned",
    "sovereignty_escalation_ready",
    "restricted_region_blockers_clear",
    "dry_run_enforced",
    "human_supervision_required",
    "live_cloud_credentials_present",
    "production_data_movement_enabled",
    "autonomous_remediation_enabled",
    "governance_history",
]


def test_required_files_exist() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    assert not missing, f"Missing data residency governance files: {missing}"


def test_service_contains_required_governance_terms() -> None:
    service = (ROOT / "app/services/data_residency_governance_service.py").read_text()
    missing = [term for term in REQUIRED_SERVICE_TERMS if term not in service]
    assert not missing, f"Missing governance terms: {missing}"


def test_no_live_or_autonomous_data_movement() -> None:
    service = (ROOT / "app/services/data_residency_governance_service.py").read_text()

    forbidden = [
        "production_data_movement_enabled=True",
        "autonomous_remediation_enabled=True",
        "live_cloud_credentials_present=True",
    ]

    violations = [term for term in forbidden if term in service]
    assert not violations, f"Unsafe data residency configuration found: {violations}"


if __name__ == "__main__":
    test_required_files_exist()
    test_service_contains_required_governance_terms()
    test_no_live_or_autonomous_data_movement()
    print("Data residency sovereignty governance package validation passed.")
