from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_vector_intelligence_endpoint() -> None:
    response = client.get("/rfq-lifecycle/vector-intelligence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["autonomous_vector_decisioning_enabled"] is False


def test_vector_intelligence_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/vector-intelligence/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["vector_intelligence_readiness"]["ready"] is True
    assert payload["production_vector_learning_enabled"] is False


def test_vector_intelligence_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/vector-intelligence/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run_enforced"] is True
    assert payload["human_supervision_required"] is True
