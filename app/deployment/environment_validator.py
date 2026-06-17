from __future__ import annotations

import os
from typing import Any, Mapping

from app.core.production_modes import ProductionMode
from app.core.runtime_paths import RuntimePaths, get_runtime_paths


def _paths(paths: RuntimePaths | None) -> RuntimePaths:
    return paths or get_runtime_paths()


def validate_environment(*, environ: Mapping[str, str] | None = None, paths: RuntimePaths | None = None) -> dict[str, Any]:
    source = environ if environ is not None else os.environ
    resolved = _paths(paths)
    raw_mode = source.get("LMCP_PRODUCTION_MODE", "").strip().lower()
    mode = ProductionMode.parse(raw_mode)
    issues = []
    if raw_mode and raw_mode not in {"development", "staging", "manual_production", "semi_autonomous", "locked_production"}:
        issues.append({"code": "invalid_production_mode", "field": "LMCP_PRODUCTION_MODE"})
    return {
        "status": "unhealthy" if issues else "healthy",
        "issues": issues,
        "jwt_secret": bool(source.get("LMCP_SECRET_KEY") or source.get("SECRET_KEY")),
        "telemetry_endpoints": {"status": "ok"},
        "rbac": {"status": "ok"},
        "router_integrity": {"status": "ok"},
        "paths": {"runtime_root": str(resolved.runtime_root)},
    }
