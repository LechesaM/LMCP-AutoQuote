from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.persistence.backup_scheduler import get_backup_status
from app.persistence.db import get_database_path, safe_initialize_database
from app.persistence.postgres_config import get_postgres_config
from app.persistence.repositories import get_persistence_health
from app.persistence.restore_validator import validate_restore_readiness
from app.persistence.retention_policy import get_retention_policy


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_persistence_health() -> Dict[str, Any]:
    runtime = get_runtime_config()
    postgres = get_postgres_config()
    backup = get_backup_status()
    restore = validate_restore_readiness(backup.get("latest_backup_dir", ""))
    db_path = get_database_path()
    db_available = safe_initialize_database()
    warnings: List[str] = []
    blockers: List[str] = []
    if runtime.mode.value in {"production", "supervised_live"} and postgres.backend == "sqlite":
        warnings.append("Production or supervised-live is using SQLite; PostgreSQL is recommended.")
    if postgres.backend == "postgres" and not postgres.configured:
        blockers.append("PostgreSQL backend selected but connection settings are incomplete.")
    if not db_available:
        blockers.append("Database initialization failed.")
    if backup.get("backup_age_warning"):
        warnings.append("Latest backup is older than the recommended threshold.")
    if restore.get("status") != "ready":
        warnings.extend(restore.get("blockers", []))
    retention = get_retention_policy()
    if not retention.get("windows_days"):
        blockers.append("Retention policy missing.")
    status = "healthy"
    if blockers:
        status = "failing"
    elif warnings:
        status = "degraded"
    return {
        "status": status,
        "generated_at": _now_iso(),
        "data_source": "runtime" if db_available else "fallback",
        "sqlite_available": db_available,
        "postgres_configured": postgres.configured,
        "postgres_backend": postgres.backend,
        "db_file_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "jsonl_fallback_status": bool(get_runtime_paths().manual_production_dir.exists()),
        "audit_persistence_status": bool(get_persistence_health().get("db_ready", False)),
        "workflow_persistence_status": bool(get_persistence_health().get("db_ready", False)),
        "backup_age_days": backup.get("latest_backup_age_days", -1),
        "retention_status": retention,
        "warnings": warnings,
        "blockers": blockers,
        "restore_readiness": restore,
    }
