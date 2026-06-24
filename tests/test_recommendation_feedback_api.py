from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_recommendation_feedback_endpoint() -> None:
    response = client.get("/rfq-lifecycle/recommendation-feedback")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["autonomous_feedback_learning_enabled"] is False


def test_recommendation_feedback_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/recommendation-feedback/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendation_feedback_readiness"]["ready"] is True
    assert payload["production_calibration_mode_enabled"] is False


def test_recommendation_feedback_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/recommendation-feedback/history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run_enforced"] is True
    assert payload["human_supervision_required"] is True
