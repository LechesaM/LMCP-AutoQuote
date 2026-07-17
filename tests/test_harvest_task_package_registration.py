import app.tasks
from app.celery_app import celery_app
from app.tasks import run_harvest_only
from app.tasks import harvest_tasks
import importlib


def test_app_tasks_resolves_to_package_and_harvest_task_is_registered():
    assert app.tasks.__file__.endswith("/app/tasks/__init__.py")
    assert run_harvest_only.name == "app.tasks.run_harvest_only"
    assert "app.tasks.run_harvest_only" in celery_app.tasks


def test_harvest_beat_schedule_is_omitted_when_disabled(monkeypatch):
    monkeypatch.setenv("AUTO_HARVEST_SCHEDULE_ENABLED", "false")

    import app.celery_app as celery_module

    reloaded = importlib.reload(celery_module)

    assert "rfq-harvest-cycle" not in reloaded.celery_app.conf.beat_schedule


def test_harvest_beat_schedule_targets_registered_task_when_enabled(
    monkeypatch,
):
    monkeypatch.setenv("AUTO_HARVEST_SCHEDULE_ENABLED", "true")
    monkeypatch.setenv("AUTO_HARVEST_SCHEDULE_MINUTES", "30")

    import app.celery_app as celery_module

    reloaded = importlib.reload(celery_module)
    entry = reloaded.celery_app.conf.beat_schedule["rfq-harvest-cycle"]

    assert entry["task"] == "app.tasks.run_harvest_only"
    assert entry["options"]["queue"] == "acquisition_queue"


def test_disabled_auto_harvest_skips_without_calling_entrypoint(monkeypatch):
    monkeypatch.setattr(
        harvest_tasks,
        "AUTO_HARVEST_ENABLED",
        False,
    )

    result = harvest_tasks.run_harvest_only.run(
        max_total=5,
        max_per_source=1,
        persist_to_live_store=False,
        persist_source_health=False,
    )

    assert result["status"] == "skipped"
    assert result["persist_to_live_store"] is False
    assert result["persist_source_health"] is False
    assert result["auto_quote_enabled"] is False
    assert result["autonomous_downstream_enabled"] is False


def test_task_propagates_non_persisting_limits_and_governance_flags(
    monkeypatch,
):
    calls = []

    def fake_entrypoint(**kwargs):
        calls.append(kwargs)
        return {
            "status": "completed",
            "persist_to_live_store": kwargs["persist_to_live_store"],
            "persist_source_health": kwargs["persist_source_health"],
            "auto_quote_enabled": False,
            "autonomous_downstream_enabled": False,
            "result": {"items": []},
        }

    monkeypatch.setattr(
        harvest_tasks,
        "AUTO_HARVEST_ENABLED",
        True,
    )

    from app.services import harvest_entrypoint

    monkeypatch.setattr(
        harvest_entrypoint,
        "run_canonical_harvest",
        fake_entrypoint,
    )

    result = harvest_tasks.run_harvest_only.run(
        max_total=5,
        max_per_source=1,
        persist_to_live_store=False,
        persist_source_health=False,
    )

    assert calls == [
        {
            "max_total": 5,
            "max_per_source": 1,
            "persist_to_live_store": False,
            "persist_source_health": False,
        }
    ]
    assert result["status"] == "ok"
    assert result["persist_to_live_store"] is False
    assert result["persist_source_health"] is False
    assert result["auto_quote_enabled"] is False
    assert result["autonomous_downstream_enabled"] is False


def test_task_failure_result_keeps_downstream_governance_flags_false(
    monkeypatch,
):
    def fake_entrypoint(**_kwargs):
        return {
            "status": "failed",
            "error": "controlled failure",
        }

    monkeypatch.setattr(
        harvest_tasks,
        "AUTO_HARVEST_ENABLED",
        True,
    )

    from app.services import harvest_entrypoint

    monkeypatch.setattr(
        harvest_entrypoint,
        "run_canonical_harvest",
        fake_entrypoint,
    )

    result = harvest_tasks.run_harvest_only.run(
        max_total=5,
        max_per_source=1,
        persist_to_live_store=False,
        persist_source_health=False,
    )

    assert result["status"] == "failed"
    assert result["persist_to_live_store"] is False
    assert result["persist_source_health"] is False
    assert result["auto_quote_enabled"] is False
    assert result["autonomous_downstream_enabled"] is False
    assert result["error"] == "controlled failure"
