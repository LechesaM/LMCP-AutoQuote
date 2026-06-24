from __future__ import annotations

import importlib


def test_margin_scenario_service_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.margin_scenario_service")
    service = module.MarginScenarioService(runtime_dir=tmp_path / "runtime" / "staging" / "pricing-governance")
    item = {
        "rfq_id": "RFQ-PRC-003",
        "title": "Supply and delivery of office stationery",
        "description": "Framework agreement for stationery and consumables.",
        "unit_price": 120.0,
        "quantity": 20,
        "vat_rate": 0.15,
        "markup_rate": 0.25,
    }
    benchmark = {"market_rate": 110.0}

    analysis = service.build_margin_scenarios(item, benchmark=benchmark, record_history=True)
    latest = service.latest_margin_scenarios(benchmark=benchmark)
    history = service.margin_scenario_history(limit=5)

    assert analysis["margin_scenario_readiness"]["ready"] is True
    assert analysis["mandatory_human_price_approval"] is True
    assert analysis["abnormal_price_variance_indicators"] is not None
    assert latest["status"] in {"ok", "watch"}
    assert history["count"] >= 1
