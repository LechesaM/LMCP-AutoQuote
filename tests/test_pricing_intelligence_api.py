from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_pricing_intelligence_endpoint() -> None:
    response = client.get("/rfq-lifecycle/pricing-intelligence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mandatory_human_price_approval"] is True
    assert payload["autonomous_pricing_submission_enabled"] is False


def test_pricing_intelligence_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/pricing-intelligence/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live_procurement_commitment_enabled"] is False
    assert payload["dry_run_enforced"] is True


def test_pricing_intelligence_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/pricing-intelligence/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "staging"
