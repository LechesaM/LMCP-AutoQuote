from __future__ import annotations

import json
from pathlib import Path

from app.api import operator_workflow_contracts as contracts
from app.api import operator_workflow_routes
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowStage
from app.harvest.source_health import record_failure, record_success
from app.harvest.source_registry import load_source_registry
from app.main import app
from app.persistence.repositories import WorkflowRepository


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
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


def _seed_runtime() -> None:
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "op", "quote")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.QUOTE_GENERATED, WorkflowStage.APPROVAL_REQUIRED, "op", "approval required")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "op", "approved")
    workflow_state_engine.record_transition("T-OPS-1", WorkflowStage.APPROVED, WorkflowStage.REVIEW_READY, "op", "review ready")

    workflow_state_engine.record_transition("T-OPS-2", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-OPS-2", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-OPS-2", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")
    workflow_state_engine.refuse_workflow("T-OPS-3", actor="op", reason="manual review", details={"reason": "manual review required"})

    registry = load_source_registry()
    registry.add_source(
        {
            "id": "ops-source-1",
            "name": "Operations Source 1",
            "entity_type": "municipality",
            "source_tier": "tier_1",
            "base_url": "https://example.org/one",
            "harvest_url": "https://example.org/one/listing",
            "parser_type": "html",
            "province": "Gauteng",
            "is_active": True,
            "requires_browser": False,
            "requires_login": False,
        }
    )
    record_success("ops-source-1", response_time_seconds=0.16)
    record_failure("ops-source-1", parser_failure=True)


def test_operator_workflow_routes_are_registered_and_read_only() -> None:
    routes = {route.path: route for route in app.routes if route.path.startswith("/operations/")}
    expected_paths = {
        "/operations/rfqs",
        "/operations/rfqs/{tender_id}",
        "/operations/qualification-insights",
        "/operations/pricing-evidence",
        "/operations/source-health-details",
    }

    assert expected_paths <= set(routes)
    assert all(route.methods == {"GET"} for route in routes.values())
    assert not any("submit" in path.lower() for path in routes)


def test_operator_workflow_contracts_return_json_safe_payloads(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()

    payloads = [
        contracts.get_operator_workflow_rows(),
        contracts.get_operator_workflow_detail("T-OPS-1"),
        contracts.get_qualification_insights(),
        contracts.get_pricing_evidence_overview(),
        contracts.get_source_health_details(),
    ]

    for payload in payloads:
        json.dumps(payload, default=str)
        assert payload["generated_at"]
        assert payload["data_source"]

    assert payloads[0]["rows"]
    assert payloads[1]["tender_id"] == "T-OPS-1"


def test_missing_runtime_data_returns_safe_fallback(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("runtime unavailable")

    monkeypatch.setattr(contracts, "get_dashboard_summary", _raise)
    monkeypatch.setattr(contracts, "load_source_registry", _raise)

    assert contracts.get_operator_workflow_rows()["data_source"] == "fallback"
    assert contracts.get_operator_workflow_detail("missing")["data_source"] == "fallback"
    assert contracts.get_qualification_insights()["data_source"] == "fallback"
    assert contracts.get_pricing_evidence_overview()["data_source"] == "fallback"
    assert contracts.get_source_health_details()["data_source"] == "fallback"


def test_operator_workflow_contracts_do_not_mutate_state(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_runtime()

    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    before = repo.fetch_recent(limit=50)

    responses = [
        operator_workflow_routes.list_rfqs(),
        operator_workflow_routes.get_rfq_detail("T-OPS-1"),
        operator_workflow_routes.qualification_insights(),
        operator_workflow_routes.pricing_evidence(),
        operator_workflow_routes.source_health_details(),
    ]
    for response in responses:
        json.dumps(response, default=str)

    after = repo.fetch_recent(limit=50)
    assert after == before
