from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_data_residency_governance_endpoint() -> None:
    response = client.get("/rfq-lifecycle/data-residency-governance")

    assert response.status_code == 200

    payload = response.json()

    assert payload["ready"] is True
    assert payload["environment"] == "staging"
    assert payload["governance_mode"] == "read_only"


def test_data_residency_governance_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/data-residency-governance/latest")

    assert response.status_code == 200

    payload = response.json()

    assert payload["tenant_data_residency_ready"] is True
    assert payload["cross_region_movement_restricted"] is True
    assert payload["dry_run_enforced"] is True
    assert payload["human_supervision_required"] is True


def test_data_residency_governance_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/data-residency-governance/history")

    assert response.status_code == 200

    payload = response.json()

    assert payload["environment"] == "staging"
    assert payload["governance_mode"] == "read_only"
    assert len(payload["history"]) >= 1
