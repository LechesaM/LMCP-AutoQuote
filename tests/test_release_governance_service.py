from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_validation_bundle(root: Path, validation_id: str, *, status: str = "PASS", readiness_score: float = 96.0, warn: bool = False) -> Path:
    bundle_dir = root / validation_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "validation_id": validation_id,
        "generated_at": "2026-06-23T15:55:59+00:00",
        "overall_status": status,
        "overall_grade": "ready" if status == "PASS" else "watch" if status == "WARN" else "blocked",
        "readiness_summary": {
            "production_readiness_score": readiness_score,
            "production_readiness_status": "PASS" if status == "PASS" else "WARN" if status == "WARN" else "FAIL",
            "production_readiness_grade": "ready" if status == "PASS" else "watch" if status == "WARN" else "blocked",
            "summary_components": {
                "runtime_segmentation": readiness_score,
                "operator_access": readiness_score,
                "observability": readiness_score,
                "backup_restore": readiness_score,
                "disaster_recovery": readiness_score,
                "high_availability": readiness_score,
                "audit_retention": readiness_score,
                "deployment_readiness": readiness_score,
            },
        },
        "validation_sections": {
            "runtime_segmentation": {
                "production_runtime_segmentation_score": readiness_score,
                "production_runtime_segmentation_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "tenant_workspace_isolation": {"isolation_verified": True},
            },
            "operator_access": {
                "operator_access_governance_score": readiness_score,
                "operator_access_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "operator_access_details": {"operator_name": "governance", "operator_role": "supervisor"},
                "operator_access_risk_indicators": {"pending_approval_backlog": warn},
            },
            "observability": {
                "production_observability_governance_score": readiness_score,
                "production_observability_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "observability_readiness_indicators": {"worker_heartbeat": True},
                "observability_risk_indicators": {"telemetry_degradation": []},
            },
            "backup_restore": {
                "backup_restore_governance_score": readiness_score,
                "backup_restore_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "backup_restore_details": {"latest_pack_id": "pack-1"},
                "recovery_readiness_indicators": {"evidence_pack_available": True},
            },
            "disaster_recovery": {
                "disaster_recovery_governance_score": readiness_score,
                "disaster_recovery_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "recovery_readiness_indicators": {"final_readiness_cleared": status == "PASS"},
            },
            "high_availability": {
                "high_availability_governance_score": readiness_score,
                "high_availability_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "ha_readiness_indicators": {"queue_stable": status == "PASS"},
            },
            "audit_retention": {
                "audit_retention_governance_score": readiness_score,
                "audit_retention_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "audit_retention_details": {"cycle_count": 2},
                "audit_retention_indicators": {"cycle_history_available": True},
            },
            "deployment_readiness": {
                "deployment_readiness_governance_score": readiness_score,
                "deployment_readiness_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "deployment_readiness_indicators": {"executive_ready": True},
            },
        },
        "deployment_risk_indicators": {
            "deployment_risk": status != "PASS",
            "operator_access_risk": warn,
            "ha_risk": status != "PASS",
            "recovery_risk": status != "PASS",
        },
        "operator_access_risk_indicators": {"pending_approval_backlog": warn},
        "ha_readiness_indicators": {"queue_stable": status == "PASS"},
        "recovery_readiness_indicators": {"final_readiness_cleared": status == "PASS"},
        "environment_safety": {
            "status": "PASS",
            "details": {
                "lmcp_env": "staging",
                "lmcp_production_mode": "staging",
                "lmcp_allow_final_automation": "false",
                "lmcp_allow_degraded_startup": "true",
            },
            "blockers": [],
        },
        "submission_lock_verification": {
            "status": "PASS",
            "exists": True,
            "verified": True,
        },
        "dry_run_enforcement_verification": {
            "status": "PASS",
            "verified": True,
        },
        "validation_counts": {"PASS": 8 if status == "PASS" else 0, "WARN": 8 if status == "WARN" else 0, "FAIL": 8 if status == "FAIL" else 0},
        "warnings": [] if status == "PASS" else ["deployment readiness below threshold"],
        "governance_validation_history": [
            {
                "analysis_id": f"{validation_id}:release-gate",
                "generated_at": "2026-06-23T15:55:59+00:00",
                "production_readiness_score": readiness_score,
                "release_governance_score": readiness_score,
                "release_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "release_governance_authority": "GO" if status == "PASS" else "WATCH" if status == "WARN" else "NO_GO",
                "release_governance_grade": "ready" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "deployment_risk_indicators": {"deployment_risk": status != "PASS"},
                "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True, "history_available": True, "overall_validation_passed": status == "PASS"},
                "release_readiness_indicators": {"runtime_segmentation_ready": status == "PASS"},
                "release_authority_indicators": {"go_release_authority": status == "PASS", "watch_release_authority": status == "WARN", "no_go_release_authority": status == "FAIL", "active_authority": "GO" if status == "PASS" else "WATCH" if status == "WARN" else "NO_GO"},
                "unresolved_deployment_blockers": [] if status == "PASS" else ["deployment readiness below threshold"],
                "governance_override_authority": status != "PASS",
                "release_escalation_authority": status != "PASS",
                "production_rollout_readiness": status == "PASS",
                "production_rollout_readiness_status": "ready" if status == "PASS" else "watch" if status == "WARN" else "blocked",
                "summary_components": {"runtime_segmentation": readiness_score},
                "validation_counts": {"PASS": 8 if status == "PASS" else 0, "WARN": 8 if status == "WARN" else 0, "FAIL": 8 if status == "FAIL" else 0},
                "warnings": [] if status == "PASS" else ["deployment readiness below threshold"],
            }
        ],
        "latest_release_governance": {
            "analysis_id": f"{validation_id}:release-gate",
            "generated_at": "2026-06-23T15:55:59+00:00",
            "production_readiness_score": readiness_score,
            "release_governance_score": readiness_score,
            "release_governance_status": "ok" if status == "PASS" else "watch" if status == "WARN" else "blocked",
            "release_governance_authority": "GO" if status == "PASS" else "WATCH" if status == "WARN" else "NO_GO",
            "release_governance_grade": "ready" if status == "PASS" else "watch" if status == "WARN" else "blocked",
        },
    }
    (bundle_dir / "production_deployment_validation.json").write_text(json.dumps(payload), encoding="utf-8")
    return bundle_dir


