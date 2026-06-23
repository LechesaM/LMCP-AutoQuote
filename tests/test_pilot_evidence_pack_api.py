from __future__ import annotations

import importlib


class _DummyPilotEvidenceService:
    def list_packs(self, limit: int = 20):
        return {"status": "ok", "count": 1, "packs": [{"pack_id": "pack-1"}], "latest_pack_id": "pack-1"}

    def latest_pack(self):
        return {"status": "ok", "pack": {"pack_id": "pack-1"}, "summary": {"readiness_score": 100.0}, "pack_id": "pack-1"}

    def get_pack(self, pack_id: str):
        return {"status": "ok", "pack_id": pack_id, "pack": {"pack_id": pack_id}}

    def governance_review(self):
        return {
            "status": "ok",
            "readiness_score": 100.0,
            "pilot_authorization_status": "authorized",
            "no_go_indicators": [],
            "operator_sign_off_checklist": [],
            "governance_review_checklist": [],
            "submission_lock_verification": {"status": "PASS"},
            "rollback_evidence": {"status": "PASS"},
            "queue_stability_evidence": {"status": "PASS"},
            "telemetry_health_evidence": {"status": "PASS"},
        }


def test_pilot_evidence_routes_expose_read_only_governance_review(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "pilot_evidence_service", lambda: _DummyPilotEvidenceService())

    assert module.pilot_evidence_history(limit=5)["count"] == 1
    assert module.pilot_evidence_latest()["pack_id"] == "pack-1"
    assert module.pilot_evidence_pack("pack-2")["pack_id"] == "pack-2"
    assert module.pilot_evidence_governance_review()["pilot_authorization_status"] == "authorized"
