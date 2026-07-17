from __future__ import annotations

"""
Celery task package and legacy compatibility bridge.

Public compatibility exports:
- celery
- manual_harvest
- run_harvest_only
- run_harvest_pipeline

The harvest task is implemented in app.tasks.harvest_tasks.
"""

from typing import Any, Dict

try:
    from app.celery_app import celery_app as celery
except Exception:
    celery = None


from app.tasks.harvest_tasks import (  # noqa: E402,F401
    manual_harvest,
    run_harvest_only,
)


def run_harvest_pipeline(
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Legacy compatibility placeholder.

    The production pipeline task remains outside the scope of the
    harvest-scheduler repair.
    """
    return {
        "status": "placeholder",
        "task": "run_harvest_pipeline",
        "message": (
            "Legacy compatibility stub loaded from app.tasks "
            "for run_harvest_pipeline"
        ),
    }


try:
    from app.tasks.submission_scheduler_tasks import *  # noqa: F401,F403,E402
except Exception:
    pass
