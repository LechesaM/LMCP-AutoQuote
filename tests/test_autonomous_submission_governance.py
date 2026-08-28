from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from app import autonomous_engine
from app.services import autonomous_submission_governance as governance
from app.services import autonomous_submission_loop_service as submission_loop
from app.services import submission_scheduler_service
from app.services import system_control_service
from app.services import tender_pipeline
from app.services import tender_submission_pipeline
from app.tasks import submission_scheduler_tasks


AUTHORIZED_STATE = {
    "system_on": True,
    "autonomous_enabled": True,
    "submission_scheduler_enabled": True,
    "submission_paused": False,
    "emergency_stop": False,
}


def _authorize(monkeypatch: pytest.MonkeyPatch, state=AUTHORIZED_STATE) -> None:
    monkeypatch.setattr(governance, "get_system_control_state", lambda: dict(state))
    monkeypatch.setenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("AUTONOMOUS_PENDING_STAGE_ENABLED", "true")


@pytest.mark.parametrize("value", [None, "", "garbage", "false"])
def test_loop_blocks_missing_or_malformed_scheduler_flag(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    _authorize(monkeypatch)
    if value is None:
        monkeypatch.delenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", raising=False)
    else:
        monkeypatch.setenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", value)

    calls: list[str] = []
    monkeypatch.setattr(submission_loop, "run_retry_stage", lambda limit: calls.append("retry") or {})
    monkeypatch.setattr(submission_loop, "run_pending_submission_stage", lambda limit: calls.append("pending") or {})
    monkeypatch.setattr(submission_loop, "_write_last_run", lambda payload: None)

    result = submission_loop.run_autonomous_submission_loop(limit=1)

    assert result["status"] == "governance_blocked"
    assert result["reason"].startswith("environment_flag_not_explicitly_enabled")
    assert calls == []


def test_authorized_loop_enters_existing_controlled_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        submission_loop,
        "run_retry_stage",
        lambda limit: calls.append("retry") or {"total_retried": 0},
    )
    monkeypatch.setattr(
        submission_loop,
        "run_pending_submission_stage",
        lambda limit: calls.append("pending") or {"processed": 0},
    )
    monkeypatch.setattr(submission_loop, "_write_last_run", lambda payload: None)

    result = submission_loop.run_autonomous_submission_loop(limit=1)

    assert result["status"] == "ok"
    assert calls == ["retry", "pending"]


@pytest.mark.parametrize(
    "state",
    [
        {**AUTHORIZED_STATE, "submission_paused": True},
        {**AUTHORIZED_STATE, "emergency_stop": True},
        {**AUTHORIZED_STATE, "system_on": False},
    ],
)
def test_loop_blocks_explicit_system_control_pause(monkeypatch: pytest.MonkeyPatch, state: dict) -> None:
    _authorize(monkeypatch, state)
    monkeypatch.setattr(submission_loop, "_write_last_run", lambda payload: None)
    result = submission_loop.run_autonomous_submission_loop(limit=1)
    assert result["status"] == "governance_blocked"
    assert result["reason"].startswith("system_control_not_authorized")


