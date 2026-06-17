from __future__ import annotations

import asyncio

import app.services.tender_harvester as tender_harvester


def test_safe_harvest_runs_tender_harvester(monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
    monkeypatch.setenv("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

    from app.services import safe_autonomous_scheduler_service as scheduler

    calls = {"harvest": 0}

    def fake_harvest_national_tender_radar(**kwargs):
        calls["harvest"] += 1
        return {"items": [{"buyer_rfq_number": "RFQ-1"}], "status": "ok"}

    monkeypatch.setattr(tender_harvester, "run_national_tender_radar", fake_harvest_national_tender_radar)

    result = asyncio.run(scheduler._safe_harvest(5))

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert calls["harvest"] >= 1
