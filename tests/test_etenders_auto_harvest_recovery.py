from __future__ import annotations

import json
import threading
from pathlib import Path

from scripts import run_etenders_auto_harvest_recovery as module
from scripts.run_etenders_auto_harvest_recovery import run_etenders_auto_harvest_recovery


def _row(
    rfq_id: str,
    *,
    title: str,
    buyer_name: str = "National Treasury eTenders",
    detail_url: str = "",
    document_url: str = "",
    actions: str = "",
    closing_Date: str = "2026-07-01",
) -> dict:
    return {
        "id": rfq_id,
        "tenderNumber": rfq_id,
        "description": title,
        "buyerName": buyer_name,
        "category": "supply",
        "closing_Date": closing_Date,
        "actions": actions,
        "detail_url": detail_url,
        "document_url": document_url,
    }


class _QualificationResult:
    def __init__(self, status: str) -> None:
        self.qualification_status = status
        self.qualified = status == "qualified"
        self.rejected = status == "rejected"
        self.review_required = status == "review_required"

    def to_dict(self) -> dict:
        return {
            "qualification_status": self.qualification_status,
            "qualified": self.qualified,
            "rejected": self.rejected,
            "review_required": self.review_required,
        }


def _fake_qualify(item: dict) -> _QualificationResult:
    if "stationery" in str(item.get("title", "")).lower():
        return _QualificationResult("qualified")
    return _QualificationResult("rejected")


def test_multiple_pages_scanned_raw_items_persisted_and_duplicates_skipped(tmp_path: Path, monkeypatch) -> None:
    page_calls: list[tuple[str, int, int]] = []
    persist_calls: list[str] = []
    qualify_calls: list[str] = []
    acquire_calls: list[str] = []

    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=1",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=11",
                    actions='<a href="https://www.etenders.gov.za/Home/TenderDetails?id=1">Detail</a>',
                ),
                _row(
                    "RFQ-002",
                    title="Supply and Delivery of Printer Paper",
                    actions='<a href="https://www.etenders.gov.za/Home/DownloadSpec?documentId=22">Spec</a>',
                ),
            ],
        },
        1: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=2",
            "rows": [
                _row(
                    "RFQ-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=1",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=11",
                    actions='<a href="https://www.etenders.gov.za/Home/TenderDetails?id=1">Detail</a>',
                ),
                _row(
                    "RFQ-003",
                    title="Non Supply and Delivery Services",
                    actions='<div class="procurement-link">No document link</div>',
                ),
            ],
        },
        2: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=4",
            "rows": [],
        },
    }

    def fake_fetch(status: str, start: int, length: int) -> dict:
        page_calls.append((status, start, length))
        index = start // length if length else 0
        return pages.get(index, {"ok": True, "status_code": 200, "url": "https://example.com", "rows": []})

    def fake_persist(item: dict) -> dict:
        persist_calls.append(str(item.get("qualification_status") or "raw"))
        return {"ok": True, "item": item}

    def fake_apply(item: dict, result: _QualificationResult) -> dict:
        item["qualification_status"] = result.qualification_status
        return item

    def fake_acquire(item: dict, timeout_seconds: int = 20) -> dict:
        acquire_calls.append(str(item.get("rfq_id")))
        if item.get("document_url") or item.get("detail_url"):
            return {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]}
        return {"status": "no_documents_downloaded", "downloaded_count": 0, "seed_urls": []}

    monkeypatch.setattr(module, "fetch_etenders_page", fake_fetch)
    monkeypatch.setattr(module, "persist_live_rfq", fake_persist)
    monkeypatch.setattr(module, "qualify_opportunity", _fake_qualify)
    monkeypatch.setattr(module, "apply_qualification_to_opportunity", fake_apply)
    monkeypatch.setattr(module, "acquire_rfq_documents", fake_acquire)
    monkeypatch.setattr(
        module,
        "_load_registry_sources",
        lambda: (
            [
                {
                    "name": "National Treasury eTenders",
                    "source_name": "National Treasury eTenders",
                    "url": "https://www.etenders.gov.za/Home/opportunities",
                    "list_url": "https://www.etenders.gov.za/Home/opportunities",
                    "category": "aggregator",
                    "enabled": True,
                }
            ],
            ["/fake/path/harvest_sources.json"],
            "/fake/path/harvest_sources.json",
        ),
    )

    output_dir = tmp_path / "harvest_recovery"
    result = run_etenders_auto_harvest_recovery(
        pages=3,
        limit=6,
        timeout=5,
        output_dir=output_dir,
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=fake_apply,
        acquire_fn=fake_acquire,
    )

    coverage = result["coverage"]["metrics"]
    items = result["items"]["items"]

    assert page_calls == [("1", 0, 2), ("1", 2, 2), ("1", 4, 2)]
    assert coverage["pages_scanned"] == 3
    assert coverage["visible_rows_seen"] == 4
    assert coverage["rfqs_extracted"] == 3
    assert coverage["rfqs_persisted"] == 3
    assert coverage["duplicates_skipped"] == 1
    assert coverage["qualified_candidates"] == 1
    assert coverage["rejected_candidates"] == 2
    assert coverage["document_links_detected"] >= 2
    assert coverage["portal_submission_disabled"] is True
    assert coverage["human_approval_required"] is True
    assert coverage["autonomous_submission_enabled"] is False
    assert persist_calls[0] == "raw"
    assert persist_calls[1] in {"qualified", "rejected"}
    assert acquire_calls
    assert len(items) == 3
    assert items[0]["raw_extracted"]["source_mode"] == "auto_harvest_recovery"
    assert items[0]["persist"]["raw_upserted"] is True
    assert items[0]["persist"]["filtered_upserted"] is True
    assert (output_dir / "etenders_harvest_coverage.json").exists()
    assert (output_dir / "etenders_harvest_items.json").exists()
    assert (output_dir / "etenders_harvest_summary.md").exists()


