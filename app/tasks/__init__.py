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

from typing import Any, Dict

try:
    from app.celery_app import celery_app as celery
except Exception:
    celery = None


def _placeholder(name: str) -> Dict[str, Any]:
    return {
        "status": "placeholder",
        "task": name,
        "message": f"Legacy compatibility stub loaded from app.tasks.__init__ for {name}",
    }


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


