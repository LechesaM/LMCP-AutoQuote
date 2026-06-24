from __future__ import annotations

import importlib


def test_boq_trade_mapping_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.boq_trade_mapping_service")
    service = module.BoqTradeMappingService(runtime_dir=tmp_path / "runtime" / "staging" / "boq-semantic-understanding")
    item = {
        "item_number": 2,
        "description": "Electrical cabling and fittings",
        "specification": "Supply and install",
        "unit": "m",
        "quantity": 50,
    }
    analysis = service.map_boq_trade(item, record_history=True)
    latest = service.latest_boq_trade_mapping()
    history = service.boq_trade_mapping_history(limit=5)

    assert analysis["trade_package_category"] == "electrical"
    assert analysis["trade_package_mapping_readiness"]["score"] >= 0.0
    assert latest["status"] in {"ok", "watch"}
    assert latest["latest_boq_trade_mapping"]["package_category"] in {"goods", "works", "services"}
    assert history["count"] >= 1
