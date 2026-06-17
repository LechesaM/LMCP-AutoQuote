from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DIR", "/Users/cash/Documents/runtime/manual_production")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DB_PATH", "/Users/cash/Documents/runtime/manual_production/lmcp_operations.db")

from app.api import telemetry_contracts as contracts
from app.api import telemetry_routes
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowStage
from app.main import app
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


def test_telemetry_routes_are_registered_and_read_only() -> None:
    telemetry_routes = {route.path: route for route in app.routes if route.path.startswith("/telemetry/")}
    expected_paths = {
        "/telemetry/dashboard",
        "/telemetry/source-health",
        "/telemetry/review-queue",
        "/telemetry/qualification",
        "/telemetry/operational-health",
    }

    assert expected_paths <= set(telemetry_routes)
    assert all(route.methods == {"GET"} for route in telemetry_routes.values())
    assert not any("submit" in path.lower() for path in telemetry_routes)


def test_telemetry_contract_builders_return_json_safe_payloads(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    payloads = [
        contracts.build_dashboard_telemetry_response(),
        contracts.build_source_health_telemetry_response(),
        contracts.build_review_queue_telemetry_response(),
        contracts.build_qualification_telemetry_response(),
        contracts.build_operational_health_telemetry_response(),
    ]

    for payload in payloads:
        json.dumps(payload, default=str)
        assert payload["generated_at"]
        assert payload["data_source"]
        assert payload["status"]


def test_missing_runtime_data_returns_fallback_response(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("missing runtime telemetry")

    monkeypatch.setattr(contracts, "get_dashboard_summary", _raise)
    payload = contracts.build_dashboard_telemetry_response()

    assert payload["data_source"] in {"runtime_fallback", "mixed", "fallback"}
    assert payload["status"] == "degraded"
    assert payload["province_distribution"] == []
    assert payload["opportunity_breakdown"] == []


def test_telemetry_calls_do_not_mutate_workflows(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    workflow_state_engine.record_transition("T-TELEMETRY", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    before = repo.fetch_recent(limit=20)

    responses = [
        telemetry_routes.get_dashboard_telemetry(),
        telemetry_routes.get_source_health_telemetry(),
        telemetry_routes.get_review_queue_telemetry(),
        telemetry_routes.get_qualification_telemetry(),
        telemetry_routes.get_operational_health_telemetry(),
    ]
    for response in responses:
        json.dumps(response, default=str)

    after = repo.fetch_recent(limit=20)
    assert after == before


def test_telemetry_routes_timeout_fallbacks(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    def _fake_timeout(callback, timeout_seconds, timeout_label, fallback=None):
        return fallback() if fallback is not None else {"status": "timeout", "data_source": "timeout"}

    monkeypatch.setattr(telemetry_routes, "run_with_timeout", _fake_timeout)

    dashboard = telemetry_routes.get_dashboard_telemetry()
    source_health = telemetry_routes.get_source_health_telemetry()
    review_queue = telemetry_routes.get_review_queue_telemetry()
    qualification = telemetry_routes.get_qualification_telemetry()
    operational = telemetry_routes.get_operational_health_telemetry()

    assert dashboard["status"] == "degraded"
    assert dashboard["data_source"] == "runtime_fallback"
    assert source_health["status"] == "degraded"
    assert review_queue["status"] == "degraded"
    assert qualification["status"] == "degraded"
    assert operational["status"] == "degraded"
