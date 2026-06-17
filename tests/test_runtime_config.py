from __future__ import annotations

import logging

from app.api.router_registry import iter_router_specs
from app.core.production_modes import ProductionMode
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import RuntimePaths, get_runtime_paths


def test_runtime_dirs_resolve_correctly(tmp_path) -> None:
    env = {
        "LMCP_PROJECT_ROOT": str(tmp_path / "project"),
        "LMCP_RUNTIME_DIR": str(tmp_path / "project" / "runtime_root"),
        "LMCP_MONTHLY_QUOTES_DIR": str(tmp_path / "project" / "downloads_root"),
    }
    paths = RuntimePaths.from_environ(env)
    assert paths.project_root == (tmp_path / "project").resolve()
    assert paths.runtime_root == (tmp_path / "project" / "runtime_root").resolve()
    assert paths.downloads_dir == (tmp_path / "project" / "downloads_root").resolve()
    assert paths.logs_dir == (tmp_path / "project" / "runtime_root" / "logs").resolve()
    assert paths.manual_production_dir == (tmp_path / "project" / "runtime_root" / "manual_production").resolve()


def test_runtime_dirs_accept_legacy_aliases(tmp_path) -> None:
    env = {
        "PROJECT_ROOT": str(tmp_path / "project"),
        "RUNTIME_DIR": str(tmp_path / "project" / "runtime_root"),
    }
    paths = RuntimePaths.from_environ(env)
    assert paths.project_root == (tmp_path / "project").resolve()
    assert paths.runtime_root == (tmp_path / "project" / "runtime_root").resolve()


def test_required_dirs_auto_create(tmp_path) -> None:
    env = {
        "LMCP_PROJECT_ROOT": str(tmp_path / "project"),
        "LMCP_RUNTIME_DIR": str(tmp_path / "project" / "runtime_root"),
    }
    paths = RuntimePaths.from_environ(env)
    paths.ensure_directories()
    for directory in paths.required_directories():
        assert directory.exists()
        assert directory.is_dir()


def test_production_modes_parse_correctly() -> None:
    assert ProductionMode.parse("development") is ProductionMode.DEVELOPMENT
    assert ProductionMode.parse("staging") is ProductionMode.STAGING
    assert ProductionMode.parse("manual_production") is ProductionMode.MANUAL_PRODUCTION
    assert ProductionMode.parse("semi_autonomous") is ProductionMode.SEMI_AUTONOMOUS
    assert ProductionMode.parse("locked_production") is ProductionMode.LOCKED_PRODUCTION


def test_invalid_production_modes_fail_safely() -> None:
    assert ProductionMode.parse("unknown-mode") is ProductionMode.MANUAL_PRODUCTION
    assert ProductionMode.parse("") is ProductionMode.MANUAL_PRODUCTION


def test_manual_production_mode_remains_enforced(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(tmp_path / "runtime" / "manual_production"))
    monkeypatch.setenv(
        "LMCP_MANUAL_PRODUCTION_DB_PATH",
        str(tmp_path / "runtime" / "manual_production" / "lmcp_operations.db"),
    )
    monkeypatch.setenv("LMCP_PRODUCTION_MODE", "manual_production")
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    config = get_runtime_config()
    assert config.mode is ProductionMode.MANUAL_PRODUCTION
    assert config.manual_production_enforced is True
    assert config.final_submission_manual_only is True


def test_legacy_routers_remain_disabled_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(tmp_path / "runtime" / "manual_production"))
    monkeypatch.setenv(
        "LMCP_MANUAL_PRODUCTION_DB_PATH",
        str(tmp_path / "runtime" / "manual_production" / "lmcp_operations.db"),
    )
    monkeypatch.delenv("LMCP_ENABLE_LEGACY_ROUTERS", raising=False)
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    config = get_runtime_config()
    assert config.enable_legacy_routers is False
    selected_names = {spec.name for spec in iter_router_specs(include_legacy=config.enable_legacy_routers)}
    assert "portal_submission_v47_router" not in selected_names


def test_logging_configuration_uses_central_logs_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(tmp_path / "runtime" / "manual_production"))
    monkeypatch.setenv(
        "LMCP_MANUAL_PRODUCTION_DB_PATH",
        str(tmp_path / "runtime" / "manual_production" / "lmcp_operations.db"),
    )
    monkeypatch.setenv("LMCP_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    if hasattr(root, "_lmcp_logging_configured"):
        delattr(root, "_lmcp_logging_configured")

    config = get_runtime_config()
    config.configure_logging()
    assert (config.paths.logs_dir / "app.log").parent == config.paths.logs_dir
    assert config.paths.logs_dir.exists()
