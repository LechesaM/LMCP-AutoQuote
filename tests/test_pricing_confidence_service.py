from __future__ import annotations

import importlib


def test_pricing_confidence_service_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.pricing_confidence_service")
    service = module.PricingConfidenceService(runtime_dir=tmp_path / "runtime" / "staging" / "pricing-governance")
    item = {
        "rfq_id": "RFQ-PRC-002",
        "title": "Supply and delivery of office stationery",
        "description": "Framework agreement for stationery and consumables.",
        "unit_price": 120.0,
        "quantity": 20,
        "unit": "Each",
        "vat_rate": 0.15,
        "markup_rate": 0.25,
    }
    benchmark = {"pricing_benchmark_readiness": {"ready": True, "score": 88.0}, "market_rate_comparison_readiness": {"ready": True, "score": 100.0}, "historical_pricing_reference_readiness": {"ready": True, "score": 100.0}, "supplier_quote_comparison_readiness": {"ready": True, "score": 100.0}}
    margin = {"margin_scenario_readiness": {"ready": True, "score": 88.0}}

    analysis = service.assess_pricing_confidence(item, benchmark=benchmark, margin=margin, record_history=True)
    latest = service.latest_pricing_confidence(benchmark=benchmark, margin=margin)
    history = service.pricing_confidence_history(limit=5)

    assert analysis["pricing_confidence_ready"] is True
    assert analysis["pricing_confidence_score"] >= 0.0
    assert "pricing_confidence_indicators" in analysis
    assert latest["status"] in {"ok", "watch"}
    assert history["count"] >= 1
