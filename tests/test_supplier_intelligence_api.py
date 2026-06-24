from __future__ import annotations

import importlib


class _DummySupplierIntelligenceService:
    def list_supplier_intelligence(self, limit: int = 20):
        return {
            "status": "ok",
            "supplier_intelligence_status": "ok",
            "supplier_intelligence_score": 88.0,
            "latest_supplier_intelligence": {"analysis_id": "supplier-intelligence:latest"},
            "supplier_intelligence_history": [{"analysis_id": "supplier-intelligence:latest"}],
            "supplier_intelligence_history_summary": {"analysis_count": 1},
            "supplier_fit_score": 90.0,
            "delivery_risk_score": 22.0,
            "compliance_readiness": 92.0,
            "pricing_reliability": 89.0,
            "geographic_suitability": 100.0,
            "capacity_suitability": 86.0,
            "supplier_document_readiness": 94.0,
            "supplier_risk_flags": [],
            "recommended_supplier_tier": "A",
            "unresolved_supplier_blockers": [],
            "supplier_rankings": [{"analysis_id": "supplier-intelligence:latest"}],
            "supplier_category_heatmap": {"summary": {"total_suppliers": 1}},
            "what_this_unlocks": ["supplier fit scoring"],
            "warnings": [],
        }

    def latest_supplier_intelligence(self):
        return self.list_supplier_intelligence()

    def supplier_intelligence_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "supplier_intelligence_status": "ok",
            "supplier_intelligence_score": 88.0,
            "latest_supplier_intelligence": {"analysis_id": "supplier-intelligence:latest"},
            "supplier_intelligence_history": [{"analysis_id": "supplier-intelligence:latest"}],
            "supplier_intelligence_history_summary": {"analysis_count": 1},
            "warnings": [],
        }


def test_supplier_intelligence_routes_expose_read_only_analysis(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "supplier_intelligence_service", lambda: _DummySupplierIntelligenceService())

    assert module.supplier_intelligence(limit=5)["supplier_intelligence_status"] == "ok"
    assert module.supplier_intelligence_latest()["latest_supplier_intelligence"]["analysis_id"] == "supplier-intelligence:latest"
    assert module.supplier_intelligence_history(limit=5)["count"] == 1