def test_release_governance_service_ready_path(tmp_path) -> None:
    module = importlib.import_module("app.services.production_release_governance_service")
    service = module.ProductionReleaseGovernanceService(validation_root=tmp_path / "runtime" / "staging" / "production-deployment-validations")
    _write_validation_bundle(tmp_path / "runtime" / "staging" / "production-deployment-validations", "20260623T194749Z-production-ready", status="PASS", readiness_score=96.0)

    latest = service.latest_release_governance()
    history = service.release_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["release_governance_authority"] == "GO"
    assert latest["production_rollout_readiness"] is True
    assert latest["release_readiness_indicators"]["runtime_segmentation_ready"] is True
    assert history["count"] >= 1
    assert history["release_governance_history"][0]["release_governance_authority"] == "GO"


def test_release_governance_service_warn_path(tmp_path) -> None:
    module = importlib.import_module("app.services.production_release_governance_service")
    service = module.ProductionReleaseGovernanceService(validation_root=tmp_path / "runtime" / "staging" / "production-deployment-validations")
    _write_validation_bundle(tmp_path / "runtime" / "staging" / "production-deployment-validations", "20260623T194749Z-production-warn", status="WARN", readiness_score=72.0, warn=True)

    latest = service.latest_release_governance()

    assert latest["status"] in {"watch", "blocked"}
    assert latest["release_governance_authority"] in {"WATCH", "NO_GO"}
    assert latest["production_rollout_readiness"] is False
    assert latest["unresolved_deployment_blockers"]
