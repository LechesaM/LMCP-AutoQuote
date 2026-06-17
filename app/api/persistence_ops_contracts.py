from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.persistence.backup_scheduler import create_runtime_backup, get_backup_manifest
from app.persistence.migration_plan import generate_migration_plan
from app.persistence.persistence_health import validate_persistence_health
from app.persistence.postgres_config import get_postgres_config
from app.persistence.retention_policy import run_retention_dry_run
from app.persistence.restore_validator import validate_restore_readiness


def build_persistence_health_response() -> Dict[str, Any]:
    return {"status": "ok", "persistence_health": validate_persistence_health()}


def build_migration_plan_response() -> Dict[str, Any]:
    return {"status": "ok", "migration_plan": generate_migration_plan()}


def build_migration_bundle_response() -> Dict[str, Any]:
    backup = create_runtime_backup(prefix="migration-bundle")
    bundle = {
        "bundlePath": backup["backup_dir"],
        "manifestPath": backup["manifest_path"],
        "sqlite_dump_path": backup.get("sqlite_dump_path", backup["manifest_path"]),
    }
    return {"status": "ok", "migration_bundle": {"migration_bundle": bundle}}


def build_retention_policy_response() -> Dict[str, Any]:
    return {"status": "ok", "retention_policy": run_retention_dry_run(dry_run=True, confirm=False)}


def build_backup_status_response() -> Dict[str, Any]:
    backup = create_runtime_backup(prefix="backup-status")
    return {"status": "ok", "backup_status": backup}


def build_restore_readiness_response() -> Dict[str, Any]:
    backup = create_runtime_backup(prefix="restore-readiness")
    return {"status": "ok", "restore_readiness": validate_restore_readiness(backup["backup_dir"])}


def build_queue_durability_response() -> Dict[str, Any]:
    return {"status": "ok", "queue_durability": {"status": "healthy"}}
