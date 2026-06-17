from __future__ import annotations

import importlib

from app.celery_app import celery_app
from app.tasks import daily_supervised_production_ritual_tasks as ritual_tasks


def test_daily_supervised_production_ritual_task_builds_cli_arguments(monkeypatch) -> None:
    monkeypatch.setenv("DAILY_SUPERVISED_PRODUCTION_RITUAL_LIMIT", "7")
    monkeypatch.setenv("DAILY_SUPERVISED_PRODUCTION_RITUAL_MAX_TOTAL", "11")
    monkeypatch.setenv("DAILY_SUPERVISED_PRODUCTION_RITUAL_MAX_SUBMISSIONS", "4")
    monkeypatch.setenv("DAILY_SUPERVISED_PRODUCTION_RITUAL_MIN_SUBMITTED", "2")
    monkeypatch.setenv("DAILY_SUPERVISED_PRODUCTION_RITUAL_ENABLE_SUBMIT", "true")
    monkeypatch.setenv("DAILY_SUPERVISED_PRODUCTION_RITUAL_CONFIRM_SUBMIT", "true")

    captured = {}
    def fake_run(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(ritual_tasks, "_run_ritual_cli", fake_run)

    result = ritual_tasks.run_daily_supervised_production_ritual_task()

    assert result["status"] == "ok"
    assert result["exit_code"] == 0
    assert captured["argv"] == [
        "--limit",
        "7",
        "--max-total",
        "11",
        "--max-submissions",
        "4",
        "--min-submitted",
        "2",
        "--enable-submit",
        "--confirm-submit",
    ]


def test_daily_supervised_production_ritual_task_beat_schedule_is_registered() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "daily-supervised-production-ritual" in schedule
    assert schedule["daily-supervised-production-ritual"]["task"] == "app.tasks.daily_supervised_production_ritual_tasks.run_daily_supervised_production_ritual_task"


def test_celery_app_uses_configurable_daily_ritual_interval(monkeypatch) -> None:
    monkeypatch.setenv("DAILY_SUPERVISED_PRODUCTION_RITUAL_INTERVAL_HOURS", "6")
    celery_module = importlib.import_module("app.celery_app")
    celery_module = importlib.reload(celery_module)
    schedule = celery_module.celery_app.conf.beat_schedule["daily-supervised-production-ritual"]["schedule"]
    assert int(schedule.seconds + schedule.days * 86400) == 21600
