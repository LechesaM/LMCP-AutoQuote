from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _DummyExecutiveIndexService:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def latest_executive_governance_index(self):
        return self._payload


def _ready_release_bundle() -> dict[str, object]:
    return {
        "overall_status": "PASS",
        "overall_authority": "GO",
        "overall_score": 96.0,
        "release_readiness": {"runtime_segmentation_ready": True},
        "rollout_readiness": {"rollout_readiness_score": 96.0, "rollout_readiness_status": "PASS"},
        "continuity_readiness": {"continuity_governance_status": "ok", "continuity_governance_score": 94.0, "continuity_governance_history_summary": {"score_history": {"trend": "stable"}}},
        "incident_readiness": {"incident_governance_status": "ok", "incident_governance_score": 93.0},
        "supervision_readiness": {"supervision_command_status": "ok", "supervision_command_score": 95.0},
        "audit_readiness": {"operations_audit_status": "ok", "operations_audit_score": 94.0},
        "executive_readiness": {"executive_governance_index_status": "ok", "executive_governance_index_score": 95.0},
    }


def _ready_executive_index() -> dict[str, object]:
    return {
        "analysis_id": "runtime-endurance:ready",
        "generated_at": "2026-06-24T00:00:00+00:00",
        "activation_readiness": {"activation_governance_status": "ok", "activation_governance_authority": "GO", "activation_governance_score": 95.0, "activation_governance_history_summary": {"score_history": {"trend": "stable"}}},
        "supervision_readiness": {"supervision_command_status": "ok", "supervision_command_authority": "GO", "supervision_command_score": 95.0, "supervision_command_history_summary": {"score_history": {"trend": "stable"}}, "latest_supervision_command": {"active_supervised_operators": ["ops-1"]}},
        "audit_completeness": {"operations_audit_status": "ok", "operations_audit_authority": "GO", "operations_audit_score": 95.0, "operations_audit_history_summary": {"score_history": {"trend": "stable"}}},
        "incident_severity": {"incident_governance_status": "ok", "incident_governance_authority": "GO", "incident_governance_score": 95.0, "incident_governance_history_summary": {"score_history": {"trend": "stable"}}, "governance_breach_indicators": []},
        "continuity_readiness": {"continuity_governance_status": "ok", "continuity_governance_authority": "GO", "continuity_governance_score": 95.0, "continuity_governance_history_summary": {"score_history": {"trend": "stable"}}, "continuity_freeze_indicators": []},
        "release_authority": {"release_governance_status": "ok", "release_governance_authority": "GO", "release_governance_score": 95.0, "release_governance_history_summary": {"score_history": {"trend": "stable"}}},
        "operational_intelligence": {"operational_intelligence_status": "ok", "operational_intelligence_authority": "GO", "operational_intelligence_score": 95.0, "operational_intelligence_history_summary": {"score_history": {"trend": "stable"}}},
        "executive_command": {"executive_governance_status": "ok", "executive_governance_index_status": "ok", "executive_governance_index_authority": "GO", "executive_governance_index_score": 95.0, "executive_governance_index_history_summary": {"score_history": {"trend": "stable"}}},
        "institutional_rollout_readiness": {"rollout_readiness_status": "PASS", "rollout_readiness_score": 96.0},
        "governance_degradation_indicators": {"activation_degradation": False, "supervision_degradation": False, "audit_degradation": False, "incident_degradation": False, "continuity_degradation": False, "release_degradation": False, "intelligence_degradation": False, "executive_degradation": False},
        "executive_escalation_indicators": {"escalation_required": False, "high_risk": False, "governance_degradation": False, "supervision_saturation": False, "audit_gap": False, "incident_escalation": False, "continuity_gap": False, "release_blocker": False, "intelligence_drift": False, "rollout_freeze": False, "human_supervision_required": True},
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ready_boot_payload() -> dict[str, object]:
    return {
        "overall_status": "PASS",
        "overall_score": 95.0,
        "boot_readiness_summary": {
            "production_runtime_boot_ready": True,
            "backend_started": True,
            "frontend_started": True,
            "postgres_started": True,
            "redis_started": True,
            "worker_started": True,
            "prometheus_started": True,
            "grafana_started": True,
            "health_endpoints_respond": True,
            "dry_run_mode_enabled": True,
            "final_automation_disabled": True,
            "human_supervision_required": True,
            "submission_locks_enforced": True,
        },
        "compose_validation": {"compose_parsed": True, "compose_message": "ok"},
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "human_supervision_required": True,
            "dry_run_protections_active": True,
        },
    }


