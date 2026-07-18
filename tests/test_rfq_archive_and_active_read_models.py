import json
from pathlib import Path

from app.api import rfq_lifecycle_api
from app.services import live_rfq_store
from app.services.rfq_archive_service import RfqArchiveService


def _write_live(path: Path):
    payload = {
        "status": "ok",
        "updated_at": "2026-07-18T00:00:00+00:00",
        "items": [
            {
                "rfq_number": "ACTIVE-1",
                "title": "Supply and delivery of valves",
                "buyer_name": "Buyer",
                "status": "Published",
                "closing_date": "2026-07-24T12:00:00+02:00",
                "estimated_value": 100000,
                "estimated_profit": 25000,
            },
            {
                "rfq_number": "OLD-1",
                "title": "Supply and delivery of old valves",
                "buyer_name": "Buyer",
                "status": "Published",
                "closing_date": "2026-05-01T12:00:00+02:00",
                "estimated_value": 500000,
                "estimated_profit": 120000,
                "quote_ready": True,
            },
            {
                "rfq_number": "REVIEW-1",
                "title": "Supply and delivery of missing-date valves",
                "buyer_name": "Buyer",
                "status": "Published",
                "closing_date": "",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_archive_service_preserves_fields_and_is_idempotent(tmp_path):
    archive_file = tmp_path / "historical_rfqs.json"
    review_file = tmp_path / "classification_review_rfqs.json"
    service = RfqArchiveService(archive_file, review_file)
    rfq = {"rfq_number": "OLD-1", "title": "Supply RFQ", "closing_date": "2026-01-01", "documents": [{"name": "rfq.pdf"}]}

    first = service.archive_rfq(rfq, "EXPIRED", {"original_store": "test"})
    second = service.archive_rfq(rfq, "EXPIRED", {"original_store": "test"})

    assert first["count"] == 1
    assert second["count"] == 1
    items = service.list_archived_rfqs()["items"]
    assert len(items) == 1
    assert items[0]["documents"] == [{"name": "rfq.pdf"}]
    assert items[0]["archive_metadata"]["archive_reason"] == "EXPIRED"


def test_active_and_archive_read_models_exclude_each_other(tmp_path, monkeypatch):
    store = tmp_path / "live_rfqs.json"
    archive = RfqArchiveService(
        tmp_path / "historical_rfqs.json",
        tmp_path / "classification_review_rfqs.json",
    )
    _write_live(store)
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store)
    monkeypatch.setattr(live_rfq_store, "ARCHIVE_SERVICE_FACTORY", lambda: archive)

    active = live_rfq_store.list_active_rfqs()
    historical = live_rfq_store.list_historical_rfqs()
    review = live_rfq_store.list_review_required_rfqs()
    counts = live_rfq_store.get_active_counts()

    assert [item["rfq_number"] for item in active["items"]] == ["ACTIVE-1"]
    assert [item["rfq_number"] for item in historical["items"]] == ["OLD-1"]
    assert [item["rfq_number"] for item in review["items"]] == ["REVIEW-1"]
    assert counts["active_total"] == 1
    assert counts["quote_ready"] == 0
    assert counts["active_pipeline_value"] == 100000
    assert counts["projected_active_gross_profit"] == 25000


def test_rfq_lifecycle_separation_endpoints_are_read_only(tmp_path, monkeypatch):
    store = tmp_path / "live_rfqs.json"
    archive = RfqArchiveService(
        tmp_path / "historical_rfqs.json",
        tmp_path / "classification_review_rfqs.json",
    )
    before = store.read_text(encoding="utf-8") if store.exists() else ""
    _write_live(store)
    before = store.read_text(encoding="utf-8")
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store)
    monkeypatch.setattr(live_rfq_store, "ARCHIVE_SERVICE_FACTORY", lambda: archive)
    monkeypatch.setattr(rfq_lifecycle_api, "RfqArchiveService", lambda: archive)

    active = rfq_lifecycle_api.live_rfqs()
    historical = rfq_lifecycle_api.historical_rfqs()
    review = rfq_lifecycle_api.review_required_rfqs()

    assert active["count"] == 1
    assert historical["count"] == 1
    assert review["count"] == 1
    assert store.read_text(encoding="utf-8") == before
