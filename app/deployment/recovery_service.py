from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.deployment.backup_service import verify_backup
from app.domain.base import utc_now


def validate_recovery(backup_path: Path | str, *, paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    backup_dir = Path(backup_path)
    verification = verify_backup(backup_dir)
    required = [
        "lmcp_operations.db",
        "workflow_events.jsonl",
        "workflow_state.jsonl",
        "metadata.json",
    ]
    present = sorted(path.name for path in backup_dir.iterdir()) if backup_dir.exists() else []
    missing = [name for name in required if name not in present]
    return {
        "status": "ok" if verification.get("verified") and not missing else "degraded",
        "backup_dir": str(backup_dir),
        "runtime_root": str(runtime_paths.runtime_root),
        "verified": bool(verification.get("verified")) and not missing,
        "missing_files": missing,
        "checked_at": utc_now(),
    }


def restore_backup(
    backup_path: Path | str,
    *,
    confirm_overwrite: bool = False,
    paths: Optional[RuntimePaths] = None,
) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    backup_dir = Path(backup_path)
    validation = validate_recovery(backup_dir, paths=runtime_paths)
    if not confirm_overwrite:
        return {
            "status": "blocked",
            "reason": "confirmation required",
            "validation": validation,
            "restored": False,
            "checked_at": utc_now(),
        }
    if not validation.get("verified"):
        return {
            "status": "blocked",
            "reason": "backup invalid",
            "validation": validation,
            "restored": False,
            "checked_at": utc_now(),
        }

    mapping = {
        "lmcp_operations.db": runtime_paths.manual_production_db_path,
        "workflow_events.jsonl": runtime_paths.manual_production_file("workflow_events.jsonl"),
        "workflow_state.jsonl": runtime_paths.manual_production_file("workflow_state.jsonl"),
        "approvals.jsonl": runtime_paths.manual_production_file("approvals.jsonl"),
        "submission_reviews.jsonl": runtime_paths.manual_production_file("submission_reviews.jsonl"),
        "submission_proofs.jsonl": runtime_paths.manual_production_file("submission_proofs.jsonl"),
        "audit_events.json": runtime_paths.audit_trail_dir / "audit_events.json",
        "metadata.json": runtime_paths.backups_dir / "recovery_last_metadata.json",
    }
    restored_files: list[str] = []
    for filename, destination in mapping.items():
        source = backup_dir / filename
        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            restored_files.append(str(destination))
    return {
        "status": "ok",
        "restored": True,
        "restored_files": restored_files,
        "backup_dir": str(backup_dir),
        "checked_at": utc_now(),
    }


def get_recovery_summary(*, paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    from app.deployment.backup_service import list_backups

    return {
        "status": "ok",
        "runtime_root": str(runtime_paths.runtime_root),
        "backups": list_backups(paths=runtime_paths),
        "checked_at": utc_now(),
    }
