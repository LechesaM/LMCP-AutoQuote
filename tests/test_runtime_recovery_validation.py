from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ready_boot_payload() -> dict[str, object]:
    return {
        "validation_id": "boot-ready",
        "generated_at": "2026-06-24T00:00:00+00:00",
        "boot_readiness_summary": {
            "dry_run_mode_enabled": True,
            "human_supervision_required": True,
        },
    }


def _failure_payload() -> dict[str, object]:
    return {
        "validation_id": "failure-context",
        "generated_at": "2026-06-24T02:00:00+00:00",
        "overall_status": "PASS",
        "governance_containment": {"containment_active": True},
        "service_snapshots": {
            "runtime_remediation": {"status": "watch"},
        },
    }


def _endurance_payload() -> dict[str, object]:
    return {
        "validation_id": "endurance-ready",
        "generated_at": "2026-06-24T00:30:00+00:00",
        "runtime_endurance_summary": {
            "runtime_endurance_score": 98.0,
            "runtime_endurance_status": "PASS",
            "runtime_endurance_grade": "ready",
            "overall_authority": "GO",
            "governance_locks_active": True,
            "dry_run_enabled": True,
            "supervision_mandatory": True,
            "services_healthy": True,
            "observability_endpoints_reachable": True,
            "escalation_readiness_intact": True,
            "continuity_indicators_stable": True,
            "no_governance_degradation_occurs": True,
        },
        "checks": [],
        "sample_history": [],
    }


def _rollout_payload(recovered: bool = True) -> dict[str, object]:
    if recovered:
        return {
            "validation_id": "rollout-ready",
            "generated_at": "2026-06-24T00:45:00+00:00",
            "overall_status": "PASS",
            "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
            "rollout_readiness_summary": {
                "rollout_readiness_score": 96.0,
                "rollout_readiness_status": "PASS",
                "release_authorization_valid": True,
                "tenant_isolation_ready": True,
                "deployment_health_ready": True,
                "production_observability_ready": True,
                "escalation_chain_ready": True,
                "active_supervision_coverage_ready": True,
                "operator_availability_ready": True,
                "unresolved_blockers": [],
            },
            "supervision_readiness_summary": {
                "supervision_command_status": "ok",
                "supervision_score": 96.0,
                "active_supervised_operators": ["supervisor-1"],
                "assigned_rfqs": ["RFQ-1"],
                "pending_approvals": [],
            },
            "operator_onboarding_readiness_summary": {
                "operator_availability_ready": True,
                "approved_for_supervision": True,
                "onboarding_status": "ready",
            },
            "deployment_health_summary": {
                "deployment_health_ready": True,
                "production_observability_ready": True,
                "backup_restore_ready": True,
                "disaster_recovery_ready": True,
                "high_availability_ready": True,
                "audit_retention_ready": True,
            },
            "tenant_isolation_summary": {
                "tenant_isolation_ready": True,
                "tenant_count": 1,
                "workspace_count": 1,
                "tenant_workspace_pair_count": 1,
            },
            "production_observability_summary": {
                "production_observability_ready": True,
                "worker_heartbeat": {"status": "healthy"},
                "telemetry_degradation": [],
            },
            "escalation_chain_summary": {
                "escalation_chain_ready": True,
                "review_board_status": "ok",
                "outstanding_governance_actions": [],
                "unresolved_operational_exceptions": [],
            },
            "rollout_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "rollout-1", "latest_score": 96.0},
            "institutional_rollout_certification_evidence": {
                "certification_status": "CERTIFIED",
                "certification_authority": "GO",
                "rollout_governance_score": 96.0,
                "rollout_ready_for_supervised_deployment": True,
                "governance_override_indicators": {"human_supervision_required": True},
            },
            "warnings": [],
        }
    return {
        "validation_id": "rollout-partial",
        "generated_at": "2026-06-24T00:45:00+00:00",
        "overall_status": "WARN",
        "summary_counts": {"PASS": 5, "WARN": 3, "FAIL": 0},
        "rollout_readiness_summary": {
            "rollout_readiness_score": 76.0,
            "rollout_readiness_status": "WARN",
            "release_authorization_valid": True,
            "tenant_isolation_ready": True,
            "deployment_health_ready": False,
            "production_observability_ready": False,
            "escalation_chain_ready": False,
            "active_supervision_coverage_ready": True,
            "operator_availability_ready": True,
            "unresolved_blockers": ["continuity recovery incomplete", "observability recovery incomplete"],
        },
        "supervision_readiness_summary": {
            "supervision_command_status": "watch",
            "supervision_score": 78.0,
            "active_supervised_operators": ["supervisor-1"],
            "assigned_rfqs": ["RFQ-1"],
            "pending_approvals": ["recovery completion review"],
        },
        "operator_onboarding_readiness_summary": {
            "operator_availability_ready": True,
            "approved_for_supervision": True,
            "onboarding_status": "ready",
        },
        "deployment_health_summary": {
            "deployment_health_ready": False,
            "production_observability_ready": False,
            "backup_restore_ready": True,
            "disaster_recovery_ready": False,
            "high_availability_ready": False,
            "audit_retention_ready": True,
        },
        "tenant_isolation_summary": {
            "tenant_isolation_ready": True,
            "tenant_count": 1,
            "workspace_count": 1,
            "tenant_workspace_pair_count": 1,
        },
        "production_observability_summary": {
            "production_observability_ready": False,
            "worker_heartbeat": {"status": "degraded", "lag_seconds": 21},
            "telemetry_degradation": ["observability recovery incomplete"],
        },
        "escalation_chain_summary": {
            "escalation_chain_ready": False,
            "review_board_status": "watch",
            "outstanding_governance_actions": ["restore observability", "verify failover"],
            "unresolved_operational_exceptions": ["continuity recovery incomplete"],
        },
        "rollout_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "rollout-1", "latest_score": 76.0},
        "institutional_rollout_certification_evidence": {
            "certification_status": "WATCH",
            "certification_authority": "WATCH",
            "rollout_governance_score": 76.0,
            "rollout_ready_for_supervised_deployment": False,
            "governance_override_indicators": {"human_supervision_required": True},
        },
        "warnings": ["recovery incomplete"],
    }


