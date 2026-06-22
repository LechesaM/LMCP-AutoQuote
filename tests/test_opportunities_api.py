from __future__ import annotations

import json
from pathlib import Path

from app.api import opportunities_api
from app.services import live_rfq_store


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def test_opportunities_only_returns_current_open_non_fixture_rfq(monkeypatch, tmp_path: Path) -> None:
    store_path = tmp_path / "runtime" / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)

    _write_json(
        store_path,
        {
            "status": "ok",
            "updated_at": "2026-06-19T00:00:00+00:00",
            "count": 4,
            "items": [
                {
                    "rfq_number": "FIN-SCM-TEN-0235",
                    "buyer_name": "NECSA",
                    "closing_date": "2026-07-01",
                    "source": "NECSA",
                },
                {
                    "rfq_number": "FIN-SCM-TEN-0236",
                    "buyer_name": "NECSA",
                    "closing_date": "2026-07-01",
                    "source": "NECSA",
                },
                {
                    "rfq_number": "FRESH_REFRESH_20260611T101127Z_69711",
                    "buyer_name": "National Treasury eTenders",
                    "closing_date": "2026-06-11",
                    "source": "visible_bulk_validation",
                },
                {
                    "rfq_number": "RFQ-123",
                    "buyer_name": "Legacy Fixture",
                    "closing_date": "2026-07-15",
                    "source": "submission_packages",
                },
            ],
        },
    )

    payload = opportunities_api.get_opportunities()

    assert payload["source"] == "live_rfq_store"
    assert payload["count"] == 2
    assert {item["rfq_number"] for item in payload["items"]} == {
        "FIN-SCM-TEN-0235",
        "FIN-SCM-TEN-0236",
    }
    assert payload["filter"]["closing_date"] == "today_or_later"
