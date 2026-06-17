from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from app.services import live_rfq_store
from app.services.live_rfq_store import (
    get_buyer_pack_acquisition_report,
    get_benchmark_candidate_search,
    get_procurement_shape_distribution_report,
    get_source_shape_performance_report,
    get_external_submission_candidate_queue,
)
from app.services.tender_harvester import ETENDERS_URL
from app.services.tender_harvester import get_etenders_preflight_status
from app.services.tender_harvester import get_runtime_stability_report
from app.services.tender_harvester import get_runtime_stability_source_report
from app.services.tender_harvester import get_productive_source_pack_report
from app.services.tender_harvester import load_harvest_sources
from app.services.tender_harvester import select_sources_for_cycle
from app.services.tender_harvester import run_national_tender_radar
from app.services.tender_harvester import get_acquisition_runtime_summary
from app.services.tender_harvester import run_multi_portal_discovery
from app.services.tender_harvester import _scan_source_acquisition_runtime
from app.services.tender_harvester import _v56_download_document
from app.services.tender_harvester import _v56_candidate_from_document
from app.services.tender_harvester import _v53_update_source_health_after_scan
from app.services.tender_harvester import _v58_select_productive_focus_sources
from app.services.tender_harvester import _v64_repair_source_pack_sources
from app.services.tender_harvester import _v64_extract_artifact_candidate_links_from_html
from app.services.tender_harvester import _v64_resolve_buyer_pack_diagnostics_for_candidate
from app.services.tender_harvester import _v63_attach_candidate_rejection_diagnostics
from app.api.dashboard import dashboard_debug_network
from app.services.tender_harvester import recheck_source_health
from app.services.tender_harvester import recheck_suppressed_source_health
from app.services.tender_harvester import reset_source_health


def _write_live_store(path: Path, items: list[dict]) -> None:
    path.write_text(
        json.dumps({"status": "ok", "updated_at": "2026-06-13T00:00:00Z", "count": len(items), "items": items}, indent=2),
        encoding="utf-8",
    )


class _FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        status_code: int,
        headers: dict[str, str],
        body: bytes,
        history: list[object] | None = None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.headers = headers
        self._body = body
        self.history = history or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def text(self) -> str:
        try:
            return self._body.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def json(self):
        return json.loads(self.text)

    @property
    def raw(self):
        class _Raw:
            def __init__(self, body: bytes) -> None:
                self._body = body
                self._pos = 0

            def read(self, size: int = -1) -> bytes:
                if size is None or size < 0:
                    size = len(self._body) - self._pos
                start = self._pos
                end = min(len(self._body), self._pos + size)
                self._pos = end
                return self._body[start:end]

        return _Raw(self._body)

    def iter_content(self, chunk_size: int = 65536):
        for idx in range(0, len(self._body), chunk_size):
            yield self._body[idx: idx + chunk_size]

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_buyer_pack_acquisition_report_counts_verified_pending_and_blocked(tmp_path: Path, monkeypatch):
    store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)

    _write_live_store(
        store_path,
        [
                {
                    "title": "Verified RFQ",
                    "buyer_name": "Buyer A",
                    "closing_date": "2026-07-01",
                    "estimated_profit": 50000,
                    "briefing_required": False,
                    "status": "Quote Ready",
                    "document_acquisition_status": "ok",
                    "document_acquisition_result": {
                        "live_buyer_pack_path": "/tmp/verified-pack",
                        "main_document_path": "/tmp/verified-pack/main.docx",
                    },
                },
            {
                "title": "Pending RFQ",
                "buyer_name": "Buyer B",
                "closing_date": "2026-07-01",
                "estimated_profit": 45000,
                "briefing_required": False,
                "status": "Quote Ready",
            },
            {
                "title": "Blocked RFQ",
                "buyer_name": "Buyer C",
                "closing_date": "2026-07-01",
                "estimated_profit": 42000,
                "briefing_required": False,
                "status": "Quote Ready",
                "document_acquisition_status": "no_documents_downloaded",
            },
            {
                "title": "Low Profit RFQ",
                "buyer_name": "Buyer D",
                "closing_date": "2026-07-01",
                "estimated_profit": 15000,
                "briefing_required": False,
                "status": "Quote Ready",
            },
        ],
    )

    report = get_buyer_pack_acquisition_report()

    assert report["qualified_rfqs"] == 3
    assert report["buyer_pack_verified"] == 1
    assert report["acquisition_pending"] == 1
    assert report["acquisition_blocked"] == 1
    assert report["acquisition_success_rate"] == 33.33


def test_external_submission_candidate_queue_returns_top_verified_candidates(tmp_path: Path, monkeypatch):
    store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)

    _write_live_store(
        store_path,
        [
                {
                    "buyer_rfq_number": "RFQ-100",
                    "title": "Candidate A",
                    "buyer_name": "Buyer A",
                    "closing_date": "2026-07-01",
                    "estimated_profit": 50000,
                    "briefing_required": False,
                    "status": "Quote Ready",
                    "document_acquisition_status": "ok",
                    "document_acquisition_result": {
                        "live_buyer_pack_path": "/tmp/candidate-a",
                        "main_document_path": "/tmp/candidate-a/main.docx",
                    },
                },
            {
                "buyer_rfq_number": "RFQ-200",
                "title": "Candidate B",
                "buyer_name": "Buyer B",
                "closing_date": "2026-07-02",
                "estimated_profit": 60000,
                "briefing_required": False,
                "status": "Quote Ready",
                "buyer_pack_path": "/tmp/buyer-pack-b.pdf",
            },
            {
                "buyer_rfq_number": "RFQ-300",
                "title": "Excluded",
                "buyer_name": "Buyer C",
                "closing_date": "2026-07-03",
                "estimated_profit": 70000,
                "briefing_required": True,
                "status": "Quote Ready",
                "document_acquisition_status": "ok",
            },
        ],
    )

    queue = get_external_submission_candidate_queue(limit=3)

    assert queue["count"] == 2
    assert [item["priority"] for item in queue["items"]] == [1, 2]
    assert [item["rfq_id"] for item in queue["items"]] == ["RFQ-200", "RFQ-100"]
    assert queue["items"][0]["buyer_pack_path"] == "/tmp/buyer-pack-b.pdf"
    assert queue["items"][1]["verification_status"] == "ok"


def test_buyer_pack_projection_uses_nested_acquisition_artifacts(tmp_path: Path, monkeypatch):
    store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)

    _write_live_store(
        store_path,
        [
            {
                "buyer_rfq_number": "RFQ-NESTED",
                "title": "Nested acquisition",
                "buyer_name": "Buyer Z",
                "closing_date": "2026-07-01",
                "estimated_profit": 55000,
                "briefing_required": False,
                "status": "Quote Ready",
                "document_acquisition_status": "ok",
                "document_acquisition_result": {
                    "status": "ok",
                    "live_buyer_pack_path": "/tmp/nested-pack",
                    "main_document_path": "/tmp/nested-pack/main.docx",
                    "downloaded_files": [{"path": "/tmp/nested-pack/archive.zip"}],
                },
            }
        ],
    )

    report = get_buyer_pack_acquisition_report()
    queue = get_external_submission_candidate_queue(limit=3)

    assert report["qualified_rfqs"] == 1
    assert report["buyer_pack_verified"] == 1
    assert report["acquisition_success_rate"] == 100.0
    assert queue["count"] == 1
    assert queue["items"][0]["buyer_pack_path"] == "/tmp/nested-pack"


def test_benchmark_candidate_search_requires_supply_delivery_shape_and_quantity_evidence(tmp_path: Path, monkeypatch):
    store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)

    _write_live_store(
        store_path,
        [
            {
                "buyer_rfq_number": "RFQ-SUPPLY",
                "title": "Supply and delivery of office consumables",
                "buyer_name": "Buyer Supply",
                "closing_date": "2026-07-01",
                "estimated_profit": 45000,
                "briefing_required": False,
                "status": "Quote Ready",
                "document_acquisition_result": {
                    "live_buyer_pack_path": "/tmp/supply-pack",
                    "main_document_path": "/tmp/supply-pack/main.docx",
                },
                "items": [
                    {"description": "Pens", "quantity": 100, "unit": "Each"},
                    {"description": "Paper", "quantity": 50, "unit": "Boxes"},
                ],
            },
            {
                "buyer_rfq_number": "RFQ-PRO",
                "title": "Engineering services for HVAC upgrade",
                "buyer_name": "Buyer Pro",
                "closing_date": "2026-07-01",
                "estimated_profit": 50000,
                "briefing_required": False,
                "status": "Quote Ready",
                "document_acquisition_result": {
                    "live_buyer_pack_path": "/tmp/pro-pack",
                    "main_document_path": "/tmp/pro-pack/main.docx",
                },
                "items": [
                    {"description": "Stage 1 design", "quantity": 1, "unit": "Each"},
                ],
            },
        ],
    )

    result = get_benchmark_candidate_search(limit=5)

    assert result["count"] == 1
    assert result["items"][0]["rfq_id"] == "RFQ-SUPPLY"
    assert result["items"][0]["procurement_shape"] == "supply_delivery"
    assert result["items"][0]["quantity_verification_possible"] is True


