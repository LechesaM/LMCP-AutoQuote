from __future__ import annotations

import app.tasks.submission_scheduler_tasks as submission_scheduler_tasks

from app.celery_app import celery_app

def test_submission_retry_task_is_importable_for_manual_invocation() -> None:
    assert callable(submission_scheduler_tasks.run_submission_retry_cycle_task)
    assert (
        submission_scheduler_tasks.run_submission_retry_cycle_task.name
        == "app.tasks.submission_scheduler_tasks.run_autonomous_submission_loop_task"
    )


def test_celery_beat_does_not_schedule_submission_retry_cycle() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "submission-retry-cycle" not in schedule
