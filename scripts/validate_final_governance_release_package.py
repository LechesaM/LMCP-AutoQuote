from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "app/services/final_governance_release_readiness_service.py",
    "docs/FINAL_GOVERNANCE_RELEASE_READINESS_REPORT.md",
    "tests/test_final_governance_release_readiness_service.py",
    "tests/test_final_governance_release_readiness_api.py",
    "tests/test_final_governance_release_package_validation.py",
]

REQUIRED_SERVICE_TERMS = [
    "governance_command_centre_readiness",
    "rollout_governance_readiness",
    "supervision_governance_readiness",
    "audit_governance_readiness",
    "incident_governance_readiness",
    "continuity_governance_readiness",
    "executive_governance_index_readiness",
    "production_deployment_governance_readiness",
    "secrets_access_governance_readiness",
    "cicd_governance_readiness",
    "smoke_testing_readiness",
    "runtime_boot_validation_readiness",
    "endurance_validation_readiness",
    "remediation_governance_readiness",
    "failure_injection_validation_readiness",
    "runtime_recovery_validation_readiness",
    "kubernetes_ha_topology_readiness",
    "distributed_orchestration_governance_readiness",
    "ingress_tls_governance_readiness",
    "multi_tenant_isolation_governance_readiness",
    "observability_governance_readiness",
    "autoscaling_governance_readiness",
    "backup_restore_governance_readiness",
    "disaster_recovery_failover_governance_readiness",
    "data_residency_sovereignty_governance_readiness",
    "compliance_regulatory_governance_readiness",
    "unresolved_final_release_blockers",
    "final_governance_history",
    "dry_run_enforced",
    "human_supervision_required",
    "lmcp_allow_final_automation",
    "no_live_external_alerting",
    "no_autonomous_remediation",
    "no_production_data_movement",
]


def test_required_files_exist() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    assert not missing, f"Missing final governance release readiness files: {missing}"


def test_service_contains_required_governance_terms() -> None:
    service = (ROOT / "app/services/final_governance_release_readiness_service.py").read_text(encoding="utf-8")
    missing = [term for term in REQUIRED_SERVICE_TERMS if term not in service]
    assert not missing, f"Missing final governance release readiness terms: {missing}"


def test_no_live_or_autonomous_final_release_paths() -> None:
    service = (ROOT / "app/services/final_governance_release_readiness_service.py").read_text(encoding="utf-8")

    forbidden = [
        "LMCP_ALLOW_FINAL_AUTOMATION = True",
        "LMCP_ALLOW_FINAL_AUTOMATION: True",
        "autonomous_remediation_enabled=True",
        "live_external_alerting_enabled=True",
        "production_data_movement_enabled=True",
    ]

    violations = [term for term in forbidden if term in service]
    assert not violations, f"Unsafe final governance release configuration found: {violations}"


if __name__ == "__main__":
    test_required_files_exist()
    test_service_contains_required_governance_terms()
    test_no_live_or_autonomous_final_release_paths()
    print("Final governance release readiness package validation passed.")
