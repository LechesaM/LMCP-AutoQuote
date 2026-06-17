from __future__ import annotations

import importlib


def test_top_level_status_includes_handwriting_stack_url(monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
    monkeypatch.setenv("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
    monkeypatch.setenv("LMCP_LOG_DIR", "/private/tmp/lmcp-logs")

    main = importlib.import_module("app.main")

    root_payload = main.root()
    health_payload = main.health()

    assert root_payload["handwriting_stack_url"] == "/handwriting-stack/status"
    assert health_payload["handwriting_stack_url"] == "/handwriting-stack/status"
