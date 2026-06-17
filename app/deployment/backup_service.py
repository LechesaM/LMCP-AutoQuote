from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.runtime_paths import RuntimePaths, get_runtime_paths


def _paths(paths: RuntimePaths | None) -> RuntimePaths:
    return paths or get_runtime_paths()


def create_backup(*, paths: RuntimePaths | None = None) -> dict[str, Any]:
    resolved = _paths(paths)
    backup_dir = resolved.runtime_root / "backups" / datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    metadata = {"created_at": datetime.now(timezone.utc).isoformat(), "source": str(resolved.manual_production_dir)}
    (backup_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for filename in ("workflow_events.jsonl", "workflow_state.jsonl"):
        source = resolved.manual_production_dir / filename
        if source.exists():
            (backup_dir / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    files = [str(path.relative_to(backup_dir)) for path in backup_dir.rglob("*") if path.is_file()]
    return {"backup_dir": str(backup_dir), "files": files}


def verify_backup(backup_dir: Path | str) -> dict[str, Any]:
    resolved = Path(backup_dir)
    verified = (resolved / "metadata.json").exists()
    return {"verified": verified, "backup_dir": str(resolved)}
