from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "local_api_session.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("local_api_session", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ensure_api_session_skips_bootstrap_when_health_is_ok(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()

    monkeypatch.setattr(module, "_probe_health", lambda *args, **kwargs: {"status": "healthy", "health_url": "http://x/health"})

    def _unexpected(*args, **kwargs):  # pragma: no cover - defensive
        raise AssertionError("bootstrap should not be called when health is already healthy")

    monkeypatch.setattr(module, "_start_api", _unexpected)

    payload = module.ensure_api_session(
        health_url="http://127.0.0.1:8011/health",
        host="127.0.0.1",
        port="8011",
        bootstrap=True,
        health_timeout=1.0,
        poll_interval=0.01,
        log_file=tmp_path / "api.log",
    )

    assert payload["status"] == "healthy"
    assert payload["started"] is False
    assert payload["pid"] is None
    assert payload["bootstrapped"] is False


def test_ensure_api_session_refuses_bootstrap_when_disabled(tmp_path: Path) -> None:
    module = _load_module()
    module._probe_health = lambda *args, **kwargs: {"status": "unhealthy", "health_url": "http://x/health", "error": "down"}

    with pytest.raises(RuntimeError, match="bootstrap is disabled"):
        module.ensure_api_session(
            health_url="http://127.0.0.1:8011/health",
            host="127.0.0.1",
            port="8011",
            bootstrap=False,
            health_timeout=1.0,
            poll_interval=0.01,
            log_file=tmp_path / "api.log",
        )


def test_ensure_api_session_bootstraps_and_reports_pid(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    probe_calls = {"count": 0}

    def _probe(*args, **kwargs):
        probe_calls["count"] += 1
        if probe_calls["count"] == 1:
            return {"status": "unhealthy", "health_url": "http://x/health", "error": "down"}
        return {"status": "healthy", "health_url": "http://x/health"}

    class _Proc:
        pid = 4321

        def terminate(self):  # pragma: no cover - safety guard
            pass

        def wait(self, timeout=None):  # pragma: no cover - safety guard
            return 0

        def kill(self):  # pragma: no cover - safety guard
            pass

    monkeypatch.setattr(module, "_probe_health", _probe)
    monkeypatch.setattr(module, "_start_api", lambda *args, **kwargs: _Proc())
    monkeypatch.setattr(module, "_wait_for_health", lambda *args, **kwargs: {"status": "healthy", "health_url": "http://x/health"})

    payload = module.ensure_api_session(
        health_url="http://127.0.0.1:8011/health",
        host="127.0.0.1",
        port="8011",
        bootstrap=True,
        health_timeout=1.0,
        poll_interval=0.01,
        log_file=tmp_path / "api.log",
    )

    assert payload["status"] == "healthy"
    assert payload["started"] is True
    assert payload["pid"] == 4321
    assert payload["bootstrapped"] is True


def test_main_writes_pid_file_when_bootstrapped(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    pid_file = tmp_path / "api.pid"

    monkeypatch.setattr(
        module,
        "ensure_api_session",
        lambda **kwargs: {
            "status": "healthy",
            "started": True,
            "pid": 9876,
            "bootstrapped": True,
            "health": {"status": "healthy"},
            "health_url": "http://127.0.0.1:8011/health",
            "log_file": str(tmp_path / "api.log"),
        },
    )

    exit_code = module.main(["--pid-file", str(pid_file), "--no-bootstrap"])

    assert exit_code == 0
    assert pid_file.read_text(encoding="utf-8") == "9876"
