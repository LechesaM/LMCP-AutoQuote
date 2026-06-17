from __future__ import annotations

from typing import Any

from app.core.runtime_paths import RuntimePaths

from .deployment_report import build_deployment_report


def run_graceful_shutdown(*, paths: RuntimePaths | None = None) -> dict[str, Any]:
    return {"status": "ok", "deployment_report": build_deployment_report(paths=paths)}
