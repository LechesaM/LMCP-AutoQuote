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


class _DummyService:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def latest_release_governance(self):
        return self._payload

    def latest_supervision_command(self):
        return self._payload

    def latest_continuity_governance(self):
        return self._payload

    def latest_operations_audit(self):
        return self._payload

    def latest_incident_governance(self):
        return self._payload

    def latest_executive_governance_index(self):
        return self._payload


def _release_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "release_governance_status": "ok",
        "release_governance_authority": "GO",
        "release_governance_score": 96.0,
        "release_governance_grade": "ready",
        "release_authority_indicators": {"active_authority": "GO"},
        "deployment_risk_indicators": {"deployment_risk": False},
        "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True},
        "release_readiness_indicators": {"runtime_segmentation_ready": True},
        "release_governance_history_summary": {"analysis_count": 1},
        "unresolved_deployment_blockers": [],
        "release_authority_certification": {"authority": "GO"},
        "deployment_readiness_certification": {"status": "PASS"},
        "operational_readiness_certification": {"overall_validation_passed": True},
        "governance_certification_summary": {"certification_status": "CERTIFIED", "certification_score": 97.0},
        "release_governance_history": [{"generated_at": "2026-06-24T00:00:00+00:00", "release_governance_score": 95.0}],
    }


def _shared_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "generated_at": "2026-06-24T00:00:00+00:00",
        "summary_counts": {"PASS": 4, "WARN": 0, "FAIL": 0},
        "warnings": [],
    }


