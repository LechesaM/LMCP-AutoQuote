from __future__ import annotations

"""
Compatibility bridge for legacy imports from app.tasks.

This package now exposes:
- celery
- manual_harvest
- run_harvest_only
- run_harvest_pipeline

It also keeps the submission scheduler tasks importable.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

try:
    from app.celery_app import celery_app as celery
except Exception:
    celery = None

logger = logging.getLogger(__name__)
_LEGACY_TASKS_MODULE_NAME = "app._legacy_tasks_file"
_LEGACY_TASKS_PATH = Path(__file__).resolve().parents[1] / "tasks.py"


def _load_legacy_tasks_module() -> ModuleType | None:
    module = sys.modules.get(_LEGACY_TASKS_MODULE_NAME)
    if isinstance(module, ModuleType):
        return module

    if not _LEGACY_TASKS_PATH.exists():
        logger.warning("Legacy tasks module not found at %s", _LEGACY_TASKS_PATH)
        return None

    spec = importlib.util.spec_from_file_location(_LEGACY_TASKS_MODULE_NAME, _LEGACY_TASKS_PATH)
    if spec is None or spec.loader is None:
        logger.warning("Could not build import spec for %s", _LEGACY_TASKS_PATH)
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[_LEGACY_TASKS_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("Failed to load legacy tasks module from %s", _LEGACY_TASKS_PATH)
        sys.modules.pop(_LEGACY_TASKS_MODULE_NAME, None)
        return None
    return module


def _placeholder(name: str) -> Dict[str, Any]:
    return {
        "status": "placeholder",
        "task": name,
        "message": f"Legacy compatibility stub loaded from app.tasks.__init__ for {name}",
    }


_legacy_tasks = _load_legacy_tasks_module()

if _legacy_tasks is not None:
    celery = getattr(_legacy_tasks, "celery", celery)
    manual_harvest = getattr(_legacy_tasks, "manual_harvest")
    run_harvest_only = getattr(_legacy_tasks, "run_harvest_only")
    run_harvest_pipeline = getattr(_legacy_tasks, "run_harvest_pipeline")
else:
    def manual_harvest(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return _placeholder("manual_harvest")


    def run_harvest_only(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return _placeholder("run_harvest_only")


    def run_harvest_pipeline(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return _placeholder("run_harvest_pipeline")


try:
    from app.tasks.submission_scheduler_tasks import *  # noqa: F401,F403
except Exception:
    pass


__all__ = [
    "celery",
    "manual_harvest",
    "run_harvest_only",
    "run_harvest_pipeline",
]

