from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional

from pydantic import Field

from app.core.production_modes import ProductionMode
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now


class EnvironmentValidationIssue(StrictBaseModel):
    level: str = "warning"
    code: str = ""
    message: str = ""


class EnvironmentValidationReport(StrictBaseModel):
    status: str = "healthy"
    healthy: bool = True
    degraded: bool = False
    valid: bool = True
    checked_at: Any = None
    environment: str = ""
    production_mode: str = ""
    deployment_hardening_enabled: bool = True
    issues: list[Dict[str, Any]] = Field(default_factory=list)
    runtime_paths: Dict[str, Any] = Field(default_factory=dict)


def _raw(environ: Mapping[str, str] | None, name: str) -> str:
    source = environ if environ is not None else os.environ
    return str(source.get(name, "") or "").strip()


def validate_environment(
    environ: Mapping[str, str] | None = None,
    *,
    paths: Optional[RuntimePaths] = None,
) -> Dict[str, Any]:
    config = get_runtime_config()
    runtime_paths = paths or get_runtime_paths()
    issues: list[Dict[str, Any]] = []
    raw_mode = _raw(environ, "LMCP_PRODUCTION_MODE")
    if raw_mode and raw_mode.lower() not in {item.value for item in ProductionMode}:
        issues.append(
            EnvironmentValidationIssue(
                level="fatal",
                code="invalid_production_mode",
                message=f"Unsupported production mode: {raw_mode}",
            ).to_jsonable_dict()
        )
    if environ is not None:
        for key in ("LMCP_PROJECT_ROOT", "LMCP_RUNTIME_DIR", "LMCP_MANUAL_PRODUCTION_DIR"):
            if not _raw(environ, key):
                issues.append(
                    EnvironmentValidationIssue(
                        level="warning",
                        code=f"missing_{key.lower()}",
                        message=f"{key} is not explicitly set; runtime defaults are being used",
                    ).to_jsonable_dict()
                )
    writable_paths = {
        "runtime_root": runtime_paths.runtime_root,
        "manual_production_dir": runtime_paths.manual_production_dir,
        "backups_dir": runtime_paths.backups_dir,
    }
    for label, path in writable_paths.items():
        if not path.exists():
            issues.append(
                EnvironmentValidationIssue(
                    level="fatal",
                    code=f"missing_{label}",
                    message=f"{label} does not exist: {path}",
                ).to_jsonable_dict()
            )
        elif not path.is_dir() or not path.exists():
            issues.append(
                EnvironmentValidationIssue(
                    level="fatal",
                    code=f"invalid_{label}",
                    message=f"{label} is not a directory: {path}",
                ).to_jsonable_dict()
            )
    if config.enable_legacy_routers:
        issues.append(
            EnvironmentValidationIssue(
                level="fatal",
                code="legacy_routers_enabled",
                message="Legacy routers are enabled in the deployment environment",
            ).to_jsonable_dict()
        )
    if not config.observability_enabled:
        issues.append(
            EnvironmentValidationIssue(
                level="warning",
                code="observability_disabled",
                message="Observability is disabled",
            ).to_jsonable_dict()
        )

    fatal = any(str(item.get("level")) == "fatal" for item in issues)
    status = "unhealthy" if fatal else ("degraded" if issues else "healthy")
    return EnvironmentValidationReport(
        status=status,
        healthy=not fatal,
        degraded=bool(issues),
        valid=not fatal,
        checked_at=utc_now(),
        environment=config.environment,
        production_mode=config.mode.value,
        deployment_hardening_enabled=config.deployment_hardening_enabled,
        issues=issues,
        runtime_paths={
            "runtime_root": str(runtime_paths.runtime_root),
            "manual_production_dir": str(runtime_paths.manual_production_dir),
            "backups_dir": str(runtime_paths.backups_dir),
        },
    ).to_jsonable_dict()


def get_environment_summary(
    environ: Mapping[str, str] | None = None,
    *,
    paths: Optional[RuntimePaths] = None,
) -> Dict[str, Any]:
    return validate_environment(environ=environ, paths=paths)