def _write_snapshot_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_release_governance_bundle_export_generates_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/export_release_governance_bundle.py"), "export_release_governance_bundle_repo")
    monkeypatch.setattr(module, "_production_package_report", lambda: {"overall_status": "PASS", "summary_counts": {"PASS": 15, "WARN": 0, "FAIL": 0}, "artifact_path": "package.json", "warnings": []})
    monkeypatch.setattr(module, "_production_access_governance_report", lambda: {"overall_status": "PASS", "summary_counts": {"PASS": 15, "WARN": 0, "FAIL": 0}, "artifact_path": "access.json", "warnings": []})
    monkeypatch.setattr(module, "RELEASE_GOVERNANCE_BUNDLE_ROOT", tmp_path / "runtime" / "staging" / "release-governance-bundles")
    monkeypatch.setattr(module, "LATEST_RELEASE_GOVERNANCE_BUNDLE_JSON", tmp_path / "runtime" / "staging" / "release-governance-bundles" / "latest_release_governance_bundle.json")
    monkeypatch.setattr(module, "LATEST_RELEASE_GOVERNANCE_BUNDLE_MD", tmp_path / "runtime" / "staging" / "release-governance-bundles" / "latest_release_governance_bundle.md")
    monkeypatch.setattr(module, "LATEST_PRODUCTION_DEPLOYMENT_VALIDATION", tmp_path / "runtime" / "staging" / "production-deployment-validations" / "latest_production_deployment_validation.json")
    monkeypatch.setattr(module, "LATEST_PRODUCTION_ROLLOUT_VALIDATION", tmp_path / "runtime" / "staging" / "production-rollout-validations" / "latest_production_rollout_validation.json")
    monkeypatch.setattr(module, "LATEST_RELEASE_CERTIFICATION", tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json")
    monkeypatch.setattr(module, "LATEST_PILOT_EVIDENCE_PACK", tmp_path / "runtime" / "staging" / "evidence-packs" / "latest_pilot_evidence_pack.json")
    monkeypatch.setattr(module, "LATEST_PILOT_REHEARSAL_SUMMARY", tmp_path / "runtime" / "staging" / "governance-exports" / "latest_pilot_rehearsal_summary.json")
    monkeypatch.setattr(module, "LATEST_PILOT_CYCLE_SUMMARY", tmp_path / "runtime" / "staging" / "pilot-cycles" / "latest_pilot_cycle_summary.json")

    _write_snapshot_file(module.LATEST_PRODUCTION_DEPLOYMENT_VALIDATION, {"overall_status": "PASS", "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0}, "readiness_summary": {"production_readiness_score": 94.0}, "warnings": []})
    _write_snapshot_file(module.LATEST_PRODUCTION_ROLLOUT_VALIDATION, {
        "overall_status": "PASS",
        "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
        "institutional_rollout_certification_evidence": {"certification_status": "CERTIFIED", "certification_authority": "GO", "rollout_governance_score": 96.0},
        "rollout_readiness_summary": {"rollout_readiness_score": 96.0, "rollout_readiness_status": "PASS"},
        "supervision_readiness_summary": {"active_supervision_coverage_ready": True, "operator_name": "governance", "operator_role": "supervisor", "active_sessions": 1, "assigned_rfqs": ["RFQ-1"], "pending_approvals": []},
        "operator_onboarding_readiness_summary": {"operator_availability_ready": True, "approved_for_supervision": True, "operator_name": "governance", "operator_role": "supervisor"},
        "deployment_health_summary": {"deployment_health_ready": True, "production_observability_ready": True, "backup_restore_ready": True, "disaster_recovery_ready": True, "high_availability_ready": True, "audit_retention_ready": True},
        "tenant_isolation_summary": {"tenant_isolation_ready": True, "tenant_count": 1, "workspace_count": 1, "tenant_workspace_pair_count": 1},
        "production_observability_summary": {"production_observability_ready": True, "worker_heartbeat": {"status": "healthy"}, "telemetry_degradation": []},
        "escalation_chain_summary": {"escalation_chain_ready": True, "review_board_status": "ok", "outstanding_governance_actions": [], "unresolved_operational_exceptions": []},
        "rollout_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "rollout-1", "latest_score": 96.0},
        "warnings": [],
    })
    _write_snapshot_file(module.LATEST_RELEASE_CERTIFICATION, _release_payload())
    _write_snapshot_file(module.LATEST_PILOT_EVIDENCE_PACK, _shared_payload())
    _write_snapshot_file(module.LATEST_PILOT_REHEARSAL_SUMMARY, _shared_payload())
    _write_snapshot_file(module.LATEST_PILOT_CYCLE_SUMMARY, _shared_payload())
    monkeypatch.setattr(module, "_production_deployment_validation_report", lambda: json.loads(module.LATEST_PRODUCTION_DEPLOYMENT_VALIDATION.read_text(encoding="utf-8")))
    monkeypatch.setattr(module, "_production_rollout_validation_report", lambda: json.loads(module.LATEST_PRODUCTION_ROLLOUT_VALIDATION.read_text(encoding="utf-8")))

    payload = module.build_release_governance_bundle(output_root=module.RELEASE_GOVERNANCE_BUNDLE_ROOT)
    assert payload["overall_status"] == "PASS"
    assert payload["overall_authority"] == "GO"
    assert payload["overall_score"] >= 80.0
    assert payload["release_readiness"]["release_governance_status"] == "ok"
    assert payload["rollout_readiness"]["rollout_readiness_score"] == 96.0
    assert payload["continuity_readiness"]["continuity_governance_status"] == "ok"
    assert payload["supervision_readiness"]["supervision_command_status"] == "ok"

    exit_code = module.main(["--output-root", str(module.RELEASE_GOVERNANCE_BUNDLE_ROOT), "--json"])
    output = capsys.readouterr().out
    assert exit_code == 0
    rendered = json.loads(output)
    assert rendered["overall_status"] == "PASS"
    assert rendered["overall_authority"] == "GO"

    latest = module.RELEASE_GOVERNANCE_BUNDLE_ROOT / "latest_release_governance_bundle.json"
    assert latest.exists()
    bundle = json.loads(latest.read_text(encoding="utf-8"))
    assert bundle["overall_status"] == "PASS"
    assert bundle["safety_guarantees"]["human_supervision_required"] is True


def test_release_governance_bundle_export_warns_on_bad_inputs(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/export_release_governance_bundle.py"), "export_release_governance_bundle_warn")
    monkeypatch.setattr(module, "_production_package_report", lambda: {"overall_status": "FAIL", "summary_counts": {"PASS": 0, "WARN": 0, "FAIL": 1}, "warnings": ["package broken"], "artifact_path": "package.json"})
    monkeypatch.setattr(module, "_production_access_governance_report", lambda: {"overall_status": "FAIL", "summary_counts": {"PASS": 0, "WARN": 0, "FAIL": 1}, "warnings": ["access broken"], "artifact_path": "access.json"})
    monkeypatch.setattr(module, "RELEASE_GOVERNANCE_BUNDLE_ROOT", tmp_path / "runtime" / "staging" / "release-governance-bundles")
    monkeypatch.setattr(module, "LATEST_RELEASE_GOVERNANCE_BUNDLE_JSON", tmp_path / "runtime" / "staging" / "release-governance-bundles" / "latest_release_governance_bundle.json")
    monkeypatch.setattr(module, "LATEST_RELEASE_GOVERNANCE_BUNDLE_MD", tmp_path / "runtime" / "staging" / "release-governance-bundles" / "latest_release_governance_bundle.md")

    _write_snapshot_file(module.LATEST_PRODUCTION_DEPLOYMENT_VALIDATION, {"overall_status": "FAIL", "summary_counts": {"PASS": 0, "WARN": 0, "FAIL": 1}, "readiness_summary": {"production_readiness_score": 60.0}, "warnings": ["deployment broken"]})
    _write_snapshot_file(module.LATEST_PRODUCTION_ROLLOUT_VALIDATION, {
        "overall_status": "WARN",
        "summary_counts": {"PASS": 1, "WARN": 1, "FAIL": 0},
        "institutional_rollout_certification_evidence": {"certification_status": "WATCH", "certification_authority": "WATCH", "rollout_governance_score": 72.0},
        "rollout_readiness_summary": {"rollout_readiness_score": 72.0, "rollout_readiness_status": "WATCH"},
        "supervision_readiness_summary": {"active_supervision_coverage_ready": False, "operator_name": "governance", "operator_role": "supervisor", "active_sessions": 0, "assigned_rfqs": [], "pending_approvals": ["pending"]},
        "operator_onboarding_readiness_summary": {"operator_availability_ready": False, "approved_for_supervision": False, "operator_name": "governance", "operator_role": "supervisor"},
        "deployment_health_summary": {"deployment_health_ready": False, "production_observability_ready": False},
        "tenant_isolation_summary": {"tenant_isolation_ready": False, "tenant_count": 0, "workspace_count": 0, "tenant_workspace_pair_count": 0},
        "production_observability_summary": {"production_observability_ready": False, "worker_heartbeat": {"status": "degraded"}, "telemetry_degradation": ["degraded"]},
        "escalation_chain_summary": {"escalation_chain_ready": False, "review_board_status": "watch", "outstanding_governance_actions": ["review"], "unresolved_operational_exceptions": ["watch"]},
        "rollout_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "rollout-1", "latest_score": 72.0},
        "warnings": ["rollout watch"],
    })
    _write_snapshot_file(module.LATEST_RELEASE_CERTIFICATION, {"status": "watch", "release_governance_status": "watch", "release_governance_authority": "WATCH", "release_governance_score": 72.0, "release_governance_grade": "watch", "release_authority_indicators": {"active_authority": "WATCH"}, "deployment_risk_indicators": {"deployment_risk": True}, "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": False}, "release_readiness_indicators": {"runtime_segmentation_ready": False}, "release_governance_history": []})
    monkeypatch.setattr(module, "_production_deployment_validation_report", lambda: json.loads(module.LATEST_PRODUCTION_DEPLOYMENT_VALIDATION.read_text(encoding="utf-8")))
    monkeypatch.setattr(module, "_production_rollout_validation_report", lambda: json.loads(module.LATEST_PRODUCTION_ROLLOUT_VALIDATION.read_text(encoding="utf-8")))

    payload = module.build_release_governance_bundle(output_root=module.RELEASE_GOVERNANCE_BUNDLE_ROOT)
    assert payload["overall_status"] == "FAIL"
    assert payload["overall_authority"] == "NO_GO"
    assert payload["safety_guarantees"]["dry_run_protections_active"] is True
