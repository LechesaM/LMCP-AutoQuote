from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Mapping, Tuple

from dotenv import load_dotenv

from app.core.production_modes import ProductionMode
from app.core.runtime_paths import RuntimePaths, get_runtime_paths, resolve_project_root


TRUTHY_ENV_VALUES = {"1", "true", "yes", "y", "on"}


def load_environment(environ: Mapping[str, str] | None = None) -> Path:
    project_root = resolve_project_root(environ)
    load_dotenv(project_root / ".env")
    return project_root


def env(name: str, default: str = "", environ: Mapping[str, str] | None = None) -> str:
    source = environ if environ is not None else os.environ
    value = source.get(name)
    if value is None:
        return default
    cleaned = str(value).strip()
    return cleaned or default


def env_bool(name: str, default: bool = False, environ: Mapping[str, str] | None = None) -> bool:
    raw = env(name, "1" if default else "0", environ=environ).lower()
    return raw in TRUTHY_ENV_VALUES


def env_csv(name: str, default: str = "", environ: Mapping[str, str] | None = None) -> Tuple[str, ...]:
    raw = env(name, default, environ=environ)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class RuntimeConfig:
    project_root: Path
    environment: str
    mode: ProductionMode
    paths: RuntimePaths
    debug: bool
    log_level: str
    enable_legacy_routers: bool
    allow_degraded_startup: bool
    runtime_safety_enabled: bool
    manual_production_enforced: bool
    final_submission_manual_only: bool
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 5
    error_log_backup_count: int = 10

    def configure_environment(self) -> None:
        os.environ.setdefault("LMCP_PROJECT_ROOT", str(self.project_root))
        os.environ.setdefault("LMCP_RUNTIME_DIR", str(self.paths.runtime_root))
        os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DIR", str(self.paths.manual_production_dir))
        os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DB_PATH", str(self.paths.manual_production_db_path))
        os.environ.setdefault("LMCP_ENV", self.environment)
        os.environ.setdefault("LMCP_PRODUCTION_MODE", self.mode.value)

    def ensure_directories(self) -> None:
        self.paths.ensure_directories()

    def configure_logging(self) -> None:
        root = logging.getLogger()
        if getattr(root, "_lmcp_logging_configured", False):
            return

        self.ensure_directories()
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

        console = logging.StreamHandler()
        console.setLevel(getattr(logging, self.log_level, logging.INFO))
        console.setFormatter(formatter)

        app_log = RotatingFileHandler(
            self.paths.logs_dir / "app.log",
            maxBytes=self.log_max_bytes,
            backupCount=self.log_backup_count,
            encoding="utf-8",
        )
        app_log.setLevel(getattr(logging, self.log_level, logging.INFO))
        app_log.setFormatter(formatter)

        error_log = RotatingFileHandler(
            self.paths.logs_dir / "error.log",
            maxBytes=self.log_max_bytes,
            backupCount=self.error_log_backup_count,
            encoding="utf-8",
        )
        error_log.setLevel(logging.ERROR)
        error_log.setFormatter(formatter)

        root.setLevel(getattr(logging, self.log_level, logging.INFO))
        root.addHandler(console)
        root.addHandler(app_log)
        root.addHandler(error_log)
        root._lmcp_logging_configured = True  # type: ignore[attr-defined]


@lru_cache(maxsize=1)
def get_runtime_config() -> RuntimeConfig:
    project_root = load_environment()
    paths = get_runtime_paths()
    environment = env("LMCP_ENV", env("ENVIRONMENT", "development")).lower()
    mode = ProductionMode.parse(env("LMCP_PRODUCTION_MODE", ""))
    config = RuntimeConfig(
        project_root=project_root,
        environment=environment,
        mode=mode,
        paths=paths,
        debug=env_bool("LMCP_DEBUG", False),
        log_level=env("LMCP_LOG_LEVEL", env("LOG_LEVEL", "INFO")).upper(),
        enable_legacy_routers=env_bool("LMCP_ENABLE_LEGACY_ROUTERS", False),
        allow_degraded_startup=env_bool("LMCP_ALLOW_DEGRADED_STARTUP", False),
        runtime_safety_enabled=env_bool("LMCP_RUNTIME_SAFETY_ENABLED", True),
        manual_production_enforced=mode.manual_production_enforced,
        final_submission_manual_only=True,
    )
    config.configure_environment()
    config.ensure_directories()
    return config
