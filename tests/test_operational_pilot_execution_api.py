from __future__ import annotations

import importlib


class _DummyService:
    def list_operational_pilot_execution(self, limit: int = 20):
        return {
            "status": "ok",
            "operational_pilot_execution_status": "ok",
            "operational_endurance_score": 96.0,
            "sustained_stability_score": 95.5,
            "latest_operational_pilot_execution": {"cycle_id": "cycle-ready"},
            "execution_governance_history": [{"cycle_id": "cycle-ready"}],
            "operational_pilot_execution_history_summary": {"cycle_count": 1},
            "operational_review_intervals": {"queue": {"trend": "stable"}},
            "warnings": [],
        }

    def latest_operational_pilot_execution(self):
        return {
            "status": "ok",
            "operational_pilot_execution_status": "ok",
            "operational_endurance_score": 96.0,
            "sustained_stability_score": 95.5,
            "latest_operational_pilot_execution": {"cycle_id": "cycle-ready"},
            "execution_governance_history": [{"cycle_id": "cycle-ready"}],
            "operational_pilot_execution_history_summary": {"cycle_count": 1},
            "operational_review_intervals": {"queue": {"trend": "stable"}},
            "warnings": [],
        }

    def operational_pilot_execution_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "execution_governance_history": [{"cycle_id": "cycle-ready"}],
            "operational_pilot_execution_history_summary": {"cycle_count": 1},
            "operational_review_intervals": {"queue": {"trend": "stable"}},
            "warnings": [],
        }


def test_operational_pilot_execution_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "operational_pilot_execution_service", lambda: _DummyService())

    assert module.operational_pilot_execution(limit=5)["operational_pilot_execution_status"] == "ok"
    assert module.operational_pilot_execution_latest()["latest_operational_pilot_execution"]["cycle_id"] == "cycle-ready"
    assert module.operational_pilot_execution_history(limit=5)["count"] == 1
