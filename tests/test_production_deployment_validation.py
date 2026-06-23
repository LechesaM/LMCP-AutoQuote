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


class _DummyProductionOperationalizationService:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def latest_production_governance(self):
        return self._payload

    def production_governance_history(self, limit: int = 20):
        history = list(self._payload.get("production_governance_history", []))
        return {
            "status": "ok",
            "count": len(history),
            "production_governance_history": history[:limit],
            "production_governance_history_summary": self._payload.get("production_governance_history_summary", {}),
            "summary_components": self._payload.get("summary_components", {}),
            "warnings": self._payload.get("warnings", []),
        }


def _ready_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "generated_at": "2026-06-23T15:55:59+00:00",
        "analysis_id": "production-governance:2026-06-23T00:00:00+00:00",
        "production_readiness_score": 94.0,
        "production_readiness_status": "ok",
        "production_readiness_grade": "ready",
        "production_runtime_segmentation": {
            "production_runtime_segmentation_score": 96.0,
            "production_runtime_segmentation_status": "ok",
            "tenant_workspace_isolation": {"isolation_verified": True},
        },
        "operator_access_governance": {
            "operator_access_governance_score": 94.0,
            "operator_access_governance_status": "ok",
            "operator_access_details": {"operator_name": "governance", "operator_role": "supervisor"},
            "operator_access_risk_indicators": {"pending_approval_backlog": False},
        },
        "production_observability_governance": {
            "production_observability_governance_score": 95.0,
            "production_observability_governance_status": "ok",
            "observability_readiness_indicators": {"worker_heartbeat": True},
            "observability_risk_indicators": {"telemetry_degradation": []},
        },
        "backup_restore_governance": {
            "backup_restore_governance_score": 92.0,
            "backup_restore_governance_status": "ok",
            "backup_restore_details": {"latest_pack_id": "pack-1"},
            "recovery_readiness_indicators": {"evidence_pack_available": True},
        },
        "disaster_recovery_governance": {
            "disaster_recovery_governance_score": 93.0,
            "disaster_recovery_governance_status": "ok",
            "recovery_readiness_indicators": {"final_readiness_cleared": True},
        },
        "high_availability_governance": {
            "high_availability_governance_score": 95.0,
            "high_availability_governance_status": "ok",
            "ha_readiness_indicators": {"queue_stable": True},
        },
        "audit_retention_governance": {
            "audit_retention_governance_score": 91.0,
            "audit_retention_governance_status": "ok",
            "audit_retention_details": {"cycle_count": 2},
            "audit_retention_indicators": {"cycle_history_available": True},
        },
        "deployment_readiness_governance": {
            "deployment_readiness_governance_score": 95.0,
            "deployment_readiness_governance_status": "ok",
            "deployment_readiness_indicators": {"executive_ready": True},
        },
        "summary_components": {
            "runtime_segmentation": 96.0,
            "operator_access": 94.0,
            "observability": 95.0,
            "backup_restore": 92.0,
            "disaster_recovery": 93.0,
            "high_availability": 95.0,
            "audit_retention": 91.0,
            "deployment_readiness": 95.0,
        },
        "deployment_risk_indicators": {
            "deployment_risk": False,
            "operator_access_risk": False,
            "ha_risk": False,
            "recovery_risk": False,
        },
        "operator_access_risk_indicators": {"pending_approval_backlog": False},
        "ha_readiness_indicators": {"queue_stable": True},
        "recovery_readiness_indicators": {"final_readiness_cleared": True},
        "warnings": [],
        "production_governance_history": [
            {
                "analysis_id": "cycle-prod:production",
                "generated_at": "2026-06-22T15:55:59+00:00",
                "production_readiness_score": 93.0,
                "production_readiness_status": "ok",
                "production_readiness_grade": "ready",
                "deployment_risk_indicators": {"deployment_risk": False},
                "operator_access_risk_indicators": {"pending_approval_backlog": False},
                "ha_readiness_indicators": {"queue_stable": True},
                "recovery_readiness_indicators": {"final_readiness_cleared": True},
                "production_governance_summary": {"decision": "support_enterprise_deployment"},
            }
        ],
        "production_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "cycle-prod:production", "latest_score": 93.0},
    }


def _warn_payload() -> dict[str, object]:
    payload = _ready_payload()
    payload = dict(payload)
    payload["production_readiness_score"] = 72.0
    payload["production_readiness_status"] = "watch"
    payload["production_readiness_grade"] = "watch"
    payload["production_runtime_segmentation"] = {
        "production_runtime_segmentation_score": 74.0,
        "production_runtime_segmentation_status": "watch",
        "tenant_workspace_isolation": {"isolation_verified": True},
    }
    payload["operator_access_governance"] = {
        "operator_access_governance_score": 68.0,
        "operator_access_governance_status": "watch",
        "operator_access_details": {"operator_name": "governance", "operator_role": "supervisor"},
        "operator_access_risk_indicators": {"pending_approval_backlog": True},
    }
    payload["deployment_risk_indicators"] = {
        "deployment_risk": True,
        "operator_access_risk": True,
        "ha_risk": True,
        "recovery_risk": True,
    }
    payload["warnings"] = ["deployment readiness below threshold"]
    return payload


