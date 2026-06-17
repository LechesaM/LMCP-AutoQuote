from __future__ import annotations

import asyncio
import importlib
from pathlib import Path


def _load_api(monkeypatch, tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED", "false")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    from app.services import safe_autonomous_scheduler_service as scheduler_service
    importlib.reload(scheduler_service)

    from app.api import safe_autonomous_scheduler_api as api

    return importlib.reload(api)


def test_safe_scheduler_api_is_read_only_by_default(monkeypatch, tmp_path: Path) -> None:
    api = _load_api(monkeypatch, tmp_path)

    status = api.status(20)
    start = api.start_loop()
    enable = asyncio.run(api.enable())
    disable = api.disable()
    policy = api.update_policy({"enabled": True})
    run_once = asyncio.run(api.run_once())

    assert status["status"] == "ok"
    assert status["api_enabled"] is False
    assert start["status"] == "disabled"
    assert start["action"] == "start-loop"
    assert disable["status"] == "disabled"
    assert disable["action"] == "disable"
    assert policy["status"] == "disabled"
    assert policy["action"] == "policy"
    assert enable["status"] == "disabled"
    assert enable["action"] == "enable"
    assert run_once["status"] == "disabled"
    assert run_once["action"] == "run-once"


def test_safe_scheduler_api_mutating_routes_can_be_opted_in(monkeypatch, tmp_path: Path) -> None:
    api = _load_api(monkeypatch, tmp_path)
    monkeypatch.setenv("SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED", "true")
    api = importlib.reload(api)
    monkeypatch.setattr(api, "start_background_scheduler", lambda: {"status": "ok", "message": "started"})

    status = api.status(20)
    start = api.start_loop()

    assert status["api_enabled"] is True
    assert start["status"] == "ok"
