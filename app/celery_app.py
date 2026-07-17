from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://redis:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://redis:6379/0"))
SUBMISSION_RETRY_SCHEDULE_MINUTES = int(str(os.getenv("SUBMISSION_RETRY_SCHEDULE_MINUTES", "15")).strip() or "15")
SUBMISSION_RETRY_BATCH_LIMIT = int(str(os.getenv("SUBMISSION_RETRY_BATCH_LIMIT", "10")).strip() or "10")

AUTO_HARVEST_SCHEDULE_ENABLED = (
    str(os.getenv("AUTO_HARVEST_SCHEDULE_ENABLED", "false")).strip().lower()
    in {"1", "true", "yes", "on"}
)
AUTO_HARVEST_SCHEDULE_MINUTES = int(
    str(os.getenv("AUTO_HARVEST_SCHEDULE_MINUTES", "30")).strip() or "30"
)

WORKER_CONCURRENCY = int(str(os.getenv("WORKER_CONCURRENCY", "2")).strip() or "2")
MAX_TASKS_PER_CHILD = int(str(os.getenv("MAX_TASKS_PER_CHILD", "100")).strip() or "100")
PREFETCH_MULTIPLIER = int(str(os.getenv("PREFETCH_MULTIPLIER", "1")).strip() or "1")
QUEUE_WORKER_COUNT = int(str(os.getenv("QUEUE_WORKER_COUNT", "1")).strip() or "1")
CELERY_WORKER_POOL = str(os.getenv("CELERY_WORKER_POOL", "prefork")).strip() or "prefork"
ACQUISITION_WORKER_CONCURRENCY = int(str(os.getenv("ACQUISITION_WORKER_CONCURRENCY", "4")).strip() or "4")
PARSING_WORKER_CONCURRENCY = int(str(os.getenv("PARSING_WORKER_CONCURRENCY", "3")).strip() or "3")
PROOF_WORKER_CONCURRENCY = int(str(os.getenv("PROOF_WORKER_CONCURRENCY", "2")).strip() or "2")

celery_app = Celery(
    "lmcp_autoquote",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

beat_schedule = {
    "submission-retry-cycle": {
        "task": "app.tasks.submission_scheduler_tasks.run_submission_retry_cycle_task",
        "schedule": crontab(
            minute=f"*/{max(1, SUBMISSION_RETRY_SCHEDULE_MINUTES)}"
        ),
        "kwargs": {"limit": SUBMISSION_RETRY_BATCH_LIMIT},
    },
}

if AUTO_HARVEST_SCHEDULE_ENABLED:
    beat_schedule["rfq-harvest-cycle"] = {
        "task": "app.tasks.run_harvest_only",
        "schedule": crontab(
            minute=f"*/{max(1, AUTO_HARVEST_SCHEDULE_MINUTES)}"
        ),
        "options": {"queue": "acquisition_queue"},
    }

celery_app.conf.update(
    imports=(
        "app.tasks.harvest_tasks",
        "app.tasks.submission_scheduler_tasks",
    ),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=os.getenv("CELERY_TIMEZONE", "Africa/Johannesburg"),
    enable_utc=False,
    task_track_started=True,
    worker_pool=CELERY_WORKER_POOL,
    worker_concurrency=WORKER_CONCURRENCY,
    worker_max_tasks_per_child=MAX_TASKS_PER_CHILD,
    worker_prefetch_multiplier=PREFETCH_MULTIPLIER,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=int(str(os.getenv("CELERY_TASK_TIME_LIMIT", "1800")).strip() or "1800"),
    task_soft_time_limit=int(str(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "1500")).strip() or "1500"),
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("acquisition_queue"),
        Queue("parsing_queue"),
        Queue("pricing_queue"),
        Queue("proof_queue"),
        Queue("retry_queue"),
    ),
    task_routes={
        "app.tasks.run_harvest_only": {
            "queue": "acquisition_queue"
        },
        "app.tasks.rfq_lifecycle_acquisition_task": {"queue": "acquisition_queue"},
        "app.tasks.rfq_lifecycle_parsing_task": {"queue": "parsing_queue"},
        "app.tasks.rfq_lifecycle_pricing_task": {"queue": "pricing_queue"},
        "app.tasks.rfq_lifecycle_proof_task": {"queue": "proof_queue"},
        "app.tasks.rfq_lifecycle_retry_task": {"queue": "retry_queue"},
        "app.tasks.run_rfq_lifecycle_golden_cycle": {"queue": "retry_queue"},
    },
    result_expires=int(str(os.getenv("CELERY_RESULT_EXPIRES", "86400")).strip() or "86400"),
    beat_schedule=beat_schedule,
)

celery_app.conf.lifecycle_worker_concurrency = {
    "default": WORKER_CONCURRENCY,
    "acquisition_queue": ACQUISITION_WORKER_CONCURRENCY,
    "parsing_queue": PARSING_WORKER_CONCURRENCY,
    "pricing_queue": int(str(os.getenv("PRICING_WORKER_CONCURRENCY", "2")).strip() or "2"),
    "proof_queue": PROOF_WORKER_CONCURRENCY,
    "retry_queue": int(str(os.getenv("RETRY_WORKER_CONCURRENCY", "2")).strip() or "2"),
}

celery_app.conf.lifecycle_worker_count = {
    "default": QUEUE_WORKER_COUNT,
    "acquisition_queue": int(str(os.getenv("ACQUISITION_QUEUE_WORKER_COUNT", str(QUEUE_WORKER_COUNT))).strip() or str(QUEUE_WORKER_COUNT)),
    "parsing_queue": int(str(os.getenv("PARSING_QUEUE_WORKER_COUNT", str(QUEUE_WORKER_COUNT))).strip() or str(QUEUE_WORKER_COUNT)),
    "pricing_queue": int(str(os.getenv("PRICING_QUEUE_WORKER_COUNT", str(QUEUE_WORKER_COUNT))).strip() or str(QUEUE_WORKER_COUNT)),
    "proof_queue": int(str(os.getenv("PROOF_QUEUE_WORKER_COUNT", str(QUEUE_WORKER_COUNT))).strip() or str(QUEUE_WORKER_COUNT)),
    "retry_queue": int(str(os.getenv("RETRY_QUEUE_WORKER_COUNT", str(QUEUE_WORKER_COUNT))).strip() or str(QUEUE_WORKER_COUNT)),
}

celery_app.autodiscover_tasks([
    "app.tasks",
])
