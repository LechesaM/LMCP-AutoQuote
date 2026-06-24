from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_opportunity_scoring_service_ranks_supplier_fit_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.opportunity_scoring_service")
    service = module.OpportunityScoringService(runtime_dir=tmp_path / "runtime" / "staging" / "procurement-intelligence")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-10-003",
                "title": "Supply and delivery of office stationery",
                "description": "Framework agreement for stationery and consumables.",
                "buyer_name": "Sample Municipality",
                "category": "supplies",
                "submission_method": "portal",
                "closing_date": "2026-06-30T00:00:00+00:00",
            }
        ]
    )

    latest = service.latest_opportunity_scoring()
    history = service.opportunity_scoring_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["opportunity_scoring_score"] >= 50.0
    assert latest["latest_opportunity_scoring"]["supplier_fit_scoring"]["supplier_fit_score"] >= 0.0
    assert latest["latest_opportunity_scoring"]["bid_decision"] in {"bid_now", "review", "no_bid"}
    assert latest["latest_opportunity_scoring"]["what_this_unlocks"]
    assert history["count"] >= 1

