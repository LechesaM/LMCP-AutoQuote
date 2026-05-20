from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.runtime_paths import get_runtime_paths
from app.operations import runtime_metrics as runtime_metrics_module
from app.runtime.api_timeout_policy import build_api_timeout_policy
from app.runtime.retry_policy import build_retry_policy
from app.runtime.service_recovery import build_service_recovery_report
from app.runtime.stale_data_guard import build_stale_data_guard_report, get_last_safe_snapshot


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_runtime_metrics(monkeypatch, *, system_status: str = "healthy") -> None:
    monkeypatch.setattr(runtime_metrics_module, "get_metrics_snapshot", lambda: {"metrics": {"reviews_recorded": 6, "rate_limit_events": 0, "auth_failures": 0, "workflow_failures": 0, "persistence_failures": 0, "api_latency_ms": 18}})
    monkeypatch.setattr(runtime_metrics_module, "get_workflow_summary", lambda limit=100: {"total_workflows": 4, "updated_at": _iso_now()})
    monkeypatch.setattr(runtime_metrics_module, "get_queue_summary", lambda limit=100: {"queue_lag_minutes": 2, "summary": {"queueLagMinutes": 2}})
    monkeypatch.setattr(runtime_metrics_module, "get_source_health_summary", lambda limit=100: {"failing_sources": 0, "parser_failure_rate": 0.0, "healthy_sources": 5, "total_sources": 5})
    monkeypatch.setattr(runtime_metrics_module, "get_operator_capacity_snapshot", lambda: {"assigned_today": 10, "total_daily_capacity": 100})
    monkeypatch.setattr(runtime_metrics_module, "get_system_health", lambda: {"status": system_status, "production_mode": "supervised_live", "environment": "production"})
    monkeypatch.setattr(runtime_metrics_module, "get_persistence_health", lambda: {"status": "healthy", "db_available": True})
    monkeypatch.setattr(runtime_metrics_module, "get_redis_config", lambda: type("RedisConfig", (), {"backend": "local"})())
    monkeypatch.setattr(runtime_metrics_module, "redis_connection_ready", lambda: True)
    monkeypatch.setattr(runtime_metrics_module, "list_dlq", lambda: {"count": 0})
    monkeypatch.setattr(runtime_metrics_module, "get_backup_status", lambda: {"backup_age_warning": False, "latest_backup_age_days": 1, "latest_backup_dir": str(Path("/tmp/backup"))})
    monkeypatch.setattr(runtime_metrics_module, "validate_restore_readiness", lambda backup_dir: {"status": "healthy"})
    monkeypatch.setattr(runtime_metrics_module, "get_worker_supervision_report", lambda: {"stale_worker_count": 0})
    monkeypatch.setattr(runtime_metrics_module, "build_review_efficiency_analytics", lambda limit=100: {"rfqs_reviewed_per_hour": 3.0, "review_completion_time_minutes": 12.0})


def test_stale_data_guard_preserves_last_safe_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_runtime_paths.cache_clear()
    fresh = {
        "status": "ok",
        "generated_at": "2026-05-20T10:00:00+00:00",
        "data_source": "runtime",
        "telemetry_freshness_minutes": 1,
        "metrics": {"reviews_recorded": 6},
    }
    safe_report = build_stale_data_guard_report("runtime_metrics", fresh)
    assert safe_report["stale"] is False
    assert safe_report["data_source"] == "runtime"

    stale = {
        "status": "degraded",
        "generated_at": "2026-05-20T10:30:00+00:00",
        "data_source": "runtime",
        "telemetry_freshness_minutes": 30,
    }
    degraded_report = build_stale_data_guard_report("runtime_metrics", stale)
    assert degraded_report["stale"] is True
    assert degraded_report["data_source"] in {"runtime_safe_fallback", "fallback"}
    assert degraded_report["last_safe_snapshot"]["status"] == "ok"
    assert degraded_report["last_safe_snapshot_at"]
    assert degraded_report["warnings"]


def test_runtime_metrics_marks_degraded_state_and_uses_safe_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_runtime_paths.cache_clear()
    _seed_runtime_metrics(monkeypatch, system_status="healthy")
    fresh = runtime_metrics_module.get_runtime_metrics(limit=10)
    assert fresh["stale_telemetry"] is False
    assert fresh["degraded_state"] is False
    assert fresh["telemetry_state"] == "fresh"
    assert fresh["metrics"]["stability_score"] >= 0.0
    assert fresh["last_safe_snapshot_at"]

    _seed_runtime_metrics(monkeypatch, system_status="unhealthy")
    degraded = runtime_metrics_module.get_runtime_metrics(limit=10)
    assert degraded["stale_telemetry"] is True
    assert degraded["degraded_state"] is True
    assert degraded["telemetry_state"] == "stale"
    assert degraded["last_safe_snapshot"]
    assert degraded["status"] in {"degraded", "failing"}
    assert degraded["metrics"]["stability_score"] == fresh["metrics"]["stability_score"]


def test_service_recovery_report_and_policies_are_json_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_runtime_paths.cache_clear()
    report = build_service_recovery_report(
        "runtime_metrics",
        {"status": "degraded", "data_source": "runtime", "telemetry_freshness_minutes": 30},
        timeout_seconds=8.0,
    )
    assert report["advisory_only"] is True
    assert report["timeout_policy"]["timeout_seconds"] == 8.0
    assert report["retry_policy"]["policy"]["service_name"] == "runtime_metrics"
    assert report["warnings"] or report["blockers"]

    timeout_policy = build_api_timeout_policy("runtime")
    retry_policy = build_retry_policy("runtime")
    assert timeout_policy["timeout_seconds"] > 0
    assert retry_policy["retry_delays"]

