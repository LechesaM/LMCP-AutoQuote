from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_cycle(root: Path, cycle_id: str, generated_at: str, readiness_score: float = 100.0) -> None:
    cycle_dir = root / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "governance_export": {
            "readiness_summary": {
                "readiness_score": readiness_score,
                "readiness_grade": "ready" if readiness_score >= 85 else "watch",
                "cadence": {"runs_last_7_days": 1, "average_gap_hours": 0.0},
            }
        },
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_export(root: Path, export_id: str, generated_at: str, readiness_score: float = 100.0, *, warn: bool = False) -> None:
    export_dir = root / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "export_id": export_id,
        "generated_at": generated_at,
        "readiness_summary": {
            "readiness_score": readiness_score,
            "readiness_grade": "ready" if readiness_score >= 85 else "watch",
            "trend_summary": {"trend": "stable", "delta": 0.0},
            "cadence": {
                "runs_last_7_days": 1,
                "average_gap_hours": 0.0,
                "most_recent_run_at": generated_at,
                "previous_run_at": "",
                "runs_total": 1,
            },
        },
        "governance_review_section": {
            "guidance": ["Review readiness score and trend", "Review rehearsal cadence"],
            "items": [
                {"item": "Review readiness score and trend", "status": "PASS"},
                {"item": "Review rehearsal cadence", "status": "PASS" if not warn else "WARN"},
                {"item": "Review rollback, queue, telemetry and submission-lock evidence", "status": "PASS"},
            ],
        },
        "operator_sign_off_section": {
            "guidance": ["Review latest evidence pack and readiness score."],
            "items": [
                {"item": "Confirm latest evidence pack reviewed", "required": True, "status": "PASS"},
                {"item": "Confirm dry-run protections remain active", "required": True, "status": "PASS"},
                {"item": "Confirm submission locks remain enforced", "required": True, "status": "PASS"},
            ],
        },
        "latest_evidence_pack": {
            "pack_id": f"pack-{export_id}",
            "generated_at": generated_at,
            "readiness_score": readiness_score,
            "readiness_grade": "ready" if readiness_score >= 85 else "watch",
            "summary_counts": {"PASS": 10, "WARN": 0, "FAIL": 0},
            "trend": "stable",
        },
        "PASS/WARN/FAIL_trends": {
            "latest_run_counts": {"PASS": 54, "WARN": 0, "FAIL": 0},
            "summary": {"PASS": 10, "WARN": 0, "FAIL": 0},
        },
        "queue_stability_summary": {"status": "PASS"},
        "rollback_evidence_summary": {"status": "PASS"},
        "telemetry_health_summary": {"status": "PASS"},
        "submission_lock_verification": {
            "status": "PASS" if not warn else "WARN",
            "verified": True,
            "verified_read_only": True,
            "evidence": {"exists": True, "lock_file": "/Users/cash/Documents/runtime/staging/go_live_guards/submission_locks.json"},
        },
        "dry_run_enforcement_verification": {
            "status": "PASS" if not warn else "WARN",
            "verified": True,
            "evidence": {"dry_run_guarantees": {"live_submissions": False}},
        },
        "no_go_condition_summary": {"status": "PASS" if not warn else "WARN", "indicators": [] if not warn else ["operator_review_required"]},
        "pilot_authorization_recommendation": "authorise_pilot" if not warn else "review_required",
        "summary_counts": {"PASS": 5, "WARN": 0, "FAIL": 0},
    }
    (export_dir / "pilot_rehearsal_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_pilot_review_board_service_reports_institutional_readiness(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_review_board_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-1", "2026-06-23T11:30:52+00:00", 100.0)
    _write_export(export_root, "export-1", "2026-06-23T11:09:09+00:00", 100.0)

    service = module.PilotReviewBoardService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_review_board()
    history = service.review_board_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["review_board_score"] >= 85
    assert latest["review_board_status"] == "ok"
    assert latest["latest_session"]["review_id"] == "export-1"
    assert latest["institutional_review_summary"]["session_count"] == 1
    assert history["count"] == 1
    assert history["review_board_history"][0]["review_id"] == "export-1"
    assert history["no_go_review_history"][0]["status"] == "PASS"


def test_pilot_review_board_service_warns_on_exceptions_and_no_go(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_review_board_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-1", "2026-06-01T11:30:52+00:00", 100.0)
    _write_export(export_root, "export-1", "2026-06-01T11:09:09+00:00", 100.0, warn=True)

    service = module.PilotReviewBoardService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_review_board()

    assert latest["review_board_status"] == "watch"
    assert latest["outstanding_governance_actions"]
    assert latest["unresolved_operational_exceptions"]
    assert latest["warnings"]
