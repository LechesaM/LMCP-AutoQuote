from __future__ import annotations

import json
from pathlib import Path

from app.api import live_telemetry_adapters as live_adapters
from app.api import telemetry_routes
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowStage
from app.harvest.source_health import record_failure, record_success
from app.harvest.source_registry import load_source_registry
from app.persistence.repositories import WorkflowRepository


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
    return runtime_dir


def _seed_workflow_data() -> None:
    workflow_state_engine.record_transition("T-LIVE-1", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-LIVE-1", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-LIVE-1", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-LIVE-1", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition("T-LIVE-1", WorkflowStage.QUOTE_GENERATED, WorkflowStage.APPROVAL_REQUIRED, "op", "approval required")

    workflow_state_engine.record_transition("T-LIVE-2", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-LIVE-2", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-LIVE-2", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-LIVE-2", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition("T-LIVE-2", WorkflowStage.QUOTE_GENERATED, WorkflowStage.APPROVAL_REQUIRED, "op", "approval required")
    workflow_state_engine.record_transition("T-LIVE-2", WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "op", "approved")
    workflow_state_engine.record_transition("T-LIVE-2", WorkflowStage.APPROVED, WorkflowStage.REVIEW_READY, "op", "review ready")

    workflow_state_engine.refuse_workflow("T-LIVE-3", actor="op", reason="refused", details={"reason": "manual review"})


def _seed_sources() -> None:
    registry = load_source_registry()
    registry.add_source(
        {
            "id": "source-live-1",
            "name": "Live Source 1",
            "entity_type": "municipality",
            "source_tier": "tier_1",
            "base_url": "https://example.org/tenders/one",
            "harvest_url": "https://example.org/tenders/one/listing",
            "parser_type": "html",
            "province": "Gauteng",
            "is_active": True,
            "requires_browser": False,
            "requires_login": False,
        }
    )
    registry.add_source(
        {
            "id": "source-live-2",
            "name": "Live Source 2",
            "entity_type": "municipality",
            "source_tier": "tier_2",
            "base_url": "https://example.org/tenders/two",
            "harvest_url": "https://example.org/tenders/two/listing",
            "parser_type": "html",
            "province": "Western Cape",
            "is_active": True,
            "requires_browser": True,
            "requires_login": False,
        }
    )
    record_success("source-live-1", response_time_seconds=0.15)
    record_failure("source-live-2", parser_failure=True)


def test_live_telemetry_adapters_return_json_safe_runtime_data(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_data()
    _seed_sources()

    dashboard = live_adapters.get_live_dashboard_telemetry()
    source_health = live_adapters.get_live_source_health_telemetry()
    review_queue = live_adapters.get_live_review_queue_telemetry()
    qualification = live_adapters.get_live_qualification_telemetry()
    operational = live_adapters.get_live_operational_health_telemetry()

    for payload in [dashboard, source_health, review_queue, qualification, operational]:
        json.dumps(payload, default=str)
        assert payload["generated_at"]
        assert payload["data_source"] in {"runtime", "persistence", "mixed", "fallback"}
        assert payload["status"] in {"ok", "degraded", "healthy", "failing"}

    assert dashboard["total_harvested_rfqs"] >= 2
    assert source_health["total_sources"] == 2
    assert review_queue["operator_capacity"] == 1000
    assert qualification["go_count"] >= 0
    assert operational["status"] in {"healthy", "degraded", "failing"}


def test_live_telemetry_is_read_only(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_data()

    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    before = repo.fetch_recent(limit=50)

    responses = [
        telemetry_routes.get_dashboard_telemetry(),
        telemetry_routes.get_source_health_telemetry(),
        telemetry_routes.get_review_queue_telemetry(),
        telemetry_routes.get_qualification_telemetry(),
        telemetry_routes.get_operational_health_telemetry(),
    ]
    for response in responses:
        json.dumps(response, default=str)

    after = repo.fetch_recent(limit=50)
    assert after == before


def test_missing_runtime_data_returns_fallback(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("runtime unavailable")

    monkeypatch.setattr(live_adapters, "get_dashboard_summary", _raise)
    monkeypatch.setattr(live_adapters, "build_pilot_readiness_report", _raise)
    monkeypatch.setattr(live_adapters, "build_operational_report", _raise)
    monkeypatch.setattr(live_adapters, "get_system_health", _raise)
    monkeypatch.setattr(live_adapters, "get_metrics_snapshot", _raise)
    monkeypatch.setattr(live_adapters, "load_source_registry", _raise)
    monkeypatch.setattr(live_adapters, "get_source_health", _raise)
    monkeypatch.setattr(live_adapters, "get_pending_approval_queue", _raise)
    monkeypatch.setattr(live_adapters, "get_review_ready_queue", _raise)
    monkeypatch.setattr(live_adapters, "get_proof_capture_queue", _raise)
    monkeypatch.setattr(live_adapters, "get_refused_queue", _raise)
    monkeypatch.setattr(live_adapters, "get_queue_health", _raise)
    monkeypatch.setattr(live_adapters, "get_queue_summary", _raise)
    monkeypatch.setattr(live_adapters, "build_tender_success_analytics", _raise)
    monkeypatch.setattr(live_adapters, "get_workflow_summary", _raise)
    monkeypatch.setattr(live_adapters, "get_persistence_health", _raise)

    dashboard = live_adapters.get_live_dashboard_telemetry()
    source_health = live_adapters.get_live_source_health_telemetry()
    review_queue = live_adapters.get_live_review_queue_telemetry()
    qualification = live_adapters.get_live_qualification_telemetry()
    operational = live_adapters.get_live_operational_health_telemetry()

    assert dashboard["data_source"] == "fallback"
    assert source_health["data_source"] == "fallback"
    assert review_queue["data_source"] == "fallback"
    assert qualification["data_source"] == "fallback"
    assert operational["data_source"] == "fallback"


def test_review_queue_capacity_defaults_to_one_thousand(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_data()

    review_queue = live_adapters.get_live_review_queue_telemetry()

    assert review_queue["operator_capacity"] == 1000
    assert review_queue["operator_capacity_remaining"] <= 1000
    assert review_queue["operator_capacity_used"] >= 0
