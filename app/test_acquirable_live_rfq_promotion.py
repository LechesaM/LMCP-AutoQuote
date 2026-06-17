from __future__ import annotations

from pathlib import Path

from app.services import acquirable_live_rfq_promotion_service as promotion_service


def test_promote_acquirable_live_rfqs_persists_successful_items(tmp_path: Path, monkeypatch) -> None:
    live_items = [
        {
            "rfq_id": "LIVE-ACQ-1",
            "title": "Acquirable 1",
            "buyer_name": "Buyer",
            "buyer_pack_downloaded": False,
            "buyer_pack_verified": False,
            "document_url": "https://example.invalid/doc",
            "detail_url": "https://example.invalid/detail",
            "source_url": "https://example.invalid/source",
            "document_acquisition_status": "ready",
            "updated_at": "2026-06-15T00:00:00Z",
        },
        {
            "rfq_id": "LIVE-DOWNLOADED",
            "title": "Downloaded",
            "buyer_name": "Buyer",
            "buyer_pack_downloaded": True,
            "buyer_pack_verified": True,
            "document_acquisition_status": "downloaded",
            "updated_at": "2026-06-15T00:00:00Z",
        },
    ]
    saved = {}

    def fake_get_all():
        return {"items": [dict(item) for item in live_items]}

    def fake_acquire(item, timeout_seconds=20):
        root = tmp_path / item["rfq_id"]
        root.mkdir(parents=True, exist_ok=True)
        report = root / "acquisition.json"
        report.write_text("{}", encoding="utf-8")
        return {
            "status": "ok",
            "acquired_at": "2026-06-15T00:00:00Z",
            "report_path": str(report),
            "downloaded_count": 1,
            "live_buyer_pack_path": str(root / "main.docx"),
            "downloaded_files": [{"path": str(root / "main.docx")}],
        }

    def fake_save(items):
        saved["items"] = items
        return {"status": "ok", "count": len(items), "items": items}

    monkeypatch.setattr(promotion_service.LiveRFQStore, "get_all", staticmethod(fake_get_all))
    monkeypatch.setattr(promotion_service, "acquire_rfq_documents", fake_acquire)
    monkeypatch.setattr(promotion_service, "save_live_rfqs", fake_save)

    report = promotion_service.promote_acquirable_live_rfqs(limit=1, live_items=None, output_path=str(tmp_path / "report.json"))

    assert report["status"] == "ok"
    assert report["selected_count"] == 1
    assert report["success_count"] == 1
    assert report["failure_count"] == 0
    assert saved["items"][0]["rfq_id"] == "LIVE-DOWNLOADED"
    assert any(item["rfq_id"] == "LIVE-ACQ-1" for item in saved["items"])
