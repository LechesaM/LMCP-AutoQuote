from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_executive_decision_workspace_endpoint() -> None:
    response = client.get("/rfq-lifecycle/executive-decision-workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["executive_review_readiness"]["ready"] is True
    assert payload["autonomous_executive_approval_enabled"] is False
    assert payload["executive_human_approval_required"] is True


def test_executive_decision_workspace_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/executive-decision-workspace/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_submission_authority_enabled"] is False
    assert payload["dry_run_enforced"] is True


def test_executive_decision_workspace_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/executive-decision-workspace/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["human_supervision_required"] is True
    assert payload["escalation_review_required"] is True
