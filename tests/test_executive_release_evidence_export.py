from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _DummyService:
    def latest_release_governance(self):
        return {
            "status": "ok",
            "release_governance_status": "ok",
            "release_governance_authority": "GO",
            "release_governance_score": 96.0,
            "release_governance_grade": "ready",
            "production_rollout_readiness": True,
            "production_rollout_readiness_status": "ready",
            "latest_release_governance": {"analysis_id": "production-validation:release-gate", "production_readiness_score": 96.0},
            "release_governance_history": [{"analysis_id": "production-validation:release-gate", "release_governance_score": 96.0, "release_governance_authority": "GO"}],
            "release_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:release-gate", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "deployment_risk_indicators": {"deployment_risk": False, "runtime_segmentation_risk": False, "operator_access_risk": False, "observability_risk": False, "backup_restore_risk": False, "disaster_recovery_risk": False, "high_availability_risk": False, "audit_retention_risk": False},
            "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True, "history_available": True, "overall_validation_passed": True},
            "release_readiness_indicators": {"runtime_segmentation_ready": True, "operator_access_ready": True, "observability_ready": True, "backup_restore_ready": True, "disaster_recovery_ready": True, "high_availability_ready": True, "audit_retention_ready": True, "deployment_governance_ready": True, "submission_lock_ready": True, "dry_run_ready": True},
            "release_authority_indicators": {"go_release_authority": True, "watch_release_authority": False, "no_go_release_authority": False, "active_authority": "GO"},
            "unresolved_deployment_blockers": [],
            "governance_override_authority": False,
            "release_escalation_authority": False,
            "summary_components": {"runtime_segmentation": 96.0},
            "warnings": [],
        }

    def release_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "release_governance_history": [{"analysis_id": "production-validation:release-gate", "release_governance_score": 96.0, "release_governance_authority": "GO"}],
            "release_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:release-gate", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "deployment_risk_indicators": {"deployment_risk": False},
            "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True, "history_available": True, "overall_validation_passed": True},
            "release_readiness_indicators": {"runtime_segmentation_ready": True},
            "release_authority_indicators": {"go_release_authority": True, "watch_release_authority": False, "no_go_release_authority": False, "active_authority": "GO"},
            "unresolved_deployment_blockers": [],
            "governance_override_authority": False,
            "release_escalation_authority": False,
            "production_rollout_readiness": True,
            "production_rollout_readiness_status": "ready",
            "summary_components": {"runtime_segmentation": 96.0},
            "warnings": [],
        }


def test_executive_release_evidence_export_generates_latest_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/export_executive_release_evidence.py"), "export_executive_release_evidence")
    monkeypatch.setattr(module, "_release_service", lambda: _DummyService())
    monkeypatch.setattr(module, "RELEASE_CERTIFICATION_ROOT", tmp_path / "runtime" / "staging" / "release-certifications")

    payload = module.build_release_evidence_export(output_root=module.RELEASE_CERTIFICATION_ROOT)
    assert payload["executive_rollout_summary"]["status"] == "CERTIFIED"
    assert payload["governance_certification_summary"]["certification_status"] == "CERTIFIED"
    assert payload["release_authority_certification"]["active_authority"] == "GO"
    assert payload["operational_readiness_certification"]["submission_lock_verified"] is True

    exit_code = module.main(["--output-root", str(module.RELEASE_CERTIFICATION_ROOT), "--json"])
    output = capsys.readouterr().out
    assert exit_code == 0
    rendered = json.loads(output)
    assert rendered["governance_certification_summary"]["certification_status"] == "CERTIFIED"
    assert "-release-" in rendered["export_id"]

    latest_json = module.RELEASE_CERTIFICATION_ROOT / "latest_executive_release_evidence.json"
    latest_md = module.RELEASE_CERTIFICATION_ROOT / "latest_executive_release_evidence.md"
    assert latest_json.exists()
    assert latest_md.exists()


def test_executive_release_evidence_export_holds_when_watch(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/export_executive_release_evidence.py"), "export_executive_release_evidence_watch")
    dummy = _DummyService()
    monkeypatch.setattr(module, "_release_service", lambda: dummy)
    monkeypatch.setattr(module, "RELEASE_CERTIFICATION_ROOT", tmp_path / "runtime" / "staging" / "release-certifications")

    base_payload = dummy.latest_release_governance()

    def _watch_latest():
        payload = dict(base_payload)
        payload["release_governance_authority"] = "WATCH"
        payload["release_governance_status"] = "watch"
        payload["release_governance_grade"] = "watch"
        payload["production_rollout_readiness"] = False
        payload["production_rollout_readiness_status"] = "watch"
        payload["release_authority_indicators"] = {
            "go_release_authority": False,
            "watch_release_authority": True,
            "no_go_release_authority": False,
            "active_authority": "WATCH",
        }
        payload["warnings"] = ["deployment readiness below threshold"]
        payload["unresolved_deployment_blockers"] = ["deployment readiness below threshold"]
        return payload

    monkeypatch.setattr(dummy, "latest_release_governance", _watch_latest)

    payload = module.build_release_evidence_export(output_root=module.RELEASE_CERTIFICATION_ROOT)
    assert payload["executive_rollout_summary"]["status"] == "WATCH"
    assert payload["governance_certification_summary"]["certification_status"] == "WATCH"
    assert payload["release_authority_certification"]["watch_release_authority"] is True