def test_procurement_shape_reports_and_source_quality_ranking(tmp_path: Path, monkeypatch):
    store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)

    _write_live_store(
        store_path,
        [
            {
                "buyer_rfq_number": "RFQ-S1",
                "source_name": "Source A",
                "title": "Supply and delivery of tools",
                "buyer_name": "Buyer A",
                "closing_date": "2026-07-01",
                "estimated_profit": 45000,
                "briefing_required": False,
                "status": "Quote Ready",
                "document_acquisition_result": {"live_buyer_pack_path": "/tmp/a", "main_document_path": "/tmp/a/main.docx"},
                "items": [{"description": "Tools", "quantity": 10, "unit": "Each"}],
            },
            {
                "buyer_rfq_number": "RFQ-S2",
                "source_name": "Source A",
                "title": "Engineering services for HVAC",
                "buyer_name": "Buyer A",
                "closing_date": "2026-07-02",
                "estimated_profit": 50000,
                "briefing_required": False,
                "status": "Quote Ready",
                "document_acquisition_result": {"live_buyer_pack_path": "/tmp/b", "main_document_path": "/tmp/b/main.docx"},
                "items": [{"description": "Stage 1 design", "quantity": 1, "unit": "Each"}],
            },
            {
                "buyer_rfq_number": "RFQ-S3",
                "source_name": "Source B",
                "title": "Professional advisory service",
                "buyer_name": "Buyer B",
                "closing_date": "2026-07-03",
                "estimated_profit": 60000,
                "briefing_required": False,
                "status": "Quote Ready",
                "document_acquisition_result": {"live_buyer_pack_path": "/tmp/c", "main_document_path": "/tmp/c/main.docx"},
                "items": [{"description": "Advisory", "quantity": 1, "unit": "Each"}],
            },
        ],
    )

    distribution = get_procurement_shape_distribution_report()
    sources = get_source_shape_performance_report(limit=5)

    assert distribution["live_rfqs"] == 3
    assert distribution["shape_distribution"]["Supply & Delivery"] == 1
    assert distribution["shape_distribution"]["Engineering Services"] == 1
    assert distribution["shape_distribution"]["Professional Services"] == 1
    assert distribution["benchmark_candidate_count"] == 1
    assert distribution["benchmark_conversion_pct"] == 33.33
    assert sources["source_count"] == 2
    assert sources["top_sources"][0]["source_name"] == "Source A"
    assert sources["top_sources"][0]["benchmark_candidates"] == 1
    assert sources["top_sources"][0]["supply_delivery_share_pct"] == 50.0
    assert sources["top_sources"][0]["benchmark_quality_score"] > sources["top_sources"][1]["benchmark_quality_score"]


def test_runtime_stability_report_classifies_dns_and_playwright_failures(monkeypatch):
    sources = [
        {"name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/"},
        {"name": "NECSA", "url": "https://www.necsa.co.za/"},
        {"name": "CSD", "url": "https://secure.csd.gov.za/"},
    ]
    health_snapshot = {
        "National Treasury eTenders": {
            "reachable": False,
            "last_status": "failed",
            "last_error": "HTTPSConnectionPool(host='www.etenders.gov.za', port=443): NameResolutionError",
            "source_quarantine_status": "quarantined",
        },
        "NECSA": {
            "reachable": False,
            "last_status": "failed",
            "last_error": "BrowserType.launch: Target page, context or browser has been closed",
            "source_quarantine_status": "watch",
        },
        "CSD": {
            "reachable": True,
            "last_status": "ok",
            "last_error": "",
            "source_quarantine_status": "ready",
        },
    }

    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)
    report = get_runtime_stability_report(source_health_snapshot=health_snapshot, limit=5)

    assert report["source_count"] == 3
    assert report["reachable_sources"] == 1
    assert report["reachability_pct"] == 33.33
    assert report["dns_failure_count"] == 1
    assert report["dns_success_pct"] == 66.67
    assert report["playwright_failure_count"] == 1
    assert report["playwright_launch_success_pct"] == 66.67
    assert report["successful_harvest_count"] == 1
    assert report["failed_harvest_count"] == 2


def test_runtime_stability_source_report_classifies_failure_categories(monkeypatch):
    sources = [
        {"name": "DNS Source", "url": "https://dns.example.com/"},
        {"name": "Playwright Source", "url": "https://browser.example.com/"},
        {"name": "OK Source", "url": "https://ok.example.com/"},
    ]
    health_snapshot = {
        "DNS Source": {
            "reachable": False,
            "last_status": "failed",
            "last_error": "HTTPSConnectionPool(host='dns.example.com'): NameResolutionError",
            "failure_count": 4,
            "last_checked_at": "2026-06-13T10:00:00Z",
            "last_success_at": "2026-06-13T09:00:00Z",
            "source_operator_action": "quarantine",
        },
        "Playwright Source": {
            "reachable": False,
            "last_status": "failed",
            "last_error": "BrowserType.launch: Target page, context or browser has been closed",
            "failure_count": 2,
            "last_checked_at": "2026-06-13T10:05:00Z",
            "last_success_at": "2026-06-13T09:30:00Z",
            "source_operator_action": "inspect",
        },
        "OK Source": {
            "reachable": True,
            "last_status": "ok",
            "last_error": "",
            "failure_count": 0,
            "last_checked_at": "2026-06-13T10:10:00Z",
            "last_success_at": "2026-06-13T10:10:00Z",
            "source_operator_action": "watch",
        },
    }

    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)
    report = get_runtime_stability_source_report(source_health_snapshot=health_snapshot, limit=10)

    assert report["source_count"] == 3
    assert report["failure_counts"]["dns_failure"] == 1
    assert report["failure_counts"]["playwright_launch_failure"] == 1
    assert report["failure_counts"]["ok"] == 1

    rows = {row["source_name"]: row for row in report["sources"]}
    assert rows["DNS Source"]["failure_category"] == "dns_failure"
    assert rows["DNS Source"]["dns_success"] is False
    assert rows["Playwright Source"]["failure_category"] == "playwright_launch_failure"
    assert rows["Playwright Source"]["playwright_success"] is False
    assert rows["OK Source"]["harvest_completed"] is True


def test_load_harvest_sources_normalizes_www_fallbacks(tmp_path: Path):
    source_file = tmp_path / "sources.json"
    source_file.write_text(
        json.dumps(
            [
                {"name": "SANRAL", "url": "https://nra.co.za/"},
                {"name": "CSD", "url": "https://secure.csd.gov.za/"},
                {"name": "eTenders", "url": "https://etenders.gov.za/"},
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    sources = load_harvest_sources(str(source_file))
    by_name = {source["name"]: source for source in sources}

    assert by_name["SANRAL"]["url"] == "https://www.nra.co.za/"
    assert by_name["CSD"]["url"] == "https://secure.csd.gov.za/"
    assert by_name["eTenders"]["url"] == ETENDERS_URL


def test_runtime_stability_report_promotes_repeated_dns_failures_to_normalize_or_pause(monkeypatch):
    sources = [{"name": "DNS Source", "url": "https://dns.example.com/"}]
    health_snapshot = {
        "DNS Source": {
            "reachable": False,
            "last_status": "failed",
            "last_error": "HTTPSConnectionPool(host='dns.example.com'): NameResolutionError",
            "failure_count": 3,
            "last_checked_at": "2026-06-13T10:00:00Z",
            "last_success_at": "2026-06-13T09:00:00Z",
            "source_operator_action": "inspect",
        }
    }

    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)
    report = get_runtime_stability_source_report(source_health_snapshot=health_snapshot, limit=10)

    row = report["sources"][0]
    assert row["failure_category"] == "dns_failure"
    assert row["operator_action"] == "normalize_or_pause"


def test_etenders_preflight_status_reports_dns_failure(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='www.etenders.gov.za', port=443): NameResolutionError"
        )

    monkeypatch.setattr("app.services.tender_harvester.requests.get", _boom)
    status = get_etenders_preflight_status(timeout_seconds=2)

    assert status["status"] == "failed"
    assert status["reachable"] is False
    assert status["dns_success"] is False
    assert status["failure_category"] == "dns_failure"


def test_run_national_tender_radar_skips_when_etenders_preflight_fails(monkeypatch):
    monkeypatch.setattr(
        "app.services.tender_harvester.get_etenders_preflight_status",
        lambda **_kwargs: {
            "status": "failed",
            "reachable": False,
            "dns_success": False,
            "failure_category": "dns_failure",
            "error": "NameResolutionError",
        },
    )
    monkeypatch.setattr(
        "app.services.tender_harvester.load_harvest_sources",
        lambda *_args, **_kwargs: [{"name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/"}],
    )

    result = run_national_tender_radar(
        max_total=5,
        max_per_source=2,
        max_sources_per_cycle=2,
        persist_to_live_store=False,
        headless=True,
        include_bad_sources=False,
        controlled_mode=False,
        source_timeout_seconds=5,
        playwright_timeout_ms=5000,
        browser_available=False,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "etenders_preflight_failed"
    assert result["preflight_etenders"]["failure_category"] == "dns_failure"


def test_productive_source_pack_excludes_repeated_dns_failures_and_deprioritizes_empty_results(monkeypatch):
    sources = [
        {"name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/", "priority": 1},
        {"name": "Empty Source", "url": "https://empty.example.com/", "priority": 2},
        {"name": "DNS Source", "url": "https://dns.example.com/", "priority": 3},
    ]
    health_snapshot = {
        "National Treasury eTenders": {
            "reachable": True,
            "last_status": "ok",
            "last_error": "",
            "failure_count": 0,
            "source_selection_score": 44,
            "source_success_score": 44,
            "candidate_total": 2,
            "qualified_candidate_total": 1,
            "document_candidate_total": 1,
            "source_quarantine_status": "ready",
            "source_operator_action": "continue",
        },
        "Empty Source": {
            "reachable": True,
            "last_status": "ok_empty",
            "last_error": "",
            "failure_count": 0,
            "source_selection_score": 12,
            "source_success_score": 12,
            "candidate_total": 0,
            "qualified_candidate_total": 0,
            "document_candidate_total": 0,
            "consecutive_empty_runs": 4,
            "source_quarantine_status": "watch",
            "source_operator_action": "deprioritize",
        },
        "DNS Source": {
            "reachable": False,
            "last_status": "failed",
            "last_error": "HTTPSConnectionPool(host='dns.example.com'): NameResolutionError",
            "failure_count": 3,
            "source_selection_score": 5,
            "source_success_score": 5,
            "candidate_total": 0,
            "qualified_candidate_total": 0,
            "document_candidate_total": 0,
            "source_quarantine_status": "watch",
            "source_operator_action": "normalize_or_pause",
        },
    }

    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)
    report = get_productive_source_pack_report(source_health_snapshot=health_snapshot, limit=10)

    assert report["selected_count"] == 2
    assert report["dns_paused_count"] == 0
    assert report["empty_deprioritized_count"] == 0
    assert [row["source_name"] for row in report["sources"]] == [
        "National Treasury eTenders",
        "Empty Source",
    ]


def test_select_sources_for_cycle_skips_repeated_dns_failures(tmp_path: Path, monkeypatch):
    sources = [
        {"name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/", "priority": 1},
        {"name": "DNS Source", "url": "https://dns.example.com/", "priority": 2},
        {"name": "Empty Source", "url": "https://empty.example.com/", "priority": 3},
    ]
    health_snapshot = {
        "National Treasury eTenders": {
            "reachable": True,
            "last_status": "ok",
            "last_error": "",
            "failure_count": 0,
            "source_selection_score": 44,
            "source_success_score": 44,
            "candidate_total": 2,
            "qualified_candidate_total": 1,
            "document_candidate_total": 1,
            "source_quarantine_status": "ready",
        },
        "DNS Source": {
            "reachable": False,
            "last_status": "failed",
            "last_error": "HTTPSConnectionPool(host='dns.example.com'): NameResolutionError",
            "failure_count": 3,
            "source_selection_score": 25,
            "source_success_score": 25,
            "candidate_total": 0,
            "qualified_candidate_total": 0,
            "document_candidate_total": 0,
            "source_quarantine_status": "watch",
            "source_operator_action": "normalize_or_pause",
        },
        "Empty Source": {
            "reachable": True,
            "last_status": "ok_empty",
            "last_error": "",
            "failure_count": 0,
            "source_selection_score": 12,
            "source_success_score": 12,
            "candidate_total": 0,
            "qualified_candidate_total": 0,
            "document_candidate_total": 0,
            "consecutive_empty_runs": 4,
            "source_quarantine_status": "watch",
            "source_operator_action": "deprioritize",
        },
    }

    health_file = tmp_path / "source_health.json"
    health_file.write_text(json.dumps(health_snapshot, indent=2), encoding="utf-8")
    monkeypatch.setattr("app.services.tender_harvester._load_source_health", lambda **_kwargs: health_snapshot)

    selected = select_sources_for_cycle(
        sources,
        max_sources_per_cycle=5,
        include_bad_sources=False,
        controlled_mode=False,
        source_health_snapshot=health_snapshot,
        source_health_file=health_file,
    )

    assert [source["name"] for source in selected] == ["National Treasury eTenders", "Empty Source"]


def test_scan_source_acquisition_runtime_classifies_dns_failure(monkeypatch):
    source = {"name": "DNS Source", "url": "https://dns.example.com/", "type": "web"}

    def _dns_fail(*_args, **_kwargs):
        raise OSError("NameResolutionError: failed to resolve host")

    monkeypatch.setattr("app.services.tender_harvester.socket.getaddrinfo", _dns_fail)

    harvested, diag = _scan_source_acquisition_runtime(
        source,
        max_per_source=2,
        headless=True,
        source_timeout_seconds=5,
        playwright_timeout_ms=5000,
    )

    assert harvested == []
    assert diag["status"] == "dns_failed"
    assert diag["fallback_used"] is False
    assert diag["pages_scanned"] == 0


def test_scan_source_acquisition_runtime_uses_static_fallback_after_playwright_failure(monkeypatch):
    source = {"name": "Browser Source", "url": "https://browser.example.com/", "type": "web"}

    monkeypatch.setattr(
        "app.services.tender_harvester._preflight_source_acquisition",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "error_message": "",
            "dns_resolved": True,
            "http_status_code": 200,
            "http_reachable": True,
            "robots_blocked": False,
            "browser_required": True,
            "browser_available": True,
            "source_url": "https://browser.example.com/",
            "source_name": "Browser Source",
        },
    )

    def _playwright_fail_then_fallback(*_args, diagnostics=None, **_kwargs):
        if isinstance(diagnostics, dict):
            diagnostics.update(
                {
                    "status": "playwright_failed",
                    "error_message": "BrowserType.launch failed",
                    "fallback_used": True,
                    "retry_count": 1,
                }
            )
        return [
            {
                "title": "Fallback Candidate",
                "description": "Supply and delivery of items",
                "closing_date": "2026-07-01",
                "document_urls": ["https://example.com/doc.pdf"],
            }
        ]

    monkeypatch.setattr("app.services.tender_harvester.run_playwright_generic_scraper", _playwright_fail_then_fallback)

    harvested, diag = _scan_source_acquisition_runtime(
        source,
        max_per_source=2,
        headless=True,
        source_timeout_seconds=5,
        playwright_timeout_ms=5000,
    )

    assert len(harvested) == 1
    assert diag["status"] == "success"
    assert diag["fallback_used"] is True
    assert diag["retry_count"] == 1


