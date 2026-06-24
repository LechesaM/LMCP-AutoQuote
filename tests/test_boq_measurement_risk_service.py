from __future__ import annotations

import importlib


def test_boq_measurement_risk_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.boq_measurement_risk_service")
    service = module.BoqMeasurementRiskService(runtime_dir=tmp_path / "runtime" / "staging" / "boq-semantic-understanding")
    item = {
        "item_number": 3,
        "description": "Pack of assorted printer cartridges",
        "specification": "",
        "unit": "",
        "quantity": None,
    }
    analysis = service.score_boq_measurement_risk(item, record_history=True)
    latest = service.latest_boq_measurement_risk()
    history = service.boq_measurement_risk_history(limit=5)

    assert analysis["measurement_risk_score"] >= 0.0
    assert analysis["measurement_risk_level"] in {"low", "medium", "high", "extreme"}
    assert latest["status"] in {"ok", "watch", "blocked"}
    assert latest["latest_boq_measurement_risk"]["measurement_risk_score"] >= 0.0
    assert history["count"] >= 1
