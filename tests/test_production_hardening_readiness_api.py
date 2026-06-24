from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_production_hardening_readiness_endpoint() -> None:
    response = client.get("/rfq-lifecycle/production-hardening-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["production_mode_enabled"] is False
    assert payload["production_deployment_execution_enabled"] is False


def test_production_hardening_readiness_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/production-hardening-readiness/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live_credentials_present"] is False
    assert payload["live_external_alerting_enabled"] is False


def test_production_hardening_readiness_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/production-hardening-readiness/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run_enforced"] is True
    assert payload["human_supervision_required"] is True
