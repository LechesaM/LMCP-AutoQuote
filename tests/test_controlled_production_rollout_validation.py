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


def _write_release_cert(root: Path, *, status: str = "CERTIFIED", authority: str = "GO") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "export_id": "20260623T203218Z-release-35690031",
        "generated_at": "2026-06-23T20:32:18+00:00",
        "executive_rollout_summary": {
            "status": status,
            "release_authority": authority,
            "release_governance_score": 96.0 if status == "CERTIFIED" else 72.0,
            "production_rollout_readiness": status == "CERTIFIED",
            "production_rollout_readiness_status": "ready" if status == "CERTIFIED" else "watch",
            "unresolved_deployment_blockers": [] if status == "CERTIFIED" else ["release certification is not certified"],
            "warnings": [] if status == "CERTIFIED" else ["release certification is not certified"],
        },
        "governance_certification_summary": {
            "certification_status": status,
            "certification_score": 96.0 if status == "CERTIFIED" else 72.0,
            "certified_go_governance": status == "CERTIFIED",
            "certified_watch_governance": status == "WATCH",
            "certified_no_go_governance": status == "NO_GO",
        },
        "deployment_readiness_certification": {
            "status": status,
            "ready_for_deployment": status == "CERTIFIED",
        },
        "operational_readiness_certification": {
            "status": status,
            "submission_lock_verified": True,
            "dry_run_verified": True,
            "environment_safe": True,
            "overall_validation_passed": status == "CERTIFIED",
        },
        "release_authority_certification": {
            "status": status,
            "go_release_authority": status == "CERTIFIED",
            "watch_release_authority": status == "WATCH",
            "no_go_release_authority": status == "NO_GO",
            "active_authority": authority,
        },
        "release_governance_history": [
            {
                "analysis_id": "production-validation:release-gate",
                "release_governance_score": 96.0 if status == "CERTIFIED" else 72.0,
                "release_governance_authority": authority,
            }
        ],
        "warnings": [] if status == "CERTIFIED" else ["release certification is not certified"],
    }
    (root / "latest_executive_release_evidence.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "latest_executive_release_evidence.md").write_text("# release cert\n", encoding="utf-8")
    return root


class _DummyReviewBoard:
    def latest_review_board(self):
        return {
            "review_board_status": "ok",
            "outstanding_governance_actions": [],
            "unresolved_operational_exceptions": [],
        }


class _DummyOperationalizationService:
    def __init__(self, payload: dict[str, object], history: dict[str, object]):
        self._payload = payload
        self._history = history
        self.review_board = _DummyReviewBoard()

    def latest_production_governance(self):
        return self._payload

    def production_governance_history(self, limit: int = 20):
        history = list(self._history.get("production_governance_history", []))
        return {
            "status": "ok",
            "count": len(history),
            "production_governance_history": history[:limit],
            "production_governance_history_summary": self._history.get("production_governance_history_summary", {}),
            "summary_components": self._history.get("summary_components", {}),
            "warnings": self._history.get("warnings", []),
        }


def _ready_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "generated_at": "2026-06-23T20:32:18+00:00",
        "analysis_id": "production-governance:2026-06-23T00:00:00+00:00",
        "production_readiness_score": 94.0,
        "production_readiness_status": "ok",
        "production_readiness_grade": "ready",
        "production_runtime_segmentation": {
            "production_runtime_segmentation_score": 96.0,
            "production_runtime_segmentation_status": "ok",
            "tenant_workspace_isolation": {"tenant_count": 1, "workspace_count": 1, "tenant_workspace_pair_count": 1, "isolation_verified": True},
        },
        "operator_access_governance": {
            "operator_access_governance_score": 94.0,
            "operator_access_governance_status": "ok",
            "operator_access_details": {
                "operator_name": "governance",
                "operator_role": "supervisor",
                "active_sessions": 2,
                "assigned_rfqs": ["RFQ-PROD-001"],
                "pending_approvals": [],
            },
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
                "generated_at": "2026-06-22T20:32:18+00:00",
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
        "production_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "cycle-prod:production", "latest_score": 93.0, "warnings": []},
    }


def _watch_payload() -> dict[str, object]:
    payload = _ready_payload()
    payload = dict(payload)
    payload["production_readiness_score"] = 72.0
    payload["production_readiness_status"] = "watch"
    payload["production_readiness_grade"] = "watch"
    payload["operator_access_governance"] = {
        "operator_access_governance_score": 72.0,
        "operator_access_governance_status": "watch",
        "operator_access_details": {
            "operator_name": "governance",
            "operator_role": "supervisor",
            "active_sessions": 1,
            "assigned_rfqs": ["RFQ-PROD-002"],
            "pending_approvals": [],
        },
        "operator_access_risk_indicators": {"pending_approval_backlog": False},
    }
    payload["production_observability_governance"] = {
        "production_observability_governance_score": 72.0,
        "production_observability_governance_status": "watch",
        "observability_readiness_indicators": {"worker_heartbeat": True},
        "observability_risk_indicators": {"telemetry_degradation": []},
    }
    payload["high_availability_governance"] = {
        "high_availability_governance_score": 72.0,
        "high_availability_governance_status": "watch",
        "ha_readiness_indicators": {"queue_stable": True},
    }
    payload["deployment_readiness_governance"] = {
        "deployment_readiness_governance_score": 72.0,
        "deployment_readiness_governance_status": "watch",
        "deployment_readiness_indicators": {"executive_ready": False},
    }
    payload["deployment_risk_indicators"] = {
        "deployment_risk": True,
        "operator_access_risk": False,
        "ha_risk": False,
        "recovery_risk": False,
    }
    payload["warnings"] = ["production readiness below threshold"]
    payload["production_governance_history_summary"] = {"analysis_count": 1, "latest_analysis_id": "cycle-prod:production", "latest_score": 72.0, "warnings": ["production readiness below threshold"]}
    return payload


def test_controlled_production_rollout_validation_generates_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_controlled_production_rollout_validation.py"), "run_controlled_production_rollout_validation_ready")
    monkeypatch.setattr(module, "STAGING_ROOT", tmp_path / "runtime" / "staging")
    monkeypatch.setattr(module, "ROLLOUT_VALIDATION_ROOT", tmp_path / "runtime" / "staging" / "production-rollout-validations")
    monkeypatch.setattr(module, "RELEASE_CERTIFICATION_ROOT", tmp_path / "runtime" / "staging" / "release-certifications")
    monkeypatch.setattr(module, "LATEST_RELEASE_CERTIFICATION_FILE", tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json")
    monkeypatch.setattr(module, "LATEST_RELEASE_CERTIFICATION_MD_FILE", tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.md")

    _write_release_cert(module.RELEASE_CERTIFICATION_ROOT, status="CERTIFIED", authority="GO")

    payload = module.build_rollout_validation_report(
        operational_service=_DummyOperationalizationService(_ready_payload(), _ready_payload()),
        output_root=module.ROLLOUT_VALIDATION_ROOT,
    )
    assert payload["institutional_rollout_certification_evidence"]["certification_status"] == "CERTIFIED"
    assert payload["rollout_readiness_summary"]["release_authorization_valid"] is True
    assert payload["tenant_isolation_summary"]["tenant_isolation_ready"] is True
    assert payload["supervision_readiness_summary"]["active_supervision_coverage_ready"] is True

    exit_code = module.main(["--output-root", str(module.ROLLOUT_VALIDATION_ROOT), "--json"])
    output = capsys.readouterr().out
    assert exit_code == 0
    rendered = json.loads(output)
    assert rendered["institutional_rollout_certification_evidence"]["certification_status"] == "CERTIFIED"
    assert "-production-" in rendered["validation_id"]

    latest_json = module.ROLLOUT_VALIDATION_ROOT / "latest_production_rollout_validation.json"
    latest_md = module.ROLLOUT_VALIDATION_ROOT / "latest_production_rollout_validation.md"
    assert latest_json.exists()
    assert latest_md.exists()
    assert (module.ROLLOUT_VALIDATION_ROOT / rendered["validation_id"] / "source_release_certification.json").exists()


def test_controlled_production_rollout_validation_holds_on_watch(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_controlled_production_rollout_validation.py"), "run_controlled_production_rollout_validation_watch")
    monkeypatch.setattr(module, "STAGING_ROOT", tmp_path / "runtime" / "staging")
    monkeypatch.setattr(module, "ROLLOUT_VALIDATION_ROOT", tmp_path / "runtime" / "staging" / "production-rollout-validations")
    monkeypatch.setattr(module, "RELEASE_CERTIFICATION_ROOT", tmp_path / "runtime" / "staging" / "release-certifications")
    monkeypatch.setattr(module, "LATEST_RELEASE_CERTIFICATION_FILE", tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.json")
    monkeypatch.setattr(module, "LATEST_RELEASE_CERTIFICATION_MD_FILE", tmp_path / "runtime" / "staging" / "release-certifications" / "latest_executive_release_evidence.md")

    _write_release_cert(module.RELEASE_CERTIFICATION_ROOT, status="WATCH", authority="WATCH")

    payload = module.build_rollout_validation_report(
        operational_service=_DummyOperationalizationService(_watch_payload(), _watch_payload()),
        output_root=module.ROLLOUT_VALIDATION_ROOT,
    )
    assert payload["institutional_rollout_certification_evidence"]["certification_status"] == "WATCH"
    assert payload["rollout_readiness_summary"]["release_authorization_valid"] is False
    assert payload["rollout_readiness_summary"]["rollout_readiness_status"] == "WARN"

    exit_code = module.main(["--output-root", str(module.ROLLOUT_VALIDATION_ROOT)])
    assert exit_code == 1
