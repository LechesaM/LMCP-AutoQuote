from __future__ import annotations

from app.celery_app import celery_app
from app.services.self_clean_scheduler_service import run_scheduled_self_clean


@celery_app.task(name="app.tasks.self_clean_scheduler.run_scheduled_self_clean_task")
def run_scheduled_self_clean_task() -> dict:
    return run_scheduled_self_clean(dry_run=False)
