from __future__ import annotations

import importlib


def test_main_exposes_health_and_status_routes() -> None:
    main = importlib.import_module("app.main")

    routes = {route.path for route in main.app.routes}

    assert "/health" in routes
    assert "/status" in routes


def test_health_payload_confirms_api_is_alive(monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
    monkeypatch.setenv("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

    main = importlib.import_module("app.main")

    payload = main.health()

    assert payload["status"] == "healthy"
    assert payload["alive"] is True
    assert payload["timestamp"]


def test_status_payload_reports_backend_dependencies(monkeypatch) -> None:
    main = importlib.import_module("app.main")

    monkeypatch.setattr(
        main,
        "_probe_database_connectivity",
        lambda: {"configured": True, "connected": True, "status": "ok"},
    )
    monkeypatch.setattr(
        main,
        "_probe_broker_connectivity",
        lambda: {"configured": True, "connected": False, "status": "error", "error": "ConnectionError"},
    )

    payload = main.status()

    assert payload["api_status"] == "alive"
    assert payload["database"] == {"configured": True, "connected": True, "status": "ok"}
    assert payload["broker"]["configured"] is True
    assert payload["broker"]["connected"] is False
    assert payload["broker"]["status"] == "error"
    assert payload["environment"] == main.settings.environment
    assert payload["timestamp"]
