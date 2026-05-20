import json

from app.stabilization.runtime_cleanup import build_runtime_cleanup_dry_run, build_runtime_cleanup_report
from app.stabilization.telemetry_noise_reduction import build_telemetry_noise_reduction_report, reduce_telemetry_noise


def _assert_json_safe(payload):
    json.dumps(payload, default=str)


def test_telemetry_noise_reduction_is_json_safe_and_preserves_critical_alerts():
    payload = build_telemetry_noise_reduction_report(limit=25)
    _assert_json_safe(payload)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert payload["retained_count"] >= payload["critical_count"]
    assert payload["suppressed_count"] >= 0


def test_reduce_telemetry_noise_deduplicates_alerts():
    alerts = [
        {"type": "queue", "severity": "warning", "title": "Queue lag", "message": "Queue lag"},
        {"type": "queue", "severity": "warning", "title": "Queue lag", "message": "Queue lag"},
        {"type": "queue", "severity": "critical", "title": "Queue stall", "message": "Queue stall"},
    ]
    result = reduce_telemetry_noise(alerts=alerts, anomalies=[], limit=25)
    assert result["retained_count"] <= len(alerts)
    assert result["critical_count"] == 1
    _assert_json_safe(result)


def test_runtime_cleanup_defaults_to_dry_run_only():
    payload = build_runtime_cleanup_report(dry_run=True, confirmed=False, limit=25)
    _assert_json_safe(payload)
    assert payload["dry_run_only"] is True
    assert payload["confirmed"] is False
    assert isinstance(payload["would_cleanup"], list)


def test_runtime_cleanup_dry_run_is_safe():
    payload = build_runtime_cleanup_dry_run(confirmed=False, limit=25)
    _assert_json_safe(payload)
    assert payload["dry_run_only"] is True
    assert payload["confirmed"] is False