def _ready_smoke_payload() -> dict[str, object]:
    return {
        "overall_status": "PASS",
        "overall_score": 33.33,
        "summary_counts": {"PASS": 28, "WARN": 0, "FAIL": 0},
        "compose_validation": {
            "compose_parsed": True,
            "compose_message": "ok",
            "service_expectations": {
                "backend": True,
                "frontend": True,
                "postgres": True,
                "redis": True,
                "worker": True,
                "prometheus": True,
                "grafana": True,
            },
        },
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "human_supervision_required": True,
            "dry_run_protections_active": True,
        },
    }


def _ready_deployment_payload() -> dict[str, object]:
    return {
        "overall_status": "PASS",
        "readiness_summary": {"production_readiness_score": 100.0},
        "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
        "warnings": [],
    }


def _ready_rollout_payload() -> dict[str, object]:
    return {
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
            "active_supervision_coverage_ready": True,
            "supervision_score": 96.0,
            "operator_name": "governance",
            "operator_role": "supervisor",
            "active_sessions": 1,
            "assigned_rfqs": ["RFQ-1"],
            "pending_approvals": [],
        },
        "operator_onboarding_readiness_summary": {
            "operator_availability_ready": True,
            "operator_name": "governance",
            "operator_role": "supervisor",
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
            "governance_override_indicators": {"deployment_blockers": False, "release_authorization_override": False, "human_supervision_required": True},
        },
        "warnings": [],
    }


def _ready_release_bundle() -> dict[str, object]:
    return {
        "overall_status": "PASS",
        "overall_authority": "GO",
        "overall_score": 96.0,
        "summary_counts": {"PASS": 45, "WARN": 0, "FAIL": 0},
        "release_readiness": {"runtime_segmentation_ready": True},
        "rollout_readiness": {"rollout_readiness_score": 96.0, "rollout_readiness_status": "PASS"},
        "continuity_readiness": {
            "continuity_governance_status": "ok",
            "continuity_governance_authority": "GO",
            "continuity_governance_score": 95.0,
            "continuity_governance_history_summary": {"score_history": {"trend": "stable"}},
            "continuity_freeze_indicators": [],
        },
        "incident_readiness": {
            "incident_governance_status": "ok",
            "incident_governance_authority": "GO",
            "incident_governance_score": 95.0,
            "incident_governance_history_summary": {"score_history": {"trend": "stable"}},
        },
        "supervision_readiness": {
            "supervision_command_status": "ok",
            "supervision_command_authority": "GO",
            "supervision_command_score": 95.0,
            "supervision_command_history_summary": {"score_history": {"trend": "stable"}},
        },
        "audit_readiness": {
            "operations_audit_status": "ok",
            "operations_audit_authority": "GO",
            "operations_audit_score": 95.0,
            "operations_audit_history_summary": {"score_history": {"trend": "stable"}},
        },
        "executive_readiness": {"executive_governance_index_status": "ok", "executive_governance_index_score": 95.0},
        "operational_release_indicators": {
            "dry_run_verified": True,
            "environment_safe": True,
            "submission_lock_verified": True,
        },
        "release_authority_certification": {"active_authority": "GO"},
        "governance_certification_summary": {"certification_status": "CERTIFIED", "certification_score": 96.0},
        "warnings": [],
    }


def _ready_release_certification() -> dict[str, object]:
    return {
        "status": "PASS",
        "release_governance_status": "ok",
        "release_governance_authority": "GO",
        "release_governance_score": 96.0,
        "release_governance_grade": "ready",
        "release_governance_history_summary": {"score_history": {"trend": "stable"}},
        "release_authority_indicators": {"active_authority": "GO"},
        "deployment_risk_indicators": {"deployment_risk": False},
        "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True},
        "release_readiness_indicators": {"runtime_segmentation_ready": True},
        "release_governance_history": [{"generated_at": "2026-06-24T00:00:00+00:00", "release_governance_score": 95.0}],
    }


def _warn_release_bundle() -> dict[str, object]:
    payload = _ready_release_bundle()
    payload["overall_status"] = "FAIL"
    payload["overall_authority"] = "NO_GO"
    payload["overall_score"] = 65.16
    payload["continuity_readiness"] = {
        "continuity_governance_status": "blocked",
        "continuity_governance_authority": "NO_GO",
        "continuity_governance_score": 14.4,
        "continuity_governance_history_summary": {"score_history": {"trend": "stable"}},
        "continuity_freeze_indicators": [{"freeze_active": True}],
    }
    payload["incident_readiness"] = {
        "incident_governance_status": "watch",
        "incident_governance_authority": "WATCH",
        "incident_governance_score": 75.0,
        "incident_governance_history_summary": {"score_history": {"trend": "stable"}},
    }
    payload["supervision_readiness"] = {
        "supervision_command_status": "blocked",
        "supervision_command_authority": "NO_GO",
        "supervision_command_score": 18.0,
        "supervision_command_history_summary": {"score_history": {"trend": "stable"}},
    }
    payload["audit_readiness"] = {
        "operations_audit_status": "watch",
        "operations_audit_authority": "WATCH",
        "operations_audit_score": 75.0,
        "operations_audit_history_summary": {"score_history": {"trend": "stable"}},
    }
    payload["executive_readiness"] = {"executive_governance_index_status": "blocked", "executive_governance_index_score": 65.16}
    payload["operational_release_indicators"] = {"dry_run_verified": True, "environment_safe": False, "submission_lock_verified": True}
    payload["governance_certification_summary"] = {"certification_status": "NO_GO", "certification_score": 65.16}
    return payload