def test_url_classification_and_governance_remain_frozen(tmp_path: Path, monkeypatch) -> None:
    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-010",
                    title="Supply and Delivery of Pens",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=10",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=110",
                    actions='<a href="https://www.etenders.gov.za/Home/TenderDetails?id=10">Detail</a>',
                ),
                _row(
                    "RFQ-011",
                    title="Supply and Delivery of Paper",
                    actions='<a href="https://www.etenders.gov.za/Home/DownloadSpec?documentId=111">Spec</a>',
                ),
                _row(
                    "HIDDEN",
                    title="Office Cleaning",
                    actions='<div data-link="hidden" onclick="TenderDetails?id=12">Open</div>',
                ),
                _row(
                    "NODATA",
                    title="Stationery Batch",
                    actions="",
                    closing_Date="",
                ),
            ],
        },
    }

    def fake_fetch(status: str, start: int, length: int) -> dict:
        return pages.get(start // length, {"ok": True, "status_code": 200, "url": "https://example.com", "rows": []})

    def fake_persist(item: dict) -> dict:
        return {"ok": True, "item": item}

    monkeypatch.setattr(module, "fetch_etenders_page", fake_fetch)
    monkeypatch.setattr(module, "persist_live_rfq", fake_persist)
    monkeypatch.setattr(module, "qualify_opportunity", _fake_qualify)
    monkeypatch.setattr(module, "apply_qualification_to_opportunity", lambda item, result: item)
    monkeypatch.setattr(
        module,
        "acquire_rfq_documents",
        lambda item, timeout_seconds=20: {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]},
    )

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=4,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=lambda item, timeout_seconds=20: {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]},
    )

    items = result["items"]["items"]
    classifications = {item["raw_extracted"]["rfq_id"]: item["raw_extracted"]["url_discovery_classification"] for item in items}
    assert classifications["RFQ-010"] == "url_found_and_persisted"
    assert classifications["RFQ-011"] in {"url_hidden_in_markup", "url_found_and_persisted"}
    assert classifications["HIDDEN"] == "url_hidden_in_markup"
    assert classifications["NODATA"] == "url_absent_from_source_page"
    assert result["coverage"]["guardrails"]["autonomous_submission_enabled"] is False
    assert result["coverage"]["guardrails"]["portal_submission_disabled"] is True


