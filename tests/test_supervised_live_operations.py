from __future__ import annotations

import json
from pathlib import Path

from app.api.operations_runtime_contracts import (
    build_backup_validation_response,
    build_incidents_response,
    build_operator_analytics_response,
    build_runtime_alerts_response,
    build_runtime_metrics_response,
    build_source_reliability_response,
)
from app.api import operations_runtime_routes
from app.api.operations_runtime_routes import router
from app.operations.incident_tracker import get_incident_summary, record_incident
from app.core.runtime_paths import get_runtime_paths


def test_runtime_operations_contracts_are_json_safe() -> None:
    payloads = [
        build_runtime_metrics_response(limit=5),
        build_operator_analytics_response(limit=5),
        build_source_reliability_response(limit=5),
        build_incidents_response(limit=5),
        build_runtime_alerts_response(limit=5),
        build_backup_validation_response(),
    ]
    for payload in payloads:
        json.dumps(payload, default=str)
        assert "generated_at" in payload
        assert "data_source" in payload


def test_runtime_operations_router_is_read_only() -> None:
    paths = {route.path for route in router.routes}
    assert "/operations/runtime-metrics" in paths
    assert "/operations/operator-analytics" in paths
    assert "/operations/source-reliability" in paths
    assert "/operations/incidents" in paths
    assert "/operations/runtime-alerts" in paths
    assert "/operations/backup-validation" in paths
    for route in router.routes:
        methods = {method.upper() for method in getattr(route, "methods", set())}
        assert methods <= {"GET"}


def test_incident_tracker_is_append_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    get_runtime_paths.cache_clear()
    first = record_incident("parser_outage", "Parser outage", severity="critical", operator_id="op-1")
    second = record_incident("queue_overload", "Queue overload", severity="warning", operator_id="op-1")
    summary = get_incident_summary(limit=10)
    assert summary["total_incidents"] >= 2
    assert summary["incidents"][-1]["incident_id"] == second["incident_id"]
    assert first["incident_id"] != second["incident_id"]
    json.dumps(summary, default=str)


def test_runtime_operations_do_not_expose_mutation_routes() -> None:
    mutation_methods = {"POST", "PUT", "PATCH", "DELETE"}
    for route in router.routes:
        methods = {method.upper() for method in getattr(route, "methods", set())}
        assert not (methods & mutation_methods)


def test_runtime_operations_routes_timeout_fallbacks(monkeypatch) -> None:
    def _fake_timeout(callback, timeout_seconds, timeout_label, fallback=None):
        return fallback() if fallback is not None else {"status": "timeout", "data_source": "timeout"}

    monkeypatch.setattr(operations_runtime_routes, "run_with_timeout", _fake_timeout)

    runtime_metrics = operations_runtime_routes.runtime_metrics()
    operator_analytics = operations_runtime_routes.operator_analytics()
    source_reliability = operations_runtime_routes.source_reliability()
    incidents = operations_runtime_routes.incidents()
    runtime_alerts = operations_runtime_routes.runtime_alerts()
    backup_validation = operations_runtime_routes.backup_validation()

    assert runtime_metrics["status"] == "degraded"
    assert operator_analytics["status"] == "degraded"
    assert source_reliability["status"] == "degraded"
    assert incidents["status"] == "degraded"
    assert runtime_alerts["status"] == "degraded"
    assert backup_validation["status"] == "degraded"
