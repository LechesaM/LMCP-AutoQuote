from __future__ import annotations

import json

from app.core.runtime_paths import get_runtime_paths
from app.operations.health_snapshots import capture_health_snapshot, get_health_snapshots
from app.operations.runtime_alerts import get_runtime_alerts
from app.operations.runtime_metrics import get_runtime_metrics, record_runtime_snapshot
from app.operations.structured_logging import log_operation_event


def test_structured_logging_is_json_safe_and_contains_request_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    get_runtime_paths.cache_clear()
    record = log_operation_event("auth", "Login failed", request_id="req-123", operator_id="operator-1", details={"safe": True})
    assert record["request_id"] == "req-123"
    assert record["operator_id"] == "operator-1"
    json.dumps(record, default=str)


def test_runtime_snapshots_are_generated_and_json_safe(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    get_runtime_paths.cache_clear()
    snapshot = capture_health_snapshot()
    stored = record_runtime_snapshot(snapshot)
    snapshots = get_health_snapshots(limit=5)
    runtime = get_runtime_metrics(limit=5)
    json.dumps(snapshot, default=str)
    json.dumps(stored, default=str)
    json.dumps(snapshots, default=str)
    json.dumps(runtime, default=str)
    assert snapshots["total"] >= 1
    assert runtime["status"] in {"ok", "degraded"}


def test_runtime_alert_severity_is_valid(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    get_runtime_paths.cache_clear()
    alerts = get_runtime_alerts(limit=5)
    assert alerts["status"] in {"ok", "fallback"}
    assert set(alerts["alert_severities"]).issubset({"info", "warning", "critical"})
    json.dumps(alerts, default=str)

