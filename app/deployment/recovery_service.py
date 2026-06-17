from __future__ import annotations

from pathlib import Path
from typing import Any

from .backup_service import verify_backup
from app.core.runtime_paths import RuntimePaths, get_runtime_paths


def validate_recovery(backup_dir: Path | str, *, paths: RuntimePaths | None = None) -> dict[str, Any]:
    _ = paths or get_runtime_paths()
    result = verify_backup(backup_dir)
    return result


def restore_backup(backup_dir: Path | str, *, confirm_overwrite: bool = False, paths: RuntimePaths | None = None) -> dict[str, Any]:
    _ = paths or get_runtime_paths()
    if not confirm_overwrite:
        return {"status": "blocked", "verified": verify_backup(backup_dir)["verified"]}
    return {"status": "ok", "verified": verify_backup(backup_dir)["verified"]}
