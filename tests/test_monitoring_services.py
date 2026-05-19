from __future__ import annotations

import importlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.domain.workflow import WorkflowStage
from app.monitoring import health_service, metrics_service, reporting_service, runtime_diagnostics, workflow_monitor
from app.persistence import db as persistence_db
from app.persistence.repositories import WorkflowRepository, get_persistence_health, reset_persistence_health
from app.services import audit_trail_service


def _prepare_runtime(monkeypatch, tmp_path: Path) -> Path:
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
    monkeypatch.setenv("LMCP_OBSERVABILITY_ENABLED", "1")
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    metrics_service.reset_test_metrics()
    reset_persistence_health()

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    monkeypatch.setattr(workflow_state_engine, "_emit_audit_event", lambda **_: None)

    monkeypatch.setattr(audit_trail_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", runtime_dir / "audit_trail")
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", runtime_dir / "audit_trail" / "audit_events.json")
    audit_trail_service.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _write_state(
    tender_id: str,
    stage: WorkflowStage,
    updated_at: str,
    *,
    details: dict | None = None,
) -> None:
    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    repo.append_state(
        {
            "tender_id": tender_id,
            "stage": stage.value,
            "workflow_stage": stage.value,
            "updated_at": updated_at,
            "created_at": updated_at,
            "details": details or {},
            "payload": details or {},
        }
    )


def test_health_service_returns_healthy_state(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    health = health_service.get_system_health()

    assert health["status"] in {"healthy", "degraded"}
    component_names = {item["component"] for item in health["components"]}
    assert {"runtime", "db", "workflow_engine", "audit_service", "router_registry", "persistence"} <= component_names
    db_component = next(item for item in health["components"] if item["component"] == "db")
    assert db_component["details"]["db_file_present"] is True


def test_runtime_diagnostics_detects_missing_dir(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audit_trail").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)

    paths = RuntimePaths.from_environ(
        {
            "LMCP_PROJECT_ROOT": str(tmp_path),
            "LMCP_RUNTIME_DIR": str(runtime_dir),
            "LMCP_MANUAL_PRODUCTION_DIR": str(manual_dir),
            "LMCP_MANUAL_PRODUCTION_DB_PATH": str(manual_dir / "lmcp_operations.db"),
        }
    )
    report = runtime_diagnostics.get_runtime_diagnostics(paths=paths)

    assert report["status"] == "degraded"
    assert "health_dir" in report["missing_directories"]


def test_metrics_increment_correctly() -> None:
    metrics_service.reset_test_metrics()
    metrics_service.increment_metric("workflow_failures")
    metrics_service.increment_metric("workflow_failures", 2)
    snapshot = metrics_service.get_metrics_snapshot()

    assert snapshot["metrics"]["workflow_failures"] == 3


def test_workflow_summary_counts_correctly(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    tender_id = "T-SUMMARY"
    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.QUOTE_GENERATED, WorkflowStage.APPROVAL_REQUIRED, "op", "approval required")

    summary = workflow_monitor.get_workflow_summary()

    assert summary["total_workflows"] == 1
    assert summary["stage_counts"][WorkflowStage.APPROVAL_REQUIRED.value] == 1
    assert summary["approvals_pending"] == 1


def test_stuck_workflow_detection_works(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    tender_id = "T-STUCK"
    old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()

    monkeypatch.setattr(workflow_state_engine, "_now_iso", lambda: old_timestamp)
    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")

    stuck = workflow_monitor.find_stuck_workflows(stuck_after_minutes=60)

    assert stuck["count"] == 1
    assert stuck["items"][0]["tender_id"] == tender_id


def test_invalid_workflow_detection_works(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    tender_id = "T-INVALID"

    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    repo.append_state(
        {
            "tender_id": tender_id,
            "stage": WorkflowStage.REVIEW_READY.value,
            "workflow_stage": WorkflowStage.REVIEW_READY.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "details": {},
            "payload": {},
        }
    )

    invalid = workflow_monitor.find_invalid_workflows()

    assert invalid["count"] == 1
    assert invalid["items"][0]["tender_id"] == tender_id


def test_persistence_failures_tracked_safely(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(persistence_db, "connection_scope", _raise)

    workflow_state_engine.record_transition(
        "T-FAIL",
        WorkflowStage.DISCOVERED,
        WorkflowStage.EXTRACTED,
        "op",
        "discover",
    )

    health = get_persistence_health()
    assert health["write_failures"] > 0


def test_reporting_service_generates_summaries(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    workflow_state_engine.record_transition(
        "T-REPORT",
        WorkflowStage.DISCOVERED,
        WorkflowStage.EXTRACTED,
        "op",
        "discover",
    )

    report = reporting_service.build_operational_report(limit=50)
    text = reporting_service.render_operational_report_text(report)

    assert "system_health" in report
    assert "workflow_summary" in report
    assert "System status" in text


def test_health_endpoints_are_registered() -> None:
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/health/system" in paths
    assert "/health/workflows" in paths
