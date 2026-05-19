from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.persistence import db


class BackupRecord(StrictBaseModel):
    backup_id: str = ""
    created_at: Any = None
    backup_dir: str = ""
    files: List[str] = Field(default_factory=list)
    verified: bool = False


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup_root(paths: RuntimePaths) -> Path:
    root = paths.backups_dir / _timestamp()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _copy_if_exists(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def create_backup(*, paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    backup_dir = _backup_root(runtime_paths)
    files: List[str] = []
    targets = [
        runtime_paths.manual_production_db_path,
        runtime_paths.manual_production_file("workflow_events.jsonl"),
        runtime_paths.manual_production_file("workflow_state.jsonl"),
        runtime_paths.manual_production_file("approvals.jsonl"),
        runtime_paths.manual_production_file("submission_reviews.jsonl"),
        runtime_paths.manual_production_file("submission_proofs.jsonl"),
        runtime_paths.audit_trail_dir / "audit_events.json",
    ]
    for source in targets:
        if _copy_if_exists(source, backup_dir / source.name):
            files.append(str(backup_dir / source.name))
    metadata = {
        "backup_id": backup_dir.name,
        "created_at": utc_now(),
        "runtime_root": str(runtime_paths.runtime_root),
        "manual_production_dir": str(runtime_paths.manual_production_dir),
        "db_checksum": db.database_checksum(runtime_paths.manual_production_db_path),
        "files": files,
    }
    metadata_path = backup_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    files.append(str(metadata_path))
    return BackupRecord(
        backup_id=backup_dir.name,
        created_at=utc_now(),
        backup_dir=str(backup_dir),
        files=files,
        verified=False,
    ).to_jsonable_dict()


def list_backups(*, paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    if not runtime_paths.backups_dir.exists():
        return {"status": "ok", "items": [], "total": 0, "backups_dir": str(runtime_paths.backups_dir)}
    items = [str(path) for path in sorted(runtime_paths.backups_dir.iterdir()) if path.is_dir()]
    return {"status": "ok", "items": items, "total": len(items), "backups_dir": str(runtime_paths.backups_dir)}


def verify_backup(backup_path: Path | str) -> Dict[str, Any]:
    backup_dir = Path(backup_path)
    files_present = backup_dir.exists() and any(backup_dir.iterdir())
    metadata = backup_dir / "metadata.json"
    valid = files_present and metadata.exists()
    return {
        "status": "ok" if valid else "degraded",
        "backup_dir": str(backup_dir),
        "verified": valid,
        "metadata_present": metadata.exists(),
        "created_at": utc_now(),
    }
