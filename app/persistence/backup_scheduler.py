from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.persistence.db import get_database_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_root() -> Path:
    return get_runtime_paths().backups_dir


def _backup_name(prefix: str = "backup") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def create_runtime_backup(*, prefix: str = "backup") -> Dict[str, Any]:
    root = _backup_root()
    root.mkdir(parents=True, exist_ok=True)
    backup_dir = root / _backup_name(prefix)
    backup_dir.mkdir(parents=True, exist_ok=True)
    paths = get_runtime_paths()
    files: List[Dict[str, Any]] = []
    sources = [
        get_database_path(),
        *sorted(paths.manual_production_dir.glob("*.jsonl")),
    ]
    for source in sources:
        if not source.exists():
            continue
        destination = backup_dir / source.name
        if source.is_dir():
            continue
        shutil.copy2(source, destination)
        files.append({"source": str(source), "destination": str(destination), "sha256": _sha256(destination), "size_bytes": destination.stat().st_size})
    manifest = {
        "backup_id": backup_dir.name,
        "created_at": _now_iso(),
        "files": files,
        "source_count": len(files),
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "backup_dir": str(backup_dir),
        "manifest": manifest,
        "manifest_path": str(manifest_path),
    }


def get_backup_status() -> Dict[str, Any]:
    root = _backup_root()
    backups = sorted([path for path in root.glob("*") if path.is_dir()], key=lambda item: item.stat().st_mtime, reverse=True)
    latest = backups[0] if backups else None
    latest_age_days = None
    if latest:
        latest_age_days = round(max(0.0, (datetime.now(timezone.utc).timestamp() - latest.stat().st_mtime) / 86400.0), 2)
    return {
        "status": "ok" if latest else "warning",
        "generated_at": _now_iso(),
        "data_source": "runtime" if latest else "fallback",
        "backup_count": len(backups),
        "latest_backup_dir": str(latest) if latest else "",
        "latest_backup_age_days": latest_age_days if latest_age_days is not None else -1,
        "backup_age_warning": bool(latest_age_days is not None and latest_age_days > 3),
    }


def get_backup_manifest(backup_dir: str | Path) -> Dict[str, Any]:
    backup_path = Path(backup_dir)
    if str(backup_dir or "").strip() == "":
        return {"status": "warning", "generated_at": _now_iso(), "data_source": "fallback", "manifest_path": "", "files": [], "blockers": ["missing backup directory"]}
    manifest_path = backup_path / "manifest.json"
    if not manifest_path.exists():
        return {"status": "warning", "generated_at": _now_iso(), "data_source": "fallback", "manifest_path": str(manifest_path), "files": [], "blockers": ["missing manifest"]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "warning", "generated_at": _now_iso(), "data_source": "fallback", "manifest_path": str(manifest_path), "files": [], "blockers": [str(exc)]}
    return {"status": "ok", "generated_at": _now_iso(), "data_source": "runtime", "manifest_path": str(manifest_path), "manifest": manifest, "files": manifest.get("files", [])}
