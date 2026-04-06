from __future__ import annotations

from celery import Celery

REDIS_URL = "redis://redis:6379/0"

celery = Celery(
    "lmcp",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)

celery.conf.update(
    timezone="Africa/Johannesburg",
    enable_utc=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "run-autonomous-cycle-every-30-minutes": {
            "task": "app.tasks.run_autonomous_cycle",
            "schedule": 30 * 60,
        },
    },
)

# Force task registration on startup
import app.tasks  # noqa: F401

# Optional alias so both imports work:
# from app.celery_app import celery
# from app.celery_app import celery_app
celery_app = celery
