from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_tender_strategy_governance_endpoint() -> None:
    response = client.get("/rfq-lifecycle/tender-strategy-governance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["bid_no_bid_readiness"]["ready"] is True
    assert payload["autonomous_bid_submission_enabled"] is False
    assert payload["bid_no_bid_human_approval_required"] is True


def test_tender_strategy_governance_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/tender-strategy-governance/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["executive_review_required"] is True
    assert payload["production_submission_authority_enabled"] is False


def test_tender_strategy_governance_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/tender-strategy-governance/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run_enforced"] is True
    assert payload["human_supervision_required"] is True
