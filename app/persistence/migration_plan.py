from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.persistence.db import get_database_path
from app.persistence.postgres_config import get_postgres_config


def _jsonl_inventory() -> List[Dict[str, Any]]:
    paths = get_runtime_paths()
    items = []
    for path in sorted(paths.manual_production_dir.glob("*.jsonl")):
        items.append({"path": str(path), "size_bytes": path.stat().st_size, "exists": path.exists()})
    return items


def _table_inventory() -> List[Dict[str, Any]]:
    try:
        from app.persistence import db

        with db.connection_scope() as connection:
            rows = connection.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
        return [{"name": row["name"], "type": row["type"]} for row in rows]
    except Exception:
        return []


def generate_migration_plan() -> Dict[str, Any]:
    postgres = get_postgres_config()
    sqlite_path = get_database_path()
    table_inventory = _table_inventory()
    jsonl_inventory = _jsonl_inventory()
    blockers: List[str] = []
    if not postgres.configured:
        blockers.append("PostgreSQL target is not configured")
    if sqlite_path.exists() and sqlite_path.stat().st_size == 0:
        blockers.append("SQLite database exists but is empty")
    if not jsonl_inventory:
        blockers.append("No JSONL fallback data found")
    if not table_inventory:
        blockers.append("SQLite table inventory unavailable")
    return {
        "status": "ready" if not blockers else "blocked",
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "data_source": "runtime" if table_inventory or jsonl_inventory else "fallback",
        "current_sqlite_db_path": str(sqlite_path),
        "target_postgres_url_status": "configured" if postgres.configured else "missing",
        "target_postgres_backend": postgres.backend,
        "table_inventory": table_inventory,
        "jsonl_fallback_inventory": jsonl_inventory,
        "audit_tables": [item for item in table_inventory if "audit" in item["name"]],
        "workflow_tables": [item for item in table_inventory if "workflow" in item["name"]],
        "operator_action_tables": [item for item in table_inventory if "operator" in item["name"]],
        "queue_tables": [item for item in table_inventory if "queue" in item["name"]],
        "backup_required": True,
        "migration_blockers": blockers,
    }

