from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
os.environ.setdefault("LMCP_ALLOW_DEGRADED_STARTUP", "true")

from app.main import app
import app.api.opportunities_api as opportunities_api


def test_harvest_local_uses_sync_engine(monkeypatch) -> None:
    calls = {}

    def fake_run_local_sprint7_harvest(**kwargs):
        calls["kwargs"] = kwargs
        return {
            "status": "ok",
            "source_file": "curated-live-sources.json",
            "items": [
                {"rfq_number": "FIN-SCM-TEN-0235"},
                {"rfq_number": "FIN-SCM-TEN-0236"},
            ],
        }

    monkeypatch.setattr(opportunities_api, "run_local_sprint7_harvest", fake_run_local_sprint7_harvest)

    with TestClient(app) as client:
        response = client.post("/opportunities/harvest-local")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["source"] == "local_harvest"
    assert body["source_name"] == "NECSA"
    assert body["count"] == 2
    assert [item["rfq_number"] for item in body["result"]["items"]] == ["FIN-SCM-TEN-0235", "FIN-SCM-TEN-0236"]
    assert calls["kwargs"]["persist_to_live_store"] is True
    assert calls["kwargs"]["source_name"] == "NECSA"
