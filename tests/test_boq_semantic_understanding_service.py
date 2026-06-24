from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_boq_semantic_understanding_aggregates_readiness_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.boq_semantic_understanding_service")
    service = module.BoqSemanticUnderstandingService(runtime_dir=tmp_path / "runtime" / "staging" / "boq-semantic-understanding")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-BOQ-010",
                "title": "Supply and install electrical fittings",
                "boq_rows": [
                    {"item_number": 1, "description": "LED light fitting", "specification": "1200mm fitting", "unit": "Each", "quantity": 10},
                    {"item_number": 2, "description": "Cable ducting approx", "specification": "", "unit": "m", "quantity": None},
                ],
            }
        ]
    )

    latest = service.latest_boq_semantic_understanding()
    history = service.boq_semantic_understanding_history(limit=5)

    assert latest["status"] in {"ok", "watch", "blocked"}
    assert latest["boq_semantic_understanding_score"] >= 0.0
    assert latest["latest_boq_semantic_understanding"]["boq_row_count"] >= 1
    assert latest["boq_item_classification_readiness"]["score"] >= 0.0
    assert latest["trade_package_mapping_readiness"]["score"] >= 0.0
    assert latest["unit_of_measure_normalization_readiness"]["score"] >= 0.0
    assert latest["quantity_interpretation_readiness"]["score"] >= 0.0
    assert latest["measurement_risk_score"] >= 0.0
    assert latest["pricing_preparation_readiness"]["score"] >= 0.0
    assert isinstance(latest["ambiguous_item_flags"], list)
    assert isinstance(latest["missing_specification_flags"], list)
    assert isinstance(latest["unresolved_boq_semantic_blockers"], list)
    assert history["count"] >= 1
