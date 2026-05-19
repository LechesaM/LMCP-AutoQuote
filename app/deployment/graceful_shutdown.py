from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.deployment.deployment_report import build_deployment_report
from app.domain.base import StrictBaseModel, utc_now


class ShutdownSnapshot(StrictBaseModel):
    status: str = "ok"
    checked_at: Any = None
    reason: str = ""
    log_handlers_flushed: bool = True
    deployment_report: Dict[str, Any]


def _flush_handlers() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        try:
            handler.flush()
        except Exception:
            continue


def build_shutdown_snapshot(*, reason: str = "manual-production shutdown", paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    _ = paths or get_runtime_paths()
    _flush_handlers()
    return ShutdownSnapshot(
        status="ok",
        checked_at=utc_now(),
        reason=reason,
        log_handlers_flushed=True,
        deployment_report=build_deployment_report(paths=paths),
    ).to_jsonable_dict()


def run_graceful_shutdown(*, reason: str = "manual-production shutdown", paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    return build_shutdown_snapshot(reason=reason, paths=paths)
