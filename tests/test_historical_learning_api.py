from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_historical_learning_endpoint() -> None:
    response = client.get("/rfq-lifecycle/historical-learning")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["autonomous_learning_execution_enabled"] is False


def test_historical_learning_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/historical-learning/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["historical_learning_readiness"]["ready"] is True
    assert payload["production_learning_mode_enabled"] is False


def test_historical_learning_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/historical-learning/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run_enforced"] is True
    assert payload["human_supervision_required"] is True
