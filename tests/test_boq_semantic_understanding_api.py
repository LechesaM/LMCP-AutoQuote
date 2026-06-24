from __future__ import annotations

import importlib


class _DummyBoqSemanticUnderstandingService:
    def list_boq_semantic_understanding(self, limit: int = 20):
        return {
            "status": "ok",
            "boq_semantic_understanding_status": "ok",
            "boq_semantic_understanding_score": 88.0,
            "latest_boq_semantic_understanding": {"analysis_id": "boq-semantic-understanding:latest"},
            "boq_semantic_understanding_history": [{"analysis_id": "boq-semantic-understanding:latest"}],
            "boq_semantic_understanding_history_summary": {"analysis_count": 1},
            "boq_item_classification_readiness": {"ready": True, "score": 90.0},
            "trade_package_mapping_readiness": {"ready": True, "score": 88.0},
            "unit_of_measure_normalization_readiness": {"ready": True, "score": 92.0},
            "quantity_interpretation_readiness": {"ready": True, "score": 91.0},
            "measurement_risk_score": 12.0,
            "ambiguous_item_flags": [],
            "missing_specification_flags": [],
            "pricing_preparation_readiness": {"ready": True, "score": 90.0},
            "unresolved_boq_semantic_blockers": [],
            "boq_row_analyses": [{"analysis_id": "boq-semantic:row-1"}],
            "what_this_unlocks": ["BOQ item classification"],
            "warnings": [],
        }

    def latest_boq_semantic_understanding(self):
        return self.list_boq_semantic_understanding()

    def boq_semantic_understanding_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "boq_semantic_understanding_status": "ok",
            "boq_semantic_understanding_score": 88.0,
            "latest_boq_semantic_understanding": {"analysis_id": "boq-semantic-understanding:latest"},
            "boq_semantic_understanding_history": [{"analysis_id": "boq-semantic-understanding:latest"}],
            "boq_semantic_understanding_history_summary": {"analysis_count": 1},
            "warnings": [],
        }


def test_boq_semantic_understanding_routes_expose_read_only_analysis(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "boq_semantic_understanding_service", lambda: _DummyBoqSemanticUnderstandingService())

    assert module.boq_semantic_understanding(limit=5)["boq_semantic_understanding_status"] == "ok"
    assert module.boq_semantic_understanding_latest()["latest_boq_semantic_understanding"]["analysis_id"] == "boq-semantic-understanding:latest"
    assert module.boq_semantic_understanding_history(limit=5)["count"] == 1
