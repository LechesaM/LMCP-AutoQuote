from __future__ import annotations

from typing import Any, Dict

from app.persistence.backup_scheduler import get_backup_status
from app.persistence.migration_plan import generate_migration_plan
from app.persistence.persistence_health import validate_persistence_health
from app.persistence.restore_validator import validate_restore_readiness
from app.persistence.retention_policy import get_retention_policy


def build_persistence_reliability_report() -> Dict[str, Any]:
    health = validate_persistence_health()
    backup = get_backup_status()
    plan = generate_migration_plan()
    restore = validate_restore_readiness(backup.get("latest_backup_dir", ""))
    retention = get_retention_policy()
    return {
        "status": health.get("status", "degraded"),
        "generated_at": health.get("generated_at"),
        "data_source": health.get("data_source", "fallback"),
        "health": health,
        "backup": backup,
        "migration_plan": plan,
        "restore_readiness": restore,
        "retention_policy": retention,
        "readiness": {
            "sqlite": health.get("sqlite_available", False),
            "postgres": health.get("postgres_configured", False),
            "backup_ready": backup.get("backup_count", 0) > 0,
            "restore_ready": restore.get("status") == "ready",
        },
    }