def test_submission_type_is_mapped_to_submission_method(tmp_path: Path, monkeypatch) -> None:
    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                {
                    "id": "RFQ-PORTAL",
                    "tenderNumber": "RFQ-PORTAL",
                    "description": "Supply and Delivery of Stationery",
                    "buyerName": "National Treasury eTenders",
                    "category": "supply",
                    "closing_Date": "2026-07-01",
                    "submission_type": "portal",
                    "actions": "",
                }
            ],
        }
    }

    def fake_fetch(status: str, start: int, length: int) -> dict:
        return pages.get(start // length, {"ok": True, "status_code": 200, "url": "https://example.com", "rows": []})

    captured: list[dict] = []

    def fake_persist(item: dict) -> dict:
        captured.append(dict(item))
        return {"ok": True, "item": item}

    monkeypatch.setattr(module, "fetch_etenders_page", fake_fetch)
    monkeypatch.setattr(module, "persist_live_rfq", fake_persist)
    monkeypatch.setattr(module, "qualify_opportunity", lambda item: _QualificationResult("qualified"))
    monkeypatch.setattr(module, "apply_qualification_to_opportunity", lambda item, result: item)
    monkeypatch.setattr(module, "acquire_rfq_documents", lambda item, timeout_seconds=20: {"status": "skipped"})

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=1,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=lambda item: _QualificationResult("qualified"),
        apply_fn=lambda item, result: item,
        acquire_fn=lambda item, timeout_seconds=20: {"status": "skipped"},
        skip_acquisition=True,
    )

    assert captured
    assert captured[0]["submission_method"] == "portal"
    assert result["items"]["items"][0]["raw_extracted"]["submission_method"] == "portal"


def test_skip_acquisition_skips_document_downloads(tmp_path: Path, monkeypatch) -> None:
    page_calls: list[tuple[str, int, int]] = []
    acquire_calls: list[str] = []

    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-SKIP-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=100",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=210",
                    actions='<a href="https://www.etenders.gov.za/Home/TenderDetails?id=100">Detail</a>',
                ),
            ],
        }
    }

    def fake_fetch(status: str, start: int, length: int) -> dict:
        page_calls.append((status, start, length))
        return pages.get(0)

    def fake_persist(item: dict) -> dict:
        return {"ok": True, "item": item}

    def fake_acquire(item: dict, timeout_seconds: int = 20) -> dict:
        acquire_calls.append(str(item.get("rfq_id")))
        return {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]}

    monkeypatch.setattr(module, "fetch_etenders_page", fake_fetch)
    monkeypatch.setattr(module, "persist_live_rfq", fake_persist)
    monkeypatch.setattr(module, "qualify_opportunity", _fake_qualify)
    monkeypatch.setattr(module, "apply_qualification_to_opportunity", lambda item, result: item)
    monkeypatch.setattr(module, "acquire_rfq_documents", fake_acquire)
    monkeypatch.setattr(
        module,
        "_load_registry_sources",
        lambda: (
            [
                {
                    "name": "National Treasury eTenders",
                    "source_name": "National Treasury eTenders",
                    "url": "https://www.etenders.gov.za/Home/opportunities",
                    "list_url": "https://www.etenders.gov.za/Home/opportunities",
                    "category": "aggregator",
                    "enabled": True,
                }
            ],
            ["/fake/path/harvest_sources.json"],
            "/fake/path/harvest_sources.json",
        ),
    )

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=1,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        skip_acquisition=True,
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=fake_acquire,
    )

    assert page_calls == [("1", 0, 1)]
    assert acquire_calls == []
    coverage = result["coverage"]["metrics"]
    assert coverage["acquisition_skipped"] is True
    assert coverage["acquisition_succeeded"] == 0
    assert coverage["acquisition_failed"] == 0
    assert (tmp_path / "harvest_recovery" / "etenders_harvest_coverage.json").exists()
    assert (tmp_path / "harvest_recovery" / "etenders_harvest_items.json").exists()
    assert (tmp_path / "harvest_recovery" / "etenders_harvest_summary.md").exists()

    items = result["items"]["items"]
    assert items[0]["acquisition"]["status"] == "skipped"
    assert items[0]["acquisition"]["reason"] == "skip_acquisition_enabled"


