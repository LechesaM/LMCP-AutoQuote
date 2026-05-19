from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.dashboard import dashboard_service, health_views, operator_actions_service, report_views, workflow_queue_service
from app.domain.workflow import WorkflowStage
from app.main import app
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

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    monkeypatch.setattr(workflow_state_engine, "_emit_audit_event", lambda **_: None)

    monkeypatch.setattr(audit_trail_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", runtime_dir / "audit_trail")
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", runtime_dir / "audit_trail" / "audit_events.json")
    async def _noop_publish_dashboard_event(**_: object) -> None:
        return None

    monkeypatch.setattr(audit_trail_service, "publish_dashboard_event", _noop_publish_dashboard_event)
    audit_trail_service.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _seed_dashboard_data() -> None:
    workflow_state_engine.record_transition("T-APPROVAL", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-APPROVAL", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-APPROVAL", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-APPROVAL", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition(
        "T-APPROVAL",
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        "op",
        "approval required",
    )

    workflow_state_engine.record_transition("T-APPROVED", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-APPROVED", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-APPROVED", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-APPROVED", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition(
        "T-APPROVED",
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        "op",
        "approval required",
    )
    workflow_state_engine.record_transition(
        "T-APPROVED",
        WorkflowStage.APPROVAL_REQUIRED,
        WorkflowStage.APPROVED,
        "op",
        "approved",
    )

    workflow_state_engine.record_transition("T-REVIEW", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-REVIEW", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-REVIEW", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-REVIEW", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition(
        "T-REVIEW",
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        "op",
        "approval required",
    )
    workflow_state_engine.record_transition(
        "T-REVIEW",
        WorkflowStage.APPROVAL_REQUIRED,
        WorkflowStage.APPROVED,
        "op",
        "approved",
    )
    workflow_state_engine.record_transition(
        "T-REVIEW",
        WorkflowStage.APPROVED,
        WorkflowStage.REVIEW_READY,
        "op",
        "review ready",
    )

    workflow_state_engine.record_transition("T-PROOF", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-PROOF", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-PROOF", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-PROOF", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition(
        "T-PROOF",
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        "op",
        "approval required",
    )
    workflow_state_engine.record_transition(
        "T-PROOF",
        WorkflowStage.APPROVAL_REQUIRED,
        WorkflowStage.APPROVED,
        "op",
        "approved",
    )
    workflow_state_engine.record_transition(
        "T-PROOF",
        WorkflowStage.APPROVED,
        WorkflowStage.REVIEW_READY,
        "op",
        "review ready",
    )
    workflow_state_engine.record_transition(
        "T-PROOF",
        WorkflowStage.REVIEW_READY,
        WorkflowStage.PROOF_RECORDED,
        "op",
        "proof recorded",
    )

    workflow_state_engine.refuse_workflow("T-REFUSED", actor="op", reason="refused", details={"reason": "not suitable"})
    workflow_state_engine.refuse_workflow("T-ARCHIVED", actor="op", reason="refused", details={"reason": "not suitable"})
    workflow_state_engine.archive_workflow("T-ARCHIVED", actor="op", reason="archived", details={})


def test_dashboard_summary_loads(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_dashboard_data()

    summary = dashboard_service.get_dashboard_summary(limit=50)

    assert summary["pending_approvals"] == 1
    assert summary["pending_review_ready"] == 1
    assert summary["pending_proof_capture"] == 1
    assert summary["refused_workflows"] == 1
    assert summary["archived_workflows"] == 1
    assert summary["persistence_health"]["status"] in {"healthy", "degraded"}


def test_workflow_queues_return_correctly(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_dashboard_data()

    assert len(workflow_queue_service.get_pending_approval_queue()) == 1
    assert len(workflow_queue_service.get_review_ready_queue()) == 1
    assert len(workflow_queue_service.get_proof_capture_queue()) == 1
    assert len(workflow_queue_service.get_refused_queue()) == 1
    assert len(workflow_queue_service.get_archived_queue()) == 1


def test_operator_archive_action_works(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    workflow_state_engine.refuse_workflow("T-ARCHIVE", actor="op", reason="refused", details={"note": "prepare archive"})

    result = operator_actions_service.archive_workflow("T-ARCHIVE", actor="Dana", reason="operator archive", details={"note": "done"})

    assert result["stage"] == WorkflowStage.ARCHIVED.value
    assert workflow_state_engine.get_current_state("T-ARCHIVE").stage is WorkflowStage.ARCHIVED


def test_operator_refuse_action_works(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    workflow_state_engine.record_transition("T-REFUSE", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")

    result = operator_actions_service.refuse_workflow("T-REFUSE", actor="Dana", reason="operator refuse", details={"note": "blocked"})

    assert result["stage"] == WorkflowStage.REFUSED.value
    assert workflow_state_engine.get_current_state("T-REFUSE").stage is WorkflowStage.REFUSED


def test_invalid_operator_transitions_blocked(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    operator_actions_service.refuse_workflow("T-BLOCK", actor="Dana", reason="refuse", details={})
    operator_actions_service.archive_workflow("T-BLOCK", actor="Dana", reason="archive", details={})

    with pytest.raises(ValueError):
        operator_actions_service.refuse_workflow("T-BLOCK", actor="Dana", reason="should fail", details={})


def test_dashboard_health_summary_loads(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_dashboard_data()

    health = health_views.get_dashboard_health()

    assert health["status"] in {"healthy", "degraded"}
    assert "system_health" in health
    assert "summary" in health


def test_persistence_health_visible(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_dashboard_data()

    summary = dashboard_service.get_operational_summary()

    assert "persistence" in summary
    assert summary["persistence"]["status"] in {"healthy", "degraded"}


def test_monitoring_integration_visible(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_dashboard_data()

    report = report_views.get_operational_report_view()

    assert "dashboard_summary" in report
    assert "operational_summary" in report


def test_audit_events_emitted_for_operator_actions(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    audit_file = audit_trail_service.AUDIT_FILE

    operator_actions_service.add_operator_note("T-NOTE", actor="Dana", note="Needs review", details={"kind": "note"})
    operator_actions_service.acknowledge_warning("T-NOTE", actor="Dana", warning="Check margin", details={"kind": "warning"})

    events = json.loads(audit_file.read_text(encoding="utf-8"))
    event_types = {item.get("event_type") for item in events}
    assert "operator_note" in event_types
    assert "operator_acknowledge_warning" in event_types


def test_dashboard_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/dashboard/summary" in paths
    assert "/dashboard/workflows" in paths
    assert "/dashboard/refusals" in paths
    assert "/dashboard/health" in paths
    assert "/dashboard/queues" in paths
    assert "/dashboard/archive" in paths
    assert "/dashboard/refuse" in paths
    assert "/dashboard/operator-note" in paths