def test_scan_source_acquisition_runtime_marks_no_candidates(monkeypatch):
    source = {"name": "Empty Source", "url": "https://empty.example.com/", "type": "api"}

    monkeypatch.setattr(
        "app.services.tender_harvester._preflight_source_acquisition",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "error_message": "",
            "dns_resolved": True,
            "http_status_code": 200,
            "http_reachable": True,
            "robots_blocked": False,
            "browser_required": False,
            "browser_available": False,
            "source_url": "https://empty.example.com/",
            "source_name": "Empty Source",
        },
    )
    monkeypatch.setattr("app.services.tender_harvester.run_ocds_api_harvester", lambda *_args, **_kwargs: [])

    harvested, diag = _scan_source_acquisition_runtime(
        source,
        max_per_source=2,
        headless=True,
        source_timeout_seconds=5,
        playwright_timeout_ms=5000,
    )

    assert harvested == []
    assert diag["status"] == "no_candidates"
    assert diag["fallback_used"] is False


def test_get_acquisition_runtime_summary_aggregates_status_counts(tmp_path: Path, monkeypatch):
    store_path = tmp_path / "source_health.json"
    monkeypatch.setattr("app.services.tender_harvester.SOURCE_HEALTH_FILE", store_path)
    store_path.write_text(
        json.dumps(
            {
                "DNS Source": {"acquisition_status": "dns_failed", "acquisition_raw_candidates_count": 0, "acquisition_document_links_detected": 0},
                "Playwright Source": {"acquisition_status": "playwright_failed", "acquisition_raw_candidates_count": 0, "acquisition_document_links_detected": 0},
                "Empty Source": {"acquisition_status": "no_candidates", "acquisition_raw_candidates_count": 0, "acquisition_document_links_detected": 0},
                "OK Source": {"acquisition_status": "success", "acquisition_raw_candidates_count": 3, "acquisition_document_links_detected": 2},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.tender_harvester.load_harvest_sources",
        lambda *_args, **_kwargs: [
            {"name": "DNS Source", "url": "https://dns.example.com/"},
            {"name": "Playwright Source", "url": "https://browser.example.com/"},
            {"name": "Empty Source", "url": "https://empty.example.com/"},
            {"name": "OK Source", "url": "https://ok.example.com/"},
        ],
    )

    report = get_acquisition_runtime_summary(source_health_file=store_path, limit=10)

    assert report["sources_scanned_count"] == 4
    assert report["sources_successful_count"] == 1
    assert report["sources_failed_count"] == 2
    assert report["dns_failures_count"] == 1
    assert report["playwright_failures_count"] == 1
    assert report["no_candidate_sources_count"] == 1
    assert report["total_raw_candidates"] == 3
    assert report["total_document_links_detected"] == 2
    assert report["acquisition_completion_rate"] == 50.0


def test_run_multi_portal_discovery_continues_after_source_failure(monkeypatch):
    sources = [
        {"name": "Broken Source", "url": "https://broken.example.com/", "type": "web", "enabled": True, "priority": 1},
        {"name": "Healthy Source", "url": "https://healthy.example.com/", "type": "api", "enabled": True, "priority": 2},
    ]

    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)
    monkeypatch.setattr(
        "app.services.tender_harvester._v58_select_sources_for_pack_rotation",
        lambda sorted_sources, max_sources, include_bad_sources, pack_mode: (sources, "batch-1", [], {"diagnostics": {"active_pack_mode": "focus"}, "artifacts": {}, "source_rows": []}),
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._scan_source_acquisition_runtime",
        lambda source, **_kwargs: (
            [],
            {
                "source_name": source["name"],
                "source_url": source["url"],
                "scan_started_at": "2026-06-13T10:00:00Z",
                "scan_finished_at": "2026-06-13T10:00:01Z",
                "status": "dns_failed" if source["name"] == "Broken Source" else "success",
                "error_message": "NameResolutionError" if source["name"] == "Broken Source" else "",
                "pages_scanned": 0 if source["name"] == "Broken Source" else 1,
                "raw_candidates_count": 0,
                "document_links_detected": 0,
                "retry_count": 0,
                "fallback_used": False,
            },
        ) if source["name"] == "Broken Source" else (
            [
                {
                    "title": "Healthy RFQ",
                    "description": "Supply and delivery of stationery",
                    "closing_date": "2026-07-01",
                    "document_urls": ["https://example.com/doc.pdf"],
                    "buyer_name": "Buyer",
                }
            ],
            {
                "source_name": source["name"],
                "source_url": source["url"],
                "scan_started_at": "2026-06-13T10:01:00Z",
                "scan_finished_at": "2026-06-13T10:01:01Z",
                "status": "success",
                "error_message": "",
                "pages_scanned": 1,
                "raw_candidates_count": 1,
                "document_links_detected": 1,
                "retry_count": 0,
                "fallback_used": False,
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._v56_discover_documents_for_source",
        lambda *_args, **_kwargs: {"document_links": [], "downloads": [], "parsed_documents": [], "skipped_links": [], "built_items": []},
    )

    result = run_multi_portal_discovery(
        max_sources=2,
        max_per_source=2,
        headless=True,
        include_bad_sources=False,
        dry_run=True,
    )

    assert result["status"] == "ok"
    assert result["sources_scanned_count"] == 2
    assert result["acquisition_runtime_summary"]["sources_scanned_count"] == 2
    assert result["acquisition_runtime_summary"]["dns_failures_count"] == 1
    assert result["acquisition_runtime_summary"]["sources_successful_count"] == 1


def test_source_health_persistence_records_runtime_fields(tmp_path: Path, monkeypatch):
    source_health_file = tmp_path / "source_health.json"
    monkeypatch.setattr("app.services.tender_harvester.SOURCE_HEALTH_FILE", source_health_file)

    source = {"name": "Persisted Source", "url": "https://persisted.example.com/", "enabled": True}
    row = _v53_update_source_health_after_scan(
        source,
        harvested_count=1,
        candidate_count=1,
        response_time=0.12,
        error="",
        extracted_count=1,
        qualified_count=1,
        document_count=1,
        source_health_file=source_health_file,
        acquisition_status="success",
        scan_started_at="2026-06-13T10:00:00+00:00",
        scan_finished_at="2026-06-13T10:00:01+00:00",
        pages_scanned=2,
        raw_candidates_count=1,
        document_links_detected=1,
        retry_count=0,
        fallback_used=False,
        source_url=source["url"],
        preflight_dns_status="ok",
        preflight_http_status=200,
    )

    payload = json.loads(source_health_file.read_text(encoding="utf-8"))
    persisted = payload["Persisted Source"]

    assert persisted["source_name"] == "Persisted Source"
    assert persisted["last_dns_status"] == "ok"
    assert persisted["last_http_status"] == 200
    assert persisted["health_status"] == "healthy"
    assert persisted["consecutive_dns_failures"] == 0
    assert row["health_status"] == "healthy"


def test_dns_failure_threshold_suppresses_source(tmp_path: Path, monkeypatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "DNS Source": {
                    "consecutive_dns_failures": 2,
                    "consecutive_http_failures": 0,
                    "consecutive_empty_runs": 0,
                    "last_status": "failed",
                    "last_dns_status": "failed",
                    "last_error": "Previous DNS failure",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    source = {"name": "DNS Source", "url": "https://dns.example.com/", "enabled": True}

    row = _v53_update_source_health_after_scan(
        source,
        harvested_count=0,
        candidate_count=0,
        response_time=0.0,
        error="NameResolutionError",
        source_health_file=source_health_file,
        acquisition_status="dns_failed",
        scan_started_at="2026-06-13T10:00:00+00:00",
        scan_finished_at="2026-06-13T10:00:01+00:00",
        pages_scanned=0,
        raw_candidates_count=0,
        document_links_detected=0,
        retry_count=0,
        fallback_used=False,
        source_url=source["url"],
        preflight_dns_status="failed",
        preflight_http_status=0,
    )

    assert row["health_status"] == "dns_blocked"
    assert row["consecutive_dns_failures"] >= 3

    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: [source])
    report = get_productive_source_pack_report(source_file=None, limit=10, source_health_file=source_health_file)
    assert report["suppressed_dns_count"] == 1
    assert report["productive_sources_count"] == 0


def test_http_failure_threshold_suppresses_source(tmp_path: Path) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "HTTP Source": {
                    "consecutive_dns_failures": 0,
                    "consecutive_http_failures": 2,
                    "consecutive_empty_runs": 0,
                    "last_status": "failed",
                    "last_http_status": 500,
                    "last_error": "Previous HTTP failure",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    source = {"name": "HTTP Source", "url": "https://http.example.com/", "enabled": True}

    row = _v53_update_source_health_after_scan(
        source,
        harvested_count=0,
        candidate_count=0,
        response_time=0.0,
        error="HTTP 503",
        source_health_file=source_health_file,
        acquisition_status="http_failed",
        scan_started_at="2026-06-13T10:00:00+00:00",
        scan_finished_at="2026-06-13T10:00:01+00:00",
        pages_scanned=0,
        raw_candidates_count=0,
        document_links_detected=0,
        retry_count=0,
        fallback_used=False,
        source_url=source["url"],
        preflight_dns_status="ok",
        preflight_http_status=503,
    )

    assert row["health_status"] == "http_blocked"
    assert row["consecutive_http_failures"] >= 3


def test_empty_run_threshold_marks_empty_but_keeps_source_selectable(tmp_path: Path) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "Empty Source": {
                    "consecutive_dns_failures": 0,
                    "consecutive_http_failures": 0,
                    "consecutive_empty_runs": 4,
                    "last_status": "ok_empty",
                    "last_empty_at": "2026-06-12T10:00:00+00:00",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    source = {"name": "Empty Source", "url": "https://empty.example.com/", "enabled": True}

    row = _v53_update_source_health_after_scan(
        source,
        harvested_count=0,
        candidate_count=0,
        response_time=0.0,
        error="",
        source_health_file=source_health_file,
        acquisition_status="no_candidates",
        scan_started_at="2026-06-13T10:00:00+00:00",
        scan_finished_at="2026-06-13T10:00:01+00:00",
        pages_scanned=1,
        raw_candidates_count=0,
        document_links_detected=0,
        retry_count=0,
        fallback_used=False,
        source_url=source["url"],
        preflight_dns_status="ok",
        preflight_http_status=200,
    )

    assert row["health_status"] == "empty"
    selected = select_sources_for_cycle([source], max_sources_per_cycle=1, source_health_file=source_health_file)
    assert [row["name"] for row in selected] == ["Empty Source"]


def test_productive_source_pack_excludes_blocked_sources(tmp_path: Path, monkeypatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "Healthy Source": {"health_status": "healthy", "last_status": "ok", "consecutive_empty_runs": 0},
                "Degraded Source": {"health_status": "degraded", "last_status": "ok_empty", "consecutive_empty_runs": 1},
                "Empty Source": {"health_status": "empty", "last_status": "ok_empty", "consecutive_empty_runs": 5},
                "DNS Blocked": {"health_status": "dns_blocked", "last_status": "failed", "consecutive_dns_failures": 3},
                "HTTP Blocked": {"health_status": "http_blocked", "last_status": "failed", "consecutive_http_failures": 3},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.tender_harvester.load_harvest_sources",
        lambda *_args, **_kwargs: [
            {"name": "Healthy Source", "url": "https://healthy.example.com/", "enabled": True},
            {"name": "Degraded Source", "url": "https://degraded.example.com/", "enabled": True},
            {"name": "Empty Source", "url": "https://empty.example.com/", "enabled": True},
            {"name": "DNS Blocked", "url": "https://dns.example.com/", "enabled": True},
            {"name": "HTTP Blocked", "url": "https://http.example.com/", "enabled": True},
        ],
    )

    report = get_productive_source_pack_report(limit=10, source_health_file=source_health_file)

    assert report["productive_sources_count"] == 3
    assert report["suppressed_sources_count"] == 2
    assert report["suppressed_dns_count"] == 1
    assert report["suppressed_http_count"] == 1
    assert report["suppressed_empty_count"] == 1
    assert {row["source_name"] for row in report["sources"]} == {"Healthy Source", "Degraded Source", "Empty Source"}


def test_manual_reset_and_recheck_source_health(tmp_path: Path, monkeypatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "Reset Source": {
                    "consecutive_dns_failures": 3,
                    "consecutive_http_failures": 0,
                    "consecutive_empty_runs": 0,
                    "health_status": "dns_blocked",
                    "last_status": "failed",
                    "last_error": "DNS failure",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    source = {"name": "Reset Source", "url": "https://reset.example.com/", "enabled": True}
    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(
        "app.services.tender_harvester._preflight_source_acquisition",
        lambda src, timeout_seconds=8: {
            "status": "ok",
            "error_message": "",
            "dns_status": "ok",
            "http_status": 200,
            "http_status_code": 200,
            "source_url": src["url"],
        },
    )

    reset_result = reset_source_health("Reset Source", source_health_file=source_health_file)
    assert reset_result["status"] == "ok"
    assert reset_result["health"]["health_status"] == "healthy"

    recheck_result = recheck_source_health("Reset Source", source_health_file=source_health_file)
    assert recheck_result["status"] == "ok"
    assert recheck_result["health"]["health_status"] == "healthy"
    assert recheck_result["health"]["last_success_at"]


def test_recheck_suppressed_sources_respects_recheck_results(tmp_path: Path, monkeypatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "DNS Blocked": {"consecutive_dns_failures": 3, "health_status": "dns_blocked", "last_status": "failed"},
                "HTTP Blocked": {"consecutive_http_failures": 3, "health_status": "http_blocked", "last_status": "failed"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    sources = [
        {"name": "DNS Blocked", "url": "https://dns.example.com/", "enabled": True},
        {"name": "HTTP Blocked", "url": "https://http.example.com/", "enabled": True},
    ]
    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)

    def _preflight(src, timeout_seconds=8):
        if src["name"] == "DNS Blocked":
            return {
                "status": "ok",
                "error_message": "",
                "dns_status": "ok",
                "http_status": 200,
                "http_status_code": 200,
                "source_url": src["url"],
            }
        return {
            "status": "http_failed",
            "error_message": "HTTP 503",
            "dns_status": "ok",
            "http_status": 503,
            "http_status_code": 503,
            "source_url": src["url"],
        }

    monkeypatch.setattr("app.services.tender_harvester._preflight_source_acquisition", _preflight)

    result = recheck_suppressed_source_health(source_health_file=source_health_file)

    assert result["status"] == "ok"
    assert result["count"] == 2
    assert any(row["health"]["health_status"] == "healthy" for row in result["results"] if row["source"]["source_name"] == "DNS Blocked")
    assert any(row["health"]["health_status"] == "http_blocked" for row in result["results"] if row["source"]["source_name"] == "HTTP Blocked")


def test_acquisition_summary_includes_suppressed_source_counts(tmp_path: Path, monkeypatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "Healthy Source": {"health_status": "healthy", "acquisition_status": "success", "acquisition_raw_candidates_count": 2, "acquisition_document_links_detected": 1},
                "Degraded Source": {"health_status": "degraded", "acquisition_status": "no_candidates", "acquisition_raw_candidates_count": 0, "acquisition_document_links_detected": 0},
                "Empty Source": {"health_status": "empty", "acquisition_status": "no_candidates", "acquisition_raw_candidates_count": 0, "acquisition_document_links_detected": 0},
                "DNS Blocked": {"health_status": "dns_blocked", "acquisition_status": "dns_failed", "acquisition_raw_candidates_count": 0, "acquisition_document_links_detected": 0},
                "HTTP Blocked": {"health_status": "http_blocked", "acquisition_status": "http_failed", "acquisition_raw_candidates_count": 0, "acquisition_document_links_detected": 0},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.tender_harvester.load_harvest_sources",
        lambda *_args, **_kwargs: [
            {"name": "Healthy Source", "url": "https://healthy.example.com/", "enabled": True},
            {"name": "Degraded Source", "url": "https://degraded.example.com/", "enabled": True},
            {"name": "Empty Source", "url": "https://empty.example.com/", "enabled": True},
            {"name": "DNS Blocked", "url": "https://dns.example.com/", "enabled": True},
            {"name": "HTTP Blocked", "url": "https://http.example.com/", "enabled": True},
        ],
    )

    report = get_acquisition_runtime_summary(source_health_file=source_health_file, limit=10)

    assert report["productive_sources_count"] == 3
    assert report["suppressed_sources_count"] == 2
    assert report["suppressed_dns_count"] == 1
    assert report["suppressed_http_count"] == 1
    assert report["suppressed_empty_count"] == 1


def test_productive_focus_source_mode_selects_only_productive_sources(tmp_path: Path) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "Productive Source": {
                    "health_status": "healthy",
                    "candidate_total": 3,
                    "qualified_candidate_total": 1,
                    "document_candidate_total": 2,
                    "acquisition_document_links_detected": 2,
                    "source_selection_score": 72,
                    "source_success_score": 72,
                    "last_candidate_time": "2026-06-13T09:00:00Z",
                },
                "Dead Productive Source": {
                    "health_status": "healthy",
                    "candidate_total": 18,
                    "qualified_candidate_total": 8,
                    "document_candidate_total": 12,
                    "acquisition_document_links_detected": 12,
                    "source_selection_score": 95,
                    "source_success_score": 95,
                    "reachable": False,
                    "acquisition_status": "dns_failed",
                    "last_dns_status": "failed",
                },
                "Dormant Source": {
                    "health_status": "healthy",
                    "candidate_total": 0,
                    "qualified_candidate_total": 0,
                    "document_candidate_total": 0,
                    "acquisition_document_links_detected": 0,
                    "source_selection_score": 12,
                    "source_success_score": 12,
                },
                "DNS Blocked": {
                    "health_status": "dns_blocked",
                    "candidate_total": 0,
                    "qualified_candidate_total": 0,
                    "document_candidate_total": 0,
                    "acquisition_document_links_detected": 0,
                    "source_selection_score": 0,
                    "source_success_score": 0,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    sources = [
        {"name": "Productive Source", "url": "https://productive.example.com/", "enabled": True},
        {"name": "Dead Productive Source", "url": "https://dead.example.com/", "enabled": True},
        {"name": "Dormant Source", "url": "https://dormant.example.com/", "enabled": True},
        {"name": "DNS Blocked", "url": "https://dns.example.com/", "enabled": True},
    ]

    selected, diagnostics = _v58_select_productive_focus_sources(sources, max_sources=5, source_health_file=source_health_file)

    assert [source["name"] for source in selected] == ["Productive Source"]
    assert diagnostics["focused_source_count"] == 1
    assert diagnostics["skipped_unproductive_source_count"] >= 3
    assert diagnostics["focused_source_names"] == ["Productive Source"]


def test_focused_source_set_empty_without_repair_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    monkeypatch.setattr(
        "app.services.tender_harvester.load_harvest_sources",
        lambda *_args, **_kwargs: [{"name": "Dead Source", "url": "https://dead.example.com/", "enabled": True}],
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._v58_select_productive_focus_sources",
        lambda *_args, **_kwargs: ([], {"focused_source_count": 0, "skipped_unproductive_source_count": 1, "focused_source_names": []}),
    )
    result = run_multi_portal_discovery(
        max_sources=1,
        max_per_source=1,
        headless=True,
        source_health_file=source_health_file,
        dry_run=True,
        focus_productive_sources=True,
        repair_source_pack=False,
        buyer_intelligence=False,
        opportunity_forecasting=False,
        forecast_watchlist=False,
    )

    assert result["focused_source_count"] == 0
    assert result["repair_mode_used"] is False
    assert result["sources_scanned_count"] == 0
    assert result["raw_candidates_count"] == 0


def test_repair_mode_selects_currently_reachable_sources_and_reports_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "Reachable Source": {"health_status": "healthy", "candidate_total": 0, "qualified_candidate_total": 0, "document_candidate_total": 0},
                "DNS Failed Source": {"health_status": "dns_blocked", "candidate_total": 0, "qualified_candidate_total": 0, "document_candidate_total": 0},
                "HTTP Failed Source": {"health_status": "http_blocked", "candidate_total": 0, "qualified_candidate_total": 0, "document_candidate_total": 0},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    sources = [
        {"name": "Reachable Source", "url": "https://reachable.example.com/", "enabled": True},
        {"name": "DNS Failed Source", "url": "https://dns.example.com/", "enabled": True},
        {"name": "HTTP Failed Source", "url": "https://http.example.com/", "enabled": True},
    ]

    def fake_preflight(source, timeout_seconds=8):
        if source["name"] == "Reachable Source":
            return {
                "status": "ok",
                "error_message": "",
                "dns_resolved": True,
                "dns_status": "ok",
                "http_status_code": 200,
                "http_status": 200,
                "http_reachable": True,
                "robots_blocked": False,
                "browser_required": False,
                "browser_available": True,
                "source_url": source["url"],
            }
        if source["name"] == "DNS Failed Source":
            return {
                "status": "dns_failed",
                "error_message": "DNS failure",
                "dns_resolved": False,
                "dns_status": "failed",
                "http_status_code": 0,
                "http_status": 0,
                "http_reachable": False,
                "robots_blocked": False,
                "browser_required": False,
                "browser_available": False,
                "source_url": source["url"],
            }
        return {
            "status": "http_failed",
            "error_message": "HTTP 503",
            "dns_resolved": True,
            "dns_status": "ok",
            "http_status_code": 503,
            "http_status": 503,
            "http_reachable": False,
            "robots_blocked": False,
            "browser_required": False,
            "browser_available": True,
            "source_url": source["url"],
        }

    monkeypatch.setattr("app.services.tender_harvester._preflight_source_acquisition", fake_preflight)

    selected, diagnostics, checked_rows = _v64_repair_source_pack_sources(sources, max_sources=5, source_health_file=source_health_file)

    assert [source["name"] for source in selected] == ["Reachable Source"]
    assert diagnostics["repair_mode_used"] is True
    assert diagnostics["repair_sources_checked_count"] == 3
    assert diagnostics["repair_sources_selected_count"] == 1
    assert diagnostics["repair_sources_failed_count"] == 2
    assert diagnostics["repair_selected_source_names"] == ["Reachable Source"]
    assert diagnostics["repair_failed_by_reason"]["dns_failed"] == 1
    assert diagnostics["repair_failed_by_reason"]["http_failed"] == 1
    assert len(checked_rows) == 3
    assert checked_rows[0]["repair_checked_at"]
    assert checked_rows[0]["repair_status"] in {"selected", "dns_failed", "http_failed"}
    assert source_health_file.read_text(encoding="utf-8")


def test_repair_mode_does_not_permanently_mark_selected_sources_healthy_before_acquisition_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(json.dumps({"Reachable Source": {"health_status": "degraded", "candidate_total": 2}}, indent=2), encoding="utf-8")
    sources = [{"name": "Reachable Source", "url": "https://reachable.example.com/", "enabled": True}]

    monkeypatch.setattr("app.services.tender_harvester._preflight_source_acquisition", lambda *_args, **_kwargs: {
        "status": "ok",
        "error_message": "",
        "dns_resolved": True,
        "dns_status": "ok",
        "http_status_code": 200,
        "http_status": 200,
        "http_reachable": True,
        "robots_blocked": False,
        "browser_required": False,
        "browser_available": True,
        "source_url": "https://reachable.example.com/",
    })

    selected, diagnostics, _checked_rows = _v64_repair_source_pack_sources(sources, max_sources=5, source_health_file=source_health_file)

    assert [source["name"] for source in selected] == ["Reachable Source"]
    assert diagnostics["repair_mode_used"] is True
    persisted = json.loads(source_health_file.read_text(encoding="utf-8"))
    assert persisted["Reachable Source"]["health_status"] == "degraded"
    assert persisted["Reachable Source"]["candidate_total"] == 2


def test_repair_summary_shape_is_exposed_in_acquisition_runtime_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    monkeypatch.setattr(
        "app.services.tender_harvester.load_harvest_sources",
        lambda *_args, **_kwargs: [{"name": "Dead Source", "url": "https://dead.example.com/", "enabled": True}],
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._v58_select_productive_focus_sources",
        lambda *_args, **_kwargs: ([], {"focused_source_count": 0, "skipped_unproductive_source_count": 1, "focused_source_names": []}),
    )
    result = run_multi_portal_discovery(
        max_sources=1,
        max_per_source=1,
        headless=True,
        source_health_file=source_health_file,
        dry_run=True,
        focus_productive_sources=True,
        repair_source_pack=True,
        buyer_intelligence=False,
        opportunity_forecasting=False,
        forecast_watchlist=False,
    )

    runtime_summary = result["acquisition_runtime_summary"]
    assert runtime_summary["repair_mode_used"] is True
    assert runtime_summary["repair_sources_checked_count"] == 1
    assert runtime_summary["repair_sources_selected_count"] == 0
    assert runtime_summary["repair_sources_failed_count"] == 1
    assert runtime_summary["repair_failed_by_reason"]["dns_failed"] == 1


def test_debug_network_endpoint_reports_dns_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_gethostbyname(host: str) -> str:
        if host == "google.com":
            return "142.250.72.14"
        if host == "www.etenders.gov.za":
            return "102.130.115.34"
        raise AssertionError(f"unexpected host {host}")

    monkeypatch.setattr("app.api.dashboard.socket.gethostbyname", fake_gethostbyname)

    result = dashboard_debug_network()

    assert result["status"] == "ok"
    assert result["google"] == "142.250.72.14"
    assert result["etenders"] == "102.130.115.34"


def test_rejection_diagnostics_and_conversion_summary_are_persisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Acquisition Source", "url": "https://example.com/", "enabled": True, "priority": 1}
    sources = [source]
    source_health_file = tmp_path / "source_health.json"
    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)
    monkeypatch.setattr(
        "app.services.tender_harvester._v57_load_memory_files",
        lambda: {
            "source": {"qualified_candidate_fingerprints": {}, "sources": {}},
            "buyer": {"buyers": {}},
            "category": {"categories": {}},
            "document_pattern": {"patterns": {}},
        },
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._v58_select_sources_for_pack_rotation",
        lambda sorted_sources, max_sources, include_bad_sources, pack_mode: (
            sources,
            "batch-1",
            [],
            {
                "diagnostics": {"active_pack_mode": "balanced"},
                "artifacts": {},
                "source_rows": [
                    {
                        "source_name": "Acquisition Source",
                        "v58_yield_score": 50,
                        "candidate_total": 0,
                        "qualified_candidate_total": 0,
                        "document_candidate_total": 0,
                        "source_selection_score": 50,
                        "source_success_score": 50,
                        "packs": [],
                    }
                ],
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._scan_source_acquisition_runtime",
        lambda *_args, **_kwargs: (
            [
                {
                    "title": "Supply and delivery of stationery",
                    "description": "Supply and delivery of stationery",
                    "buyer_name": "Buyer A",
                    "province": "Gauteng",
                    "category": "Office Supplies",
                    "closing_date": "2026-07-01",
                    "document_urls": ["https://example.com/doc.pdf"],
                    "briefing_required": True,
                    "estimated_profit_signal": {"estimated_profit": 50000.0},
                    "estimated_margin_pct": 32.0,
                    "source_name": "Acquisition Source",
                    "source_url": "https://example.com/",
                },
                    {
                        "title": "Supply and delivery of pens",
                        "description": "Supply and delivery of pens",
                        "buyer_name": "Buyer B",
                        "province": "Gauteng",
                        "category": "Office Supplies",
                        "closing_date": "2026-07-01",
                        "document_urls": ["https://example.com/doc2.pdf"],
                        "briefing_required": False,
                        "estimated_profit_signal": {"estimated_profit": 70000.0},
                        "estimated_margin_pct": 32.0,
                        "source_name": "Acquisition Source",
                        "source_url": "https://example.com/",
                    },
                ],
            {
                "source_name": "Acquisition Source",
                "source_url": "https://example.com/",
                "scan_started_at": "2026-06-13T10:00:00Z",
                "scan_finished_at": "2026-06-13T10:00:01Z",
                "status": "success",
                "error_message": "",
                "pages_scanned": 1,
                "raw_candidates_count": 2,
                "document_links_detected": 2,
                "retry_count": 0,
                "fallback_used": False,
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._v56_discover_documents_for_source",
        lambda *_args, **_kwargs: {
            "document_links": [{"url": "https://example.com/doc.pdf"}],
            "downloads": [],
            "parsed_documents": [],
            "skipped_links": [{"reason": "download_error"}],
            "built_items": [],
        },
    )
    def fake_get(url, *args, **kwargs):
        if url.endswith("/doc.pdf") or url.endswith("/doc2.pdf"):
            return _FakeResponse(
                url=url,
                status_code=500,
                headers={"content-type": "application/pdf", "content-length": "0"},
                body=b"",
            )
        if url in {"https://example.com/", "https://example.com"}:
            return _FakeResponse(
                url=url,
                status_code=500,
                headers={"content-type": "text/html", "content-length": "0"},
                body=b"",
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)

    result = run_multi_portal_discovery(
        max_sources=1,
        max_per_source=2,
        headless=True,
        source_file=None,
        source_health_file=source_health_file,
        include_bad_sources=False,
        dry_run=True,
        source_pack_mode="focus",
        focus_productive_sources=False,
        buyer_intelligence=False,
        opportunity_forecasting=False,
        forecast_watchlist=False,
    )

    assert result["raw_candidates_count"] == 2
    assert result["eligible_candidates_count"] == 1
    assert result["qualified_candidates_count"] == 1
    assert result["rejected_candidates_count"] == 1
    assert result["raw_to_eligible_rate"] == 50.0
    assert result["eligible_to_qualified_rate"] == 100.0
    assert result["candidates_with_document_links"] == 2
    assert result["candidates_without_document_links"] == 0
    assert result["buyer_pack_attempted_count"] == 2
    assert result["buyer_pack_downloaded_count"] == 0
    assert result["buyer_pack_failed_count"] == 2
    assert result["rejected_by_stage"]["eligibility_filter"] == 1
    assert result["rejected_by_reason_code"]["briefing_required"] == 1
    rejected_path = Path(result["artifacts"]["rejected_candidates_report"])
    rejected_report = json.loads(rejected_path.read_text(encoding="utf-8"))
    assert isinstance(rejected_report, list)
    rejected_candidate = rejected_report[0]
    assert rejected_candidate["candidate_id"]
    assert rejected_candidate["document_links_count"] == 2
    assert rejected_candidate["buyer_pack_attempted"] is True
    assert rejected_candidate["buyer_pack_downloaded"] is False
    assert rejected_candidate["buyer_pack_failure_reason"] == "buyer_pack_download_failed"
    assert rejected_candidate["rejection_stage"] == "eligibility_filter"


def test_buyer_pack_download_requires_artifact_evidence_when_artifact_missing(tmp_path: Path) -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://example.com/"}
    artifact = tmp_path / "missing-pack.pdf"
    document = {
        "classification": "RFQ document",
        "classification_confidence": 0.97,
        "filename": "rfq-pack.pdf",
        "path": str(artifact),
        "url": "https://example.com/rfq-pack.pdf",
        "parser": "pypdf",
        "text": "Supply and delivery of stationery",
        "metadata": {"title": "Supply and delivery of stationery"},
    }

    built = _v56_candidate_from_document(document, source)
    assert built is not None
    assert built["buyer_pack_downloaded"] is False
    assert built["buyer_pack_path"] == str(artifact)
    assert built["buyer_pack_source"] == "Document Source"

    raw_candidate = {
        "title": "Supply and delivery of stationery",
        "description": "Supply and delivery of stationery",
        "buyer_name": "Buyer Raw",
        "source_name": "Document Source",
        "source_url": "https://example.com/",
        "document_urls": ["https://example.com/rfq-pack.pdf"],
        "briefing_required": False,
        "exclusion_reason": "qualification_score_below_threshold",
    }
    diagnostics = _v63_attach_candidate_rejection_diagnostics(
        raw_candidate,
        source,
        {"skipped_links": [{"reason": "download_error"}]},
    )

    assert diagnostics["buyer_pack_attempted"] is True
    assert diagnostics["buyer_pack_downloaded"] is False
    assert diagnostics["buyer_pack_failure_reason"] == "buyer_pack_download_failed"


def test_relative_document_url_resolution_downloads_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "url": "https://example.com/source/page.html", "enabled": True}
    link = {"url": "/documents/rfq-pack.pdf?token=abc", "filename": "rfq-pack.pdf"}
    requested_urls: list[str] = []

    def fake_get(url, *args, **kwargs):
        requested_urls.append(url)
        return _FakeResponse(
            url=url,
            status_code=200,
            headers={"content-type": "application/pdf", "content-length": "12"},
            body=b"%PDF-1.4 data",
        )

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v56_download_document(link, source)

    assert result["status"] == "downloaded"
    assert requested_urls[0] == "https://example.com/documents/rfq-pack.pdf?token=abc"
    assert result["resolved_document_url"] == "https://example.com/documents/rfq-pack.pdf?token=abc"
    assert result["artifact_exists"] is True
    assert result["artifact_size_bytes"] > 0
    assert Path(result["artifact_path"]).exists()


def test_download_fallback_uses_source_root_when_first_resolution_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "url": "https://example.com/path/page.html", "enabled": True}
    link = {"url": "documents/rfq-pack.pdf", "filename": "rfq-pack.pdf"}
    requested_urls: list[str] = []

    def fake_get(url, *args, **kwargs):
        requested_urls.append(url)
        if url.endswith("/path/documents/rfq-pack.pdf"):
            raise requests.RequestException("temporary failure")
        return _FakeResponse(
            url="https://example.com/documents/rfq-pack.pdf",
            status_code=200,
            headers={"content-type": "application/pdf", "content-length": "12"},
            body=b"%PDF-1.4 data",
        )

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v56_download_document(link, source)

    assert result["status"] == "downloaded"
    assert result["fallback_used"] is True
    assert requested_urls[0].endswith("/path/documents/rfq-pack.pdf")
    assert requested_urls[1].endswith("/documents/rfq-pack.pdf")


def test_malformed_document_url_fails_at_url_resolution() -> None:
    source = {"name": "Document Source", "url": "https://example.com/", "enabled": True}
    result = _v56_download_document({"url": "not a valid url", "filename": "bad.pdf"}, source)

    assert result["status"] == "failed"
    assert result["failure_stage"] == "url_resolution"


def test_unsupported_content_type_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "url": "https://example.com/", "enabled": True}
    link = {"url": "https://example.com/rfq-pack.pdf", "filename": "rfq-pack.pdf"}

    def fake_get(url, *args, **kwargs):
        return _FakeResponse(
            url=url,
            status_code=200,
            headers={"content-type": "text/html", "content-length": "18"},
            body=b"<html>landing page</html>",
        )

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v56_download_document(link, source)

    assert result["status"] == "failed"
    assert result["failure_stage"] == "artifact_resolved_to_html"
    assert result["attempts"][-1]["response_classification"] == "html_response"


@pytest.mark.parametrize(
    ("filename", "body", "expected_ext"),
    [
        ("rfq-pack.pdf", b"%PDF-1.4 data", ".pdf"),
        ("documents.zip", b"PK\x03\x04zip data", ".zip"),
        ("returnables.docx", b"PK\x03\x04docx data", ".docx"),
        ("pricing-schedule.xlsx", b"PK\x03\x04xlsx data", ".xlsx"),
    ],
)
def test_direct_file_candidates_are_classified_and_downloaded_with_generic_content_type(
    filename: str,
    body: bytes,
    expected_ext: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = {"name": "Document Source", "url": "https://example.com/", "enabled": True}
    link = {
        "url": f"https://example.com/downloads/{filename}",
        "filename": filename,
        "candidate_classification": "direct_file",
        "candidate_score": 100,
    }

    def fake_get(url, *args, **kwargs):
        return _FakeResponse(
            url=url,
            status_code=200,
            headers={"content-type": "application/octet-stream", "content-length": str(len(body))},
            body=body,
        )

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v56_download_document(link, source)

    assert result["status"] == "downloaded"
    assert result["extension"] == expected_ext
    assert result["binary_signature_verified"] is True
    assert Path(result["artifact_path"]).exists()


def test_tenderdetails_candidate_classification_rejects_navigation_and_keeps_download_actions() -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://www.etenders.gov.za/Home/opportunities"}
    html = """
    <html>
      <body>
        <a href="/Home/Download?itemId=12345">Download</a>
        <a href="/Home/TenderDocument?id=77">TenderDocument</a>
        <a href="/Home/TenderDetails?id=77">View details</a>
        <a href="/Home/opportunities">Menu</a>
        <a href="javascript:void(0)">Open</a>
        <a href="/api/TenderDetails?id=77&format=json">JSON</a>
      </body>
    </html>
    """

    candidates = _v64_extract_artifact_candidate_links_from_html(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=77",
        source,
        "https://www.etenders.gov.za/Home/TenderDetails?id=77",
    )

    by_url = {candidate["url"]: candidate for candidate in candidates}

    assert by_url["https://www.etenders.gov.za/Home/Download?itemId=12345"]["candidate_classification"] == "likely_download_endpoint"
    assert by_url["https://www.etenders.gov.za/Home/Download?itemId=12345"]["candidate_should_attempt"] is True
    assert by_url["https://www.etenders.gov.za/Home/TenderDocument?id=77"]["candidate_classification"] == "document_action_link"
    assert by_url["https://www.etenders.gov.za/Home/TenderDocument?id=77"]["candidate_should_attempt"] is True
    assert by_url["https://www.etenders.gov.za/Home/TenderDetails?id=77"]["candidate_classification"] == "html_navigation"
    assert by_url["https://www.etenders.gov.za/Home/TenderDetails?id=77"]["candidate_should_attempt"] is False
    assert by_url["https://www.etenders.gov.za/Home/opportunities"]["candidate_rejection_reason"] in {"social_or_menu_link", "html_navigation_link"}
    assert by_url["javascript:void(0)"]["candidate_classification"] == "javascript_link"
    assert by_url["javascript:void(0)"]["candidate_should_attempt"] is False
    assert by_url["https://www.etenders.gov.za/api/TenderDetails?id=77&format=json"]["candidate_classification"] == "api_json_endpoint"
    assert by_url["https://www.etenders.gov.za/api/TenderDetails?id=77&format=json"]["candidate_should_attempt"] is False


def test_empty_content_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "url": "https://example.com/", "enabled": True}
    link = {"url": "https://example.com/rfq-pack.pdf", "filename": "rfq-pack.pdf"}

    def fake_get(url, *args, **kwargs):
        return _FakeResponse(
            url=url,
            status_code=200,
            headers={"content-type": "application/pdf", "content-length": "0"},
            body=b"",
        )

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v56_download_document(link, source)

    assert result["status"] == "failed"
    assert result["failure_stage"] == "empty_content"


def test_redirect_chain_is_captured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "url": "https://example.com/", "enabled": True}
    link = {"url": "https://example.com/rfq-pack.pdf", "filename": "rfq-pack.pdf"}
    redirect = _FakeResponse(
        url="https://example.com/login",
        status_code=302,
        headers={"content-type": "text/html"},
        body=b"<html>login</html>",
    )

    def fake_get(url, *args, **kwargs):
        return _FakeResponse(
            url="https://example.com/final/rfq-pack.pdf",
            status_code=200,
            headers={"content-type": "application/pdf", "content-length": "12"},
            body=b"%PDF-1.4 data",
            history=[redirect],
        )

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v56_download_document(link, source)

    assert result["status"] == "downloaded"
    assert len(result["redirect_chain"]) == 2
    assert result["redirect_chain"][0]["url"] == "https://example.com/login"
    assert result["redirect_chain"][1]["url"] == "https://example.com/final/rfq-pack.pdf"


def test_buyer_pack_downloaded_only_true_when_artifact_exists_and_size_positive(tmp_path: Path) -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://example.com/"}
    artifact = tmp_path / "rfq-pack.pdf"
    artifact.write_bytes(b"%PDF-1.4 test")
    document = {
        "classification": "RFQ document",
        "classification_confidence": 0.97,
        "filename": "rfq-pack.pdf",
        "path": str(artifact),
        "url": "https://example.com/rfq-pack.pdf",
        "parser": "pypdf",
        "text": "Supply and delivery of stationery",
        "metadata": {"title": "Supply and delivery of stationery"},
        "download_result": {
            "artifact_path": str(artifact),
            "content_type": "application/pdf",
            "extension": ".pdf",
            "download_finished_at": "2026-06-13T12:00:00Z",
        },
    }

    built = _v56_candidate_from_document(document, source)
    assert built is not None
    assert built["buyer_pack_downloaded"] is True
    assert built["buyer_pack_path"] == str(artifact)
    assert built["buyer_pack_source"] == "Document Source"


def test_tenderdetails_page_resolves_relative_artifact_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://example.com/Home/opportunities", "verify_ssl": True}
    candidate = {
        "title": "RFQ Candidate",
        "document_urls": ["https://example.com/Home/TenderDetails?id=159127"],
        "source_url": source["url"],
        "document_links_count": 1,
    }
    artifact = tmp_path / "rfq-pack.pdf"
    artifact.write_bytes(b"%PDF-1.4 artifact")
    html = """
    <html>
      <body>
        <div class="attachments">
          <a href="/downloads/rfq-pack.pdf">Download RFQ pack</a>
        </div>
      </body>
    </html>
    """

    def fake_get(url, *args, **kwargs):
        if "TenderDetails" in url:
            return _FakeResponse(
                url="https://example.com/Home/TenderDetails?id=159127",
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8", "content-length": str(len(html))},
                body=html.encode("utf-8"),
            )
        if url.endswith("/downloads/rfq-pack.pdf"):
            return _FakeResponse(
                url="https://example.com/downloads/rfq-pack.pdf",
                status_code=200,
                headers={"content-type": "application/pdf", "content-length": str(artifact.stat().st_size)},
                body=artifact.read_bytes(),
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)

    assert result["attempted"] is True
    assert result["downloaded"] is True
    assert result["buyer_pack_path"]
    assert Path(result["buyer_pack_path"]).exists()
    assert result["artifact_candidates_found_count"] == 1
    assert result["index_pages_fetched_count"] == 1
    assert result["index_pages_with_artifacts_count"] == 1
    assert result["artifact_download_attempts_count"] == 1
    assert result["artifact_download_success_count"] == 1
    assert result["artifact_candidates_total"] == 1
    assert result["artifact_candidates_attempted"] == 1
    assert result["artifact_candidates_rejected_before_fetch"] == 0
    assert result["artifact_binary_signature_success_count"] == 1
    assert any(diag.get("diagnostic_type") == "source_link" for diag in result["diagnostics"])
    assert any(diag.get("diagnostic_type") == "artifact_candidate" for diag in result["diagnostics"])
    artifact_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "artifact_candidate")
    assert artifact_diag["resolved_document_url"] == "https://example.com/downloads/rfq-pack.pdf"
    assert artifact_diag["artifact_exists"] is True
    assert artifact_diag["artifact_size_bytes"] > 0
    assert artifact_diag["candidate_classification"] == "direct_file"
    assert artifact_diag["binary_signature_verified"] is True


def test_index_page_without_artifacts_persists_source_link_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://example.com/Home/opportunities", "verify_ssl": True}
    candidate = {
        "title": "RFQ Candidate",
        "document_urls": ["https://example.com/Home/TenderDetails?id=159128"],
        "source_url": source["url"],
        "document_links_count": 1,
    }
    html = "<html><body><p>No downloads published here.</p></body></html>"

    def fake_get(url, *args, **kwargs):
        if "TenderDetails" in url:
            return _FakeResponse(
                url="https://example.com/Home/TenderDetails?id=159128",
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8", "content-length": str(len(html))},
                body=html.encode("utf-8"),
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)

    assert result["attempted"] is True
    assert result["downloaded"] is False
    assert result["index_pages_fetched_count"] == 1
    assert result["index_page_no_artifacts_count"] == 1
    assert result["artifact_candidates_found_count"] == 0
    assert result["failure_reason"] == "index_page_no_artifacts"
    assert result["diagnostics"]
    source_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "source_link")
    assert source_diag["failure_stage"] == "index_page_no_artifacts"
    assert source_diag["artifact_candidates_found_count"] == 0


def test_attempted_artifact_html_response_is_diagnosed_and_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://example.com/Home/opportunities", "verify_ssl": True}
    candidate = {
        "title": "RFQ Candidate",
        "document_urls": ["https://example.com/Home/TenderDetails?id=159129"],
        "source_url": source["url"],
        "document_links_count": 1,
    }
    html = """
    <html>
      <body>
        <a href="/downloads/rfq-pack.pdf">Download RFQ pack</a>
      </body>
    </html>
    """

    def fake_get(url, *args, **kwargs):
        if "TenderDetails" in url:
            return _FakeResponse(
                url="https://example.com/Home/TenderDetails?id=159129",
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8", "content-length": str(len(html))},
                body=html.encode("utf-8"),
            )
        if url.endswith("/downloads/rfq-pack.pdf"):
            return _FakeResponse(
                url="https://example.com/downloads/rfq-pack.pdf",
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8", "content-length": "25"},
                body=b"<html>not a file</html>",
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)

    assert result["downloaded"] is False
    assert result["artifact_download_attempts_count"] == 1
    assert result["artifact_resolved_to_html_count"] == 1
    assert result["failure_reason"] == "artifact_resolved_to_html"
    artifact_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "artifact_candidate")
    assert artifact_diag["failure_stage"] == "artifact_resolved_to_html"
    assert artifact_diag["response_classification"] == "html_response"


def test_rejected_candidates_produce_diagnostics_and_summary_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://example.com/Home/opportunities", "verify_ssl": True}
    candidate = {
        "title": "RFQ Candidate",
        "document_urls": ["https://example.com/Home/TenderDetails?id=159130"],
        "source_url": source["url"],
        "document_links_count": 1,
    }
    html = """
    <html>
      <body>
        <a href="/downloads/specification.pdf">Specification PDF</a>
        <a href="/Home/TenderDetails?id=159130">View details</a>
        <a href="javascript:void(0)">Open menu</a>
        <a href="/api/TenderDetails?id=159130&format=json">JSON endpoint</a>
      </body>
    </html>
    """

    def fake_get(url, *args, **kwargs):
        if "TenderDetails" in url and "format=json" not in url and not url.endswith(".pdf"):
            return _FakeResponse(
                url="https://example.com/Home/TenderDetails?id=159130",
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8", "content-length": str(len(html))},
                body=html.encode("utf-8"),
            )
        if url.endswith("/downloads/specification.pdf"):
            return _FakeResponse(
                url="https://example.com/downloads/specification.pdf",
                status_code=200,
                headers={"content-type": "application/pdf", "content-length": "14"},
                body=b"%PDF-1.4 file",
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)

    assert result["downloaded"] is True
    assert result["artifact_candidates_total"] == 4
    assert result["artifact_candidates_attempted"] == 1
    assert result["artifact_candidates_rejected_before_fetch"] == 3
    assert result["artifact_candidates_by_classification"]["direct_file"] == 1
    assert result["artifact_candidates_by_classification"]["html_navigation"] >= 1
    assert result["artifact_candidates_by_classification"]["javascript_link"] == 1
    assert result["artifact_candidates_by_classification"]["api_json_endpoint"] == 1
    assert result["artifact_rejections_by_reason"]["html_navigation_link"] >= 1
    assert result["artifact_rejections_by_reason"]["javascript_or_anchor_link"] == 1
    assert result["artifact_rejections_by_reason"]["api_json_endpoint_not_binary"] == 1
    rejected = [diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "artifact_candidate_rejected"]
    assert len(rejected) == 3
    assert all(diag.get("candidate_rejection_reason") for diag in rejected)


def test_etenders_endpoint_discovery_flows_into_artifact_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True}
    candidate = {
        "title": "eTenders Candidate",
        "document_urls": ["https://www.etenders.gov.za/Home/TenderDetails?id=155559"],
        "source_url": source["url"],
        "document_links_count": 1,
    }
    detail_html = """
    <html>
      <body>
        <script>
          var documentsApi = '/Home/GetTenderDocuments?id=155559';
        </script>
        <a href="/Home">Home</a>
      </body>
    </html>
    """

    def fake_get(url, *args, **kwargs):
        if url == "https://www.etenders.gov.za/Home/TenderDetails?id=155559":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8", "content-length": str(len(detail_html))},
                body=detail_html.encode("utf-8"),
            )
        if url == "https://www.etenders.gov.za/Home/GetTenderDocuments?id=155559":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/json", "content-length": "98"},
                body=b'{"documents":[{"downloadUrl":"/Home/DownloadFile?documentId=99","fileName":"Tender Document.pdf"}]}',
            )
        if url == "https://www.etenders.gov.za/Home/DownloadFile?documentId=99":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/octet-stream", "content-length": "13"},
                body=b"%PDF-1.4 file",
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)

    assert result["downloaded"] is True
    assert result["etenders_endpoint_probe_count"] > 0
    assert result["etenders_document_candidates_from_endpoints"] > 0
    assert result["artifact_candidates_attempted"] > 0
    assert result["artifact_download_success_count"] == 1
    probe_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_endpoint_probe")
    assert probe_diag["response_shape"] == "json"
    artifact_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "artifact_candidate")
    assert artifact_diag["candidate_classification"] in {"likely_download_endpoint", "direct_file"}


def test_etenders_tenderdetails_json_still_triggers_endpoint_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True}
    candidate = {
        "title": "eTenders Candidate",
        "document_urls": ["https://www.etenders.gov.za/Home/TenderDetails?id=155559"],
        "source_url": source["url"],
        "document_links_count": 1,
    }

    def fake_get(url, *args, **kwargs):
        if url == "https://www.etenders.gov.za/Home/TenderDetails?id=155559":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/json", "content-length": "20"},
                body=b'{"tenderId":"155559"}',
            )
        if url == "https://www.etenders.gov.za/Home/GetTenderDocuments?id=155559":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/json", "content-length": "98"},
                body=b'{"documents":[{"downloadUrl":"/Home/DownloadFile?documentId=99","fileName":"Tender Document.pdf"}]}',
            )
        if url == "https://www.etenders.gov.za/Home/GetTenderDocuments?tenderId=155559":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/json", "content-length": "98"},
                body=b'{"documents":[{"downloadUrl":"/Home/DownloadFile?documentId=99","fileName":"Tender Document.pdf"}]}',
            )
        if url == "https://www.etenders.gov.za/Home/GetTenderDocuments?tendersID=155559":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/json", "content-length": "98"},
                body=b'{"documents":[{"downloadUrl":"/Home/DownloadFile?documentId=99","fileName":"Tender Document.pdf"}]}',
            )
        if url == "https://www.etenders.gov.za/Home/DownloadFile?documentId=99":
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/octet-stream", "content-length": "13"},
                body=b"%PDF-1.4 file",
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)
    result = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)

    assert result["downloaded"] is True
    assert result["etenders_endpoint_probe_count"] > 0
    assert result["etenders_document_candidates_from_endpoints"] > 0