def test_production_deployment_validation_generates_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_production_deployment_validation.py"), "run_production_deployment_validation_ready")
    monkeypatch.setattr(module, "ProductionOperationalizationService", lambda: _DummyProductionOperationalizationService(_ready_payload()))
    monkeypatch.setattr(module, "STAGING_ROOT", tmp_path / "runtime" / "staging")
    monkeypatch.setattr(module, "VALIDATION_ROOT", tmp_path / "runtime" / "staging" / "production-deployment-validations")
    monkeypatch.setattr(module, "LATEST_VALIDATION_FILE", tmp_path / "runtime" / "staging" / "production-deployment-validations" / "latest_production_deployment_validation.json")
    monkeypatch.setattr(module, "DEFAULT_LOCK_FILE", tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json")

    lock_file = tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(
        json.dumps(
            {
                "final_automation_disabled": True,
                "live_portal_submission_disabled": True,
                "production_credentials_disabled": True,
                "dry_run_mode_required": True,
                "submission_execution_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LMCP_SUBMISSION_LOCK_FILE", str(lock_file))
    monkeypatch.setenv("LMCP_ENV", "staging")
    monkeypatch.setenv("LMCP_PRODUCTION_MODE", "staging")
    monkeypatch.setenv("LMCP_ALLOW_FINAL_AUTOMATION", "false")
    monkeypatch.setenv("LMCP_ALLOW_DEGRADED_STARTUP", "true")

    payload = module.build_production_deployment_validation_report(output_root=module.VALIDATION_ROOT)
    assert payload["overall_status"] == "PASS"
    assert payload["readiness_summary"]["production_readiness_score"] == 94.0
    assert payload["submission_lock_verification"]["verified"] is True
    assert payload["environment_safety"]["status"] == "PASS"

    exit_code = module.main(["--output-root", str(module.VALIDATION_ROOT), "--json"])
    output = capsys.readouterr().out
    assert exit_code == 0
    rendered = json.loads(output)
    assert "-production-" in rendered["validation_id"]
    assert rendered["overall_status"] == "PASS"

    latest = module.VALIDATION_ROOT / "latest_production_deployment_validation.json"
    assert latest.exists()
    bundle = json.loads(latest.read_text(encoding="utf-8"))
    assert bundle["overall_status"] == "PASS"
    assert bundle["validation_counts"]["PASS"] == 8


def test_production_deployment_validation_warns_on_readiness_drift(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_production_deployment_validation.py"), "run_production_deployment_validation_warn")
    monkeypatch.setattr(module, "ProductionOperationalizationService", lambda: _DummyProductionOperationalizationService(_warn_payload()))
    monkeypatch.setattr(module, "STAGING_ROOT", tmp_path / "runtime" / "staging")
    monkeypatch.setattr(module, "VALIDATION_ROOT", tmp_path / "runtime" / "staging" / "production-deployment-validations")
    monkeypatch.setattr(module, "LATEST_VALIDATION_FILE", tmp_path / "runtime" / "staging" / "production-deployment-validations" / "latest_production_deployment_validation.json")
    monkeypatch.setattr(module, "DEFAULT_LOCK_FILE", tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json")

    lock_file = tmp_path / "runtime" / "staging" / "go_live_guards" / "submission_locks.json"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(
        json.dumps(
            {
                "final_automation_disabled": True,
                "live_portal_submission_disabled": True,
                "production_credentials_disabled": True,
                "dry_run_mode_required": True,
                "submission_execution_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LMCP_SUBMISSION_LOCK_FILE", str(lock_file))
    monkeypatch.setenv("LMCP_ENV", "staging")
    monkeypatch.setenv("LMCP_PRODUCTION_MODE", "staging")
    monkeypatch.setenv("LMCP_ALLOW_FINAL_AUTOMATION", "false")
    monkeypatch.setenv("LMCP_ALLOW_DEGRADED_STARTUP", "true")

    payload = module.build_production_deployment_validation_report(output_root=module.VALIDATION_ROOT)
    assert payload["overall_status"] == "WARN"
    assert payload["readiness_summary"]["production_readiness_status"] == "WARN"
    assert payload["deployment_risk_summary"]["deployment_risk"] is True
    assert payload["validation_sections"]["operator_access"]["status"] == "WARN"