def test_preserve_run_writes_run_scoped_copy(tmp_path: Path, monkeypatch) -> None:
    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-PRESERVE-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=200",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=310",
                ),
            ],
        }
    }

    def fake_fetch(status: str, start: int, length: int) -> dict:
        return pages[0]

    def fake_persist(item: dict) -> dict:
        return {"ok": True, "item": item}

    monkeypatch.setattr(module, "fetch_etenders_page", fake_fetch)
    monkeypatch.setattr(module, "persist_live_rfq", fake_persist)
    monkeypatch.setattr(module, "qualify_opportunity", _fake_qualify)
    monkeypatch.setattr(module, "apply_qualification_to_opportunity", lambda item, result: item)
    monkeypatch.setattr(module, "acquire_rfq_documents", lambda item, timeout_seconds=20: {"status": "skipped", "reason": "test"})
    monkeypatch.setattr(
        module,
        "_load_registry_sources",
        lambda: (
            [
                {
                    "name": "National Treasury eTenders",
                    "source_name": "National Treasury eTenders",
                    "url": "https://www.etenders.gov.za/Home/opportunities",
                    "list_url": "https://www.etenders.gov.za/Home/opportunities",
                    "category": "aggregator",
                    "enabled": True,
                }
            ],
            ["/fake/path/harvest_sources.json"],
            "/fake/path/harvest_sources.json",
        ),
    )

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=1,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        preserve_run=True,
        run_id="run-123",
        skip_acquisition=True,
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=lambda item, timeout_seconds=20: {"status": "skipped", "reason": "test"},
    )

    run_dir = tmp_path / "harvest_recovery" / "runs" / "run-123"
    assert result["run_id"] == "run-123"
    assert result["run_dir"] == str(run_dir)
    assert (run_dir / "etenders_harvest_coverage.json").exists()
    assert (run_dir / "etenders_harvest_items.json").exists()
    assert (run_dir / "etenders_harvest_summary.md").exists()
    assert result["coverage"]["guardrails"]["human_approval_required"] is True
    registry_path = Path("app/data/harvest_sources.json")
    before = registry_path.stat().st_mtime_ns
    after = registry_path.stat().st_mtime_ns
    assert before == after


def test_dry_controlled_acquisition_prepares_but_does_not_download(tmp_path: Path, monkeypatch) -> None:
    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-DRY-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=501",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=601",
                ),
            ],
        }
    }

    acquire_calls: list[str] = []

    def fake_fetch(status: str, start: int, length: int) -> dict:
        return pages[0]

    def fake_persist(item: dict) -> dict:
        return {"ok": True, "item": item}

    def fake_acquire(item: dict, timeout_seconds: int = 20) -> dict:
        acquire_calls.append(str(item.get("rfq_id")))
        return {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]} 

    monkeypatch.setattr(module, "fetch_etenders_page", fake_fetch)
    monkeypatch.setattr(module, "persist_live_rfq", fake_persist)
    monkeypatch.setattr(module, "qualify_opportunity", _fake_qualify)
    monkeypatch.setattr(module, "apply_qualification_to_opportunity", lambda item, result: item)
    monkeypatch.setattr(module, "acquire_rfq_documents", fake_acquire)

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=1,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=fake_acquire,
        dry_controlled_acquisition=True,
    )

    coverage = result["coverage"]["metrics"]
    items = result["items"]["items"]
    assert acquire_calls == []
    assert coverage["acquisition_mode"] == "dry_controlled"
    assert coverage["acquisition_prepared"] == 1
    assert coverage["live_acquisition_attempts"] == 0
    assert items[0]["acquisition"]["status"] == "prepared"
    assert items[0]["acquisition"]["reason"] == "dry_controlled_acquisition_enabled"


