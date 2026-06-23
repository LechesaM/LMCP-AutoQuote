from __future__ import annotations

import importlib


class _DummyRecurringCycleService:
    def list_recurring_cycles(self, limit: int = 20):
        return {
            "status": "ok",
            "recurring_cycle_score": 100.0,
            "recurring_cycle_grade": "sustainable",
            "recurring_cycle_status": "ok",
            "latest_cycle": {"cycle_id": "cycle-3"},
            "cycle_history": [{"cycle_id": "cycle-3"}],
            "longitudinal_pilot_history": [{"cycle_id": "cycle-3"}],
            "recurring_cycle_trends": {"readiness": {"trend": "stable", "delta": 0.0}},
            "governance_compliance_summary": {"status": "PASS", "compliance_rate": 100.0},
            "operational_endurance_indicators": {"clean_cycle_rate": 100.0, "stability_snapshot_count": 1},
            "recurring_stability_snapshots": [{"cycle_id": "cycle-3"}],
            "readiness_history": [{"cycle_id": "cycle-3"}],
            "no_go_history": [{"cycle_id": "cycle-3"}],
            "governance_checkpoint_history": [{"cycle_id": "cycle-3"}],
            "operational_evidence_history": [{"cycle_id": "cycle-3"}],
            "summary_counts": {"PASS": 1, "WARN": 0, "FAIL": 0},
            "warning_indicators": {},
            "warnings": [],
            "window_days": 30,
        }

    def latest_recurring_cycles(self):
        return {
            "status": "ok",
            "latest_cycle": {"cycle_id": "cycle-3"},
            "recurring_cycle_score": 100.0,
            "recurring_cycle_grade": "sustainable",
            "recurring_cycle_status": "ok",
            "recurring_cycle_trends": {"readiness": {"trend": "stable", "delta": 0.0}},
            "governance_compliance_summary": {"status": "PASS", "compliance_rate": 100.0},
            "operational_endurance_indicators": {"clean_cycle_rate": 100.0, "stability_snapshot_count": 1},
            "recurring_stability_snapshots": [{"cycle_id": "cycle-3"}],
            "warning_indicators": {},
            "warnings": [],
            "summary_counts": {"PASS": 1, "WARN": 0, "FAIL": 0},
            "longitudinal_pilot_history": [{"cycle_id": "cycle-3"}],
            "window_days": 30,
        }

    def recurring_cycles_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "cycle_history": [{"cycle_id": "cycle-3"}],
            "longitudinal_pilot_history": [{"cycle_id": "cycle-3"}],
            "recurring_cycle_trends": {"readiness": {"trend": "stable", "delta": 0.0}},
            "governance_compliance_summary": {"status": "PASS", "compliance_rate": 100.0},
            "operational_endurance_indicators": {"clean_cycle_rate": 100.0, "stability_snapshot_count": 1},
            "recurring_stability_snapshots": [{"cycle_id": "cycle-3"}],
            "readiness_history": [{"cycle_id": "cycle-3"}],
            "no_go_history": [{"cycle_id": "cycle-3"}],
            "governance_checkpoint_history": [{"cycle_id": "cycle-3"}],
            "operational_evidence_history": [{"cycle_id": "cycle-3"}],
            "summary_counts": {"PASS": 1, "WARN": 0, "FAIL": 0},
            "warning_indicators": {},
            "warnings": [],
            "window_days": 30,
        }


def test_recurring_cycle_routes_expose_read_only_history(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "recurring_cycle_service", lambda: _DummyRecurringCycleService())

    assert module.recurring_cycles(limit=5)["status"] == "ok"
    assert module.recurring_cycles_latest()["recurring_cycle_score"] == 100.0
    assert module.recurring_cycles_history(limit=5)["count"] == 1
