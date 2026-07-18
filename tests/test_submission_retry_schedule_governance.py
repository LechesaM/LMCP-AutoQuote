import importlib


def _reload_celery_app(monkeypatch, submission_value=None):
    monkeypatch.setenv("AUTO_HARVEST_SCHEDULE_ENABLED", "false")
    if submission_value is None:
        monkeypatch.delenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", raising=False)
    else:
        monkeypatch.setenv(
            "AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED",
            submission_value,
        )

    import app.celery_app as celery_module

    return importlib.reload(celery_module)


def test_submission_retry_schedule_omitted_when_explicitly_false(monkeypatch):
    module = _reload_celery_app(monkeypatch, "false")
    schedule = module.celery_app.conf.beat_schedule

    assert "submission-retry-cycle" not in schedule
    assert "rfq-harvest-cycle" not in schedule


def test_submission_retry_schedule_omitted_when_missing(monkeypatch):
    module = _reload_celery_app(monkeypatch, None)
    schedule = module.celery_app.conf.beat_schedule

    assert "submission-retry-cycle" not in schedule
    assert "rfq-harvest-cycle" not in schedule


def test_submission_retry_schedule_omitted_when_malformed(monkeypatch):
    module = _reload_celery_app(monkeypatch, "unexpected")
    schedule = module.celery_app.conf.beat_schedule

    assert "submission-retry-cycle" not in schedule
    assert "rfq-harvest-cycle" not in schedule


def test_submission_retry_schedule_enabled_only_with_valid_task(monkeypatch):
    module = _reload_celery_app(monkeypatch, "true")
    schedule = module.celery_app.conf.beat_schedule

    entry = schedule["submission-retry-cycle"]
    task_name = (
        "app.tasks.submission_scheduler_tasks."
        "run_autonomous_submission_loop_task"
    )

    assert entry["task"] == task_name
    assert entry["options"]["queue"] == "retry_queue"
    assert task_name in module.celery_app.tasks
    assert "rfq-harvest-cycle" not in schedule
