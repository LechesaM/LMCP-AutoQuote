from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.dashboard import dashboard_service
from app.domain.workflow import WorkflowStage
from app.pilot import (
    PilotMode,
    assert_pilot_guardrails,
    build_controlled_pilot_dashboard,
    build_pilot_readiness_report,
    calculate_readiness_score,
    calculate_success_rate,
    get_pilot_execution_metadata,
    get_pilot_failures,
    get_pilot_metrics,
    get_pilot_mode,
    get_pilot_signoffs,
    get_pilot_summary,
    get_pilot_successes,
    record_pilot_run,
    record_signoff,
    render_pilot_readiness_text,
)
from app.pilot.pilot_metrics import reset_pilot_metrics
from app.persistence import db as persistence_db


def _prepare_runtime(monkeypatch, tmp_path: Path, pilot_mode: str = "supervised_live") -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audit_trail").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_PILOT_MODE", pilot_mode)
    monkeypatch.setenv("LMCP_OBSERVABILITY_ENABLED", "1")

    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    reset_pilot_metrics()
    persistence_db._INITIALIZED = False
    persistence_db._INITIALIZED_PATH = None

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    return runtime_dir


def _count_rows(db_path: Path, table: str) -> int:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0] if row else 0)
    finally:
        connection.close()


def test_pilot_mode_enforcement(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, pilot_mode="disabled")
    assert get_pilot_mode() is PilotMode.DISABLED
    assert get_pilot_execution_metadata()["pilot_enabled"] is False