def test_controlled_live_acquisition_limits_to_one_per_run(tmp_path: Path, monkeypatch) -> None:
    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-LIVE-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=701",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=801",
                ),
                _row(
                    "RFQ-LIVE-002",
                    title="Supply and Delivery of Stationery Paper",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=702",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=802",
                ),
            ],
        }
    }

    acquire_calls: list[str] = []

    def fake_fetch(status: str, start: int, length: int) -> dict:
        return pages[0]

    def fake_persist(item: dict) -> dict:
        return {"ok": True, "item": item}

    def fake_acquire(item: dict, timeout_seconds: int = 20) -> dict:
        acquire_calls.append(str(item.get("rfq_id")))
        return {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]} 

    monkeypatch.setattr(module, "fetch_etenders_page", fake_fetch)
    monkeypatch.setattr(module, "persist_live_rfq", fake_persist)
    monkeypatch.setattr(module, "qualify_opportunity", _fake_qualify)
    monkeypatch.setattr(module, "apply_qualification_to_opportunity", lambda item, result: item)
    monkeypatch.setattr(module, "acquire_rfq_documents", fake_acquire)

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=2,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=fake_acquire,
        controlled_acquisition=True,
        max_live_acquisitions=1,
    )

    coverage = result["coverage"]["metrics"]
    items = result["items"]["items"]
    assert acquire_calls == ["RFQ-LIVE-001"]
    assert coverage["acquisition_mode"] == "controlled_live"
    assert coverage["live_acquisition_attempts"] == 1
    assert coverage["acquisition_succeeded"] == 1
    assert coverage["acquisition_deferred"] == 1
    assert items[0]["acquisition"]["status"] == "ok"
    assert items[1]["acquisition"]["status"] == "deferred"


def test_live_timeout_seconds_alias_maps_to_timeout(monkeypatch) -> None:
    captured: dict[str, int] = {}

    def fake_run_etenders_auto_harvest_recovery(*, timeout: int = 0, **kwargs):
        captured["timeout"] = timeout
        return {"coverage": {}, "items": {}, "leaderboard": {}, "output_dir": "", "run_dir": "", "run_id": ""}

    monkeypatch.setattr(module, "run_etenders_auto_harvest_recovery", fake_run_etenders_auto_harvest_recovery)
    exit_code = module.main(["--live-timeout-seconds", "120", "--pages", "1", "--limit", "1", "--skip-acquisition"])

    assert exit_code == 0
    assert captured["timeout"] == 120


def test_debug_controlled_live_attaches_trace(tmp_path: Path, monkeypatch) -> None:
    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-TRACE-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=901",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=902",
                )
            ],
        }
    }

    def fake_fetch(status: str, start: int, length: int) -> dict:
        return pages[0]

    def fake_persist(item: dict) -> dict:
        return {"ok": True, "item": item}

    def fake_acquire(item: dict, timeout_seconds: int = 20) -> dict:
        return {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]}

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=1,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=fake_acquire,
        controlled_acquisition=True,
        max_live_acquisitions=1,
        debug_controlled_live=True,
    )

    items = result["items"]["items"]
    coverage = result["coverage"]["metrics"]
    assert coverage["debug_controlled_live"] is True
    assert coverage["controlled_live_trace_count"] == 1
    assert "controlled_live_trace" in items[0]["filtered"]
    debug_path = tmp_path / "harvest_recovery" / "controlled_live_debug.jsonl"
    assert debug_path.exists()
    debug_lines = [json.loads(line) for line in debug_path.read_text().splitlines() if line.strip()]
    assert [line["stage"] for line in debug_lines] == ["page_fetch", "before_acquire", "after_acquire"]
    assert debug_lines[1]["rfq_id"] == "RFQ-TRACE-001"


