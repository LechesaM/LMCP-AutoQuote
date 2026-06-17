from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.runtime_paths import get_runtime_paths


def create_runtime_backup(prefix: str = "backup") -> Dict[str, Any]:
    paths = get_runtime_paths()
    backup_dir = paths.runtime_root / "backups" / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = backup_dir / "manifest.json"
    sqlite_dump_path = backup_dir / "dump.sql"
    manifest = {"source_count": 0, "created_at": datetime.now(timezone.utc).isoformat()}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    sqlite_dump_path.write_text("-- sqlite dump placeholder\n", encoding="utf-8")
    return {"backup_dir": str(backup_dir), "manifest_path": str(manifest_path), "manifest": manifest, "sqlite_dump_path": str(sqlite_dump_path)}


def get_backup_manifest(backup_dir: str | Path) -> Dict[str, Any]:
    manifest_path = Path(backup_dir) / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    else:
        manifest = {}
    return {"status": "ok" if manifest else "warning", "files": list(str(p) for p in Path(backup_dir).iterdir()) if Path(backup_dir).exists() else [], "manifest": manifest}
