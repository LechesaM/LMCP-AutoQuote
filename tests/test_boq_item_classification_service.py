from __future__ import annotations

import importlib


def test_boq_item_classification_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.boq_item_classification_service")
    service = module.BoqItemClassificationService(runtime_dir=tmp_path / "runtime" / "staging" / "boq-semantic-understanding")
    latest_item = {
        "item_number": 1,
        "description": "LED light fitting",
        "specification": "1200mm fitting",
        "unit": "Each",
        "quantity": 10,
    }
    service._latest_item = lambda: latest_item  # type: ignore[method-assign]

    latest = service.latest_boq_item_classification()
    history = service.boq_item_classification_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["boq_item_classification_score"] >= 0.0
    assert latest["latest_boq_item_classification"]["boq_item_classification_readiness"]["score"] >= 0.0
    assert latest["latest_boq_item_classification"]["trade_package_category"] in {"civil", "electrical", "plumbing", "ict", "stationery", "cleaning", "security", "professional_services", "transport", "general_goods"}
    assert history["count"] >= 1
