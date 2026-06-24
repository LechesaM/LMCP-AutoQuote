from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_controlled_automation_orchestration_endpoint() -> None:
    response = client.get("/rfq-lifecycle/controlled-automation-orchestration")

    assert response.status_code == 200
    payload = response.json()
    assert payload["automation_readiness_score"] >= 0
    assert payload["orchestration_plan_readiness"]["ready"] is True
    assert payload["final_automation_enabled"] is False


def test_controlled_automation_orchestration_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/controlled-automation-orchestration/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["guardrail_readiness"]["ready"] is True
    assert payload["dry_run_enforced"] is True


def test_controlled_automation_orchestration_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/controlled-automation-orchestration/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["human_supervision_required"] is True
    assert payload["rollback_planning_required"] is True