def test_pilot_guardrails_block_invalid_operations(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        assert_pilot_guardrails(
            {
                "operator": "Operator A",
                "workflow_stage": "proof_recorded",
                "final_submission_attempted": True,
                "proof_confirmed": True,
            }
        )


def test_pilot_runs_persist_correctly(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"

    result = record_pilot_run(
        {
            "tender_id": "P-001",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator A",
            "actor": "Operator A",
            "outcome": "completed",
            "status": "recorded",
            "warnings": [],
            "failures": [],
            "recovery_events": [],
            "proof_confirmed": True,
        }
    )

    assert result["tender_id"] == "P-001"
    assert (runtime_dir / "manual_production" / "pilot_runs.jsonl").exists()
    assert _count_rows(db_path, "pilot_run_records") == 1
    assert get_pilot_summary()["total_runs"] == 1
    assert get_pilot_metrics()["rfqs_processed"] == 1


def test_pilot_signoffs_persist_correctly(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"

    signoff = record_signoff(
        {
            "tender_id": "P-002",
            "workflow_stage": "approval_required",
            "signoff_type": "approval",
            "signoff_status": "signed",
            "operator": "Operator B",
            "actor": "Operator B",
            "note": "approved for pilot",
        }
    )

    assert signoff["signoff_type"] == "approval"
    assert (runtime_dir / "manual_production" / "pilot_signoffs.jsonl").exists()
    assert _count_rows(db_path, "pilot_signoff_records") == 1
    assert get_pilot_signoffs()[0]["tender_id"] == "P-002"


def test_readiness_score_generates(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    record_pilot_run(
        {
            "tender_id": "P-003",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator C",
            "actor": "Operator C",
            "outcome": "completed",
            "status": "recorded",
            "proof_confirmed": True,
        }
    )
    record_signoff(
        {
            "tender_id": "P-003",
            "workflow_stage": "proof_recorded",
            "signoff_type": "proof",
            "signoff_status": "signed",
            "operator": "Operator C",
            "actor": "Operator C",
        }
    )

    report = build_pilot_readiness_report()
    assert report["pilot_readiness_score"] >= 0
    assert "Pilot readiness score" in render_pilot_readiness_text(report)


def test_pilot_metrics_calculate_correctly(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    record_pilot_run(
        {
            "tender_id": "P-004",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator D",
            "actor": "Operator D",
            "outcome": "completed",
            "status": "recorded",
            "proof_confirmed": True,
        }
    )
    record_pilot_run(
        {
            "tender_id": "P-005",
            "workflow_stage": "review_ready",
            "pilot_mode": "supervised_live",
            "operator": "Operator D",
            "actor": "Operator D",
            "outcome": "refused",
            "status": "refused",
            "warnings": ["blocked workflow"],
        }
    )

    metrics = get_pilot_metrics()
    assert metrics["rfqs_processed"] == 2
    assert metrics["rfqs_refused"] == 1
    assert calculate_success_rate() == pytest.approx(0.5)
    assert calculate_readiness_score() >= 0


def test_controlled_pilot_dashboard_reads_persisted_wave_records(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    wave_root = runtime_dir / "manual_production" / "pilot_wave_001"

    for idx in range(1, 6):
        pilot_dir = wave_root / f"WAVE1-0{idx}"
        logs_dir = pilot_dir / "submission_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (pilot_dir / "rfq_source").mkdir(parents=True, exist_ok=True)
        (pilot_dir / "pilot_manifest.json").write_text("{}", encoding="utf-8")
        (logs_dir / "pilot_status.json").write_text(
            json.dumps(
                {
                    "rfq_number": f"RFQ-{idx}",
                    "tender_id": f"RFQ-{idx}",
                    "status": "submitted",
                    "submission_ready": True,
                    "manual_submission_recorded": True,
                    "latest_run": {
                        "status": "approved",
                        "quote_pack_quality_status": "approval_ready",
                        "approval_blocked": False,
                        "submission_ready": True,
                        "blocker": "",
                    },
                    "latest_submission_proof": {
                        "status": "recorded",
                        "manual_submission_recorded": True,
                    },
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    dashboard = build_controlled_pilot_dashboard(limit=50)
    assert dashboard["rfqs_harvested"] == 5
    assert dashboard["rfqs_rejected"] == 0
    assert dashboard["rfqs_approved"] == 5
    assert dashboard["quote_packs_generated"] == 5
    assert dashboard["submission_records"] == 5
    assert dashboard["proof_records"] == 5
    assert dashboard["pilot_success_rate"] == 100.0
    assert dashboard["go_no_go"] == "HOLD"
    assert dashboard["pilot_wave"] == "stage_2_pilot_dashboard"


def test_operator_accountability_preserved(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        record_signoff(
            {
                "tender_id": "P-006",
                "workflow_stage": "approval_required",
                "signoff_type": "approval",
                "signoff_status": "signed",
                "note": "missing operator",
            }
        )


def test_no_autonomous_submission_enabled(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        assert_pilot_guardrails(
            {
                "operator": "Operator E",
                "workflow_stage": "proof_recorded",
                "final_submission_attempted": True,
                "proof_confirmed": True,
            }
        )


def test_warning_stage_runs_do_not_count_as_successful_pilot_runs(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    record_pilot_run(
        {
            "tender_id": "P-007",
            "workflow_stage": "approval_required",
            "pilot_mode": "supervised_live",
            "operator": "Operator E",
            "actor": "Operator E",
            "outcome": "warning",
            "status": "warning",
            "proof_confirmed": False,
        }
    )

    assert get_pilot_summary()["total_runs"] == 0
    assert calculate_success_rate() == 0.0

    record_pilot_run(
        {
            "tender_id": "P-008",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator E",
            "actor": "Operator E",
            "outcome": "completed",
            "status": "recorded",
            "proof_confirmed": True,
            "final_submission_attempted": False,
        }
    )

    summary = get_pilot_summary()
    assert summary["total_runs"] == 1
    assert summary["successful_runs"] == 1
    assert calculate_success_rate() == pytest.approx(1.0)


def test_workflow_integrity_preserved(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    state = workflow_state_engine.record_transition(
        "P-007",
        WorkflowStage.DISCOVERED,
        WorkflowStage.EXTRACTED,
        "operator",
        "discover",
    )
    assert state.stage is WorkflowStage.EXTRACTED
    assert workflow_state_engine.get_current_state("P-007").stage is WorkflowStage.EXTRACTED


def test_blocked_workflows_counted(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    record_pilot_run(
        {
            "tender_id": "P-008",
            "workflow_stage": "review_ready",
            "pilot_mode": "supervised_live",
            "operator": "Operator F",
            "actor": "Operator F",
            "outcome": "refused",
            "status": "refused",
        }
    )
    assert get_pilot_metrics()["blocked_workflows"] == 1
    assert get_pilot_failures()[0]["tender_id"] == "P-008"


def test_pilot_failures_reported(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    record_pilot_run(
        {
            "tender_id": "P-009",
            "workflow_stage": "review_ready",
            "pilot_mode": "supervised_live",
            "operator": "Operator G",
            "actor": "Operator G",
            "outcome": "failed",
            "status": "failed",
            "warnings": ["db unavailable"],
        }
    )
    assert any(item["tender_id"] == "P-009" for item in get_pilot_failures())


def test_pilot_recovery_events_tracked(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    record_pilot_run(
        {
            "tender_id": "P-010",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator H",
            "actor": "Operator H",
            "outcome": "completed",
            "status": "recorded",
            "recovery_events": ["queue recovery"],
            "proof_confirmed": True,
        }
    )
    metrics = get_pilot_metrics()
    assert metrics["recovery_events"] >= 1
    assert get_pilot_summary()["total_runs"] == 1


def test_dashboard_summary_includes_pilot_visibility(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    record_pilot_run(
        {
            "tender_id": "P-011",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator I",
            "actor": "Operator I",
            "outcome": "completed",
            "status": "recorded",
            "proof_confirmed": True,
        }
    )
    monkeypatch.setattr(
        dashboard_service,
        "build_controlled_pilot_dashboard",
        lambda limit=50: {
            "rfqs_harvested": 5,
            "rfqs_rejected": 1,
            "rfqs_approved": 2,
            "quote_packs_generated": 4,
            "submission_records": 3,
            "proof_records": 3,
            "pilot_success_rate": 80.0,
            "go_no_go": "HOLD",
            "pilot_wave": "stage_2_pilot_dashboard",
        },
    )

    summary = dashboard_service.get_dashboard_summary(limit=20)
    assert "pilot_mode" in summary
    assert "pilot_metrics" in summary
    assert "pilot_readiness_score" in summary
    assert summary["pilot_readiness_score"] >= 0
    assert summary["controlled_pilot_dashboard"]["rfqs_harvested"] == 5
