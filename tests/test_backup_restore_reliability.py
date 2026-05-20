from __future__ import annotations

import json
from pathlib import Path

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.persistence.backup_scheduler import create_runtime_backup, get_backup_manifest
from app.persistence.db import safe_initialize_database
from app.persistence.restore_validator import validate_restore_readiness


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    backups_dir = runtime_dir / "backups"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_BACKUPS_DIR", str(backups_dir))
    monkeypatch.setenv("LMCP_DEPLOYMENT_PROFILE", "local_dev")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()
    safe_initialize_database()


def test_backup_manifest_valid(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    backup = create_runtime_backup(prefix="backup-test")
    manifest = get_backup_manifest(backup["backup_dir"])
    json.dumps(manifest, default=str)
    assert manifest["status"] in {"ok", "warning"}
    assert manifest["files"] is not None


def test_restore_validation_non_destructive(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    backup = create_runtime_backup(prefix="restore-test")
    readiness = validate_restore_readiness(backup["backup_dir"])
    json.dumps(readiness, default=str)
    assert readiness["non_destructive"] is True
    assert readiness["status"] in {"ready", "blocked"}


def test_missing_backup_reports_blocker(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    missing = tmp_path / "does-not-exist"
    readiness = validate_restore_readiness(missing)
    assert readiness["status"] == "blocked"
    assert readiness["blockers"]


def test_audit_and_workflow_readability_checked(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    backup = create_runtime_backup(prefix="readability-test")
    readiness = validate_restore_readiness(backup["backup_dir"])
    assert readiness["persistence_ok"] is True
    assert readiness["workflow_readable"] is True
    assert readiness["queue_readable"] is True
