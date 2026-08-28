from __future__ import annotations

import logging
import os

from app.celery_app import celery_app
from app.services.autonomous_submission_governance import autonomous_submission_authorization
from app.services.autonomous_submission_loop_service import run_autonomous_submission_loop

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.submission_scheduler_tasks.run_autonomous_submission_loop_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": int(str(os.getenv("SUBMISSION_RETRY_TASK_MAX_RETRIES", "3")).strip() or "3")},
    acks_late=True,
    time_limit=int(str(os.getenv("SUBMISSION_RETRY_TASK_TIME_LIMIT", "900")).strip() or "900"),
    soft_time_limit=int(str(os.getenv("SUBMISSION_RETRY_TASK_SOFT_TIME_LIMIT", "840")).strip() or "840"),
)
def run_submission_retry_cycle_task(self, limit: int | None = None):
    logger.info("Celery task started: autonomous submission loop | limit=%s", limit)
    governance = autonomous_submission_authorization()
    if not governance["authorized"]:
        return {
            "status": "governance_blocked",
            "scheduler": "autonomous_submission_loop",
            "message": "Celery submission task blocked by governance.",
            "reason": governance["reason"],
            "system_control_state": governance["system_control_state"],
            "total_processed": 0,
        }
    return run_autonomous_submission_loop(limit=limit)

