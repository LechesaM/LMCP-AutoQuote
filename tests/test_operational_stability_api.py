from __future__ import annotations

import importlib


class _DummyStabilityService:
    def list_stability(self, limit: int = 20):
        return {
            "status": "ok",
            "stability_score": 92.0,
            "stability_grade": "stable",
            "stability": {"readiness_drift": {"trend": "stable", "delta": 0.0}},
            "cycle_history": [{"cycle_id": "cycle-1"}],
            "rehearsal_history": [{"run_id": "rehearsal-1"}],
            "warning_indicators": {},
            "drift_warnings": [],
            "latest_cycle": {"cycle_id": "cycle-1"},
            "latest_governance_export": {"export_id": "export-1"},
        }

    def latest_stability(self):
        return {
            "status": "ok",
            "stability_score": 92.0,
            "stability_grade": "stable",
            "stability": {"readiness_drift": {"trend": "stable", "delta": 0.0}},
            "warning_indicators": {},
            "drift_warnings": [],
        }

    def stability_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "cycles": [{"cycle_id": "cycle-1"}],
            "rehearsals": [{"run_id": "rehearsal-1"}],
            "stability": {"readiness_drift": {"trend": "stable", "delta": 0.0}},
            "warning_indicators": {},
        }


def test_stability_routes_expose_read_only_monitoring(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "stability_service", lambda: _DummyStabilityService())

    assert module.stability(limit=5)["status"] == "ok"
    assert module.stability_latest()["stability_score"] == 92.0
    assert module.stability_history(limit=5)["count"] == 1
