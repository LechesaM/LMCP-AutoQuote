from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone

from app.persistence.backup_scheduler import get_backup_manifest
from app.persistence.db import get_database_path
from app.persistence.repositories import get_persistence_health, WorkflowRepository, QueueJobRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_restore_readiness(backup_dir: str | Path) -> Dict[str, Any]:
    if str(backup_dir or "").strip() == "":
        return {
            "status": "blocked",
            "generated_at": _now_iso(),
            "data_source": "fallback",
            "manifest": {"status": "warning", "generated_at": _now_iso(), "data_source": "fallback", "manifest_path": "", "files": [], "blockers": ["missing backup directory"]},
            "persistence_ok": False,
            "workflow_readable": False,
            "queue_readable": False,
            "blockers": ["missing backup directory"],
            "non_destructive": True,
        }
    manifest = get_backup_manifest(backup_dir)
    blockers: List[str] = list(manifest.get("blockers", []))
    required_files = [get_database_path().name]
    present_files = {Path(item.get("source") or item.get("destination") or "").name for item in manifest.get("files", [])}
    missing_files = [name for name in required_files if name not in present_files]
    blockers.extend([f"missing file: {name}" for name in missing_files])
    try:
        persistence_ok = bool(get_persistence_health().get("db_ready", False))
        workflow_readable = len(WorkflowRepository().fetch_recent(limit=1)) >= 0
        queue_readable = len(QueueJobRepository().fetch_recent(limit=1)) >= 0
    except Exception as exc:
        blockers.append(str(exc))
        persistence_ok = False
        workflow_readable = False
        queue_readable = False
    return {
        "status": "ready" if not blockers and persistence_ok and workflow_readable and queue_readable else "blocked",
        "generated_at": manifest.get("generated_at") or _now_iso(),
        "data_source": "runtime" if not blockers else "fallback",
        "manifest": manifest,
        "persistence_ok": persistence_ok,
        "workflow_readable": workflow_readable,
        "queue_readable": queue_readable,
        "blockers": blockers,
        "non_destructive": True,
    }
