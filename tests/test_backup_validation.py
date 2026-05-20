from __future__ import annotations

import json

from app.core.runtime_paths import get_runtime_paths
from app.operations.backup_validation import get_backup_validation_summary, validate_backup_restore


def test_backup_validation_is_safe_and_non_destructive(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    get_runtime_paths.cache_clear()
    backup_dir = get_runtime_paths().backups_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / "lmcp-backup-001.tar.gz"
    backup_file.write_text("backup", encoding="utf-8")
    summary = get_backup_validation_summary()
    restore = validate_backup_restore()
    assert summary["latest_backup_verified"] is True
    assert restore["restore_simulation"]["non_destructive"] is True
    assert restore["restore_simulation"]["validation_only"] is True
    json.dumps(summary, default=str)
    json.dumps(restore, default=str)


def test_backup_validation_handles_missing_backups(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    get_runtime_paths.cache_clear()
    summary = get_backup_validation_summary()
    assert summary["restore_simulation"]["non_destructive"] is True
    assert "backup_dir" in summary
    json.dumps(summary, default=str)

