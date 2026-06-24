from __future__ import annotations

import importlib


def test_market_benchmarking_service_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.market_benchmarking_service")
    service = module.MarketBenchmarkingService(runtime_dir=tmp_path / "runtime" / "staging" / "pricing-governance")
    item = {
        "rfq_id": "RFQ-PRC-001",
        "title": "Supply and delivery of office stationery",
        "description": "Framework agreement for stationery and consumables.",
        "unit_price": 118.0,
        "quantity": 20,
        "unit": "Each",
        "vat_rate": 0.15,
        "markup_rate": 0.25,
    }

    analysis = service.benchmark_market_rates(item, record_history=True)
    latest = service.latest_market_benchmarking()
    history = service.market_benchmarking_history(limit=5)

    assert analysis["pricing_benchmark_readiness"]["ready"] is True
    assert analysis["market_rate_comparison_readiness"]["ready"] is True
    assert analysis["historical_pricing_reference_readiness"]["ready"] is True
    assert analysis["supplier_quote_comparison_readiness"]["ready"] is True
    assert "abnormal_price_variance_indicators" in analysis
    assert "underpricing_risk_indicators" in analysis
    assert "overpricing_competitiveness_indicators" in analysis
    assert latest["status"] in {"ok", "watch"}
    assert history["count"] >= 1
