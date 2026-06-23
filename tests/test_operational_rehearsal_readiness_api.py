from __future__ import annotations

import importlib


class _DummyService:
    def readiness_summary(self, limit: int = 20):
        return {
            "status": "ok",
            "readiness_score": 91.5,
            "readiness_grade": "ready",
            "metrics": {"rehearsal_success_rate": 100.0},
            "warning_threshold_indicators": {"score_below_threshold": False},
            "thresholds": {"readiness_score": 70.0},
            "trend_summary": {"trend": "improving", "delta": 3.0},
            "cadence": {"runs_last_7_days": 2},
            "history": [{"run_id": "run-1"}],
        }

    def readiness_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "runs": [{"run_id": "run-1", "readiness_score": 91.5}],
            "trend_summary": {"trend": "improving"},
            "cadence": {"runs_last_7_days": 2},
            "warning_threshold_indicators": {"score_below_threshold": False},
        }

    def latest_rehearsal(self):
        return {
            "status": "ok",
            "run_id": "run-1",
            "timeline": [],
            "warning_banners": [],
            "operational_health": {"status": "ok"},
            "drill_outcomes": {},
            "artifact_summary": {},
            "readiness": {"readiness_score": 91.5},
        }

    def get_rehearsal(self, run_id: str):
        return {"status": "ok", "run_id": run_id}


def test_rfq_lifecycle_rehearsal_readiness_routes_expose_read_only_scoring(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "rehearsal_service", lambda: _DummyService())

    summary = module.rehearsal_readiness()
    history = module.rehearsal_readiness_history(limit=5)

    assert summary["status"] == "ok"
    assert summary["readiness_score"] == 91.5
    assert summary["readiness_grade"] == "ready"
    assert summary["trend_summary"]["trend"] == "improving"
    assert history["count"] == 1
    assert history["runs"][0]["readiness_score"] == 91.5
