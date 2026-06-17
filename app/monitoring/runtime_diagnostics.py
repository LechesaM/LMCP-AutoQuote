from __future__ import annotations

from typing import Any

from app.core.runtime_paths import RuntimePaths, get_runtime_paths


def get_runtime_diagnostics(*, paths: RuntimePaths | None = None) -> dict[str, Any]:
    resolved = paths or get_runtime_paths()
    missing = [name for name, path in {
        "health_dir": resolved.health_dir,
        "logs_dir": resolved.logs_dir,
        "runtime_root": resolved.runtime_root,
    }.items() if not path.exists()]
    return {
        "status": "degraded" if missing else "healthy",
        "missing_directories": missing,
        "runtime_root": str(resolved.runtime_root),
    }
