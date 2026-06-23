from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Optional


def _write_release_certification(root: Path, *, status: str = "CERTIFIED", authority: str = "GO") -> Path:
    export_id = "20260623T205315Z-release-supervision"
    export_dir = root / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "export_id": export_id,
        "generated_at": "2026-06-23T20:53:15+00:00",
        "governance_certification_summary": {
            "certification_status": status,
            "certification_score": 100.0 if status == "CERTIFIED" else 74.0,
            "certified_go_governance": status == "CERTIFIED",
            "certified_watch_governance": status != "CERTIFIED",
            "certified_no_go_governance": False,
        },
        "operational_readiness_certification": {
            "status": "PASS",
            "submission_lock_verified": True,
            "dry_run_verified": True,
            "environment_safe": True,
            "overall_validation_passed": True,
        },
        "deployment_readiness_certification": {
            "status": "PASS",
            "ready_for_deployment": True,
            "release_readiness_indicators": {"runtime_segmentation_ready": True},
            "deployment_risk_indicators": {"deployment_risk": False},
        },
        "release_authority_certification": {
            "status": "PASS",
            "active_authority": authority,
            "go_release_authority": authority == "GO",
            "watch_release_authority": authority == "WATCH",
            "no_go_release_authority": authority == "NO_GO",
        },
        "institutional_sign_off_summary": {
            "rollout_authorization": "authorise_rollout" if status == "CERTIFIED" else "review_required",
            "rollout_recommendation": "supervised_activation",
            "governance_review_status": "ok",
            "operator_sign_off_status": "complete",
            "sign_off_history": [{"generated_at": "2026-06-23T20:53:15+00:00"}],
        },
        "readiness_summary": {
            "production_readiness_score": 100.0 if status == "CERTIFIED" else 74.0,
            "production_readiness_status": "ok" if status == "CERTIFIED" else "watch",
            "production_readiness_grade": "ready" if status == "CERTIFIED" else "watch",
            "trend_summary": {"trend": "stable", "delta": 0.0, "average": 100.0, "latest": 100.0, "previous": 100.0, "points": [100.0]},
            "thresholds": {"readiness_score": 85.0},
            "release_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:release-gate", "latest_score": 100.0},
        },
        "deployment_risk_summary": {
            "deployment_risk": False,
            "runtime_segmentation_risk": False,
            "operator_access_risk": False,
            "observability_risk": False,
            "backup_restore_risk": False,
            "disaster_recovery_risk": False,
            "high_availability_risk": False,
            "audit_retention_risk": False,
        },
        "release_governance_history": [
            {
                "analysis_id": "production-validation:release-gate",
                "generated_at": "2026-06-23T20:53:15+00:00",
                "release_governance_score": 100.0 if status == "CERTIFIED" else 74.0,
                "release_governance_authority": authority,
            }
        ],
        "release_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:release-gate", "latest_score": 100.0 if status == "CERTIFIED" else 74.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 100.0 if status == "CERTIFIED" else 74.0, "latest": 100.0 if status == "CERTIFIED" else 74.0, "previous": 100.0 if status == "CERTIFIED" else 74.0, "points": [100.0 if status == "CERTIFIED" else 74.0]}},
        "summary_counts": {"PASS": 8, "WARN": 0 if status == "CERTIFIED" else 1, "FAIL": 0},
        "warnings": [],
    }
    (export_dir / "executive_release_evidence.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "latest_executive_release_evidence.json").write_text(json.dumps(payload), encoding="utf-8")
    return export_dir


def _write_rollout_bundle(
    root: Path,
    bundle_id: str,
    *,
    score: float = 100.0,
    status: str = "PASS",
    rollout_ready: Optional[bool] = None,
    warnings: Optional[list[str]] = None,
    active_sessions: int = 1,
    pending_approvals: Optional[list[str]] = None,
    assigned_rfqs: Optional[list[str]] = None,
) -> Path:
    bundle_dir = root / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    pack_root = root.parent / "release-certifications"
    _write_release_certification(pack_root, status="CERTIFIED" if score >= 85.0 else "WATCH", authority="GO" if score >= 85.0 else "WATCH")
    warning_list = warnings if warnings is not None else ([] if status == "PASS" else ["readiness score below threshold"])
    assigned = assigned_rfqs if assigned_rfqs is not None else [f"{bundle_id}-rfq"]
    pending = pending_approvals if pending_approvals is not None else []

    payload = {
        "validation_id": bundle_id,
        "generated_at": "2026-06-23T20:53:15+00:00",
        "source_runtime": {"environment": "staging", "mode": "production-rollout-validation"},
        "source_artifacts": {"rollout_validation": "production_rollout_validation.json"},
        "summary_counts": {"PASS": 8, "WARN": 0 if status == "PASS" else 1, "FAIL": 0},
        "warnings": warning_list,
        "rollout_readiness_summary": {
            "rollout_readiness_score": score,
            "rollout_readiness_status": status,
            "rollout_readiness_grade": "ready" if score >= 85.0 else "watch",
            "tenant_isolation_ready": True,
            "operator_availability_ready": True,
            "active_supervision_coverage_ready": True,
            "deployment_health_ready": True,
            "production_observability_ready": True,
            "release_authorization_valid": True,
            "escalation_chain_ready": True,
            "unresolved_blockers": [],
            "warnings": warning_list,
        },
        "tenant_isolation_summary": {
            "tenant_count": 1,
            "workspace_count": 1,
            "tenant_workspace_pair_count": 1,
            "tenant_isolation_ready": True,
        },
        "operator_onboarding_readiness_summary": {
            "approved_for_supervision": True,
            "onboarding_status": "ready",
            "operator_availability_ready": True,
            "operator_name": "staging-governance-operator",
            "operator_role": "governance_reviewer",
        },
        "supervision_readiness_summary": {
            "active_sessions": active_sessions,
            "active_supervision_coverage_ready": True,
            "assigned_rfqs": assigned,
            "operator_name": "staging-governance-operator",
            "operator_role": "governance_reviewer",
            "pending_approvals": pending,
            "supervision_score": 100.0,
        },
        "deployment_health_summary": {
            "deployment_health_ready": True,
            "production_observability_ready": True,
            "backup_restore_ready": True,
            "disaster_recovery_ready": True,
            "high_availability_ready": True,
            "audit_retention_ready": True,
        },
        "production_observability_summary": {
            "production_observability_ready": True,
            "telemetry_degradation": [],
            "worker_heartbeat": True,
        },
        "escalation_chain_summary": {
            "escalation_chain_ready": True,
            "review_board_status": "watch",
            "outstanding_governance_actions": [],
            "unresolved_operational_exceptions": [],
        },
        "institutional_rollout_certification_evidence": {
            "certification_authority": "GO" if score >= 85.0 else "WATCH",
            "certification_status": "CERTIFIED" if score >= 85.0 else "WATCH",
            "governance_override_indicators": {
                "deployment_blockers": False,
                "human_supervision_required": True,
                "release_authorization_override": False,
            },
            "release_authorization_valid": True,
            "rollout_governance_score": score,
            "rollout_ready_for_supervised_deployment": rollout_ready if rollout_ready is not None else score >= 85.0,
        },
        "latest_release_certification": {
            "artifact_path": str(pack_root / "latest_executive_release_evidence.json"),
            "certification_score": 100.0 if score >= 85.0 else 74.0,
            "certification_status": "CERTIFIED" if score >= 85.0 else "WATCH",
            "production_rollout_readiness": score >= 85.0,
            "release_authority": "GO" if score >= 85.0 else "WATCH",
        },
        "rollout_governance_history": [
            {
                "analysis_id": f"{bundle_id}:production",
                "cycle_id": bundle_id,
                "generated_at": "2026-06-23T20:53:15+00:00",
                "production_readiness_score": score,
                "production_readiness_status": "ok" if score >= 85.0 else "watch",
                "production_readiness_grade": "ready" if score >= 85.0 else "watch",
                "deployment_risk_indicators": {"deployment_risk": False},
                "operator_access_risk_indicators": {"pending_approval_backlog": False},
                "ha_readiness_indicators": {"queue_stable": True},
                "recovery_readiness_indicators": {"final_readiness_cleared": True},
                "production_governance_summary": {"decision": "support_enterprise_deployment"},
            }
        ],
        "rollout_governance_history_summary": {
            "analysis_count": 1,
            "latest_analysis_id": f"{bundle_id}:production",
            "latest_score": score,
            "score_history": {
                "trend": "stable",
                "delta": 0.0,
                "average": score,
                "latest": score,
                "previous": score,
                "points": [score],
            },
        },
        "supervision_readiness_summary": {
            "active_sessions": active_sessions,
            "active_supervision_coverage_ready": True,
            "assigned_rfqs": assigned,
            "operator_name": "staging-governance-operator",
            "operator_role": "governance_reviewer",
            "pending_approvals": pending,
            "supervision_score": 100.0,
        },
    }
    (bundle_dir / "production_rollout_validation.json").write_text(json.dumps(payload), encoding="utf-8")
    return bundle_dir


def test_production_supervision_command_service_ready_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.production_supervision_command_service")
    validation_root = tmp_path / "runtime" / "staging" / "production-rollout-validations"
    release_root = tmp_path / "runtime" / "staging" / "release-certifications"
    service = module.ProductionSupervisionCommandService(validation_root=validation_root, release_certification_root=release_root)
    _write_rollout_bundle(validation_root, "20260623T205315Z-production-ready", score=96.0, status="PASS", rollout_ready=True, active_sessions=1, assigned_rfqs=["RFQ-1"], pending_approvals=[])

    latest = service.latest_supervision_command()
    history = service.supervision_command_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["supervision_command_authority"] == "GO"
    assert latest["production_rollout_readiness"] is True
    assert latest["supervision_coverage"]["supervision_coverage_ready"] is True
    assert latest["supervision_sla_visibility"]["sla_ready"] is True
    assert latest["supervision_lapse_indicators"]["coverage_lapse"] is False
    assert history["count"] >= 1
    assert history["supervision_governance_history"][0]["supervision_command_authority"] == "GO"


def test_production_supervision_command_service_watch_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.production_supervision_command_service")
    validation_root = tmp_path / "runtime" / "staging" / "production-rollout-validations"
    release_root = tmp_path / "runtime" / "staging" / "release-certifications"
    service = module.ProductionSupervisionCommandService(validation_root=validation_root, release_certification_root=release_root)
    _write_rollout_bundle(validation_root, "20260623T205315Z-production-watch", score=74.0, status="WARN", rollout_ready=True, active_sessions=1, assigned_rfqs=["RFQ-1", "RFQ-2"], pending_approvals=["approval-1"], warnings=["supervision review required"])

    latest = service.latest_supervision_command()

    assert latest["status"] == "watch"
    assert latest["supervision_command_authority"] == "WATCH"
    assert latest["production_rollout_readiness"] is False
    assert latest["supervision_saturation"]["supervision_saturation_active"] is True
    assert latest["warnings"]