def _release_payload(recovered: bool = True) -> dict[str, object]:
    if recovered:
        return {
            "validation_id": "release-ready",
            "generated_at": "2026-06-24T01:00:00+00:00",
            "status": "PASS",
            "release_governance_status": "ok",
            "release_governance_authority": "GO",
            "release_governance_score": 96.0,
            "release_governance_grade": "ready",
            "release_governance_history_summary": {"score_history": {"trend": "improving"}},
            "release_authority_indicators": {"active_authority": "GO"},
            "deployment_risk_indicators": {"deployment_risk": False},
            "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True},
            "release_readiness_indicators": {"runtime_segmentation_ready": True},
            "release_governance_history": [{"generated_at": "2026-06-24T01:00:00+00:00", "release_governance_score": 96.0}],
        }
    return {
        "validation_id": "release-partial",
        "generated_at": "2026-06-24T01:00:00+00:00",
        "status": "WARN",
        "release_governance_status": "watch",
        "release_governance_authority": "WATCH",
        "release_governance_score": 76.0,
        "release_governance_grade": "watch",
        "release_governance_history_summary": {"score_history": {"trend": "stable"}},
        "release_authority_indicators": {"active_authority": "WATCH"},
        "deployment_risk_indicators": {"deployment_risk": True},
        "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True},
        "release_readiness_indicators": {"runtime_segmentation_ready": True},
        "release_governance_history": [{"generated_at": "2026-06-24T01:00:00+00:00", "release_governance_score": 76.0}],
    }