def _warn_release_certification() -> dict[str, object]:
    payload = _ready_release_certification()
    payload["status"] = "watch"
    payload["release_governance_status"] = "watch"
    payload["release_governance_authority"] = "WATCH"
    payload["release_governance_score"] = 72.0
    payload["release_governance_grade"] = "watch"
    payload["deployment_risk_indicators"] = {"deployment_risk": True}
    payload["operational_release_indicators"] = {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": False}
    payload["release_readiness_indicators"] = {"runtime_segmentation_ready": False}
    return payload


def test_runtime_endurance_validation_generates_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_runtime_endurance_validation.py"), "run_runtime_endurance_validation_repo")

    boot_file = tmp_path / "runtime" / "staging" / "runtime-boot-validations" / "latest_runtime_boot_validation.json"
    smoke_file = tmp_path / "runtime" / "staging" / "production-smoke-tests" / "latest_production_smoke_test.json"
    deployment_file = tmp_path / "runtime" / "staging" / "production-deployment-validations" / "latest_production_deployment_validation.json"
    rollout_file = tmp_path / "runtime" / "staging" / "production-rollout-validations" / "latest_production_rollout_validation.json"
    bundle_file = tmp_path / "runtime" / "staging" / "release-governance-bundles" / "latest_release_governance_bundle.json"
    release_file = tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json"
    lock_file = tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "runtime-endurance-validations"

    _write_json(boot_file, _ready_boot_payload())
    _write_json(smoke_file, _ready_smoke_payload())
    _write_json(deployment_file, _ready_deployment_payload())
    _write_json(rollout_file, _ready_rollout_payload())
    _write_json(bundle_file, _ready_release_bundle())
    _write_json(release_file, _ready_release_certification())
    _write_json(
        lock_file,
        {
            "final_automation_disabled": True,
            "live_portal_submission_disabled": True,
            "production_credentials_disabled": True,
            "dry_run_mode_required": True,
            "submission_execution_allowed": False,
            "human_supervision_required": True,
        },
    )

    monkeypatch.setattr(module, "BOOT_VALIDATION_FILE", boot_file)
    monkeypatch.setattr(module, "SMOKE_TEST_FILE", smoke_file)
    monkeypatch.setattr(module, "DEPLOYMENT_VALIDATION_FILE", deployment_file)
    monkeypatch.setattr(module, "ROLLOUT_VALIDATION_FILE", rollout_file)
    monkeypatch.setattr(module, "RELEASE_GOVERNANCE_BUNDLE_FILE", bundle_file)
    monkeypatch.setattr(module, "RELEASE_CERTIFICATION_FILE", release_file)
    monkeypatch.setattr(module, "LOCK_FILE", lock_file)
    monkeypatch.setattr(module, "ENDURANCE_VALIDATION_ROOT", output_root)
    monkeypatch.setattr(module, "LATEST_ENDURANCE_VALIDATION_JSON", output_root / "latest_runtime_endurance_validation.json")
    monkeypatch.setattr(module, "LATEST_ENDURANCE_VALIDATION_MD", output_root / "latest_runtime_endurance_validation.md")
    monkeypatch.setattr(module, "_governance_sources", lambda: {"executive_index": _DummyExecutiveIndexService(_ready_executive_index())})
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    payload = module.build_runtime_endurance_validation_report(
        output_root=output_root,
        sample_count=3,
        sample_interval_seconds=0.0,
    )
    assert payload["runtime_endurance_summary"]["runtime_endurance_status"] == "PASS"
    assert payload["runtime_endurance_summary"]["governance_locks_active"] is True
    assert payload["runtime_endurance_summary"]["dry_run_enabled"] is True
    assert payload["runtime_endurance_summary"]["supervision_mandatory"] is True
    assert payload["runtime_endurance_summary"]["services_healthy"] is True
    assert payload["runtime_endurance_summary"]["observability_endpoints_reachable"] is True
    assert payload["runtime_endurance_summary"]["escalation_readiness_intact"] is True
    assert payload["runtime_endurance_summary"]["continuity_indicators_stable"] is True
    assert payload["runtime_endurance_summary"]["no_governance_degradation_occurs"] is True
    assert len(payload["sample_history"]) == 3
    assert payload["history_summary"]["score_history"]["trend"] == "stable"

    exit_code = module.main(["--output-root", str(output_root), "--samples", "3", "--interval-seconds", "0"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Runtime endurance validation:" in output
    assert (output_root / "latest_runtime_endurance_validation.json").exists()
    assert (output_root / "latest_runtime_endurance_validation.md").exists()


def test_runtime_endurance_validation_reports_warn_for_degraded_staging_state(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_runtime_endurance_validation.py"), "run_runtime_endurance_validation_warn")

    boot_file = tmp_path / "runtime" / "staging" / "runtime-boot-validations" / "latest_runtime_boot_validation.json"
    smoke_file = tmp_path / "runtime" / "staging" / "production-smoke-tests" / "latest_production_smoke_test.json"
    deployment_file = tmp_path / "runtime" / "staging" / "production-deployment-validations" / "latest_production_deployment_validation.json"
    rollout_file = tmp_path / "runtime" / "staging" / "production-rollout-validations" / "latest_production_rollout_validation.json"
    bundle_file = tmp_path / "runtime" / "staging" / "release-governance-bundles" / "latest_release_governance_bundle.json"
    release_file = tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json"
    lock_file = tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "runtime-endurance-validations"

    boot_payload = _ready_boot_payload()
    boot_payload["overall_status"] = "WARN"
    boot_payload["boot_readiness_summary"]["production_runtime_boot_ready"] = False
    boot_payload["boot_readiness_summary"]["health_endpoints_respond"] = False
    _write_json(boot_file, boot_payload)
    smoke_payload = _ready_smoke_payload()
    smoke_payload["overall_status"] = "PASS"
    smoke_payload["summary_counts"] = {"PASS": 20, "WARN": 0, "FAIL": 0}
    _write_json(smoke_file, smoke_payload)
    _write_json(deployment_file, {"overall_status": "WARN", "readiness_summary": {"production_readiness_score": 72.0}, "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0}, "warnings": ["deployment watch"]})
    rollout_payload = _ready_rollout_payload()
    rollout_payload["overall_status"] = "WARN"
    rollout_payload["rollout_readiness_summary"]["rollout_readiness_status"] = "WATCH"
    rollout_payload["rollout_readiness_summary"]["release_authorization_valid"] = False
    rollout_payload["institutional_rollout_certification_evidence"]["certification_status"] = "WATCH"
    rollout_payload["institutional_rollout_certification_evidence"]["certification_authority"] = "WATCH"
    _write_json(rollout_file, rollout_payload)
    _write_json(bundle_file, _warn_release_bundle())
    _write_json(release_file, _warn_release_certification())
    _write_json(
        lock_file,
        {
            "final_automation_disabled": True,
            "live_portal_submission_disabled": True,
            "production_credentials_disabled": True,
            "dry_run_mode_required": True,
            "submission_execution_allowed": False,
            "human_supervision_required": True,
        },
    )

    monkeypatch.setattr(module, "BOOT_VALIDATION_FILE", boot_file)
    monkeypatch.setattr(module, "SMOKE_TEST_FILE", smoke_file)
    monkeypatch.setattr(module, "DEPLOYMENT_VALIDATION_FILE", deployment_file)
    monkeypatch.setattr(module, "ROLLOUT_VALIDATION_FILE", rollout_file)
    monkeypatch.setattr(module, "RELEASE_GOVERNANCE_BUNDLE_FILE", bundle_file)
    monkeypatch.setattr(module, "RELEASE_CERTIFICATION_FILE", release_file)
    monkeypatch.setattr(module, "LOCK_FILE", lock_file)
    monkeypatch.setattr(module, "ENDURANCE_VALIDATION_ROOT", output_root)
    monkeypatch.setattr(module, "LATEST_ENDURANCE_VALIDATION_JSON", output_root / "latest_runtime_endurance_validation.json")
    monkeypatch.setattr(module, "LATEST_ENDURANCE_VALIDATION_MD", output_root / "latest_runtime_endurance_validation.md")
    monkeypatch.setattr(module, "_governance_sources", lambda: {"executive_index": _DummyExecutiveIndexService(_ready_executive_index())})
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    payload = module.build_runtime_endurance_validation_report(
        output_root=output_root,
        sample_count=2,
        sample_interval_seconds=0.0,
    )
    assert payload["runtime_endurance_summary"]["runtime_endurance_status"] == "WARN"
    assert payload["runtime_endurance_summary"]["governance_locks_active"] is True
    assert payload["runtime_endurance_summary"]["dry_run_enabled"] is True
    assert payload["runtime_endurance_summary"]["supervision_mandatory"] is True
    assert payload["runtime_endurance_summary"]["observability_endpoints_reachable"] is False
    assert payload["runtime_endurance_summary"]["services_healthy"] is False
    assert any(check["level"] == "WARN" for check in payload["checks"])
