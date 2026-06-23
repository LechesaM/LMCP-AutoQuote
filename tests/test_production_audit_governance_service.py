from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_release_certification(root: Path, *, status: str = "CERTIFIED", authority: str = "GO") -> Path:
    export_id = "20260623T205315Z-release-audit"
    export_dir = root / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "export_id": export_id,
        "generated_at": "2026-06-23T20:53:15+00:00",
        "governance_certification_summary": {
            "certification_status": status,
            "certification_score": 100.0 if status == "CERTIFIED" else 76.0,
        },
        "operational_readiness_certification": {
            "status": "PASS",
            "submission_lock_verified": True,
            "dry_run_verified": True,
            "overall_validation_passed": True,
        },
        "release_authority_certification": {
            "status": "PASS",
            "active_authority": authority,
        },
        "institutional_sign_off_summary": {
            "governance_review_status": "ok",
            "operator_sign_off_status": "complete",
        },
        "release_governance_history": [
            {
                "analysis_id": "production-validation:release-audit",
                "generated_at": "2026-06-23T20:53:15+00:00",
                "release_governance_score": 100.0 if status == "CERTIFIED" else 76.0,
                "release_governance_authority": authority,
            }
        ],
        "release_governance_history_summary": {
            "analysis_count": 1,
            "latest_analysis_id": "production-validation:release-audit",
            "latest_score": 100.0 if status == "CERTIFIED" else 76.0,
            "score_history": {
                "trend": "stable",
                "delta": 0.0,
                "average": 100.0 if status == "CERTIFIED" else 76.0,
                "latest": 100.0 if status == "CERTIFIED" else 76.0,
                "previous": 100.0 if status == "CERTIFIED" else 76.0,
                "points": [100.0 if status == "CERTIFIED" else 76.0],
            },
        },
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
    warnings: list[str] | None = None,
    freeze_active: bool = False,
    release_authority: str = "GO",
) -> Path:
    bundle_dir = root / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    pack_root = root.parent / "release-certifications"
    _write_release_certification(pack_root, status="CERTIFIED" if score >= 85.0 else "WATCH", authority=release_authority)
    warning_list = warnings if warnings is not None else ([] if score >= 85.0 else ["audit readiness below threshold"])
    payload = {
        "validation_id": bundle_id,
        "generated_at": "2026-06-23T20:53:15+00:00",
        "source_runtime": {"environment": "staging", "mode": "production-rollout-validation"},
        "summary_counts": {"PASS": 8, "WARN": 0 if score >= 85.0 else 1, "FAIL": 0},
        "warnings": warning_list,
        "rollout_readiness_summary": {
            "rollout_readiness_score": score,
            "rollout_readiness_status": "PASS" if score >= 85.0 else "WARN",
            "rollout_readiness_grade": "ready" if score >= 85.0 else "watch",
            "tenant_isolation_ready": True,
            "operator_availability_ready": True,
            "active_supervision_coverage_ready": True,
            "deployment_health_ready": True,
            "production_observability_ready": True,
            "release_authorization_valid": True,
            "escalation_chain_ready": True,
        },
        "tenant_isolation_summary": {
            "tenant_count": 1,
            "workspace_count": 1,
            "tenant_workspace_pair_count": 1,
            "tenant_isolation_ready": True,
        },
        "operator_onboarding_readiness_summary": {
            "approved_for_supervision": True,
            "operator_availability_ready": True,
            "operator_name": "staging-governance-operator",
            "operator_role": "governance_reviewer",
        },
        "supervision_readiness_summary": {
            "active_sessions": 1,
            "active_supervision_coverage_ready": True,
            "assigned_rfqs": [f"{bundle_id}-rfq"],
            "pending_approvals": [],
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
            "worker_heartbeat": True,
        },
        "escalation_chain_summary": {
            "escalation_chain_ready": True,
            "review_board_status": "watch",
            "outstanding_governance_actions": [],
            "unresolved_operational_exceptions": [],
        },
        "institutional_rollout_certification_evidence": {
            "release_authorization_valid": True,
            "rollout_ready_for_supervised_deployment": score >= 85.0,
            "rollout_governance_score": score,
            "certification_status": "CERTIFIED" if score >= 85.0 else "WATCH",
            "certification_authority": "GO" if score >= 85.0 else "WATCH",
            "governance_override_indicators": {
                "deployment_blockers": False,
                "human_supervision_required": True,
                "release_authorization_override": False,
            },
        },
        "latest_release_certification": {
            "artifact_path": str(pack_root / "latest_executive_release_evidence.json"),
            "certification_status": "CERTIFIED" if score >= 85.0 else "WATCH",
            "certification_score": 100.0 if score >= 85.0 else 76.0,
            "release_authority": release_authority,
        },
        "rollout_governance_history": [
            {
                "analysis_id": f"{bundle_id}:production",
                "generated_at": "2026-06-23T20:53:15+00:00",
                "production_readiness_score": score,
                "production_readiness_status": "ok" if score >= 85.0 else "watch",
                "production_readiness_grade": "ready" if score >= 85.0 else "watch",
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
        "operational_freeze_history": [{"freeze_active": freeze_active}],
    }
    (bundle_dir / "production_rollout_validation.json").write_text(json.dumps(payload), encoding="utf-8")
    return bundle_dir


def test_production_audit_governance_service_ready_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.production_audit_governance_service")
    validation_root = tmp_path / "runtime" / "staging" / "production-rollout-validations"
    release_root = tmp_path / "runtime" / "staging" / "release-certifications"
    service = module.ProductionAuditGovernanceService(validation_root=validation_root, release_certification_root=release_root)
    _write_rollout_bundle(validation_root, "20260623T205315Z-production-audit-ready", score=97.0)

    latest = service.latest_operations_audit()
    history = service.operations_audit_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["operations_audit_authority"] == "GO"
    assert latest["audit_retention_indicators"]["retention_compliant"] is True
    assert latest["audit_completeness_indicators"]["audit_completeness_ready"] is True
    assert latest["latest_release_certification"]["release_authority"] == "GO"
    assert history["count"] >= 1
    assert history["operations_audit_history"][0]["operations_audit_authority"] == "GO"


def test_production_audit_governance_service_watch_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.production_audit_governance_service")
    validation_root = tmp_path / "runtime" / "staging" / "production-rollout-validations"
    release_root = tmp_path / "runtime" / "staging" / "release-certifications"
    service = module.ProductionAuditGovernanceService(validation_root=validation_root, release_certification_root=release_root)
    _write_rollout_bundle(
        validation_root,
        "20260623T205315Z-production-audit-watch",
        score=74.0,
        warnings=["retention review required"],
        freeze_active=True,
        release_authority="WATCH",
    )

    latest = service.latest_operations_audit()

    assert latest["status"] == "watch"
    assert latest["operations_audit_authority"] == "WATCH"
    assert latest["audit_retention_indicators"]["retention_compliant"] is True
    assert latest["operations_audit_score"] < 85.0
    assert latest["warnings"]