def test_buyer_pack_attempted_stays_false_without_document_links() -> None:
    source = {"name": "Document Source", "source_name": "Document Source", "url": "https://example.com/Home/opportunities"}
    candidate = {
        "title": "RFQ Candidate",
        "document_urls": [],
        "source_url": source["url"],
        "document_links_count": 0,
    }

    result = _v64_resolve_buyer_pack_diagnostics_for_candidate(candidate, source)

    assert result["attempted"] is False
    assert result["diagnostics"] == []
    assert result["downloaded"] is False


def test_buyer_pack_summary_failure_counts_are_exposed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {"name": "Acquisition Source", "url": "https://example.com/source/page.html", "enabled": True, "priority": 1}
    sources = [source]
    source_health_file = tmp_path / "source_health.json"
    artifact = tmp_path / "success.pdf"
    artifact.write_bytes(b"%PDF-1.4 success")
    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda *_args, **_kwargs: sources)
    monkeypatch.setattr(
        "app.services.tender_harvester._v57_load_memory_files",
        lambda: {
            "source": {"qualified_candidate_fingerprints": {}, "sources": {}},
            "buyer": {"buyers": {}},
            "category": {"categories": {}},
            "document_pattern": {"patterns": {}},
        },
    )

    raw_candidates = [
        {"title": "HTTP Fail", "description": "Supply and delivery", "document_urls": ["https://example.com/http.pdf"]},
        {"title": "Auth Fail", "description": "Supply and delivery", "document_urls": ["https://example.com/auth.pdf"]},
        {"title": "Unsupported", "description": "Supply and delivery", "document_urls": ["https://example.com/unsupported.zip"]},
        {"title": "Empty", "description": "Supply and delivery", "document_urls": ["https://example.com/empty.pdf"]},
        {"title": "Success", "description": "Supply and delivery", "document_urls": ["https://example.com/success.pdf"]},
    ]

    def fake_scan(*_args, **_kwargs):
        return raw_candidates, {
            "source_name": "Acquisition Source",
            "source_url": source["url"],
            "scan_started_at": "2026-06-13T10:00:00Z",
            "scan_finished_at": "2026-06-13T10:00:01Z",
            "status": "success",
            "error_message": "",
            "pages_scanned": 1,
            "raw_candidates_count": len(raw_candidates),
            "document_links_detected": len(raw_candidates),
            "retry_count": 0,
            "fallback_used": False,
        }

    monkeypatch.setattr("app.services.tender_harvester._scan_source_acquisition_runtime", fake_scan)

    def fake_get(url, *args, **kwargs):
        if url.endswith("/unsupported.zip"):
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8", "content-length": "18"},
                body=b"<html>landing page</html>",
            )
        if url.endswith("/http.pdf"):
            return _FakeResponse(
                url=url,
                status_code=500,
                headers={"content-type": "application/pdf", "content-length": "0"},
                body=b"",
            )
        if url.endswith("/auth.pdf"):
            return _FakeResponse(
                url=url,
                status_code=403,
                headers={"content-type": "application/pdf", "content-length": "0"},
                body=b"",
            )
        if url.endswith("/empty.pdf"):
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/pdf", "content-length": "0"},
                body=b"",
            )
        if url.endswith("/success.pdf"):
            return _FakeResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/pdf", "content-length": str(artifact.stat().st_size)},
                body=artifact.read_bytes(),
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.tender_harvester.requests.get", fake_get)

    result = run_multi_portal_discovery(
        max_sources=1,
        max_per_source=5,
        headless=True,
        source_file=None,
        source_health_file=source_health_file,
        include_bad_sources=False,
        dry_run=True,
        source_pack_mode="focus",
        focus_productive_sources=False,
        buyer_intelligence=False,
        opportunity_forecasting=False,
        forecast_watchlist=False,
    )

    assert result["raw_candidates_count"] == 5
    assert result["candidates_with_document_links"] == 5
    assert result["buyer_pack_attempted_count"] == 5
    assert result["buyer_pack_downloaded_count"] == 1
    assert result["buyer_pack_failed_count"] == 4
    assert round(result["buyer_pack_success_rate"], 2) == 20.0
    assert result["buyer_pack_http_failures"] >= 1
    assert result["buyer_pack_unsupported_content_failures"] >= 1
    assert result["buyer_pack_empty_content_failures"] >= 1
    assert result["index_pages_fetched_count"] == 0
    assert result["artifact_candidates_found_count"] == 4
    assert result["artifact_candidates_total"] == 4
    assert result["artifact_candidates_attempted"] == 4
    assert result["artifact_candidates_rejected_before_fetch"] == 0
    assert result["artifact_candidates_by_classification"]["direct_file"] == 4
    assert result["artifact_download_attempts_count"] == 4
    assert result["artifact_download_success_count"] == 1
    assert result["artifact_resolved_to_html_count"] == 1
    assert result["artifact_binary_signature_success_count"] == 1
    assert result["index_page_no_artifacts_count"] == 0
    assert result["artifact_download_failed_count"] == 3
