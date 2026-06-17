from __future__ import annotations

import importlib
from pathlib import Path


def test_system_control_defaults_keep_autonomy_disabled(tmp_path: Path, monkeypatch) -> None:
    from app.services import system_control_service as control

    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(control, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(control, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(control, "CONTROL_DIR", runtime_dir / "system_control")
    monkeypatch.setattr(control, "STATE_FILE", runtime_dir / "system_control" / "state.json")
    monkeypatch.setattr(control, "HARVESTER_PAUSE_FILE", runtime_dir / "harvester.paused")
    monkeypatch.setattr(control, "SUBMISSION_PAUSE_FILE", runtime_dir / "submission.paused")
    monkeypatch.setattr(control, "EMERGENCY_STOP_FILE", runtime_dir / "emergency.stop")

    status = control.get_system_control_status()
    turned_on = control.turn_system_on()

    assert status["autonomous_enabled"] is False
    assert status["system_on"] is True
    assert turned_on["autonomous_enabled"] is False
    assert turned_on["system_on"] is True


def test_system_control_reports_controlled_when_v48_policy_is_controlled(tmp_path: Path, monkeypatch) -> None:
    from app.services import system_control_service as control

    runtime_dir = tmp_path / "runtime"
    system_control_dir = runtime_dir / "system_control"
    full_autonomous_dir = runtime_dir / "full_autonomous_v48"
    system_control_dir.mkdir(parents=True, exist_ok=True)
    full_autonomous_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(control, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(control, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(control, "CONTROL_DIR", system_control_dir)
    monkeypatch.setattr(control, "STATE_FILE", system_control_dir / "state.json")
    monkeypatch.setattr(control, "HARVESTER_PAUSE_FILE", runtime_dir / "harvester.paused")
    monkeypatch.setattr(control, "SUBMISSION_PAUSE_FILE", runtime_dir / "submission.paused")
    monkeypatch.setattr(control, "EMERGENCY_STOP_FILE", runtime_dir / "emergency.stop")
    monkeypatch.setattr(control, "V48_STATE_FILE", system_control_dir / "v48_autonomous_state.json")
    monkeypatch.setattr(control, "V48_POLICY_FILE", full_autonomous_dir / "policy.json")

    (system_control_dir / "v48_autonomous_state.json").write_text(
        '{"policy": {"mode": "controlled"}}',
        encoding="utf-8",
    )

    status = control.get_system_control_status()

    assert status["system_on"] is True
    assert status["control_mode"] == "controlled"
    assert status["effective_system_status"] == "controlled"


def test_autonomous_submission_loop_defaults_to_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", "false")

    from app.services import autonomous_submission_loop_service as loop_service

    reloaded = importlib.reload(loop_service)

    result = reloaded.run_autonomous_submission_loop(limit=1, runtime_dir=str(tmp_path / "runtime"))

    assert reloaded.AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED is False
    assert result["status"] == "disabled"


def test_submission_scheduler_defaults_to_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", "false")

    from app.services import submission_scheduler_service as scheduler_service

    reloaded = importlib.reload(scheduler_service)

    result = reloaded.run_submission_retry_cycle(limit=1)

    assert reloaded.AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED is False
    assert result["status"] == "disabled"