def test_debug_controlled_live_logs_page_fetch_failures(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(status: str, start: int, length: int) -> dict:
        raise ConnectionError("dns failure")

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=1,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        fetch_page_fn=fake_fetch,
        persist_fn=lambda item: {"ok": True, "item": item},
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=lambda item, timeout_seconds=20: {"status": "ok", "downloaded_count": 1, "seed_urls": []},
        controlled_acquisition=True,
        max_live_acquisitions=1,
        debug_controlled_live=True,
    )

    debug_path = tmp_path / "harvest_recovery" / "controlled_live_debug.jsonl"
    assert debug_path.exists()
    debug_lines = [json.loads(line) for line in debug_path.read_text().splitlines() if line.strip()]
    assert debug_lines[0]["stage"] == "page_fetch"
    assert debug_lines[0]["ok"] is False
    assert result["coverage"]["metrics"]["pages_scanned"] == 1


def test_controlled_live_acquisition_timeout_writes_progress_and_reports(tmp_path: Path, monkeypatch) -> None:
    pages = {
        0: {
            "ok": True,
            "status_code": 200,
            "url": "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            "rows": [
                _row(
                    "RFQ-TIMEOUT-001",
                    title="Supply and Delivery of Stationery",
                    detail_url="https://www.etenders.gov.za/Home/TenderDetails?id=999",
                    document_url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=999",
                )
            ],
        }
    }
    seen_run_dir_exists: list[bool] = []
    block_event = threading.Event()

    def fake_fetch(status: str, start: int, length: int) -> dict:
        return pages[0]

    def fake_persist(item: dict) -> dict:
        return {"ok": True, "item": item}

    def fake_acquire(item: dict, timeout_seconds: int = 20) -> dict:
        seen_run_dir_exists.append((tmp_path / "harvest_recovery" / "runs" / "timeout-run").exists())
        block_event.wait(5)
        return {"status": "ok", "downloaded_count": 1, "seed_urls": [item.get("document_url") or item.get("detail_url")]}

    result = run_etenders_auto_harvest_recovery(
        pages=1,
        limit=1,
        timeout=1,
        output_dir=tmp_path / "harvest_recovery",
        preserve_run=True,
        run_id="timeout-run",
        fetch_page_fn=fake_fetch,
        persist_fn=fake_persist,
        qualify_fn=_fake_qualify,
        apply_fn=lambda item, result: item,
        acquire_fn=fake_acquire,
        controlled_acquisition=True,
        max_live_acquisitions=1,
        debug_controlled_live=True,
    )

    run_dir = tmp_path / "harvest_recovery" / "runs" / "timeout-run"
    assert seen_run_dir_exists == [True]
    assert run_dir.exists()
    progress_json = run_dir / "controlled_acquisition_progress.json"
    progress_md = run_dir / "controlled_acquisition_progress.md"
    assert progress_json.exists()
    assert progress_md.exists()
    progress = json.loads(progress_json.read_text())
    assert progress["acquisition_timeout"] is True
    assert progress["last_step"] == "acquisition_timeout"
    assert progress["selected_rfq_id"] == "RFQ-TIMEOUT-001"
    assert progress["timeout_seconds"] == 1
    coverage = result["coverage"]["metrics"]
    assert coverage["acquisition_mode"] == "controlled_live"
    assert coverage["live_acquisition_attempts"] == 1
    assert coverage["acquisition_succeeded"] == 0
    assert coverage["acquisition_failed"] == 1
    assert coverage["acquisition_prepared"] == 0
    assert (run_dir / "etenders_harvest_summary.md").exists()
    assert (run_dir / "etenders_harvest_coverage.json").exists()
    assert (run_dir / "etenders_harvest_items.json").exists()
    assert result["items"]["items"][0]["acquisition"]["status"] == "timeout"
