import importlib
import os
import sys
from pathlib import Path


def test_runtime_paths_resolve_host_project_root():
    for key in ("LMCP_PROJECT_ROOT", "LMCP_RUNTIME_DIR", "LMCP_LOG_DIR", "MONTHLY_QUOTES_ROOT"):
        os.environ.pop(key, None)
    sys.modules.pop("app.core.runtime_paths", None)
    runtime_paths = importlib.import_module("app.core.runtime_paths")

    assert (runtime_paths.PROJECT_ROOT / "app").is_dir()
    assert runtime_paths.RUNTIME_DIR == runtime_paths.PROJECT_ROOT / "runtime"


def test_runtime_paths_honor_environment_overrides(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    runtime_root = tmp_path / "runtime-root"
    log_root = tmp_path / "log-root"
    monthly_root = tmp_path / "monthly-root"
    project_root.mkdir()

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_root))
    monkeypatch.setenv("LMCP_LOG_DIR", str(log_root))
    monkeypatch.setenv("MONTHLY_QUOTES_ROOT", str(monthly_root))

    sys.modules.pop("app.core.runtime_paths", None)
    runtime_paths = importlib.import_module("app.core.runtime_paths")

    assert runtime_paths.PROJECT_ROOT == project_root.resolve()
    assert runtime_paths.RUNTIME_DIR == runtime_root.resolve()
    assert runtime_paths.LOG_DIR == log_root.resolve()
    assert runtime_paths.MONTHLY_QUOTES_DIR == monthly_root.resolve()
    assert not runtime_root.exists()
    assert not log_root.exists()
    assert not monthly_root.exists()

    runtime_paths.ensure_runtime_directories()
    runtime_paths.ensure_runtime_directories()

    assert runtime_root.is_dir()
    assert log_root.is_dir()
    assert monthly_root.is_dir()
