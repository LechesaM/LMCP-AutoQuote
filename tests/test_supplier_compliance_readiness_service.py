from __future__ import annotations

import importlib


def test_supplier_compliance_readiness_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.supplier_compliance_readiness_service")
    service = module.SupplierComplianceReadinessService(runtime_dir=tmp_path / "runtime" / "staging" / "supplier-intelligence")
    supplier = {
        "supplier_id": "SUP-001",
        "supplier_name": "LMCP Industrial Supplies",
        "contact_person": "Sales Desk",
        "email": "sales@example.com",
        "phone": "+27-11-000-0000",
        "delivery_regions": ["All"],
        "products": [{"product_name": "A4 paper", "category": "stationery_office"}],
    }

    latest = service.latest_supplier_compliance_readiness(supplier)
    history = service.supplier_compliance_readiness_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["supplier_compliance_status"] == "ok"
    assert latest["latest_supplier_compliance_readiness"]["compliance_readiness"] >= 80.0
    assert latest["latest_supplier_compliance_readiness"]["supplier_document_readiness"] >= 80.0
    assert history["count"] >= 1

