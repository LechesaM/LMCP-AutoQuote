from __future__ import annotations

import importlib


def test_dashboard_endpoints_expose_handwriting_stack_url(monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
    monkeypatch.setenv("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
    monkeypatch.setenv("LMCP_LOG_DIR", "/private/tmp/lmcp-logs")

    dashboard = importlib.import_module("app.api.dashboard")

    system_health = dashboard.dashboard_system_health()
    summary = dashboard.dashboard_summary()

    assert system_health["handwriting_stack_url"] == "/handwriting-stack/status"
    assert summary["handwriting_stack_url"] == "/handwriting-stack/status"
