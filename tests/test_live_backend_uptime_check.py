from __future__ import annotations

import importlib


def test_live_backend_uptime_check_monitor_only_mode(monkeypatch) -> None:
    module = importlib.import_module("scripts.live_backend_uptime_check")

    calls = {"start": 0, "cleanup": 0, "health": 0}
    ticks = iter([1000.0, 1000.0, 1001.0, 1002.0, 1003.0])

    monkeypatch.setattr(module, "_start_backend", lambda host, port: calls.__setitem__("start", calls["start"] + 1))
    monkeypatch.setattr(module, "_login", lambda api_base: "token")

    def _curl_json(url: str, *, token=None, timeout=10):
        calls["health"] += 1
        if url.endswith("/health"):
            return {"status": "healthy"}
        return {"status": "ok", "data_source": "runtime"}

    monkeypatch.setattr(module, "_curl_json", _curl_json)
    monkeypatch.setattr(module, "_assert_paper", lambda token, api_base: {"review_ready": True})
    monkeypatch.setattr(module, "_assert_route_shape", lambda token, api_base, path, allowed_status, timeout=10: {"status": "ok", "data_source": "runtime", "prometheus": True} if "prometheus" in path else {"status": "ok", "data_source": "runtime"})
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))

    assert module.main(["--no-start-backend", "--duration-seconds", "0", "--interval-seconds", "0", "--health-timeout", "1"]) == 0
    assert calls["start"] == 0
    assert calls["health"] >= 1


def test_live_backend_uptime_check_starts_and_cleans_backend(monkeypatch) -> None:
    module = importlib.import_module("scripts.live_backend_uptime_check")

    calls = {"start": 0, "terminate": 0, "wait": 0}
    ticks = iter([2000.0, 2000.0, 2001.0, 2002.0, 2003.0])

    class _Proc:
        def terminate(self) -> None:
            calls["terminate"] += 1

        def wait(self, timeout: int | None = None) -> None:
            calls["wait"] += 1

    monkeypatch.setattr(module, "_start_backend", lambda host, port: calls.__setitem__("start", calls["start"] + 1) or _Proc())
    monkeypatch.setattr(module, "_login", lambda api_base: "token")
    monkeypatch.setattr(module, "_curl_json", lambda url, **kwargs: {"status": "healthy"} if url.endswith("/health") else {"status": "ok", "data_source": "runtime"})
    monkeypatch.setattr(module, "_assert_paper", lambda token, api_base: {"review_ready": True})
    monkeypatch.setattr(module, "_assert_route_shape", lambda token, api_base, path, allowed_status, timeout=10: {"status": "ok", "data_source": "runtime", "prometheus": True} if "prometheus" in path else {"status": "ok", "data_source": "runtime"})
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))

    assert module.main(["--duration-seconds", "0", "--interval-seconds", "0", "--health-timeout", "1"]) == 0
    assert calls["start"] == 1
    assert calls["terminate"] == 1
    assert calls["wait"] >= 1
