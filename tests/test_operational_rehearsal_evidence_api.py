from __future__ import annotations

import importlib


class _DummyService:
    def list_rehearsals(self, limit: int = 20):
        return {"status": "ok", "count": 1, "runs": [{"run_id": "run-1"}]}

    def latest_rehearsal(self):
        return {"status": "ok", "run_id": "run-1", "timeline": [], "warning_banners": [], "operational_health": {"status": "ok"}, "drill_outcomes": {}, "artifact_summary": {}}

    def get_rehearsal(self, run_id: str):
        return {"status": "ok", "run_id": run_id}


def test_rfq_lifecycle_rehearsal_routes_expose_read_only_evidence(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "rehearsal_service", lambda: _DummyService())

    assert module.rehearsal_history(limit=5)["count"] == 1
    assert module.rehearsal_latest()["run_id"] == "run-1"
    assert module.rehearsal_run("run-2")["run_id"] == "run-2"
