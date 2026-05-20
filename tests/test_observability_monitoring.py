from __future__ import annotations

import json

from app.api.observability_contracts import (
    build_observability_alerts_response,
    build_observability_anomalies_response,
    build_observability_grafana_response,
    build_observability_logs_response,
    build_observability_performance_response,
    build_observability_prometheus_response,
    build_observability_sentry_response,
    build_observability_sla_response,
    build_observability_uptime_response,
)
from app.api.observability_routes import router
from app.observability.grafana_dashboards import build_grafana_dashboard_bundle
from app.observability.log_aggregation import build_log_aggregation_summary
from app.observability.prometheus_metrics import build_prometheus_metrics_export
from app.observability.sentry_integration import build_sentry_status, get_sentry_config


def test_observability_contracts_are_json_safe() -> None:
    payloads = [
        build_observability_prometheus_response(limit=5),
        build_observability_grafana_response(limit=5),
        build_observability_sentry_response(),
        build_observability_sla_response(limit=5),
        build_observability_anomalies_response(limit=5),
        build_observability_alerts_response(limit=5),
        build_observability_logs_response(limit=5),
        build_observability_uptime_response(limit=5),
        build_observability_performance_response(limit=5),
        build_prometheus_metrics_export(limit=5),
        build_grafana_dashboard_bundle(limit=5),
        build_sentry_status(),
        build_log_aggregation_summary(limit=5),
    ]
    for payload in payloads:
        json.dumps(payload, default=str)
        assert "generated_at" in payload
        assert "data_source" in payload


def test_observability_prometheus_export_contains_help() -> None:
    payload = build_prometheus_metrics_export(limit=5)
    assert "# HELP" in payload["text"]
    assert "# TYPE" in payload["text"]
    json.dumps(payload, default=str)


def test_sentry_disables_safely_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("LMCP_ENABLE_SENTRY", raising=False)
    monkeypatch.delenv("LMCP_SENTRY_DSN", raising=False)
    config = get_sentry_config()
    payload = build_sentry_status()
    assert config.enabled is False
    assert payload["sentry"]["enabled"] is False
    json.dumps(payload, default=str)


def test_alert_routing_is_advisory_only() -> None:
    payload = build_observability_alerts_response(limit=5)
    assert payload["advisory_only"] is True
    assert all("targets" in route for route in payload["alerts"])
    json.dumps(payload, default=str)


def test_log_aggregation_redacts_secrets(tmp_path, monkeypatch) -> None:
    from app.core.runtime_paths import get_runtime_paths

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    get_runtime_paths.cache_clear()
    paths = get_runtime_paths()
    log_path = paths.manual_production_file("operations_logs.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        '{"category":"auth","message":"password=secret token=abc123","severity":"warning"}\n',
        encoding="utf-8",
    )
    payload = build_log_aggregation_summary(limit=5)
    redacted = " ".join(payload["redacted_samples"])
    assert "secret" not in redacted
    assert "abc123" not in redacted
    json.dumps(payload, default=str)


def test_observability_routes_are_read_only() -> None:
    paths = {route.path for route in router.routes}
    assert "/observability/prometheus" in paths
    assert "/observability/grafana" in paths
    assert "/observability/sentry" in paths
    assert "/observability/sla" in paths
    assert "/observability/anomalies" in paths
    assert "/observability/alerts" in paths
    assert "/observability/logs" in paths
    assert "/observability/uptime" in paths
    assert "/observability/performance" in paths
    for route in router.routes:
        methods = {method.upper() for method in getattr(route, "methods", set())}
        assert methods <= {"GET"}
