from __future__ import annotations

import json
from pathlib import Path

from app.api.persistence_ops_contracts import (
    build_backup_status_response,
    build_migration_bundle_response,
    build_migration_plan_response,
    build_persistence_health_response,
    build_queue_durability_response,
    build_retention_policy_response,
    build_restore_readiness_response,
)
from app.config import get_settings
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.persistence.backup_scheduler import create_runtime_backup
from app.persistence.db import database_connection_ready, get_database_backend
from app.persistence.migration_plan import generate_migration_plan
from app.persistence.persistence_health import validate_persistence_health
from app.persistence.postgres_config import get_postgres_config, postgres_connection_ready
from app.persistence.retention_policy import run_retention_dry_run
from app.api.persistence_ops_routes import router as persistence_ops_router


def _prepare_runtime(monkeypatch, tmp_path: Path, *, env: str = "development") -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    backups_dir = runtime_dir / "backups"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_BACKUPS_DIR", str(backups_dir))
    monkeypatch.setenv("LMCP_ENV", env)
    monkeypatch.setenv("LMCP_PRODUCTION_MODE", "supervised_live" if env != "development" else "manual_production")
    monkeypatch.setenv("LMCP_DEPLOYMENT_PROFILE", "production" if env == "production" else "local_dev")
    monkeypatch.setenv("LMCP_DB_BACKEND", "sqlite")
    monkeypatch.setenv("LMCP_QUEUE_BACKEND", "local")
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "0")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()
    get_settings.cache_clear()


def test_postgres_config_parses(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, env="production")
    monkeypatch.setenv("LMCP_DB_BACKEND", "postgres")
    monkeypatch.setenv("LMCP_DATABASE_URL", "postgresql://lmcp:secret@localhost:5432/lmcp")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()

    config = get_postgres_config()
    assert config.backend == "postgres"
    assert config.host == "localhost"
    assert config.port == 5432
    assert config.database == "lmcp"
    assert config.configured is True
    assert postgres_connection_ready() is True


def test_sqlite_fallback_works(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    assert get_database_backend() == "sqlite"
    assert database_connection_ready() is True


def test_sqlite_backend_uses_local_sqlite_database_url(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("LMCP_DB_BACKEND", "sqlite")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.database_url.startswith("sqlite:///")
    assert str(tmp_path / "runtime" / "manual_production" / "lmcp_operations.db") in settings.database_url


def test_production_warns_when_sqlite_used(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, env="production")

    config = get_postgres_config()
    assert config.backend == "sqlite"
    assert "PostgreSQL" in config.production_warning


def test_migration_plan_json_safe(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    plan = generate_migration_plan()
    json.dumps(plan, default=str)
    assert "migration_blockers" in plan


def test_migration_bundle_json_safe(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    payload = build_migration_bundle_response()
    json.dumps(payload, default=str)
    bundle = payload["migration_bundle"]["migration_bundle"]
    assert Path(bundle["bundlePath"]).exists()
    assert Path(bundle["manifestPath"]).exists()
    assert Path(bundle["sqlite_dump_path"]).exists()


def test_persistence_health_json_safe(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    payload = validate_persistence_health()
    json.dumps(payload, default=str)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert "restore_readiness" in payload


def test_retention_dry_run_does_not_delete(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    payload = run_retention_dry_run(dry_run=True, confirm=False)
    json.dumps(payload, default=str)
    assert payload["deleted"] == []
    assert payload["dry_run"] is True


def test_backup_scheduler_manifest_json_safe(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    payload = create_runtime_backup(prefix="test")
    json.dumps(payload, default=str)
    assert Path(payload["manifest_path"]).exists()
    assert payload["manifest"]["source_count"] >= 0


def test_persistence_ops_responses_cover_readonly_views(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, env="production")
    paths = {route.path for route in persistence_ops_router.routes}
    assert {"/persistence/health", "/persistence/migration-plan", "/persistence/migration-bundle", "/persistence/migration-bundle/download", "/persistence/retention-policy", "/persistence/backup-status", "/persistence/restore-readiness"} <= paths
    assert {"/queue/durability", "/queue/dead-letter", "/queue/recovery", "/queue/workers"} <= paths
    for payload in [
        build_persistence_health_response(),
        build_migration_plan_response(),
        build_migration_bundle_response(),
        build_retention_policy_response(),
        build_backup_status_response(),
        build_restore_readiness_response(),
        build_queue_durability_response(),
    ]:
        json.dumps(payload, default=str)
