from __future__ import annotations

import importlib


class _DummyProcurementIntelligenceService:
    def list_procurement_intelligence(self, limit: int = 20):
        return {
            "status": "ok",
            "procurement_intelligence_status": "ok",
            "procurement_intelligence_score": 91.0,
            "latest_procurement_intelligence": {"analysis_id": "procurement-intelligence:latest"},
            "procurement_intelligence_history": [{"analysis_id": "procurement-intelligence:latest"}],
            "procurement_intelligence_history_summary": {"analysis_count": 1},
            "opportunity_score": 88.0,
            "tender_complexity": {"score": 42.0, "band": "moderate"},
            "risk_flags": ["deadline_elevated"],
            "mandatory_documents": ["company_registration"],
            "submission_urgency": {"label": "elevated", "score": 65.0, "days_left": 10},
            "procurement_category_heatmap": {"summary": {"total_tenders": 1}},
            "supplier_fit_scoring": {"supplier_fit_score": 82.0},
            "warnings": [],
        }

    def latest_procurement_intelligence(self):
        return self.list_procurement_intelligence()

    def procurement_intelligence_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "latest_procurement_intelligence": {"analysis_id": "procurement-intelligence:latest"},
            "procurement_intelligence_history": [{"analysis_id": "procurement-intelligence:latest"}],
            "procurement_intelligence_history_summary": {"analysis_count": 1},
            "warnings": [],
        }


def test_procurement_intelligence_routes_expose_read_only_analysis(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "procurement_intelligence_service", lambda: _DummyProcurementIntelligenceService())

    assert module.procurement_intelligence(limit=5)["procurement_intelligence_status"] == "ok"
    assert module.procurement_intelligence_latest()["latest_procurement_intelligence"]["analysis_id"] == "procurement-intelligence:latest"
    assert module.procurement_intelligence_history(limit=5)["count"] == 1

