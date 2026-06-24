from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_risk_scoring_service_identifies_risk_flags_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.risk_scoring_service")
    service = module.RiskScoringService(runtime_dir=tmp_path / "runtime" / "staging" / "procurement-intelligence")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-10-002",
                "title": "Mandatory briefing supply contract",
                "description": "Supply and delivery with compulsory briefing and site inspection.",
                "buyer_name": "High Risk Buyer",
                "category": "supplies",
                "submission_method": "email",
                "closing_date": "2026-06-25T00:00:00+00:00",
            }
        ]
    )

    latest = service.latest_risk_scoring()
    history = service.risk_scoring_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["risk_scoring_score"] >= 35.0
    assert latest["latest_risk_scoring"]["risk_flags"]
    assert latest["latest_risk_scoring"]["risk_level"] in {"medium", "high", "critical"}
    assert latest["latest_risk_scoring"]["risk_recommendation"] in {"review", "no_bid"}
    assert history["count"] >= 1