def test_loop_blocks_unreadable_system_control(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("AUTONOMOUS_PENDING_STAGE_ENABLED", "true")
    monkeypatch.setattr(governance, "get_system_control_state", lambda: (_ for _ in ()).throw(OSError("unreadable")))
    monkeypatch.setattr(submission_loop, "_write_last_run", lambda payload: None)

    result = submission_loop.run_autonomous_submission_loop(limit=1)

    assert result["status"] == "governance_blocked"
    assert result["reason"].startswith("system_control_unreadable")


def test_loop_blocks_missing_or_ambiguous_system_control_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize(monkeypatch, {"system_on": True, "autonomous_enabled": "true"})
    monkeypatch.setattr(submission_loop, "_write_last_run", lambda payload: None)

    result = submission_loop.run_autonomous_submission_loop(limit=1)

    assert result["status"] == "governance_blocked"
    assert result["reason"] == "system_control_not_authorized:autonomous_enabled"


def test_pending_stage_requires_its_explicit_environment_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize(monkeypatch)
    monkeypatch.delenv("AUTONOMOUS_PENDING_STAGE_ENABLED", raising=False)
    monkeypatch.setattr(submission_loop, "_find_pending_stage_callable", lambda: pytest.fail("hook must not resolve"))

    result = submission_loop.run_pending_submission_stage(limit=1)

    assert result["status"] == "governance_blocked"
    assert result["reason"] == "environment_flag_not_explicitly_enabled:AUTONOMOUS_PENDING_STAGE_ENABLED"


def test_pending_pipeline_entry_is_blocked_before_state_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", raising=False)
    monkeypatch.delenv("AUTONOMOUS_PENDING_STAGE_ENABLED", raising=False)
    monkeypatch.setattr(governance, "get_system_control_state", lambda: dict(AUTHORIZED_STATE))

    result = tender_pipeline.process_pending_submissions(limit=1)

    assert result["status"] == "governance_blocked"
    assert result["processed"] == 0


def test_system_control_defaults_pause_autonomous_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(system_control_service, "CONTROL_DIR", runtime_root / "system_control")
    monkeypatch.setattr(system_control_service, "STATE_FILE", runtime_root / "system_control" / "state.json")
    monkeypatch.setattr(system_control_service, "HARVESTER_PAUSE_FILE", runtime_root / "harvester.paused")
    monkeypatch.setattr(system_control_service, "SUBMISSION_PAUSE_FILE", runtime_root / "submission.paused")
    monkeypatch.setattr(system_control_service, "EMERGENCY_STOP_FILE", runtime_root / "emergency.stop")

    state = system_control_service.SystemControlService().get_status()

    assert state["system_on"] is True  # master switch remains available to human workflows
    assert state["autonomous_enabled"] is False
    assert state["submission_scheduler_enabled"] is False
    assert state["submission_paused"] is True
    assert state["state_file"] == str(runtime_root / "system_control" / "state.json")


def test_explicit_submission_pause_overrides_conflicting_scheduler_enable() -> None:
    normalized = system_control_service.SystemControlService()._normalize_state(
        {
            "system_on": True,
            "autonomous_enabled": True,
            "submission_scheduler_enabled": True,
            "submission_paused": True,
            "emergency_stop": False,
        }
    )

    assert normalized["submission_scheduler_enabled"] is False
    assert normalized["submission_paused"] is True


def test_system_on_false_blocks_engine_and_portal_submission_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {**AUTHORIZED_STATE, "system_on": False}
    monkeypatch.setattr(governance, "get_system_control_state", lambda: dict(state))
    monkeypatch.setattr(autonomous_engine, "_import_harvester", lambda: pytest.fail("harvester must not run"))
    logged: list[dict] = []
    monkeypatch.setattr(tender_submission_pipeline, "_log_submission_history_if_available", lambda *args: logged.append({}))

    engine_result = autonomous_engine.run_autonomous_cycle()
    submission_result = tender_submission_pipeline.submit_tender_to_portal({"portal_url": "https://example.invalid"})

    assert engine_result["skipped"] is True
    assert engine_result["skipped_reason"] == "system_control_not_authorized:system_on"
    assert submission_result["status"] == "skipped"
    assert submission_result["reason"] == "system_control_not_authorized:system_on"
    assert logged == []


def test_manual_portal_submission_behavior_remains_available_when_master_control_allows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manual_state = {"system_on": True, "submission_paused": False, "emergency_stop": False}
    monkeypatch.setattr(governance, "get_system_control_state", lambda: dict(manual_state))
    monkeypatch.setattr(tender_submission_pipeline, "_duplicate_submission_guard", lambda payload: None)
    monkeypatch.setattr(tender_submission_pipeline, "_log_submission_history_if_available", lambda *args: None)
    monkeypatch.setattr(tender_submission_pipeline, "PORTAL_AUTOMATION_ENABLED", False)
    attachment = tmp_path / "manual.pdf"
    attachment.write_bytes(b"manual-test")

    result = tender_submission_pipeline.submit_tender_to_portal(
        {"buyer_rfq_number": "MANUAL-1", "portal_url": "https://example.invalid", "final_pdf_path": str(attachment)}
    )

    assert result["status"] == "submitted"
    assert result["success"] is True


def test_scheduler_service_does_not_write_heartbeat_when_governance_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", raising=False)
    monkeypatch.setattr(governance, "get_system_control_state", lambda: dict(AUTHORIZED_STATE))
    monkeypatch.setattr(submission_scheduler_service, "_write_scheduler_heartbeat", lambda status: pytest.fail("heartbeat must not write"))

    result = submission_scheduler_service.run_submission_retry_cycle(limit=1)

    assert result["status"] == "governance_blocked"


def test_celery_submission_task_blocks_before_invoking_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", raising=False)
    monkeypatch.setattr(governance, "get_system_control_state", lambda: dict(AUTHORIZED_STATE))
    monkeypatch.setattr(submission_scheduler_tasks, "run_autonomous_submission_loop", lambda **kwargs: pytest.fail("loop must not run"))

    result = submission_scheduler_tasks.run_submission_retry_cycle_task.run(limit=1)

    assert result["status"] == "governance_blocked"


def test_celery_beat_registration_is_absent_when_scheduler_flag_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_HARVEST_SCHEDULE_ENABLED", "false")
    monkeypatch.setenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", "false")
    import app.celery_app as celery_module

    module = importlib.reload(celery_module)
    assert "submission-retry-cycle" not in module.celery_app.conf.beat_schedule
