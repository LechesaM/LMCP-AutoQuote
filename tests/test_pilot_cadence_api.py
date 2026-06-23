from __future__ import annotations

import importlib


class _DummyCadenceService:
    def list_cadence(self, limit: int = 20):
        return {
            "status": "ok",
            "cadence_score": 100.0,
            "cadence_grade": "on_track",
            "warnings": [],
            "warning_indicators": {},
            "pilot_cycle_cadence": {"compliant": True},
            "governance_review_cadence": {"compliant": True},
            "stability_trend_checkpoints": {"cadence_compliant": True},
            "readiness_checkpoints": [],
            "cycle_history": [{"id": "cycle-1"}],
            "governance_review_history": [{"id": "export-1"}],
            "stability_snapshot": {},
        }

    def latest_cadence(self):
        return {
            "status": "ok",
            "cadence_score": 100.0,
            "cadence_grade": "on_track",
            "warnings": [],
            "warning_indicators": {},
            "latest_cycle": {"id": "cycle-1"},
            "latest_governance_review": {"id": "export-1"},
            "latest_stability": {},
            "cadence": {"pilot_cycle_cadence": {"compliant": True}},
        }

    def cadence_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "cycles": [{"id": "cycle-1"}],
            "governance_reviews": [{"id": "export-1"}],
            "checkpoints": [],
            "cadence": {"pilot_cycle_cadence": {"compliant": True}},
            "warning_indicators": {},
            "warnings": [],
        }


def test_cadence_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "cadence_service", lambda: _DummyCadenceService())

    assert module.cadence(limit=5)["status"] == "ok"
    assert module.cadence_latest()["cadence_score"] == 100.0
    assert module.cadence_history(limit=5)["count"] == 1