def test_runtime_recovery_validation_generates_recovered_evidence(tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_runtime_recovery_validation.py"), "run_runtime_recovery_validation_repo")
    failure_file = tmp_path / "runtime" / "staging" / "runtime-failure-validations" / "latest_runtime_failure_validation.json"
    endurance_file = tmp_path / "runtime" / "staging" / "runtime-endurance-validations" / "latest_runtime_endurance_validation.json"
    boot_file = tmp_path / "runtime" / "staging" / "runtime-boot-validations" / "latest_runtime_boot_validation.json"
    rollout_file = tmp_path / "runtime" / "staging" / "production-rollout-validations" / "latest_production_rollout_validation.json"
    release_file = tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json"
    lock_file = tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "runtime-recovery-validations"

    _write_json(failure_file, _failure_payload())
    _write_json(endurance_file, _endurance_payload())
    _write_json(boot_file, _ready_boot_payload())
    _write_json(rollout_file, _rollout_payload(recovered=True))
    _write_json(release_file, _release_payload(recovered=True))
    _write_json(
        lock_file,
        {
            "final_automation_disabled": True,
            "live_portal_submission_disabled": True,
            "production_credentials_disabled": True,
            "dry_run_mode_required": True,
            "submission_execution_allowed": False,
        },
    )

    report = module.build_runtime_recovery_validation_report(
        failure_validation_file=failure_file,
        endurance_validation_file=endurance_file,
        boot_validation_file=boot_file,
        rollout_validation_file=rollout_file,
        release_certification_file=release_file,
        lock_file=lock_file,
        output_root=output_root,
        recovered=True,
    )

    assert report["overall_status"] == "PASS"
    assert report["governance_recovery"]["containment_active"] is True
    assert report["service_snapshots"]["runtime_remediation"]["status"] == "ok"
    assert report["service_snapshots"]["continuity_governance"]["status"] == "ok"
    assert report["service_snapshots"]["incident_governance"]["status"] == "ok"
    assert report["service_snapshots"]["executive_governance_index"]["status"] == "ok"
    assert report["unresolved_blockers"] == []
    assert (output_root / "latest_runtime_recovery_validation.json").exists()
    assert (output_root / "latest_runtime_recovery_validation.md").exists()


def test_runtime_recovery_validation_surfaces_incomplete_recovery(tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_runtime_recovery_validation.py"), "run_runtime_recovery_validation_partial")
    failure_file = tmp_path / "runtime" / "staging" / "runtime-failure-validations" / "latest_runtime_failure_validation.json"
    endurance_file = tmp_path / "runtime" / "staging" / "runtime-endurance-validations" / "latest_runtime_endurance_validation.json"
    boot_file = tmp_path / "runtime" / "staging" / "runtime-boot-validations" / "latest_runtime_boot_validation.json"
    rollout_file = tmp_path / "runtime" / "staging" / "production-rollout-validations" / "latest_production_rollout_validation.json"
    release_file = tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json"
    lock_file = tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "runtime-recovery-validations"

    _write_json(failure_file, _failure_payload())
    _write_json(endurance_file, _endurance_payload())
    _write_json(boot_file, _ready_boot_payload())
    _write_json(rollout_file, _rollout_payload(recovered=False))
    _write_json(release_file, _release_payload(recovered=False))
    _write_json(
        lock_file,
        {
            "final_automation_disabled": True,
            "live_portal_submission_disabled": True,
            "production_credentials_disabled": True,
            "dry_run_mode_required": True,
            "submission_execution_allowed": False,
        },
    )

    report = module.build_runtime_recovery_validation_report(
        failure_validation_file=failure_file,
        endurance_validation_file=endurance_file,
        boot_validation_file=boot_file,
        rollout_validation_file=rollout_file,
        release_certification_file=release_file,
        lock_file=lock_file,
        output_root=output_root,
        recovered=False,
    )

    assert report["overall_status"] == "WARN"
    assert report["service_snapshots"]["runtime_remediation"]["status"] == "watch"
    assert report["service_snapshots"]["continuity_governance"]["status"] == "watch"
    assert report["service_snapshots"]["incident_governance"]["status"] == "watch"
    assert report["service_snapshots"]["executive_governance_index"]["status"] == "watch"
    assert report["unresolved_blockers"]


def test_runtime_recovery_validation_main_writes_latest_files(tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_runtime_recovery_validation.py"), "run_runtime_recovery_validation_main")
    failure_file = tmp_path / "runtime" / "staging" / "runtime-failure-validations" / "latest_runtime_failure_validation.json"
    endurance_file = tmp_path / "runtime" / "staging" / "runtime-endurance-validations" / "latest_runtime_endurance_validation.json"
    boot_file = tmp_path / "runtime" / "staging" / "runtime-boot-validations" / "latest_runtime_boot_validation.json"
    rollout_file = tmp_path / "runtime" / "staging" / "production-rollout-validations" / "latest_production_rollout_validation.json"
    release_file = tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json"
    lock_file = tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "runtime-recovery-validations"

    _write_json(failure_file, _failure_payload())
    _write_json(endurance_file, _endurance_payload())
    _write_json(boot_file, _ready_boot_payload())
    _write_json(rollout_file, _rollout_payload(recovered=True))
    _write_json(release_file, _release_payload(recovered=True))
    _write_json(
        lock_file,
        {
            "final_automation_disabled": True,
            "live_portal_submission_disabled": True,
            "production_credentials_disabled": True,
            "dry_run_mode_required": True,
            "submission_execution_allowed": False,
        },
    )

    exit_code = module.main(["--output-root", str(output_root)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Runtime recovery validation:" in output
    assert (output_root / "latest_runtime_recovery_validation.json").exists()
    assert (output_root / "latest_runtime_recovery_validation.md").exists()
