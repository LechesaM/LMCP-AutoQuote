from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_validation_bundle(root: Path, validation_id: str, generated_at: str, payload: dict[str, object]) -> None:
    bundle_dir = root / validation_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record["validation_id"] = validation_id
    record["generated_at"] = generated_at
    (bundle_dir / "runtime_endurance_validation.json").write_text(json.dumps(record), encoding="utf-8")


def _ready_payload() -> dict[str, object]:
    return {
        "runtime_endurance_summary": {
            "runtime_endurance_score": 98.96,
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
        "checks": [
            {"level": "PASS", "name": "governance locks remain active", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "dry-run remains enabled", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "supervision remains mandatory", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "services remain healthy", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "observability endpoints remain reachable", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "continuity indicators remain stable", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "escalation readiness remains intact", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "no governance degradation occurs", "message": "ok", "score": 100.0, "remediation": ""},
        ],
        "sample_history": [
            {
                "analysis_id": "runtime-endurance:ready",
                "window_score": 98.96,
                "continuity_score": 98.75,
                "service_health_score": 100.0,
                "observability_score": 100.0,
                "escalation_score": 100.0,
                "governance_score": 95.0,
                "continuity_stable": True,
                "escalation_ready": True,
                "governance_degradation_detected": False,
                "sources": {
                    "executive_governance_index_status": "OK",
                    "continuity_readiness": {"continuity_governance_status": "ok"},
                    "incident_severity": {"incident_governance_status": "ok"},
                    "release_bundle": {"overall_status": "PASS", "overall_authority": "GO"},
                    "release_certification": {"status": "PASS", "release_governance_status": "ok"},
                },
            }
        ],
    }


def _warn_payload() -> dict[str, object]:
    return {
        "runtime_endurance_summary": {
            "runtime_endurance_score": 76.0,
            "runtime_endurance_status": "WARN",
            "runtime_endurance_grade": "watch",
            "overall_authority": "WATCH",
            "governance_locks_active": True,
            "dry_run_enabled": True,
            "supervision_mandatory": True,
            "services_healthy": True,
            "observability_endpoints_reachable": False,
            "escalation_readiness_intact": True,
            "continuity_indicators_stable": True,
            "no_governance_degradation_occurs": True,
        },
        "checks": [
            {"level": "PASS", "name": "governance locks remain active", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "dry-run remains enabled", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "supervision remains mandatory", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "services remain healthy", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "WARN", "name": "observability endpoints remain reachable", "message": "observability endpoints are not fully reachable in the staged evidence", "score": 75.0, "remediation": "Restore observability endpoints."},
            {"level": "PASS", "name": "continuity indicators remain stable", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "escalation readiness remains intact", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "no governance degradation occurs", "message": "ok", "score": 100.0, "remediation": ""},
        ],
        "sample_history": [
            {
                "analysis_id": "runtime-endurance:warn",
                "window_score": 76.0,
                "continuity_score": 94.0,
                "service_health_score": 100.0,
                "observability_score": 75.0,
                "escalation_score": 100.0,
                "governance_score": 90.0,
                "continuity_stable": True,
                "escalation_ready": True,
                "governance_degradation_detected": False,
                "sources": {
                    "executive_governance_index_status": "OK",
                    "continuity_readiness": {"continuity_governance_status": "ok"},
                    "incident_severity": {"incident_governance_status": "ok"},
                    "release_bundle": {"overall_status": "PASS", "overall_authority": "GO"},
                    "release_certification": {"status": "PASS", "release_governance_status": "ok"},
                },
            }
        ],
    }


def test_runtime_remediation_service_tracks_ready_and_warn_paths(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.runtime_remediation_governance_service")
    validation_root = tmp_path / "runtime" / "staging" / "runtime-endurance-validations"
    _write_validation_bundle(validation_root, "runtime-endurance-ready", "2026-06-24T00:00:00+00:00", _ready_payload())
    _write_validation_bundle(validation_root, "runtime-endurance-warn", "2026-06-24T01:00:00+00:00", _warn_payload())

    service = module.RuntimeRemediationGovernanceService(validation_root=validation_root)
    latest = service.latest_runtime_remediation()
    history = service.runtime_remediation_history(limit=5)

    assert latest["status"] == "watch"
    assert latest["runtime_remediation_status"] == "watch"
    assert latest["runtime_remediation_summary"]["open_remediation_count"] >= 1
    assert latest["runtime_remediation_summary"]["resolved_remediation_count"] >= 1
    assert latest["remediation_readiness_score"] < 85.0
    assert latest["warning_indicators"]["observability_failure_warning"] is True
    assert latest["remediation_escalation_indicators"]["governance_degradation_found"] is False
    assert latest["governance_recovery_tracking"]["governance_recovery_ready"] is False
    assert latest["remediation_governance_history"]["remediation_count"] >= 1
    assert history["count"] >= 1
    assert history["runtime_remediation_history"]
    assert history["remediation_governance_history"]["analysis_count"] >= 1


def test_runtime_remediation_service_reports_ok_for_all_clear(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.runtime_remediation_governance_service")
    validation_root = tmp_path / "runtime" / "staging" / "runtime-endurance-validations"
    _write_validation_bundle(validation_root, "runtime-endurance-ready", "2026-06-24T00:00:00+00:00", _ready_payload())

    service = module.RuntimeRemediationGovernanceService(validation_root=validation_root)
    latest = service.latest_runtime_remediation()

    assert latest["status"] == "ok"
    assert latest["runtime_remediation_status"] == "ok"
    assert latest["runtime_remediation_summary"]["open_remediation_count"] == 0
    assert latest["runtime_remediation_summary"]["blocking_remediation_count"] == 0
    assert latest["warning_indicators"]["observability_failure_warning"] is False
    assert latest["remediation_governance_history"]["score_history"]["trend"] == "stable"
