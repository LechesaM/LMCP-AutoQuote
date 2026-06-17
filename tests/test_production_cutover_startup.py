from __future__ import annotations

import os

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DIR", "/Users/cash/Documents/runtime/manual_production")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DB_PATH", "/Users/cash/Documents/runtime/manual_production/lmcp_operations.db")

from app.config import get_settings
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.startup.environment_validator import validate_environment
from app.startup.startup_health_report import build_startup_health_report


def _clear_startup_caches() -> None:
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()
    get_settings.cache_clear()


def test_startup_health_report_contains_required_sections() -> None:
    _clear_startup_caches()
    report = build_startup_health_report()

    assert report["environment"]["status"] in {"healthy", "degraded", "failing"}
    assert report["dependencies"]["status"] in {"healthy", "failing"}
    assert report["startup_validation"]["status"] in {"healthy", "degraded", "unhealthy"}
    assert "production_blockers" in report
    assert "blockers" in report
    assert "warnings" in report


def test_strict_startup_reports_fail_loudly_on_placeholder_secret(monkeypatch) -> None:
    monkeypatch.setenv("STRICT_PRODUCTION_STARTUP", "1")
    monkeypatch.setenv("LMCP_SECRET_KEY", "change-me")
    monkeypatch.setenv("LMCP_ENV", "production")
    monkeypatch.setenv("LMCP_PRODUCTION_MODE", "production")
    monkeypatch.setenv("LMCP_DEPLOYMENT_PROFILE", "production")
    monkeypatch.setenv("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
    monkeypatch.setenv("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", "/Users/cash/Documents/runtime/manual_production")
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", "/Users/cash/Documents/runtime/manual_production/lmcp_operations.db")
    monkeypatch.setenv("LMCP_DB_BACKEND", "sqlite")
    monkeypatch.setenv("LMCP_QUEUE_BACKEND", "local")
    _clear_startup_caches()

    report = build_startup_health_report()

    assert report["strict_production_startup"] is True
    assert report["production_blockers"]["fail_loudly"] is True
    assert report["blockers"]


def test_environment_validator_reports_core_sections() -> None:
    _clear_startup_caches()
    report = validate_environment()

    assert "jwt_secret" in report
    assert "telemetry_endpoints" in report
    assert "rbac" in report
    assert "router_integrity" in report
