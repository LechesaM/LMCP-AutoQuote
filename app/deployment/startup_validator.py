from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.runtime_paths import RuntimePaths, get_runtime_paths


def _paths(paths: RuntimePaths | None) -> RuntimePaths:
    return paths or get_runtime_paths()


def validate_startup(*, paths: RuntimePaths | None = None, allow_degraded_startup: bool = False) -> dict[str, Any]:
    resolved = _paths(paths)
    required = {
        "runtime_root": resolved.runtime_root,
        "logs_dir": resolved.logs_dir,
        "health_dir": resolved.health_dir,
        "manual_production_dir": resolved.manual_production_dir,
    }
    fatal_issues = []
    for name, directory in required.items():
        if not directory.exists():
            fatal_issues.append({"code": "missing_directory", "field": name, "path": str(directory)})
    degraded = bool(fatal_issues) and allow_degraded_startup
    status = "healthy" if not fatal_issues else "degraded" if degraded else "unhealthy"
    return {"status": status, "valid": not fatal_issues, "fatal_issues": [] if degraded else fatal_issues}
