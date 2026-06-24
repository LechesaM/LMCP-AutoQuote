from __future__ import annotations

from fastapi.testclient import TestClient

from etenders_acquisition.api.main import app


client = TestClient(app)


def test_tender_knowledge_graph_endpoint() -> None:
    response = client.get("/rfq-lifecycle/tender-knowledge-graph")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ok"
    assert payload["autonomous_graph_decisioning_enabled"] is False


def test_tender_knowledge_graph_latest_endpoint() -> None:
    response = client.get("/rfq-lifecycle/tender-knowledge-graph/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge_graph_readiness"]["ready"] is True
    assert payload["production_graph_learning_enabled"] is False


def test_tender_knowledge_graph_history_endpoint() -> None:
    response = client.get("/rfq-lifecycle/tender-knowledge-graph/history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run_enforced"] is True
    assert payload["human_supervision_required"] is True
