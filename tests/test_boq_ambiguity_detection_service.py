from __future__ import annotations

import importlib


def test_boq_ambiguity_detection_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.boq_ambiguity_detection_service")
    service = module.BoqAmbiguityDetectionService(runtime_dir=tmp_path / "runtime" / "staging" / "boq-semantic-understanding")
    item = {
        "item_number": 4,
        "description": "Various fittings or equivalent",
        "specification": "",
        "unit": "",
        "quantity": None,
    }
    analysis = service.detect_boq_ambiguity(item, record_history=True)
    latest = service.latest_boq_ambiguity_detection()
    history = service.boq_ambiguity_detection_history(limit=5)

    assert analysis["ambiguity_score"] >= 0.0
    assert analysis["ambiguous_item_flags"]
    assert latest["status"] in {"ok", "watch"}
    assert latest["latest_boq_ambiguity_detection"]["ambiguity_score"] >= 0.0
    assert history["count"] >= 1
