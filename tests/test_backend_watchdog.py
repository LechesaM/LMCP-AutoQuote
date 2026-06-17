from __future__ import annotations

import importlib
from pathlib import Path


def test_backend_watchdog_restarts_only_when_unhealthy(monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("scripts.backend_watchdog")
    monkeypatch.setenv("LMCP_WATCHDOG_DIR", str(tmp_path / "watchdog"))

    calls = {"restart": 0}

    monkeypatch.setattr(module, "check_health", lambda backend_url, timeout_seconds=5: {"ok": False, "status": 500, "body": "down", "checked_at": module._now_iso()})
    monkeypatch.setattr(module, "restart_backend", lambda start_command: calls.__setitem__("restart", calls["restart"] + 1))

    result = module.ensure_backend_running("http://127.0.0.1:8011", "echo restart", cooldown_seconds=0)
    assert result["restarted"] is True
    assert calls["restart"] == 1

    monkeypatch.setattr(module, "check_health", lambda backend_url, timeout_seconds=5: {"ok": True, "status": 200, "body": "ok", "checked_at": module._now_iso()})
    result_ok = module.ensure_backend_running("http://127.0.0.1:8011", "echo restart", cooldown_seconds=0)
    assert result_ok["restarted"] is False
    assert result_ok["health"]["ok"] is True


def test_backend_watchdog_honors_cooldown(monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("scripts.backend_watchdog")
    monkeypatch.setenv("LMCP_WATCHDOG_DIR", str(tmp_path / "watchdog"))
    state = module.WatchdogState(last_checked_at=module._now_iso(), last_health_status="unhealthy", last_restart_at=module._now_iso(), restart_count=1)
    module._write_state(state)

    calls = {"restart": 0}
    monkeypatch.setattr(module, "check_health", lambda backend_url, timeout_seconds=5: {"ok": False, "status": 500, "body": "down", "checked_at": module._now_iso()})
    monkeypatch.setattr(module, "restart_backend", lambda start_command: calls.__setitem__("restart", calls["restart"] + 1))

    result = module.ensure_backend_running("http://127.0.0.1:8011", "echo restart", cooldown_seconds=999999)
    assert result["restarted"] is False
    assert result.get("cooldown_active") is True
    assert calls["restart"] == 0


def test_backend_watchdog_waits_for_post_restart_health(monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("scripts.backend_watchdog")
    monkeypatch.setenv("LMCP_WATCHDOG_DIR", str(tmp_path / "watchdog"))
    monkeypatch.setenv("LMCP_WATCHDOG_STARTUP_TIMEOUT_SECONDS", "3")

    calls = {"restart": 0, "wait": 0}

    monkeypatch.setattr(module, "check_health", lambda backend_url, timeout_seconds=5: {"ok": False, "status": 500, "body": "down", "checked_at": module._now_iso()})

    def _restart(start_command):
        calls["restart"] += 1

    def _wait(backend_url, timeout_seconds, poll_interval_seconds=1):
        calls["wait"] += 1
        return {"ok": True, "status": 200, "body": "ok", "checked_at": module._now_iso()}

    monkeypatch.setattr(module, "restart_backend", _restart)
    monkeypatch.setattr(module, "wait_for_healthy_backend", _wait)

    result = module.ensure_backend_running("http://127.0.0.1:8011", "python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8011", cooldown_seconds=0)
    assert result["restarted"] is True
    assert result["startup_health"]["ok"] is True
    assert calls["restart"] == 1
    assert calls["wait"] == 1


def test_backend_watchdog_restarts_from_project_root(monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("scripts.backend_watchdog")
    monkeypatch.setenv("LMCP_WATCHDOG_DIR", str(tmp_path / "watchdog"))
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))

    captured = {}

    def _popen(*args, **kwargs):
        captured["cwd"] = kwargs.get("cwd")
        captured["command"] = args[0] if args else kwargs.get("args")
        class _Proc:
            pass
        return _Proc()

    monkeypatch.setattr(module.subprocess, "Popen", _popen)
    module.restart_backend("python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8011")

    assert captured["cwd"] == str(tmp_path)
    assert captured["command"] == ["python3", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8011"]
