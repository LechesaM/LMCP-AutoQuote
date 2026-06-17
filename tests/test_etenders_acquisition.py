from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

import requests

from app.services import etenders_dom_modal_autoclick_v50_9_4_service as etenders_dom_service
from app.services import tender_harvester
from app.services import etenders_tenderdetails_json_v50_9_1_service as tenderdetails_service


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeHTTPResponse:
    def __init__(
        self,
        *,
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        text: str = "",
        json_payload=None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self._text = text
        self._json_payload = json_payload
        self.history = []

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def text(self) -> str:
        return self._text

    def json(self):
        if self._json_payload is None:
            raise ValueError("no json payload")
        return self._json_payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeDownloadResponse:
    def __init__(
        self,
        *,
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []
        self.history = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def iter_content(self, chunk_size=8192):
        for chunk in self._chunks:
            yield chunk

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeLocator:
    def __init__(self, page, selector: str, index: int | None = None) -> None:
        self._page = page
        self._selector = selector
        self._index = index

    @property
    def first(self):
        return _FakeLocator(self._page, self._selector, 0)

    def nth(self, index: int):
        return _FakeLocator(self._page, self._selector, index)

    async def count(self) -> int:
        return int(self._page.selector_counts.get(self._selector, 0))

    async def inner_text(self, timeout=None) -> str:
        if self._selector == "body":
            return self._page._body_text
        values = self._page.selector_texts.get(self._selector, [])
        if isinstance(values, str):
            return values
        if self._index is None:
            return values[0] if values else ""
        if 0 <= self._index < len(values):
            return values[self._index]
        return ""

    async def get_attribute(self, name: str):
        if name != "href":
            return None
        values = self._page.selector_hrefs.get(self._selector, [])
        if isinstance(values, str):
            return values
        if self._index is None:
            return values[0] if values else None
        if 0 <= self._index < len(values):
            return values[self._index]
        return None

    async def click(self, timeout=None, force=None) -> None:
        self._page.clicks.append({"selector": self._selector, "index": self._index})

    async def scroll_into_view_if_needed(self, timeout=None) -> None:
        return None


class _FakePlaywrightPage:
    def __init__(
        self,
        *,
        url: str = "https://www.etenders.gov.za/Home/opportunities",
        title: str = "eTenders",
        body_text: str = "",
        body_html: str = "<html><body></body></html>",
        selector_counts: dict[str, int] | None = None,
        selector_texts: dict[str, list[str] | str] | None = None,
        selector_hrefs: dict[str, list[str] | str] | None = None,
        goto_status: int = 200,
        goto_error: str | None = None,
    ) -> None:
        self.url = url
        self._title = title
        self._body_text = body_text
        self._body_html = body_html
        self.selector_counts = selector_counts or {}
        self.selector_texts = selector_texts or {}
        self.selector_hrefs = selector_hrefs or {}
        self.goto_status = goto_status
        self.goto_error = goto_error
        self.clicks: list[dict[str, object]] = []
        self.goto_calls: list[str] = []

    async def title(self) -> str:
        return self._title

    def locator(self, selector: str):
        return _FakeLocator(self, selector)

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        return None

    async def wait_for_function(self, *args, **kwargs) -> None:
        return None

    async def wait_for_load_state(self, *args, **kwargs) -> None:
        return None

    async def goto(self, url: str, *args, **kwargs):
        self.goto_calls.append(url)
        self.url = url
        if self.goto_error:
            raise RuntimeError(self.goto_error)
        return types.SimpleNamespace(status=self.goto_status)

    async def screenshot(self, *args, **kwargs) -> None:
        return None

    async def content(self) -> str:
        return self._body_html

    def on(self, *args, **kwargs) -> None:
        return None

    async def evaluate(self, script: str, *args, **kwargs):
        if "document.body.innerText" in script or "document.body.textContent" in script:
            return self._body_text
        return ""


def _install_fake_playwright(
    monkeypatch,
    page: _FakePlaywrightPage | None = None,
    *,
    cdp_ok: bool = True,
    managed_ok: bool = True,
) -> None:
    fake_page = page or _FakePlaywrightPage()

    class _FakeBrowser:
        def __init__(self, contexts) -> None:
            self.contexts = contexts

        async def new_context(self, **kwargs):
            context = _FakeContext(fake_page)
            context.browser = self
            self.contexts.append(context)
            return context

        async def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self, fake_page: _FakePlaywrightPage) -> None:
            self.pages = [fake_page]
            self.browser = None

        async def new_page(self):
            return fake_page

        def set_default_timeout(self, timeout_ms: int) -> None:
            return None

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def connect_over_cdp(self, websocket_url: str):
            if not cdp_ok:
                raise RuntimeError("cdp attach failed")
            browser = _FakeBrowser([])
            context = _FakeContext(fake_page)
            context.browser = browser
            browser.contexts = [context]
            return browser

        async def launch_persistent_context(self, user_data_dir: str, **kwargs):
            if not managed_ok:
                raise RuntimeError("managed launch failed")
            browser = _FakeBrowser([])
            context = _FakeContext(fake_page)
            context.browser = browser
            browser.contexts = [context]
            return context

    class _FakeAsyncPlaywright:
        def __init__(self) -> None:
            self.chromium = _FakeChromium()

        async def start(self):
            return self

        async def stop(self):
            return None

    fake_module = types.ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: _FakeAsyncPlaywright()
    fake_package = types.ModuleType("playwright")
    fake_package.async_api = fake_module
    monkeypatch.setitem(sys.modules, "playwright", fake_package)
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)


def test_load_harvest_sources_normalizes_etenders_root_url(tmp_path: Path) -> None:
    source_file = tmp_path / "sources.json"
    source_file.write_text(
        json.dumps(
            [
                {
                    "name": "National Treasury eTenders",
                    "url": "https://www.etenders.gov.za/",
                    "list_url": "https://www.etenders.gov.za/",
                    "type": "tenders_api",
                    "source_group": "aggregator",
                }
            ]
        ),
        encoding="utf-8",
    )

    sources = tender_harvester.load_harvest_sources(str(source_file))

    assert sources[0]["url"] == tender_harvester.ETENDERS_URL
    assert sources[0]["list_url"] == tender_harvester.ETENDERS_URL


def test_direct_etenders_prefers_paginated_json_feed(monkeypatch) -> None:
    def fake_get(url, params=None, timeout=None, headers=None, **kwargs):
        if url == tender_harvester.ETENDERS_PAGINATED_OPPORTUNITIES_URL:
            assert params["status"] == 1
            assert params["length"] == 5
            return _FakeResponse(
                {
                    "data": [
                        {
                            "id": 158918,
                            "tender_No": "274G/2025/26",
                            "description": "PROCUREMENT OF NEW CREMATORS AND ASSOCIATED WORKS",
                            "category": "Services: General",
                            "organ_of_State": "City of Cape Town",
                            "closing_Date": "2026-07-27T10:00:00",
                            "date_Published": "2026-06-12T00:00:00",
                            "department": "City of Cape Town",
                            "province": "Western Cape",
                            "supportDocument": [
                                {
                                    "supportDocumentID": "da82ec59-5332-446c-ad2a-2367c2cd8df4",
                                    "fileName": "Tender Document.pdf",
                                }
                            ],
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(tender_harvester, "run_generic_scraper", lambda *args, **kwargs: [])

    results = tender_harvester._direct_etenders(
        {
            "name": "National Treasury eTenders",
            "url": "https://www.etenders.gov.za/",
            "list_url": "https://www.etenders.gov.za/",
            "type": "tenders_api",
            "source_group": "aggregator",
        },
        max_items=5,
        headless=True,
        timeout_seconds=20,
        playwright_timeout_ms=30000,
    )

    assert len(results) == 1
    item = results[0]
    assert item["title"] == "PROCUREMENT OF NEW CREMATORS AND ASSOCIATED WORKS"
    assert item["buyer_name"] == "City of Cape Town"
    assert item["rfq_number"] == "274G/2025/26"
    assert item["source_url"] == tender_harvester.ETENDERS_URL
    assert item["detail_url"].endswith("/Home/TenderDetails?id=158918")
    assert item["document_url"].endswith("/Home/TenderDetails?id=158918")
    assert item["v50_8_discovered_tender_id"] == "158918"
    assert item["supportDocumentID"] == "da82ec59-5332-446c-ad2a-2367c2cd8df4"


def test_extracts_etenders_ajax_endpoints_from_inline_scripts() -> None:
    html = """
    <html><body>
      <script>
        var docsUrl = '/Home/GetTenderDocuments?id=155559';
        $.get('/Home/DownloadFile?documentId=99');
        fetch('/Home/GetDocuments?tenderId=155559');
        var xhr = new XMLHttpRequest(); xhr.open('GET', '/Home/TenderDocuments?tendersID=155559');
      </script>
    </body></html>
    """

    result = tender_harvester._v64_discover_etenders_document_endpoints(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
    )

    urls = [row["endpoint_url"] for row in result["endpoints"]]
    assert "https://www.etenders.gov.za/Home/GetTenderDocuments?id=155559" in urls
    assert "https://www.etenders.gov.za/Home/DownloadFile?documentId=99" in urls
    assert "https://www.etenders.gov.za/Home/GetDocuments?tenderId=155559" in urls
    assert "https://www.etenders.gov.za/Home/TenderDocuments?tendersID=155559" in urls
    assert result["tender_id"] == "155559"


def test_extracts_etenders_endpoints_from_data_attributes_and_form_actions() -> None:
    html = """
    <html><body>
      <div data-endpoint="/Home/TenderDocuments?id=155559" data-action="/Home/GetDocuments?tenderId=155559"></div>
      <button data-download-url="/Home/DownloadSupportDocument?supportDocumentID=abc-123">Download</button>
      <form action="/Home/GetTenderDetails?id=155559"></form>
      <input type="hidden" name="supportDocumentID" value="abc-123" />
    </body></html>
    """

    result = tender_harvester._v64_discover_etenders_document_endpoints(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
    )

    urls = [row["endpoint_url"] for row in result["endpoints"]]
    assert "https://www.etenders.gov.za/Home/TenderDocuments?id=155559" in urls
    assert "https://www.etenders.gov.za/Home/GetDocuments?tenderId=155559" in urls
    assert "https://www.etenders.gov.za/Home/DownloadSupportDocument?supportDocumentID=abc-123" in urls
    assert "https://www.etenders.gov.za/Home/GetTenderDetails?id=155559" in urls


def test_extracts_ids_from_hidden_inputs_and_json_blobs() -> None:
    html = """
    <html><body>
      <input type="hidden" name="documentId" value="98765" />
      <script type="application/json">
        {"supportDocumentID":"abc-123","tenderId":"155559","noticeNumber":"NT-42"}
      </script>
    </body></html>
    """

    result = tender_harvester._v64_discover_etenders_document_endpoints(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
    )

    fields = {(row["name"], row["value"]) for row in result["evidence"]["id_like_fields"]}
    assert ("documentId", "98765") in fields
    assert ("supportDocumentID", "abc-123") in fields
    assert ("tenderId", "155559") in fields
    assert ("noticeNumber", "NT-42") in fields


def test_recursive_tenderdetails_json_mining_finds_document_rows_and_sanitizes_payload(monkeypatch) -> None:
    payload = {
        "tenderId": "159131",
        "documents": [
            {
                "documentId": "doc-77",
                "fileName": "Pricing Schedule.pdf",
                "downloadUrl": "/Home/DownloadFile?documentId=doc-77",
            },
            {
                "supportDocumentID": "sup-88",
                "path": "files/supporting-doc.docx",
                "nested": [{"attachmentUrl": "https://www.etenders.gov.za/files/boq.xlsx"}],
            },
        ],
        "meta": {
            "returnableDocuments": {
                "rows": [
                    {"fileName": "Tender Returnable.zip", "filePath": "/files/returnables/Tender Returnable.zip"}
                ]
            }
        },
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    result = tenderdetails_service.inspect_tenderdetails_json({"tender_id": "159131"})

    assert result["json_top_level_keys"] == ["tenderId", "documents", "meta"]
    assert result["document_row_candidates_count"] > 0
    assert any(path.endswith("$.documents[0]") for path in result["document_like_key_paths"])
    assert any("Pricing Schedule.pdf" in value for value in result["filename_like_values_limited"])
    assert any("DownloadFile?documentId=doc-77" in value for value in result["url_like_values_limited"])
    id_pairs = {(row["path"], row["name"], row["value"]) for row in result["id_like_values_by_path"]}
    assert ("$.documents[0].documentId", "documentId", "doc-77") in id_pairs
    assert ("$.tenderId", "tenderId", "159131") in id_pairs
    assert "raw_details" not in result
    assert all("data" not in attempt for attempt in result["details_attempts"])
    assert result["tenderdetails_json_document_rows_accepted"] >= 1
    assert result["tenderdetails_json_document_rows_rejected"] == 1


def test_top_level_tenderdetails_row_with_only_tender_id_is_rejected(monkeypatch) -> None:
    payload = {
        "tenderId": "159049",
        "title": "BID 2636S - Provision of Strategic Partners for Engineering Services.",
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    result = tenderdetails_service.inspect_tenderdetails_json({"tender_id": "159049"})

    assert result["tenderdetails_json_rows_seen"] >= 1
    assert result["tenderdetails_json_document_rows_rejected"] == 1
    assert result["tenderdetails_json_top_level_rows_rejected"] == 1
    assert result["tenderdetails_json_document_rows_accepted"] == 0
    assert result["document_rows"] == []
    assert result["document_row_rejections"][0]["diagnostic_type"] == "tenderdetails_json_document_row_rejected"
    assert result["document_row_rejections"][0]["rejection_reason"] == "top_level_tender_row_not_document"


def test_tender_id_is_not_promoted_into_document_routes(monkeypatch) -> None:
    payload = {
        "tenderId": "159049",
        "title": "BID 2636S - Provision of Strategic Partners for Engineering Services.",
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    def fake_download_candidate(url, output_path, timeout=35):
        return {
            "url": url,
            "ok": False,
            "verified_download": False,
            "status_code": 404,
            "http_status": 404,
            "final_url": url,
            "content_type": "",
            "content_disposition": "",
            "content_length": 0,
            "saved_path": "",
            "error": "http_status_404",
            "validation": {},
            "binary_signature_detected": False,
        }

    monkeypatch.setattr(tenderdetails_service, "_download_candidate", fake_download_candidate)

    result = tenderdetails_service.download_from_tenderdetails_json({"tender_id": "159049"})

    non_rejection_attempts = [attempt for attempt in result["attempts"] if attempt.get("diagnostic_type") != "tenderdetails_json_document_row_rejected"]
    assert non_rejection_attempts
    assert all(attempt.get("route_pattern_name") == "tender_id_fallback" for attempt in non_rejection_attempts)
    assert all(attempt.get("source_json_path") == "tender_id_fallback" for attempt in non_rejection_attempts)
    assert all(str(attempt.get("failure_reason") or "").startswith("tender_id_fallback") for attempt in non_rejection_attempts)
    assert all((attempt.get("document_id") or "") == "" for attempt in non_rejection_attempts)


def test_explicit_download_url_row_is_accepted(monkeypatch) -> None:
    payload = {
        "documents": [
            {
                "downloadUrl": "/files/TenderPack.zip",
                "fileName": "Tender Pack.zip",
            }
        ]
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    inspected = tenderdetails_service.inspect_tenderdetails_json({"tender_id": "159131"})
    assert inspected["tenderdetails_json_document_rows_accepted"] == 1
    assert inspected["tenderdetails_json_document_rows_rejected"] == 1
    assert inspected["document_rows"][0]["source_json_path"] == "$.documents[0]"


def test_filename_plus_distinct_document_id_row_is_accepted(monkeypatch) -> None:
    payload = {
        "documents": [
            {
                "documentId": "doc-77",
                "fileName": "Pricing Schedule.pdf",
            }
        ]
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    inspected = tenderdetails_service.inspect_tenderdetails_json({"tender_id": "159131"})
    doc_row = inspected["document_rows"][0]
    assert inspected["tenderdetails_json_document_rows_accepted"] == 1
    assert inspected["tenderdetails_json_document_rows_rejected"] == 1
    assert inspected["documents"][0]["document_id"] == "doc-77"
    assert inspected["documents"][0]["filename"] == "Pricing Schedule.pdf"


def test_nested_document_row_is_accepted(monkeypatch) -> None:
    payload = {
        "documents": [
            {
                "nested": [
                    {
                        "supportDocumentID": "sup-88",
                        "fileName": "Tender Document.pdf",
                    }
                ]
            }
        ]
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    inspected = tenderdetails_service.inspect_tenderdetails_json({"tender_id": "159131"})
    assert inspected["tenderdetails_json_document_rows_accepted"] == 1
    assert inspected["tenderdetails_json_document_rows_rejected"] == 1
    assert any(row["source_json_path"] == "$.documents[0].nested[0]" for row in inspected["document_rows"])
    assert inspected["documents"][0]["support_document_id"] == "sup-88"


def test_rejection_diagnostic_is_persisted_for_top_level_non_document_row(monkeypatch) -> None:
    payload = {
        "tenderId": "159049",
        "title": "BID 2636S - Provision of Strategic Partners for Engineering Services.",
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    def fake_download_candidate(url, output_path, timeout=35):
        return {
            "url": url,
            "ok": False,
            "verified_download": False,
            "status_code": 404,
            "http_status": 404,
            "final_url": url,
            "content_type": "",
            "content_disposition": "",
            "content_length": 0,
            "saved_path": "",
            "error": "http_status_404",
            "validation": {},
            "binary_signature_detected": False,
        }

    monkeypatch.setattr(tenderdetails_service, "_download_candidate", fake_download_candidate)

    result = tenderdetails_service.download_from_tenderdetails_json({"tender_id": "159049"})

    assert any(attempt.get("diagnostic_type") == "tenderdetails_json_document_row_rejected" for attempt in result["attempts"])
    rejection = next(attempt for attempt in result["attempts"] if attempt.get("diagnostic_type") == "tenderdetails_json_document_row_rejected")
    assert rejection["source_json_path"] == "$"
    assert rejection["tender_id"] == "159049"
    assert rejection["candidate_document_id"] == "159049"
    assert rejection["rejection_reason"] == "top_level_tender_row_not_document"
    assert rejection["available_keys_limited"] == ["tenderId", "title"]


def test_summary_metrics_count_accepted_and_rejected_rows(monkeypatch) -> None:
    payload = {
        "tenderId": "159049",
        "documents": [
            {
                "documentId": "doc-77",
                "fileName": "Pricing Schedule.pdf",
            }
        ],
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    result = tenderdetails_service.inspect_tenderdetails_json({"tender_id": "159049"})

    assert result["tenderdetails_json_rows_seen"] >= 2
    assert result["tenderdetails_json_document_rows_accepted"] == 1
    assert result["tenderdetails_json_document_rows_rejected"] == 1
    assert result["tenderdetails_json_top_level_rows_rejected"] == 1


def test_fallback_route_is_marked_tender_id_fallback(monkeypatch) -> None:
    payload = {
        "tenderId": "159049",
        "title": "BID 2636S - Provision of Strategic Partners for Engineering Services.",
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159049", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    def fake_download_candidate(url, output_path, timeout=35):
        return {
            "url": url,
            "ok": False,
            "verified_download": False,
            "status_code": 404,
            "http_status": 404,
            "final_url": url,
            "content_type": "",
            "content_disposition": "",
            "content_length": 0,
            "saved_path": "",
            "error": "http_status_404",
            "validation": {},
            "binary_signature_detected": False,
        }

    monkeypatch.setattr(tenderdetails_service, "_download_candidate", fake_download_candidate)

    result = tenderdetails_service.download_from_tenderdetails_json({"tender_id": "159049"})
    fallback_attempts = [attempt for attempt in result["attempts"] if attempt.get("route_pattern_name") == "tender_id_fallback"]
    assert fallback_attempts
    assert all(attempt.get("source_json_path") == "tender_id_fallback" for attempt in fallback_attempts)
    assert all(str(attempt.get("failure_reason") or "").startswith("tender_id_fallback") for attempt in fallback_attempts)


def test_tenderdetails_json_candidate_generation_prefers_document_ids_before_tender_fallback(monkeypatch) -> None:
    payload = {
        "tenderId": "159131",
        "documents": [
            {
                "documentId": "doc-77",
                "fileName": "Pricing Schedule.pdf",
                "downloadUrl": "/Home/DownloadFile?documentId=doc-77",
            }
        ],
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    calls: list[str] = []

    def fake_download_candidate(url, output_path, timeout=35):
        calls.append(url)
        return {
            "url": url,
            "ok": False,
            "verified_download": False,
            "status_code": 404,
            "http_status": 404,
            "final_url": url,
            "content_type": "text/html; charset=utf-8",
            "content_disposition": "",
            "content_length": 9,
            "saved_path": "",
            "error": "http_status_404",
            "validation": {},
            "binary_signature_detected": False,
        }

    monkeypatch.setattr(tenderdetails_service, "_download_candidate", fake_download_candidate)

    result = tenderdetails_service.download_from_tenderdetails_json({"tender_id": "159131"})

    assert calls
    assert calls[0].startswith("https://www.etenders.gov.za/Home/DownloadFile")
    assert "documentId=doc-77" in calls[1] or "documentId=doc-77" in calls[0]
    assert result["attempt_count"] > 0


def test_explicit_json_download_url_becomes_first_artifact_candidate(monkeypatch) -> None:
    row = {
        "source_json_path": "$.documents[0]",
        "row_keys": ["downloadUrl", "fileName"],
        "value": {
            "downloadUrl": "/files/tender-pack.zip",
            "fileName": "Tender Pack.zip",
        },
    }
    doc = tenderdetails_service._row_to_document_record(row)
    candidates = tenderdetails_service._build_download_candidates(
        "159131",
        row,
        doc,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert candidates[0]["route_pattern_name"] == "explicit_json_url_or_path"
    assert candidates[0]["source_json_path"] == "$.documents[0]"
    assert candidates[0]["resolved_document_url"] == "https://www.etenders.gov.za/files/tender-pack.zip"
    assert candidates[0]["original_json_value"] == "/files/tender-pack.zip"
    assert candidates[0]["parameter_names_used"] == ["path"]


def test_relative_file_path_resolves_against_tenderdetails_page() -> None:
    row = {
        "source_json_path": "$.documents[2]",
        "row_keys": ["filePath", "fileName"],
        "value": {
            "filePath": "files/relative/TenderSpec.pdf",
            "fileName": "TenderSpec.pdf",
        },
    }
    doc = tenderdetails_service._row_to_document_record(row)
    candidates = tenderdetails_service._build_download_candidates(
        "159131",
        row,
        doc,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert candidates[0]["resolved_document_url"] == "https://www.etenders.gov.za/Home/files/relative/TenderSpec.pdf"
    assert candidates[0]["route_pattern_name"] == "explicit_json_url_or_path"
    assert candidates[0]["source_json_path"] == "$.documents[2]"


def test_filename_only_value_is_not_attempted_without_id_or_path() -> None:
    row = {
        "source_json_path": "$.documents[4]",
        "row_keys": ["fileName"],
        "value": {
            "fileName": "TenderPack.zip",
        },
    }
    doc = tenderdetails_service._row_to_document_record(row)
    candidates = tenderdetails_service._build_download_candidates(
        "159131",
        row,
        doc,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert all(cand.get("route_pattern_name") != "explicit_json_url_or_path" for cand in candidates)
    assert all(cand.get("original_json_value") != "TenderPack.zip" or cand.get("route_pattern_name") != "explicit_json_url_or_path" for cand in candidates)
    assert any(cand.get("route_pattern_name") == "tender_id_fallback" for cand in candidates)


def test_generic_guessed_routes_follow_explicit_json_candidates() -> None:
    row = {
        "source_json_path": "$.documents[7]",
        "row_keys": ["downloadUrl", "documentId", "fileName"],
        "value": {
            "downloadUrl": "/files/direct-pack.pdf",
            "documentId": "doc-77",
            "fileName": "Pricing Schedule.pdf",
        },
    }
    doc = tenderdetails_service._row_to_document_record(row)
    candidates = tenderdetails_service._build_download_candidates(
        "159131",
        row,
        doc,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert candidates[0]["route_pattern_name"] == "explicit_json_url_or_path"
    assert candidates[0]["candidate_priority"] == 0
    assert all(cand["candidate_priority"] >= 1 for cand in candidates[1:])
    assert all(cand["candidate_priority"] >= 0 for cand in candidates)


def test_tenderdetails_download_attempts_include_route_pattern_diagnostics(monkeypatch) -> None:
    payload = {
        "tenderId": "159131",
        "documents": [
            {
                "supportDocumentID": "sup-88",
                "fileName": "Tender Document.pdf",
                "path": "/files/Tender Document.pdf",
            }
        ],
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    def fake_download_candidate(url, output_path, timeout=35):
        return {
            "url": url,
            "ok": False,
            "verified_download": False,
            "status_code": 404,
            "http_status": 404,
            "final_url": url,
            "content_type": "text/html; charset=utf-8",
            "content_disposition": "",
            "content_length": 9,
            "saved_path": "",
            "error": "http_status_404",
            "validation": {},
            "binary_signature_detected": False,
        }

    monkeypatch.setattr(tenderdetails_service, "_download_candidate", fake_download_candidate)

    result = tenderdetails_service.download_from_tenderdetails_json({"tender_id": "159131"})

    first_attempt = next(attempt for attempt in result["attempts"] if attempt.get("route_pattern_name"))
    assert first_attempt["route_pattern_name"] is not None
    assert first_attempt["source_json_path"] is not None
    assert first_attempt["parameter_names_used"] is not None
    assert first_attempt["http_status"] == 404
    assert first_attempt["response_shape"] in {"html", "unknown"}
    assert first_attempt["binary_signature_detected"] is False
    assert first_attempt["resolved_document_url"]


def test_blobname_plus_downloaded_filename_generates_home_download_url() -> None:
    row = {
        "source_json_path": "$.documents[0]",
        "row_keys": ["blobName", "downloadedFileName"],
        "value": {
            "blobName": "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf",
            "downloadedFileName": "Platinum Weekly Advert - 12 June 2026.pdf",
        },
    }
    doc = tenderdetails_service._row_to_document_record(row)
    candidates = tenderdetails_service._build_download_candidates(
        "159131",
        row,
        doc,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert candidates[0]["route_pattern_name"] == "etenders_blob_download"
    assert candidates[0]["parameter_names_used"] == ["blobName", "downloadedFileName"]
    assert candidates[0]["resolved_document_url"] == (
        "https://www.etenders.gov.za/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
        "&downloadedFileName=Platinum+Weekly+Advert+-+12+June+2026.pdf"
    )
    assert candidates[0]["original_json_value"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert candidates[0]["candidate_classification"] == "direct_file"


def test_blobname_only_generates_home_download_url() -> None:
    row = {
        "source_json_path": "$.documents[1]",
        "row_keys": ["blobName"],
        "value": {
            "blobName": "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf",
        },
    }
    doc = tenderdetails_service._row_to_document_record(row)
    candidates = tenderdetails_service._build_download_candidates(
        "159131",
        row,
        doc,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert candidates[0]["route_pattern_name"] == "etenders_blob_download"
    assert candidates[0]["parameter_names_used"] == ["blobName"]
    assert candidates[0]["resolved_document_url"] == "https://www.etenders.gov.za/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert candidates[0]["candidate_classification"] == "direct_file"


def test_explicit_json_path_rejects_external_blob_url() -> None:
    row = {
        "source_json_path": "$.documents[2]",
        "row_keys": ["downloadUrl", "fileName"],
        "value": {
            "downloadUrl": "https://malicious.example/download.pdf",
            "fileName": "download.pdf",
        },
    }
    doc = tenderdetails_service._row_to_document_record(row)
    candidates = tenderdetails_service._build_download_candidates(
        "159131",
        row,
        doc,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert all(cand.get("route_pattern_name") != "explicit_json_url_or_path" for cand in candidates)


def test_blob_route_is_classified_as_direct_file() -> None:
    scored = tender_harvester._v64_score_artifact_candidate(
        "/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf",
        "https://www.etenders.gov.za/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf",
        "",
        "metadata_blobname",
    )

    assert scored["classification"] == "direct_file"
    assert scored["should_attempt"] is True
    assert scored["extension"] == ".pdf"


def test_blob_route_pdf_response_is_saved_as_artifact(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "documents": [
            {
                "blobName": "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf",
                "downloadedFileName": "Platinum Weekly Advert - 12 June 2026.pdf",
            }
        ]
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    def fake_get(url, *args, **kwargs):
        if "Home/Download" in url and "blobName=" in url:
            return _FakeDownloadResponse(
                url=url,
                status_code=200,
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="Platinum Weekly Advert - 12 June 2026.pdf"',
                },
                chunks=[b"%PDF-1.4\n", b"binarypdf"],
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tenderdetails_service.requests, "get", fake_get)

    result = tenderdetails_service.download_from_tenderdetails_json({"tender_id": "159131", "output_dir": str(tmp_path)})

    assert result["status"] == "ok"
    assert result["saved_path"]
    assert Path(result["saved_path"]).exists()
    route_attempt = next(attempt for attempt in result["attempts"] if attempt.get("route_pattern_name") == "etenders_blob_download")
    assert route_attempt["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert route_attempt["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert route_attempt["source_json_path"] == "$.documents[0]"
    assert route_attempt["artifact_path"] == result["saved_path"]
    assert route_attempt["artifact_exists"] is True
    assert route_attempt["artifact_size_bytes"] > 0
    assert route_attempt["binary_signature_detected"] is True


def test_blob_backed_diagnostics_preserve_route_metadata(monkeypatch) -> None:
    payload = {
        "documents": [
            {
                "blobName": "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf",
                "downloadedFileName": "Platinum Weekly Advert - 12 June 2026.pdf",
            }
        ]
    }
    monkeypatch.setattr(
        tenderdetails_service,
        "_fetch_tenderdetails",
        lambda tender_id: {
            "ok": True,
            "winning_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
            "attempts": [{"url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131", "data": payload, "status_code": 200, "content_type": "application/json"}],
            "data": payload,
        },
    )

    def fake_get(url, *args, **kwargs):
        return _FakeDownloadResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            chunks=[b"not found"],
        )

    monkeypatch.setattr(tenderdetails_service.requests, "get", fake_get)

    result = tenderdetails_service.download_from_tenderdetails_json({"tender_id": "159131"})

    route_attempt = next(attempt for attempt in result["attempts"] if attempt.get("route_pattern_name") == "etenders_blob_download")
    assert route_attempt["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert route_attempt["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert route_attempt["source_json_path"] == "$.documents[0]"
    assert route_attempt["parameter_names_used"] == ["blobName", "downloadedFileName"]


def test_html_blob_candidates_are_attempted_before_tender_id_fallback(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    html = """
    <html><body>
      <a href="/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf">
        Platinum Weekly Advert - 12 June 2026
      </a>
    </body></html>
    """

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text=html,
            )
        if "Home/Download" in url and "blobName=" in url:
            return _FakeDownloadResponse(
                url=url,
                status_code=200,
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="Platinum Weekly Advert - 12 June 2026.pdf"',
                },
                chunks=[b"%PDF-1.4\n", b"binarypdf"],
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    assert result["buyer_pack_downloaded"] is True
    assert result["buyer_pack_path"]
    assert result["artifact_download_success_count"] > 0
    blob_diag = next(diag for diag in result["diagnostics"] if diag.get("route_pattern_name") == "etenders_blob_download_html")
    assert blob_diag["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert blob_diag["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert blob_diag["source_html_path"] == "Platinum Weekly Advert - 12 June 2026"
    assert blob_diag["artifact_exists"] is True
    assert blob_diag["binary_signature_detected"] is True
    assert not any(str(diag.get("route_pattern_name")) == "tender_id_fallback" for diag in result["diagnostics"] if diag.get("diagnostic_type") == "artifact_candidate")


def test_rendered_dom_blob_candidates_are_attempted_before_tender_id_fallback(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    html = """
    <html><body>
      <div class="detail-view">Tender details rendered without direct blob link in raw HTML.</div>
    </body></html>
    """
    rendered_html = """
    <html><body>
      <a href="/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf">
        Platinum Weekly Advert - 12 June 2026
      </a>
    </body></html>
    """

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text=html,
            )
        if "Home/Download" in url and "blobName=" in url:
            return _FakeDownloadResponse(
                url=url,
                status_code=200,
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="Platinum Weekly Advert - 12 June 2026.pdf"',
                },
                chunks=[b"%PDF-1.4\n", b"binarypdf"],
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_clicked": True,
            "row_expanded": True,
            "documents_section_found": True,
            "blob_links": [
                {
                    "href": "/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf",
                    "text": "Platinum Weekly Advert - 12 June 2026",
                }
            ],
            "expanded_dom": {"body_html_preview": rendered_html},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Platinum Weekly Advert",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    assert result["buyer_pack_downloaded"] is True
    blob_diag = next(diag for diag in result["diagnostics"] if diag.get("route_pattern_name") == "etenders_blob_download_interactive")
    assert blob_diag["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert blob_diag["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert blob_diag["source_html_path"] == "interactive_rendered_dom_blob_link"
    assert blob_diag["source_context"] == "clicked_expanded_tender_row"
    assert blob_diag["artifact_exists"] is True
    assert blob_diag["binary_signature_verified"] is True
    assert any(diag.get("diagnostic_type") == "etenders_interactive_dom_capture" for diag in result["diagnostics"])
    assert not any(str(diag.get("route_pattern_name")) == "tender_id_fallback" for diag in result["diagnostics"] if diag.get("diagnostic_type") == "artifact_candidate")


def test_rendered_dom_capture_diagnostic_is_persisted_without_blob_candidates(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    rendered_html = "<html><body><div>rendered detail without blob links</div></body></html>"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "expanded_dom": {"body_html_preview": rendered_html},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Announcements",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    dom_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_rendered_dom_capture")
    assert dom_diag["source_html_path"] == "rendered_html_blob_link"
    assert dom_diag["source_json_path"] == "rendered_html_blob_link"
    assert dom_diag["rendered_html_length"] > 0
    assert dom_diag["rendered_blob_candidates_count"] == 0


def test_interactive_capture_propagates_row_discovery_fields_when_row_is_missing(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_found": False,
            "row_expanded": False,
            "table_container_found": True,
            "datatables_processing_seen": False,
            "datatables_processing_finished": True,
            "visible_row_count": 2,
            "page_text_limited_before_row_search": "Currently Advertised",
            "table_count": 1,
            "row_count_by_selector": {"#tendeList tbody tr": 2},
            "first_rows_text_limited": ["159131 Unrelated Tender A", "158918 Unrelated Tender B"],
            "visible_links_limited": ["/Home/TenderDetails?id=159131"],
            "page_url_after_load": "https://www.etenders.gov.za/Home/opportunities",
            "page_title": "eTenders",
            "row_match_strategy": "tender_id",
            "row_match_text": "159131",
            "matched_row_text_limited": "",
            "row_selector_used": "#tendeList tbody tr",
            "row_click_target_used": "",
            "documents_section_found": False,
            "tender_documents_text_limited": "",
            "document_anchor_count": 0,
            "all_anchor_hrefs_limited": [],
            "all_anchor_texts_limited": [],
            "download_like_anchor_count": 0,
            "blob_like_string_count": 0,
            "visible_text_limited": "Currently Advertised",
            "post_click_wait_ms": 0,
            "blob_links": [],
            "interactive_blob_candidates_count": 0,
            "expanded_dom": {"body_html_preview": "<html><body>row missing</body></html>"},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Missing Tender",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["row_found"] is False
    assert interactive_diag["failure_reason"] == "row_not_found"
    assert interactive_diag["table_container_found"] is True
    assert interactive_diag["visible_row_count"] == 2
    assert interactive_diag["first_rows_text_limited"] == ["159131 Unrelated Tender A", "158918 Unrelated Tender B"]
    assert interactive_diag["page_text_limited_before_row_search"] == "Currently Advertised"
    assert interactive_diag["row_match_strategy"] == "tender_id"
    assert interactive_diag["row_match_text"] == "159131"
    assert interactive_diag["matched_row_text_limited"] == ""


def test_interactive_capture_uses_documents_section_failure_reason_when_row_found(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_found": True,
            "row_expanded": True,
            "table_container_found": True,
            "datatables_processing_seen": False,
            "datatables_processing_finished": True,
            "visible_row_count": 2,
            "page_text_limited_before_row_search": "Currently Advertised",
            "table_count": 1,
            "row_count_by_selector": {"#tendeList tbody tr": 2},
            "first_rows_text_limited": ["159131 Platinum Weekly Advert", "158918 Other Tender Notice"],
            "visible_links_limited": ["/Home/TenderDetails?id=159131"],
            "page_url_after_load": "https://www.etenders.gov.za/Home/opportunities",
            "page_title": "eTenders",
            "row_match_strategy": "exact_title",
            "row_match_text": "159131 Platinum Weekly Advert",
            "matched_row_text_limited": "159131 Platinum Weekly Advert",
            "row_selector_used": "#tendeList tbody tr",
            "row_click_target_used": "row",
            "documents_section_found": False,
            "tender_documents_text_limited": "",
            "document_anchor_count": 0,
            "all_anchor_hrefs_limited": [],
            "all_anchor_texts_limited": [],
            "download_like_anchor_count": 0,
            "blob_like_string_count": 0,
            "visible_text_limited": "Platinum Weekly Advert",
            "post_click_wait_ms": 1000,
            "blob_links": [],
            "interactive_blob_candidates_count": 0,
            "expanded_dom": {"body_html_preview": "<html><body>row matched but no documents section</body></html>"},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Platinum Weekly Advert",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["row_found"] is True
    assert interactive_diag["documents_section_found"] is False
    assert interactive_diag["failure_reason"] == "documents_section_not_found"
    assert interactive_diag["row_match_strategy"] == "exact_title"
    assert interactive_diag["matched_row_text_limited"] == "159131 Platinum Weekly Advert"


def test_interactive_capture_uses_no_blob_links_failure_reason_when_documents_section_has_no_blob_links(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_found": True,
            "row_expanded": True,
            "table_container_found": True,
            "datatables_processing_seen": False,
            "datatables_processing_finished": True,
            "visible_row_count": 2,
            "page_text_limited_before_row_search": "Currently Advertised",
            "table_count": 1,
            "row_count_by_selector": {"#tendeList tbody tr": 2},
            "first_rows_text_limited": ["159131 Platinum Weekly Advert", "158918 Other Tender Notice"],
            "visible_links_limited": ["/Home/TenderDetails?id=159131"],
            "page_url_after_load": "https://www.etenders.gov.za/Home/opportunities",
            "page_title": "eTenders",
            "row_match_strategy": "exact_title",
            "row_match_text": "159131 Platinum Weekly Advert",
            "matched_row_text_limited": "159131 Platinum Weekly Advert",
            "row_selector_used": "#tendeList tbody tr",
            "row_click_target_used": "row",
            "documents_section_found": True,
            "tender_documents_text_limited": "TENDER DOCUMENTS",
            "document_anchor_count": 2,
            "all_anchor_hrefs_limited": [
                "https://www.etenders.gov.za/Home/Announcements",
                "https://www.etenders.gov.za/Home/View?id=159131",
            ],
            "all_anchor_texts_limited": ["Announcements", "View"],
            "download_like_anchor_count": 1,
            "blob_like_string_count": 0,
            "visible_text_limited": "TENDER DOCUMENTS",
            "post_click_wait_ms": 1000,
            "blob_links": [],
            "interactive_blob_candidates_count": 0,
            "expanded_dom": {"body_html_preview": "<html><body>documents section but no blob links</body></html>"},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Platinum Weekly Advert",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["row_found"] is True
    assert interactive_diag["documents_section_found"] is True
    assert interactive_diag["failure_reason"] == "no_blob_links_found"
    assert interactive_diag["document_anchor_count"] == 2
    assert interactive_diag["blob_like_string_count"] == 0
    assert interactive_diag["visible_row_count"] == 2


def test_extracts_interactive_blob_candidates_from_blob_links() -> None:
    blob_links = [
        {
            "href": "/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf",
            "text": "Platinum Weekly Advert - 12 June 2026",
        }
    ]

    candidates = tender_harvester._v64_extract_interactive_blob_candidates(
        blob_links,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
        {"name": "eTenders", "source_name": "eTenders"},
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    assert candidates
    candidate = candidates[0]
    assert candidate["route_pattern_name"] == "etenders_blob_download_interactive"
    assert candidate["url"] == "https://www.etenders.gov.za/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf"
    assert candidate["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert candidate["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert candidate["source_html_path"] == "interactive_rendered_dom_blob_link"
    assert candidate["source_context"] == "clicked_expanded_tender_row"
    assert candidate["candidate_classification"] == "direct_file"


def test_etenders_datatables_wait_records_table_snapshot() -> None:
    page = _FakePlaywrightPage(
        body_text="Currently Advertised\n159131 Platinum Weekly Advert 12 June 2026 Tender Pack",
        selector_counts={
            "#tendeList": 1,
            "table#tendeList": 1,
            ".dataTables_wrapper": 1,
            "table": 1,
            "#tendeList tbody tr": 2,
            "table#tendeList tbody tr": 2,
            ".dataTables_wrapper tbody tr": 2,
            "tr[role='row']": 1,
            "td.sorting_1": 1,
            "a[href]": 2,
        },
        selector_texts={
            "#tendeList tbody tr": [
                "159131 Platinum Weekly Advert 12 June 2026 Tender Pack",
                "158918 Other Tender Notice",
            ],
            "table#tendeList tbody tr": [
                "159131 Platinum Weekly Advert 12 June 2026 Tender Pack",
                "158918 Other Tender Notice",
            ],
            ".dataTables_wrapper tbody tr": [
                "159131 Platinum Weekly Advert 12 June 2026 Tender Pack",
                "158918 Other Tender Notice",
            ],
            "tr[role='row']": ["159131 Platinum Weekly Advert 12 June 2026 Tender Pack"],
            "td.sorting_1": ["159131"],
        },
        selector_hrefs={
            "a[href]": [
                "/Home/Download/?blobName=abc.pdf&downloadedFileName=abc.pdf",
                "/Home/TenderDetails?id=159131",
            ],
        },
    )

    snapshot = asyncio.run(
        etenders_dom_service._v50_9_4_wait_for_etenders_table_ready(
            page,
            {"tender_id": "159131", "search_text": "Platinum Weekly Advert 12 June 2026 Tender Pack"},
            timeout_ms=50,
        )
    )

    assert snapshot["table_container_found"] is True
    assert snapshot["datatables_processing_seen"] is False
    assert snapshot["datatables_processing_finished"] is True
    assert snapshot["visible_row_count"] > 0
    assert snapshot["page_url_after_load"] == "https://www.etenders.gov.za/Home/opportunities"
    assert snapshot["page_title"] == "eTenders"
    assert "#tendeList tbody tr" in snapshot["row_count_by_selector"]
    assert snapshot["row_count_by_selector"]["#tendeList tbody tr"] == 2
    assert snapshot["first_rows_text_limited"][0].startswith("159131 Platinum Weekly Advert 12 June 2026")
    assert "/Home/Download/?blobName=abc.pdf" in " ".join(snapshot["visible_links_limited"])
    assert "Currently Advertised" in snapshot["page_text_limited_before_row_search"]


def test_etenders_row_matching_prefers_exact_title_then_partial_normalized_title() -> None:
    exact_rows = [
        {"selector": "#tendeList tbody tr", "index": 0, "text": "Noise row"},
        {
            "selector": "#tendeList tbody tr",
            "index": 1,
            "text": "159131 Platinum Weekly Advert 12 June 2026 Tender Pack",
        },
    ]

    exact = etenders_dom_service._v50_9_4_match_etenders_row_texts(
        exact_rows,
        {"title": "159131 Platinum Weekly Advert 12 June 2026 Tender Pack"},
    )
    assert exact["row_found"] is True
    assert exact["row_match_strategy"] == "exact_title"
    assert "Platinum Weekly Advert" in exact["matched_row_text_limited"]

    partial_rows = [
        {"selector": "#tendeList tbody tr", "index": 0, "text": "Noise row"},
        {
            "selector": "#tendeList tbody tr",
            "index": 1,
            "text": "159131 Platinum Weekly Advert June 2026 Tender Attachments",
        },
    ]

    partial = etenders_dom_service._v50_9_4_match_etenders_row_texts(
        partial_rows,
        {"title": "Platinum Weekly Advert June 2026 Tender Pack Attachment"},
    )
    assert partial["row_found"] is True
    assert partial["row_match_strategy"] == "normalized_partial_title"
    assert "Platinum Weekly Advert June 2026" in partial["matched_row_text_limited"]


def test_etenders_row_not_found_snapshot_includes_first_rows_texts() -> None:
    page = _FakePlaywrightPage(
        body_text="Currently Advertised\n159131 Unrelated Tender A\n158918 Unrelated Tender B",
        selector_counts={
            "#tendeList": 1,
            "table#tendeList": 1,
            ".dataTables_wrapper": 1,
            "table": 1,
            "#tendeList tbody tr": 2,
            "table#tendeList tbody tr": 2,
            ".dataTables_wrapper tbody tr": 2,
            "a[href]": 1,
        },
        selector_texts={
            "#tendeList tbody tr": ["159131 Unrelated Tender A", "158918 Unrelated Tender B"],
            "table#tendeList tbody tr": ["159131 Unrelated Tender A", "158918 Unrelated Tender B"],
            ".dataTables_wrapper tbody tr": ["159131 Unrelated Tender A", "158918 Unrelated Tender B"],
        },
        selector_hrefs={"a[href]": ["/Home/TenderDetails?id=159131"]},
    )

    snapshot = asyncio.run(
        etenders_dom_service._v50_9_4_wait_for_etenders_table_ready(
            page,
            {"tender_id": "999999", "search_text": "Missing Tender"},
            timeout_ms=50,
        )
    )
    match = etenders_dom_service._v50_9_4_match_etenders_row_texts(snapshot["row_texts"], {"title": "Missing Tender"})

    assert match["row_found"] is False
    assert snapshot["first_rows_text_limited"] == [
        "159131 Unrelated Tender A",
        "158918 Unrelated Tender B",
        "159131 Unrelated Tender A",
        "158918 Unrelated Tender B",
        "159131 Unrelated Tender A",
        "158918 Unrelated Tender B",
    ]
    assert snapshot["row_count_by_selector"]["#tendeList tbody tr"] == 2
    assert "Missing Tender" not in snapshot["page_text_limited_before_row_search"]


def test_etenders_wait_for_table_ready_captures_page_state_even_without_rows() -> None:
    page = _FakePlaywrightPage(
        url="https://www.etenders.gov.za/Home/opportunities",
        title="eTenders Opportunities",
        body_text="Currently Advertised\nNo visible rows yet",
        body_html="<html><body><main>Currently Advertised</main></body></html>",
        selector_counts={"#tendeList": 0, "table#tendeList": 0, ".dataTables_wrapper": 0, ".dataTables_scroll": 0, "table": 0, "a[href]": 0},
        goto_status=204,
    )

    snapshot = asyncio.run(
        etenders_dom_service._v50_9_4_wait_for_etenders_table_ready(
            page,
            {"tender_id": "999999", "search_text": "Missing Tender", "output_dir": "/private/tmp/lmcp_etenders_diag"},
            timeout_ms=25,
            main_response_status=204,
        )
    )

    assert snapshot["page_url_after_load"] == "https://www.etenders.gov.za/Home/opportunities"
    assert snapshot["page_title"] == "eTenders Opportunities"
    assert snapshot["main_response_status"] == 204
    assert snapshot["body_text_length"] > 0
    assert snapshot["body_html_length"] > 0
    assert snapshot["body_text_preview_limited"].startswith("Currently Advertised")
    assert snapshot["table_container_found"] is False
    assert snapshot["visible_row_count"] == 0
    assert snapshot["first_rows_text_limited"] == []
    assert snapshot["screenshot_path"].endswith("__v50_9_4_pre_table.png")
    assert snapshot["page_text_limited_before_row_search"].startswith("Currently Advertised")


def test_etenders_activate_best_candidate_row_skips_expansion_when_row_missing(monkeypatch) -> None:
    page = _FakePlaywrightPage()

    async def fake_force_browse_currently_advertised(*args, **kwargs):
        return []

    async def fake_active_opportunities_tab_name(*args, **kwargs):
        return "Currently Advertised"

    async def fake_wait_for_etenders_table_ready(*args, **kwargs):
        return {
            "table_container_found": True,
            "datatables_processing_seen": False,
            "datatables_processing_finished": True,
            "visible_row_count": 2,
            "page_text_limited_before_row_search": "currently advertised",
            "table_count": 1,
            "row_count_by_selector": {"#tendeList tbody tr": 2},
            "first_rows_text_limited": ["159131 Unrelated Tender A", "158918 Unrelated Tender B"],
            "visible_links_limited": ["/Home/TenderDetails?id=159131"],
            "page_url_after_load": "https://www.etenders.gov.za/Home/opportunities",
            "page_title": "eTenders",
            "row_texts": [
                {"selector": "#tendeList tbody tr", "index": 0, "text": "159131 Unrelated Tender A"},
                {"selector": "#tendeList tbody tr", "index": 1, "text": "158918 Unrelated Tender B"},
            ],
        }

    async def fake_capture_expanded_dom_state(*args, **kwargs):
        raise AssertionError("expansion should not be attempted when no row is found")

    monkeypatch.setattr(etenders_dom_service, "_force_browse_currently_advertised", fake_force_browse_currently_advertised)
    monkeypatch.setattr(etenders_dom_service, "_active_opportunities_tab_name", fake_active_opportunities_tab_name)
    monkeypatch.setattr(etenders_dom_service, "_v50_9_4_wait_for_etenders_table_ready", fake_wait_for_etenders_table_ready)
    monkeypatch.setattr(
        etenders_dom_service,
        "_v50_9_4_match_etenders_row_texts",
        lambda *args, **kwargs: {
            "row_found": False,
            "row_match_strategy": "",
            "row_match_text": "",
            "matched_row_text_limited": "",
            "matched_row_index": -1,
            "matched_row_selector": "",
            "score": 0,
            "matched_terms": [],
            "matched_tokens": [],
        },
    )
    monkeypatch.setattr(etenders_dom_service, "_capture_expanded_dom_state", fake_capture_expanded_dom_state)

    result = asyncio.run(
        etenders_dom_service._activate_best_candidate_row(
            page,
            {"tender_id": "159131", "title": "Missing Tender"},
            {"best_candidate_row": {"score": 0}},
        )
    )

    assert result["row_found"] is False
    assert result["failure_reason"] == "row_not_found"
    assert result["table_container_found"] is True
    assert result["visible_row_count"] == 2
    assert result["first_rows_text_limited"][0] == "159131 Unrelated Tender A"
    assert result["row_selector_used"] == "table tbody tr, table tr, [role=\"row\"], .dataTables_wrapper tr"


def test_capture_falls_back_to_playwright_managed_when_cdp_is_unavailable(monkeypatch) -> None:
    page = _FakePlaywrightPage()
    _install_fake_playwright(monkeypatch, page, cdp_ok=False, managed_ok=True)
    monkeypatch.setattr(etenders_dom_service, "_dismiss_modals", lambda page: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(
        etenders_dom_service,
        "_snapshot_row_diagnostics",
        lambda *args, **kwargs: asyncio.sleep(
            0,
            result={
                "target_terms_used": ["159131"],
                "all_visible_row_previews_scanned": [],
                "best_candidate_row": {"score": 1.0, "index": 0},
            },
        ),
    )
    monkeypatch.setattr(
        etenders_dom_service,
        "_activate_best_candidate_row",
        lambda page_obj, data, seed: asyncio.sleep(
            0,
            result={
                "row_clicked": True,
                "row_expanded": True,
                "matched_row": {"index": 0},
                "table_container_found": True,
                "datatables_processing_seen": False,
                "datatables_processing_finished": True,
                "main_response_status": 200,
                "body_text_length": 120,
                "body_html_length": 220,
                "body_text_preview_limited": "Currently Advertised",
                "visible_row_count": 2,
                "page_text_limited_before_row_search": "Currently Advertised",
                "table_count": 1,
                "row_count_by_selector": {"#tendeList tbody tr": 2},
                "first_rows_text_limited": ["159131 Missing Tender"],
                "visible_links_limited": ["/Home/TenderDetails?id=159131"],
                "page_url_after_load": page_obj.url,
                "page_title": "eTenders Opportunities",
                "screenshot_path": "",
                "row_match_strategy": "tender_id",
                "row_match_text": "159131",
                "matched_row_text_limited": "159131 Missing Tender",
                "documents_section_found": True,
                "tender_documents_text_limited": "Tender documents",
                "document_anchor_count": 1,
                "all_anchor_hrefs_limited": ["https://www.etenders.gov.za/Home/Download/?blobName=test.pdf"],
                "all_anchor_texts_limited": ["Tender document"],
                "download_like_anchor_count": 1,
                "blob_like_string_count": 1,
                "visible_text_limited": "Tender documents",
                "post_click_wait_ms": 500,
                "expanded_dom_detected": True,
                "tender_detail_detected": False,
                "upload_controls_detected": False,
                "download_controls_detected": True,
                "helper_error_type": "",
                "helper_error_message_limited": "",
                "expanded_dom": {"blob_links": [{"href": "https://www.etenders.gov.za/Home/Download/?blobName=test.pdf"}]},
                "active_tab_name": "Currently Advertised",
                "actions": [{"action": "row_clicked"}],
            },
        ),
    )

    result = asyncio.run(
        etenders_dom_service._capture(
            {
                "tender_id": "159131",
                "tender_title": "Missing Tender",
                "opportunities_url": "https://www.etenders.gov.za/Home/opportunities?id=1",
                "wait_seconds": 0,
            }
        )
    )

    assert result["status"] == "needs_review_or_manual_click"
    assert result["browser_mode"] == "playwright_managed"
    assert result["helper_used_detail_page"] is False
    assert result["helper_used_opportunities_page"] is True
    assert result["helper_resolved_url"] == "https://www.etenders.gov.za/Home/opportunities?id=1"
    assert result["page_url_after_load"] == "https://www.etenders.gov.za/Home/opportunities?id=1"
    assert result["row_found"] is True
    assert result["row_expanded"] is True


def test_capture_returns_safe_defaults_on_runtime_exception(monkeypatch) -> None:
    _install_fake_playwright(monkeypatch, _FakePlaywrightPage(goto_error="boom"))
    monkeypatch.setattr(
        etenders_dom_service,
        "_resolve_cdp_endpoint",
        lambda cdp_url: {"ok": True, "resolved_websocket_url": "ws://example", "error": ""},
    )

    result = asyncio.run(
        etenders_dom_service._capture(
            {
                "tender_id": "159131",
                "search_text": "Missing Tender",
                "tender_url": "https://www.etenders.gov.za/Home/opportunities",
                "cdp_url": "http://host.docker.internal:9222",
            }
        )
    )

    assert result["status"] == "error"
    assert result["table_container_found"] is False
    assert result["visible_row_count"] == 0
    assert result["first_rows_text_limited"] == []
    assert result["page_text_limited_before_row_search"] == ""
    assert result["helper_error_type"] == "RuntimeError"
    assert "boom" in result["helper_error_message_limited"]
    assert result["row_found"] is False


def test_capture_prefers_detail_page_over_opportunities(monkeypatch) -> None:
    page = _FakePlaywrightPage()
    _install_fake_playwright(monkeypatch, page)
    monkeypatch.setattr(
        etenders_dom_service,
        "_resolve_cdp_endpoint",
        lambda cdp_url: {"ok": True, "resolved_websocket_url": "ws://example", "error": ""},
    )
    monkeypatch.setattr(etenders_dom_service, "_dismiss_modals", lambda page: asyncio.sleep(0, result=[]))

    async def fake_capture_expanded_dom_state(page_obj, source: str = "detail_page_initial"):
        return {
            "documents_section_found": True,
            "download_controls_detected": True,
            "document_anchor_count": 2,
            "all_anchor_hrefs_limited": ["https://www.etenders.gov.za/Home/Download/?blobName=test.pdf"],
            "all_anchor_texts_limited": ["Tender document"],
            "blob_links": [{"href": "https://www.etenders.gov.za/Home/Download/?blobName=test.pdf"}],
            "visible_text_limited": "Tender documents",
            "expanded_dom_detected": True,
            "tender_detail_detected": True,
            "upload_controls_detected": False,
            "tender_documents_text_limited": "Tender documents",
            "download_like_anchor_count": 1,
            "blob_like_string_count": 1,
        }

    async def fail_activate(*args, **kwargs):
        raise AssertionError("opportunities flow should not run when detail page already exposes documents")

    monkeypatch.setattr(etenders_dom_service, "_capture_expanded_dom_state", fake_capture_expanded_dom_state)
    monkeypatch.setattr(etenders_dom_service, "_activate_best_candidate_row", fail_activate)

    result = asyncio.run(
        etenders_dom_service._capture(
            {
                "tender_id": "159131",
                "tender_title": "Water meters",
                "detail_page_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
                "opportunities_url": "https://www.etenders.gov.za/Home/opportunities?id=1",
                "cdp_url": "http://host.docker.internal:9222",
                "wait_seconds": 0,
            }
        )
    )

    assert page.goto_calls == ["https://www.etenders.gov.za/Home/TenderDetails?id=159131"]
    assert result["helper_input_url"] == "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    assert result["helper_used_detail_page"] is True
    assert result["helper_used_opportunities_page"] is False
    assert result["helper_resolved_url"] == "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    assert result["browser_mode"] == "cdp_attach"


def test_capture_falls_back_from_detail_page_to_opportunities_with_query(monkeypatch) -> None:
    page = _FakePlaywrightPage()
    _install_fake_playwright(monkeypatch, page)
    monkeypatch.setattr(
        etenders_dom_service,
        "_resolve_cdp_endpoint",
        lambda cdp_url: {"ok": True, "resolved_websocket_url": "ws://example", "error": ""},
    )
    monkeypatch.setattr(etenders_dom_service, "_dismiss_modals", lambda page: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(
        etenders_dom_service,
        "_capture_expanded_dom_state",
        lambda *args, **kwargs: asyncio.sleep(
            0,
            result={
                "documents_section_found": False,
                "download_controls_detected": False,
                "document_anchor_count": 0,
                "all_anchor_hrefs_limited": [],
                "all_anchor_texts_limited": [],
                "blob_links": [],
                "visible_text_limited": "",
                "expanded_dom_detected": False,
                "tender_detail_detected": True,
                "upload_controls_detected": False,
                "tender_documents_text_limited": "",
                "download_like_anchor_count": 0,
                "blob_like_string_count": 0,
            },
        ),
    )
    monkeypatch.setattr(
        etenders_dom_service,
        "_snapshot_row_diagnostics",
        lambda *args, **kwargs: asyncio.sleep(
            0,
            result={
                "target_terms_used": ["159131"],
                "all_visible_row_previews_scanned": [],
                "best_candidate_row": {"score": 1.0, "index": 0},
            },
        ),
    )

    async def fake_activate_best_candidate_row(page_obj, data, seed):
        assert data["tender_url"] == "https://www.etenders.gov.za/Home/opportunities?id=1&page=3"
        return {
            "row_clicked": True,
            "row_expanded": True,
            "matched_row": {"index": 0},
            "table_container_found": True,
            "datatables_processing_seen": False,
            "datatables_processing_finished": True,
            "main_response_status": 200,
            "body_text_length": 120,
            "body_html_length": 240,
            "body_text_preview_limited": "Currently Advertised",
            "visible_row_count": 4,
            "page_text_limited_before_row_search": "Currently Advertised",
            "table_count": 1,
            "row_count_by_selector": {"#tendeList tbody tr": 4},
            "first_rows_text_limited": ["159131 Water meters"],
            "visible_links_limited": ["/Home/TenderDetails?id=159131"],
            "page_url_after_load": page_obj.url,
            "page_title": "eTenders Opportunities",
            "screenshot_path": "",
            "row_match_strategy": "tender_id",
            "row_match_text": "159131",
            "matched_row_text_limited": "159131 Water meters",
            "documents_section_found": True,
            "tender_documents_text_limited": "Tender documents",
            "document_anchor_count": 1,
            "all_anchor_hrefs_limited": ["https://www.etenders.gov.za/Home/Download/?blobName=test.pdf"],
            "all_anchor_texts_limited": ["Tender document"],
            "download_like_anchor_count": 1,
            "blob_like_string_count": 1,
            "visible_text_limited": "Tender documents",
            "post_click_wait_ms": 1000,
            "expanded_dom_detected": True,
            "tender_detail_detected": False,
            "upload_controls_detected": False,
            "download_controls_detected": True,
            "helper_error_type": "",
            "helper_error_message_limited": "",
            "expanded_dom": {"blob_links": [{"href": "https://www.etenders.gov.za/Home/Download/?blobName=test.pdf"}]},
            "active_tab_name": "Currently Advertised",
            "actions": [{"action": "row_clicked"}],
        }

    monkeypatch.setattr(etenders_dom_service, "_activate_best_candidate_row", fake_activate_best_candidate_row)

    result = asyncio.run(
        etenders_dom_service._capture(
            {
                "tender_id": "159131",
                "tender_title": "Water meters",
                "detail_page_url": "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
                "opportunities_url": "https://www.etenders.gov.za/Home/opportunities?id=1&page=3",
                "cdp_url": "http://host.docker.internal:9222",
                "wait_seconds": 0,
            }
        )
    )

    assert page.goto_calls == [
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
        "https://www.etenders.gov.za/Home/opportunities?id=1&page=3",
    ]
    assert result["helper_used_detail_page"] is True
    assert result["helper_used_opportunities_page"] is True
    assert result["helper_preserved_query_params"] is True
    assert result["page_url_after_load"] == "https://www.etenders.gov.za/Home/opportunities?id=1&page=3"
    assert result["browser_mode"] == "cdp_attach"


def test_capture_preserves_opportunities_query_params_in_page_url_after_load(monkeypatch) -> None:
    page = _FakePlaywrightPage()
    _install_fake_playwright(monkeypatch, page)
    monkeypatch.setattr(
        etenders_dom_service,
        "_resolve_cdp_endpoint",
        lambda cdp_url: {"ok": True, "resolved_websocket_url": "ws://example", "error": ""},
    )
    monkeypatch.setattr(etenders_dom_service, "_dismiss_modals", lambda page: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(
        etenders_dom_service,
        "_snapshot_row_diagnostics",
        lambda *args, **kwargs: asyncio.sleep(
            0,
            result={
                "target_terms_used": ["159131"],
                "all_visible_row_previews_scanned": [],
                "best_candidate_row": {"score": 1.0, "index": 0},
            },
        ),
    )
    monkeypatch.setattr(
        etenders_dom_service,
        "_activate_best_candidate_row",
        lambda page_obj, data, seed: asyncio.sleep(
            0,
            result={
                "row_clicked": True,
                "matched_row": {"index": 0},
                "table_container_found": True,
                "datatables_processing_seen": False,
                "datatables_processing_finished": True,
                "main_response_status": 200,
                "body_text_length": 50,
                "body_html_length": 100,
                "body_text_preview_limited": "Currently Advertised",
                "visible_row_count": 2,
                "page_text_limited_before_row_search": "Currently Advertised",
                "table_count": 1,
                "row_count_by_selector": {"#tendeList tbody tr": 2},
                "first_rows_text_limited": ["159131 Water meters"],
                "visible_links_limited": [],
                "page_url_after_load": page_obj.url,
                "page_title": "eTenders Opportunities",
                "screenshot_path": "",
                "row_match_strategy": "tender_id",
                "row_match_text": "159131",
                "matched_row_text_limited": "159131 Water meters",
                "documents_section_found": False,
                "tender_documents_text_limited": "",
                "document_anchor_count": 0,
                "all_anchor_hrefs_limited": [],
                "all_anchor_texts_limited": [],
                "download_like_anchor_count": 0,
                "blob_like_string_count": 0,
                "visible_text_limited": "",
                "post_click_wait_ms": 0,
                "expanded_dom_detected": False,
                "tender_detail_detected": False,
                "upload_controls_detected": False,
                "download_controls_detected": False,
                "helper_error_type": "",
                "helper_error_message_limited": "",
                "expanded_dom": {"blob_links": []},
                "active_tab_name": "Currently Advertised",
                "actions": [],
            },
        ),
    )

    result = asyncio.run(
        etenders_dom_service._capture(
            {
                "tender_id": "159131",
                "opportunities_url": "https://www.etenders.gov.za/Home/opportunities?id=1&tab=search&page=2",
                "cdp_url": "http://host.docker.internal:9222",
                "wait_seconds": 0,
            }
        )
    )

    assert page.goto_calls == ["https://www.etenders.gov.za/Home/opportunities?id=1&tab=search&page=2"]
    assert result["helper_input_url"] == "https://www.etenders.gov.za/Home/opportunities?id=1&tab=search&page=2"
    assert result["page_url_after_load"] == "https://www.etenders.gov.za/Home/opportunities?id=1&tab=search&page=2"


def test_activate_best_candidate_row_table_timeout_preserves_snapshot_defaults(monkeypatch) -> None:
    page = _FakePlaywrightPage()

    async def fake_force_browse(*args, **kwargs):
        return []

    async def fake_active_name(*args, **kwargs):
        return "Currently Advertised"

    async def fake_wait_for_table(*args, **kwargs):
        raise TimeoutError("table timeout")

    monkeypatch.setattr(etenders_dom_service, "_force_browse_currently_advertised", fake_force_browse)
    monkeypatch.setattr(etenders_dom_service, "_active_opportunities_tab_name", fake_active_name)
    monkeypatch.setattr(etenders_dom_service, "_v50_9_4_wait_for_etenders_table_ready", fake_wait_for_table)

    result = asyncio.run(
        etenders_dom_service._activate_best_candidate_row(
            page,
            {"tender_id": "159131", "title": "Missing Tender"},
            {"best_candidate_row": {"score": 0}},
        )
    )

    assert result["row_found"] is False
    assert result["failure_reason"] == "row_not_found|page_state_no_table"
    assert result["table_container_found"] is False
    assert result["visible_row_count"] == 0
    assert result["first_rows_text_limited"] == []
    assert result["page_text_limited_before_row_search"] == ""
    assert result["helper_error_type"] == "TimeoutError"
    assert "table timeout" in result["helper_error_message_limited"]
    assert result["body_text_length"] == 0
    assert result["body_html_length"] == 0
    assert result["main_response_status"] == 0


def test_interactive_blob_candidates_are_attempted_before_tender_id_fallback(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    rendered_blob_links = [
        {
            "href": "/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf",
            "text": "Platinum Weekly Advert - 12 June 2026",
        }
    ]

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        if "Home/Download" in url and "blobName=" in url:
            return _FakeDownloadResponse(
                url=url,
                status_code=200,
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="Platinum Weekly Advert - 12 June 2026.pdf"',
                },
                chunks=[b"%PDF-1.4\n", b"binarypdf"],
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_clicked": True,
            "row_expanded": True,
            "documents_section_found": True,
            "blob_links": rendered_blob_links,
            "expanded_dom": {"body_html_preview": "<html><body>interactive</body></html>"},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Platinum Weekly Advert",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    assert result["buyer_pack_downloaded"] is True
    assert result["artifact_download_success_count"] > 0
    assert result["buyer_pack_path"]
    assert any(diag.get("diagnostic_type") == "etenders_interactive_dom_capture" for diag in result["diagnostics"])
    blob_diag = next(diag for diag in result["diagnostics"] if diag.get("route_pattern_name") == "etenders_blob_download_interactive")
    assert blob_diag["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert blob_diag["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert blob_diag["source_html_path"] == "interactive_rendered_dom_blob_link"
    assert blob_diag["source_context"] == "clicked_expanded_tender_row"
    assert blob_diag["artifact_exists"] is True
    assert blob_diag["binary_signature_detected"] is True
    assert not any(str(diag.get("route_pattern_name")) == "tender_id_fallback" for diag in result["diagnostics"] if diag.get("diagnostic_type") == "artifact_candidate")


def test_interactive_blob_candidates_are_extracted_from_nested_expanded_dom_links(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    nested_blob_links = [
        {
            "href": "/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf",
            "text": "Platinum Weekly Advert - 12 June 2026",
        }
    ]

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        if "Home/Download" in url and "blobName=" in url:
            return _FakeDownloadResponse(
                url=url,
                status_code=200,
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="Platinum Weekly Advert - 12 June 2026.pdf"',
                },
                chunks=[b"%PDF-1.4\n", b"binarypdf"],
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "browser_mode": "playwright_managed",
            "row_found": True,
            "row_expanded": True,
            "documents_section_found": True,
            "expanded_dom": {
                "body_html_preview": "<html><body>interactive</body></html>",
                "blob_links": nested_blob_links,
            },
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Platinum Weekly Advert",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    assert result["buyer_pack_downloaded"] is True
    assert result["artifact_download_success_count"] > 0
    assert result["buyer_pack_path"]
    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["interactive_blob_candidates_count"] == 1
    assert interactive_diag["failure_reason"] == ""
    blob_diag = next(diag for diag in result["diagnostics"] if diag.get("route_pattern_name") == "etenders_blob_download_interactive")
    assert blob_diag["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert blob_diag["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert blob_diag["artifact_exists"] is True


def test_interactive_capture_diagnostic_persists_no_links(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_clicked": True,
            "row_expanded": True,
            "documents_section_found": False,
            "blob_links": [],
            "visible_text_limited": "interactive detail without blob links and TENDER DOCUMENTS heading",
            "tender_documents_text_limited": "TENDER DOCUMENTS",
            "document_anchor_count": 2,
            "all_anchor_hrefs_limited": [
                "https://www.etenders.gov.za/Home/Announcements",
                "https://www.etenders.gov.za/Home/Details?id=159131",
            ],
            "all_anchor_texts_limited": ["Announcements", "Details"],
            "download_like_anchor_count": 1,
            "blob_like_string_count": 0,
            "post_click_wait_ms": 4123,
            "row_selector_used": "table tbody tr",
            "row_click_target_used": "td.details-control",
            "expanded_dom": {"body_html_preview": "<html><body>interactive detail without blob links</body></html>"},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Announcements",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["row_found"] is True
    assert interactive_diag["row_expanded"] is True
    assert interactive_diag["documents_section_found"] is False
    assert interactive_diag["document_anchor_count"] == 2
    assert interactive_diag["all_anchor_hrefs_limited"] == [
        "https://www.etenders.gov.za/Home/Announcements",
        "https://www.etenders.gov.za/Home/Details?id=159131",
    ]
    assert interactive_diag["visible_text_limited"].startswith("interactive detail without blob links")
    assert interactive_diag["post_click_wait_ms"] == 4123
    assert interactive_diag["row_selector_used"] == "table tbody tr"
    assert interactive_diag["row_click_target_used"] == "td.details-control"
    assert interactive_diag["download_like_anchor_count"] == 1
    assert interactive_diag["interactive_blob_candidates_count"] == 0
    assert interactive_diag["failure_reason"] == "documents_section_not_found"


def test_interactive_capture_persists_helper_exception_snapshot_defaults(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: (_ for _ in ()).throw(RuntimeError("helper boom")),
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Announcements",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["row_found"] is False
    assert interactive_diag["table_container_found"] is False
    assert interactive_diag["visible_row_count"] == 0
    assert interactive_diag["first_rows_text_limited"] == []
    assert interactive_diag["page_text_limited_before_row_search"] == ""
    assert interactive_diag["helper_error_type"] == "RuntimeError"
    assert "helper boom" in interactive_diag["helper_error_message_limited"]
    assert interactive_diag["failure_reason"] == "row_not_found|page_state_no_table"


def test_interactive_capture_persists_page_state_fields_and_page_state_no_table_failure_reason(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "error",
            "helper_error_type": "CDPResolutionError",
            "helper_error_message_limited": "cdp down",
            "row_found": False,
            "row_expanded": False,
            "table_container_found": False,
            "datatables_processing_seen": False,
            "datatables_processing_finished": False,
            "main_response_status": 204,
            "body_text_length": 40,
            "body_html_length": 68,
            "body_text_preview_limited": "Currently Advertised No visible rows yet",
            "visible_row_count": 0,
            "page_text_limited_before_row_search": "Currently Advertised No visible rows yet",
            "table_count": 0,
            "row_count_by_selector": {"#tendeList tbody tr": 0},
            "first_rows_text_limited": [],
            "visible_links_limited": [],
            "page_url_after_load": "https://www.etenders.gov.za/Home/opportunities",
            "page_title": "eTenders Opportunities",
            "screenshot_path": "/private/tmp/lmcp_etenders_diag/ETENDERS_159131__v50_9_4_pre_table.png",
            "row_match_strategy": "",
            "row_match_text": "",
            "matched_row_text_limited": "",
            "documents_section_found": False,
            "tender_documents_text_limited": "",
            "document_anchor_count": 0,
            "all_anchor_hrefs_limited": [],
            "all_anchor_texts_limited": [],
            "download_like_anchor_count": 0,
            "blob_like_string_count": 0,
            "visible_text_limited": "",
            "post_click_wait_ms": 0,
            "blob_links": [],
            "interactive_blob_candidates_count": 0,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Announcements",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["table_container_found"] is False
    assert interactive_diag["main_response_status"] == 204
    assert interactive_diag["body_text_length"] == 40
    assert interactive_diag["body_html_length"] == 68
    assert interactive_diag["body_text_preview_limited"].startswith("Currently Advertised")
    assert interactive_diag["page_url_after_load"] == "https://www.etenders.gov.za/Home/opportunities"
    assert interactive_diag["page_title"] == "eTenders Opportunities"
    assert interactive_diag["screenshot_path"].endswith("__v50_9_4_pre_table.png")
    assert interactive_diag["failure_reason"] == "row_not_found|page_state_no_table"


def test_interactive_capture_passes_detail_and_opportunities_urls_to_helper(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    opportunities_url = "https://www.etenders.gov.za/Home/opportunities?id=1&page=2"
    captured_payload: dict[str, object] = {}

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        raise AssertionError(f"unexpected url {url}")

    def fake_capture(payload):
        captured_payload.update(payload)
        return {"status": "error", "blob_links": []}

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(tender_harvester, "capture_dom_modal_autoclick", fake_capture)

    tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "detail_url": detail_url,
            "source_url": opportunities_url,
            "title": "Water meters",
            "buyer_name": "City of Cape Town",
            "reference_number": "Q159131",
        },
        {"name": "eTenders", "url": opportunities_url, "verify_ssl": True},
    )

    assert captured_payload["detail_page_url"] == detail_url
    assert captured_payload["opportunities_url"] == opportunities_url
    assert captured_payload["tender_title"] == "Water meters"
    assert captured_payload["buyer"] == "City of Cape Town"
    assert captured_payload["reference_number"] == "Q159131"


def test_interactive_capture_persists_routing_diagnostics(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"
    opportunities_url = "https://www.etenders.gov.za/Home/opportunities?id=1"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "helper_input_url": detail_url,
            "helper_resolved_url": opportunities_url,
            "browser_mode": "playwright_managed",
            "helper_used_detail_page": True,
            "helper_used_opportunities_page": True,
            "helper_preserved_query_params": True,
            "detail_page_url_available": True,
            "opportunities_url_available": True,
            "page_url_after_load": opportunities_url,
            "table_container_found": True,
            "visible_row_count": 3,
            "row_found": True,
            "blob_links": [],
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "detail_url": detail_url,
            "source_url": opportunities_url,
            "title": "Water meters",
        },
        {"name": "eTenders", "url": opportunities_url, "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["helper_input_url"] == detail_url
    assert interactive_diag["helper_resolved_url"] == opportunities_url
    assert interactive_diag["helper_used_detail_page"] is True
    assert interactive_diag["helper_used_opportunities_page"] is True
    assert interactive_diag["helper_preserved_query_params"] is True
    assert interactive_diag["detail_page_url_available"] is True
    assert interactive_diag["opportunities_url_available"] is True
    assert interactive_diag["browser_mode"] == "playwright_managed"
    assert interactive_diag["page_url_after_load"] == opportunities_url


def test_interactive_capture_persists_no_blob_links_when_documents_section_is_present(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_clicked": True,
            "row_expanded": True,
            "documents_section_found": True,
            "blob_links": [],
            "visible_text_limited": "Announcements Tender Documents and attachments listed below",
            "tender_documents_text_limited": "TENDER DOCUMENTS",
            "document_anchor_count": 3,
            "all_anchor_hrefs_limited": [
                "https://www.etenders.gov.za/Home/Announcements",
                "https://www.etenders.gov.za/Home/Attachments",
                "https://www.etenders.gov.za/Home/View?id=159131",
            ],
            "all_anchor_texts_limited": ["Announcements", "Attachments", "View"],
            "download_like_anchor_count": 1,
            "blob_like_string_count": 2,
            "post_click_wait_ms": 1987,
            "row_selector_used": "table tbody tr",
            "row_click_target_used": "row",
            "expanded_dom": {"body_html_preview": "<html><body>tender documents and attachments listed below</body></html>"},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Announcements",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["row_found"] is True
    assert interactive_diag["row_expanded"] is True
    assert interactive_diag["documents_section_found"] is True
    assert interactive_diag["interactive_blob_candidates_count"] == 0
    assert interactive_diag["failure_reason"] == "no_blob_links_found"
    assert interactive_diag["blob_like_string_count"] == 2
    assert interactive_diag["document_anchor_count"] == 3


def test_interactive_capture_marks_wrong_row_when_text_does_not_match(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(
        tender_harvester,
        "download_from_tenderdetails_json",
        lambda payload: {"status": "error", "attempts": [], "message": "no json blob rows"},
    )
    monkeypatch.setattr(
        tender_harvester,
        "capture_dom_modal_autoclick",
        lambda payload: {
            "status": "ok",
            "row_clicked": True,
            "row_expanded": True,
            "documents_section_found": False,
            "visible_text_limited": "completely unrelated row content",
            "tender_documents_text_limited": "",
            "document_anchor_count": 0,
            "all_anchor_hrefs_limited": [],
            "all_anchor_texts_limited": [],
            "download_like_anchor_count": 0,
            "blob_like_string_count": 0,
            "post_click_wait_ms": 2000,
            "row_selector_used": "table tbody tr",
            "row_click_target_used": "row",
            "blob_links": [],
            "expanded_dom": {"body_html_preview": "<html><body>completely unrelated row content</body></html>"},
            "safe_to_process": True,
        },
    )

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
            "title": "Announcements",
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    interactive_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "etenders_interactive_dom_capture")
    assert interactive_diag["failure_reason"] == "documents_section_not_found"
    assert interactive_diag["row_found"] is True
    assert interactive_diag["row_expanded"] is True
    assert interactive_diag["interactive_blob_candidates_count"] == 0


def test_etenders_detail_page_json_candidates_are_attempted_before_generic_fallbacks(monkeypatch) -> None:
    detail_url = "https://www.etenders.gov.za/Home/TenderDetails?id=159131"

    def fake_get(url, *args, **kwargs):
        if url == detail_url:
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><body>tender detail</body></html>",
            )
        raise AssertionError(f"unexpected url {url}")

    def fake_download_from_tenderdetails_json(payload):
        assert payload["tender_id"] == "159131"
        return {
            "status": "ok",
            "downloaded_at": "2026-06-14T10:00:00Z",
            "saved_path": "/tmp/ETENDERS_159131__TenderPack.pdf",
            "winning_url": "https://www.etenders.gov.za/files/TenderPack.pdf",
            "attempt_count": 1,
            "attempts": [
                {
                    "url": "https://www.etenders.gov.za/files/TenderPack.pdf",
                    "route_pattern_name": "explicit_json_url_or_path",
                    "source_json_path": "$.documents[0]",
                    "parameter_names_used": ["path"],
                    "tender_id": "159131",
                    "document_id": "doc-77",
                    "filename": "TenderPack.pdf",
                    "original_json_value": "/files/TenderPack.pdf",
                    "resolved_document_url": "https://www.etenders.gov.za/files/TenderPack.pdf",
                    "http_status": 200,
                    "content_type": "application/pdf",
                    "response_shape": "binary",
                    "failure_reason": "",
                    "binary_signature_detected": True,
                }
            ],
        }

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    monkeypatch.setattr(tender_harvester, "download_from_tenderdetails_json", fake_download_from_tenderdetails_json)

    result = tender_harvester._v64_resolve_buyer_pack_diagnostics_for_candidate(
        {
            "document_url": detail_url,
            "document_urls": [detail_url],
        },
        {"name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "verify_ssl": True},
    )

    assert result["buyer_pack_downloaded"] is True
    assert result["buyer_pack_path"] == "/tmp/ETENDERS_159131__TenderPack.pdf"
    assert result["failure_reason"] == ""
    assert any(diag.get("diagnostic_type") == "tenderdetails_json_route_experiment" for diag in result["diagnostics"])

    json_diag = next(diag for diag in result["diagnostics"] if diag.get("diagnostic_type") == "tenderdetails_json_route_experiment")
    assert json_diag["route_pattern_name"] == "explicit_json_url_or_path"
    assert json_diag["source_json_path"] == "$.documents[0]"
    assert json_diag["parameter_names_used"] == ["path"]
    assert json_diag["tender_id_used"] == "159131"
    assert json_diag["document_id_used"] == "doc-77"
    assert json_diag["resolved_document_url"] == "https://www.etenders.gov.za/files/TenderPack.pdf"
    assert json_diag["http_status"] == 200
    assert json_diag["content_type"] == "application/pdf"
    assert json_diag["response_shape"] == "binary"
    assert json_diag["failure_reason"] == ""
    assert not any("DownloadSpec" in str(diag.get("endpoint_url") or "") for diag in result["diagnostics"])


def test_generated_probes_preserve_discovered_parameter_names() -> None:
    html = """
    <html><body>
      <input type="hidden" name="supportDocumentID" value="abc-123" />
      <input type="hidden" name="documentId" value="98765" />
      <input type="hidden" name="tendersID" value="155559" />
    </body></html>
    """

    result = tender_harvester._v64_discover_etenders_document_endpoints(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
    )

    urls = {row["endpoint_url"]: row for row in result["endpoints"]}
    assert "https://www.etenders.gov.za/Home/DownloadSupportDocument?supportDocumentID=abc-123" in urls
    assert urls["https://www.etenders.gov.za/Home/DownloadSupportDocument?supportDocumentID=abc-123"]["parameter_names_used"] == ["supportDocumentID"]
    assert "https://www.etenders.gov.za/Home/DownloadSpec?documentId=98765&source=sharepoint" in urls
    assert urls["https://www.etenders.gov.za/Home/DownloadSpec?documentId=98765&source=sharepoint"]["parameter_names_used"] == ["documentId", "source"]
    assert "https://www.etenders.gov.za/Home/GetTenderDocuments?tendersID=155559" in urls
    assert urls["https://www.etenders.gov.za/Home/GetTenderDocuments?tendersID=155559"]["parameter_names_used"] == ["tendersID"]


def test_parses_json_endpoint_response_into_artifact_candidates() -> None:
    payload = {
        "documents": [
            {
                "downloadUrl": "/Home/DownloadFile?documentId=98",
                "fileName": "Pricing Schedule.pdf",
            },
            {
                "supportDocumentID": "da82ec59-5332-446c-ad2a-2367c2cd8df4",
                "fileName": "Tender Document.pdf",
            },
        ]
    }

    candidates = tender_harvester._v64_extract_etenders_endpoint_candidates_from_response(
        payload,
        endpoint_url="https://www.etenders.gov.za/Home/GetTenderDocuments?id=155559",
        detail_page_url="https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        tender_id="155559",
    )

    urls = {row["url"]: row for row in candidates}
    assert "https://www.etenders.gov.za/Home/DownloadFile?documentId=98" in urls
    assert urls["https://www.etenders.gov.za/Home/DownloadFile?documentId=98"]["candidate_should_attempt"] is True
    assert any("DownloadSupportDocument" in url for url in urls)


def test_parses_blobname_json_endpoint_response_into_artifact_candidates() -> None:
    payload = {
        "documents": [
            {
                "blobName": "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf",
                "downloadedFileName": "Platinum Weekly Advert - 12 June 2026.pdf",
            }
        ]
    }

    candidates = tender_harvester._v64_extract_etenders_endpoint_candidates_from_response(
        payload,
        endpoint_url="https://www.etenders.gov.za/Home/GetTenderDocuments?id=155559",
        detail_page_url="https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        tender_id="155559",
    )

    urls = {row["url"]: row for row in candidates}
    expected = "https://www.etenders.gov.za/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum+Weekly+Advert+-+12+June+2026.pdf"
    assert expected in urls
    assert urls[expected]["candidate_classification"] == "direct_file"
    assert urls[expected]["candidate_should_attempt"] is True


def test_scans_same_origin_script_content_for_endpoint_patterns(monkeypatch) -> None:
    def fake_get(url, *args, **kwargs):
        if url == "https://www.etenders.gov.za/scripts/tender.js":
            return _FakeHTTPResponse(
                url=url,
                status_code=200,
                headers={"content-type": "application/javascript"},
                text="fetch('/Home/GetDocuments?tenderId=155559'); var id='7788'; $.get('/Home/DownloadFile?documentId=7788');",
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    result = tender_harvester._v64_discover_etenders_document_endpoints(
        """
        <html><body>
          <script src="/scripts/tender.js"></script>
        </body></html>
        """,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        source={"verify_ssl": True},
        timeout=10,
    )

    urls = [row["endpoint_url"] for row in result["endpoints"]]
    assert "https://www.etenders.gov.za/Home/GetDocuments?tenderId=155559" in urls
    assert "https://www.etenders.gov.za/Home/DownloadFile?documentId=7788" in urls
    assert result["evidence"]["script_endpoint_candidates_count"] > 0


def test_probes_html_fragment_endpoint_and_extracts_document_links(monkeypatch) -> None:
    html = """
    <div class="docs">
      <a href="/downloads/specification.pdf">Specification</a>
    </div>
    """

    def fake_get(url, *args, **kwargs):
        return _FakeHTTPResponse(
            url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=html,
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    result = tender_harvester._v64_probe_etenders_document_endpoints(
        """
        <html><body>
          <script>var endpoint='/Home/GetTenderDocuments?id=155559';</script>
        </body></html>
        """,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        {"name": "eTenders", "verify_ssl": True},
        timeout=10,
    )

    assert result["etenders_endpoint_probe_count"] > 0
    assert result["etenders_document_candidates_from_endpoints"] > 0
    assert any(candidate["url"] == "https://www.etenders.gov.za/downloads/specification.pdf" for candidate in result["artifact_candidates"])
    evidence_diag = next(diag for diag in result["diagnostics"] if diag["diagnostic_type"] == "etenders_detail_page_discovery")
    probe_diag = next(diag for diag in result["diagnostics"] if diag["diagnostic_type"] == "etenders_endpoint_probe")
    assert "raw_html" not in evidence_diag
    assert "html" not in evidence_diag
    assert probe_diag["response_shape"] == "html_fragment"
    assert probe_diag["candidates_found_count"] == 1


def test_extracts_html_blobname_anchor_links() -> None:
    html = """
    <html><body>
      <a href="/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf&downloadedFileName=Platinum%20Weekly%20Advert%20-%2012%20June%202026.pdf">
        Platinum Weekly Advert - 12 June 2026
      </a>
    </body></html>
    """

    candidates = tender_harvester._v64_extract_artifact_candidate_links_from_html(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
        {"name": "eTenders", "source_name": "eTenders"},
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    candidate = next(row for row in candidates if row["route_pattern_name"] == "etenders_blob_download_html")
    assert candidate["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert candidate["downloadedFileName"] == "Platinum Weekly Advert - 12 June 2026.pdf"
    assert candidate["source_html_path"] == "Platinum Weekly Advert - 12 June 2026"
    assert candidate["source_context"] == "Platinum Weekly Advert - 12 June 2026"
    assert candidate["candidate_classification"] == "direct_file"
    assert candidate["candidate_should_attempt"] is True


def test_extracts_relative_html_blobname_links() -> None:
    html = """
    <html><body>
      <a href="Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf">Download</a>
    </body></html>
    """

    candidates = tender_harvester._v64_extract_artifact_candidate_links_from_html(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
        {"name": "eTenders", "source_name": "eTenders"},
        "https://www.etenders.gov.za/Home/TenderDetails?id=159131",
    )

    candidate = next(row for row in candidates if row["route_pattern_name"] == "etenders_blob_download_html")
    assert candidate["url"] == "https://www.etenders.gov.za/Home/Download/?blobName=6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert candidate["blobName"] == "6a3464f5-60a2-4420-8e3a-7a4a8ab767e1.pdf"
    assert candidate["parameter_names_used"] == ["blobName"]


def test_navigation_and_javascript_links_remain_rejected() -> None:
    source = {"name": "eTenders", "source_name": "eTenders", "url": "https://www.etenders.gov.za/Home/opportunities"}
    html = """
    <html><body>
      <a href="/Home">Home</a>
      <a href="/Home/Contact">Contact</a>
      <a href="javascript:void(0)">Open</a>
    </body></html>
    """

    candidates = tender_harvester._v64_extract_artifact_candidate_links_from_html(
        html,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        source,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
    )

    by_url = {row["url"]: row for row in candidates}
    assert by_url["https://www.etenders.gov.za/Home"]["candidate_should_attempt"] is False
    assert by_url["https://www.etenders.gov.za/Home/Contact"]["candidate_should_attempt"] is False
    assert by_url["javascript:void(0)"]["candidate_classification"] == "javascript_link"
    assert by_url["javascript:void(0)"]["candidate_should_attempt"] is False


def test_endpoint_probe_diagnostics_persist_when_no_candidates_found(monkeypatch) -> None:
    def fake_get(url, *args, **kwargs):
        return _FakeHTTPResponse(
            url=url,
            status_code=200,
            headers={"content-type": "application/json"},
            json_payload={"status": "ok", "message": "no documents"},
            text='{"status":"ok","message":"no documents"}',
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    result = tender_harvester._v64_probe_etenders_document_endpoints(
        """
        <html><body>
          <script>var endpoint='/Home/GetTenderDocuments?id=155559';</script>
        </body></html>
        """,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        {"name": "eTenders", "verify_ssl": True},
        timeout=10,
    )

    assert result["etenders_endpoint_probe_count"] > 0
    assert result["etenders_document_candidates_from_endpoints"] == 0
    assert result["etenders_endpoint_failure_count"] == result["etenders_endpoint_probe_count"]
    assert result["etenders_endpoint_failures_by_reason"]["no_document_candidates_found"] == result["etenders_endpoint_probe_count"]
    probe_diag = next(diag for diag in result["diagnostics"] if diag["diagnostic_type"] == "etenders_endpoint_probe")
    assert probe_diag["diagnostic_type"] == "etenders_endpoint_probe"
    assert probe_diag["failure_reason"] == "no_document_candidates_found"


def test_404_probe_diagnostics_include_source_and_parameter_names(monkeypatch) -> None:
    def fake_get(url, *args, **kwargs):
        return _FakeHTTPResponse(
            url=url,
            status_code=404,
            headers={"content-type": "text/html; charset=utf-8"},
            text="not found",
        )

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    result = tender_harvester._v64_probe_etenders_document_endpoints(
        """
        <html><body>
          <form action="/Home/GetTenderDocuments?tenderId=155559"></form>
          <button onclick="window.location='/Home/DownloadSupportDocument?supportDocumentID=abc-123'">Download</button>
        </body></html>
        """,
        "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        {"name": "eTenders", "verify_ssl": True},
        timeout=10,
    )

    evidence_diag = next(diag for diag in result["diagnostics"] if diag["diagnostic_type"] == "etenders_detail_page_discovery")
    assert evidence_diag["endpoint_probe_404_count"] > 0
    assert evidence_diag["endpoint_probe_non_404_count"] == 0
    form_probe = next(
        diag
        for diag in result["diagnostics"]
        if diag.get("diagnostic_type") == "etenders_endpoint_probe"
        and diag.get("source") == "discovered_form"
    )
    onclick_probe = next(
        diag
        for diag in result["diagnostics"]
        if diag.get("diagnostic_type") == "etenders_endpoint_probe"
        and diag.get("source") == "discovered_onclick"
    )
    assert form_probe["parameter_names_used"] == ["tenderId"]
    assert form_probe["tender_id_used"] == "155559"
    assert form_probe["reason"] == "http_404"
    assert onclick_probe["parameter_names_used"] == ["supportDocumentID"]
    assert onclick_probe["document_id_used"] == "abc-123"


def test_etenders_only_source_filter_selects_only_etenders(tmp_path: Path, monkeypatch) -> None:
    captured_names: list[str] = []
    sources = [
        {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "list_url": "https://www.etenders.gov.za/Home/opportunities", "type": "tenders_api", "source_group": "aggregator", "enabled": True},
        {"name": "Department of Higher Education and Training", "source_name": "Department of Higher Education and Training", "url": "https://www.dhet.gov.za/", "list_url": "https://www.dhet.gov.za/", "type": "portal", "source_group": "national_department", "enabled": True},
    ]
    monkeypatch.setattr(tender_harvester, "load_harvest_sources", lambda *_args, **_kwargs: sources)
    monkeypatch.setattr(tender_harvester, "_v57_load_memory_files", lambda: {"source": {"qualified_candidate_fingerprints": {}, "sources": {}}, "buyer": {"buyers": {}}, "category": {"categories": {}}, "document_pattern": {"patterns": {}}})

    def fake_scan(source, **kwargs):
        captured_names.append(source["name"])
        return [], {
            "source_name": source["name"],
            "source_url": source["url"],
            "scan_started_at": "2026-06-14T10:00:00Z",
            "scan_finished_at": "2026-06-14T10:00:01Z",
            "status": "no_candidates",
            "error_message": "",
            "pages_scanned": 1,
            "raw_candidates_count": 0,
            "document_links_detected": 0,
            "retry_count": 0,
            "retry_stage": "",
            "fallback_used": False,
        }

    monkeypatch.setattr(tender_harvester, "_scan_source_acquisition_runtime", fake_scan)
    result = tender_harvester.run_multi_portal_discovery(
        max_sources=5,
        max_per_source=1,
        dry_run=True,
        buyer_intelligence=False,
        opportunity_forecasting=False,
        forecast_watchlist=False,
        focus_productive_sources=False,
        repair_source_pack=False,
        source_names=["etenders"],
        source_health_file=tmp_path / "source_health.json",
    )

    assert captured_names == ["National Treasury eTenders"]
    assert result["sources_selected_this_cycle"] == 1


def test_etenders_timeout_settings_are_applied(monkeypatch) -> None:
    captured: dict[str, int] = {}
    monkeypatch.setattr(
        tender_harvester,
        "_preflight_source_acquisition",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "error_message": "",
            "dns_resolved": True,
            "dns_status": "ok",
            "http_status_code": 200,
            "http_status": 200,
            "http_reachable": True,
            "robots_blocked": False,
            "browser_required": True,
            "browser_available": True,
            "source_url": "https://www.etenders.gov.za/Home/opportunities",
            "source_name": "National Treasury eTenders",
        },
    )

    def fake_direct_etenders(source, max_items, headless, timeout_seconds=8, playwright_timeout_ms=18000, diagnostics=None, page_load_timeout_seconds=None, candidate_extraction_timeout_seconds=None, document_link_timeout_seconds=None):
        captured["page_load_timeout_seconds"] = int(page_load_timeout_seconds or 0)
        captured["candidate_extraction_timeout_seconds"] = int(candidate_extraction_timeout_seconds or 0)
        captured["document_link_timeout_seconds"] = int(document_link_timeout_seconds or 0)
        return []

    monkeypatch.setattr(tender_harvester, "_direct_etenders", fake_direct_etenders)
    tender_harvester._scan_source_acquisition_runtime(
        {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "source_group": "etenders", "type": "tenders_api"},
        max_per_source=2,
        headless=True,
        source_timeout_seconds=8,
        playwright_timeout_ms=18000,
        page_load_timeout_seconds=22,
        candidate_extraction_timeout_seconds=33,
        document_link_timeout_seconds=44,
    )

    assert captured == {
        "page_load_timeout_seconds": 22,
        "candidate_extraction_timeout_seconds": 33,
        "document_link_timeout_seconds": 44,
    }


def test_partial_candidates_persist_when_later_etenders_detail_pages_timeout(monkeypatch) -> None:
    source = {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "source_group": "etenders", "type": "tenders_api"}
    monkeypatch.setattr(
        tender_harvester,
        "_preflight_source_acquisition",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "error_message": "",
            "dns_resolved": True,
            "dns_status": "ok",
            "http_status_code": 200,
            "http_status": 200,
            "http_reachable": True,
            "robots_blocked": False,
            "browser_required": True,
            "browser_available": True,
            "source_url": source["url"],
            "source_name": source["name"],
        },
    )
    json_results = [
        {"title": "Tender A", "detail_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559", "document_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559"},
        {"title": "Tender B", "detail_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155560", "document_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155560"},
    ]

    monkeypatch.setattr(tender_harvester, "_fetch_etenders_paginated_opportunities", lambda *_args, **_kwargs: json_results)

    def fake_get(url, *args, **kwargs):
        if url in {tender_harvester.ETENDERS_BASE_URL, tender_harvester.ETENDERS_URL}:
            return _FakeHTTPResponse(url=url, status_code=200, headers={"content-type": "text/html"}, text="<html>opportunities</html>")
        if "TenderDetails" in url:
            raise requests.Timeout("detail timeout")
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    harvested, diag = tender_harvester._scan_source_acquisition_runtime(
        source,
        max_per_source=2,
        headless=True,
        source_timeout_seconds=8,
        playwright_timeout_ms=18000,
        page_load_timeout_seconds=5,
        candidate_extraction_timeout_seconds=5,
        document_link_timeout_seconds=1,
    )

    assert len(harvested) == 2
    assert diag["status"] == "success"
    assert diag["partial_progress_persisted"] is True
    assert diag["etenders_candidates_extracted_count"] == 2
    assert diag["etenders_detail_pages_attempted_count"] == 2
    assert diag["etenders_detail_pages_timeout_count"] == 2
    assert diag["etenders_tenderdetails_links_found_count"] == 2


def test_etenders_staged_diagnostics_are_present(monkeypatch) -> None:
    source = {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "source_group": "etenders", "type": "tenders_api"}
    monkeypatch.setattr(
        tender_harvester,
        "_preflight_source_acquisition",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "error_message": "",
            "dns_resolved": True,
            "dns_status": "ok",
            "http_status_code": 200,
            "http_status": 200,
            "http_reachable": True,
            "robots_blocked": False,
            "browser_required": True,
            "browser_available": True,
            "source_url": source["url"],
            "source_name": source["name"],
        },
    )
    json_results = [
        {"title": "Tender A", "detail_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559", "document_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559"},
    ]
    monkeypatch.setattr(tender_harvester, "_fetch_etenders_paginated_opportunities", lambda *_args, **_kwargs: json_results)

    def fake_get(url, *args, **kwargs):
        return _FakeHTTPResponse(url=url, status_code=200, headers={"content-type": "text/html"}, text="<html>ok</html>")

    monkeypatch.setattr(tender_harvester.requests, "get", fake_get)
    _, diag = tender_harvester._scan_source_acquisition_runtime(
        source,
        max_per_source=1,
        headless=True,
        source_timeout_seconds=8,
        playwright_timeout_ms=18000,
    )

    for key in (
        "etenders_home_reached",
        "etenders_opportunities_page_reached",
        "etenders_candidates_table_detected",
        "etenders_candidates_extracted_count",
        "etenders_detail_pages_attempted_count",
        "etenders_detail_pages_success_count",
        "etenders_detail_pages_timeout_count",
        "etenders_tenderdetails_links_found_count",
    ):
        assert key in diag
    assert diag["etenders_home_reached"] is True
    assert diag["etenders_opportunities_page_reached"] is True


def test_etenders_bounded_retry_only_retries_timeout_and_429(monkeypatch) -> None:
    source = {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "source_group": "etenders", "type": "tenders_api"}
    monkeypatch.setattr(
        tender_harvester,
        "_preflight_source_acquisition",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "error_message": "",
            "dns_resolved": True,
            "dns_status": "ok",
            "http_status_code": 200,
            "http_status": 200,
            "http_reachable": True,
            "robots_blocked": False,
            "browser_required": True,
            "browser_available": True,
            "source_url": source["url"],
            "source_name": source["name"],
        },
    )
    timeout_calls = {"count": 0}

    def fake_fetch_timeout(*_args, **_kwargs):
        timeout_calls["count"] += 1
        if timeout_calls["count"] == 1:
            raise requests.Timeout("timed out")
        return [{"title": "Tender A", "detail_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559", "document_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559"}]

    monkeypatch.setattr(tender_harvester, "_fetch_etenders_paginated_opportunities", fake_fetch_timeout)
    monkeypatch.setattr(tender_harvester.requests, "get", lambda url, *args, **kwargs: _FakeHTTPResponse(url=url, status_code=200, headers={"content-type": "text/html"}, text="<html>ok</html>"))
    _, timeout_diag = tender_harvester._scan_source_acquisition_runtime(
        source,
        max_per_source=1,
        headless=True,
        source_timeout_seconds=8,
        playwright_timeout_ms=18000,
    )
    assert timeout_calls["count"] == 2
    assert timeout_diag["retry_count"] == 1
    assert timeout_diag["retry_stage"] == "candidate_extraction_timeout"

    forbidden_calls = {"count": 0}

    def fake_fetch_403(*_args, **_kwargs):
        forbidden_calls["count"] += 1
        raise requests.HTTPError("HTTP 403")

    monkeypatch.setattr(tender_harvester, "_fetch_etenders_paginated_opportunities", fake_fetch_403)
    monkeypatch.setattr(tender_harvester, "run_generic_scraper", lambda *_args, **_kwargs: [])
    _, forbidden_diag = tender_harvester._scan_source_acquisition_runtime(
        source,
        max_per_source=1,
        headless=True,
        source_timeout_seconds=8,
        playwright_timeout_ms=18000,
    )
    assert forbidden_calls["count"] == 1
    assert forbidden_diag["retry_count"] == 0


def test_etenders_endpoint_probing_is_attempted_when_tenderdetails_pages_are_reached(tmp_path: Path, monkeypatch) -> None:
    source = {"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "list_url": "https://www.etenders.gov.za/Home/opportunities", "type": "tenders_api", "source_group": "etenders", "enabled": True}
    monkeypatch.setattr(tender_harvester, "load_harvest_sources", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(tender_harvester, "_v57_load_memory_files", lambda: {"source": {"qualified_candidate_fingerprints": {}, "sources": {}}, "buyer": {"buyers": {}}, "category": {"categories": {}}, "document_pattern": {"patterns": {}}})

    def fake_scan(source, **kwargs):
        harvested = [{
            "title": "Tender A",
            "description": "Tender A",
            "source_name": source["name"],
            "source_url": source["url"],
            "document_urls": ["https://www.etenders.gov.za/Home/TenderDetails?id=155559"],
            "detail_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
            "document_url": "https://www.etenders.gov.za/Home/TenderDetails?id=155559",
        }]
        return harvested, {
            "source_name": source["name"],
            "source_url": source["url"],
            "scan_started_at": "2026-06-14T10:00:00Z",
            "scan_finished_at": "2026-06-14T10:00:01Z",
            "status": "success",
            "error_message": "",
            "pages_scanned": 1,
            "raw_candidates_count": 1,
            "document_links_detected": 1,
            "retry_count": 0,
            "retry_stage": "",
            "fallback_used": False,
            "etenders_home_reached": True,
            "etenders_opportunities_page_reached": True,
            "etenders_candidates_table_detected": True,
            "etenders_candidates_extracted_count": 1,
            "etenders_detail_pages_attempted_count": 1,
            "etenders_detail_pages_success_count": 1,
            "etenders_detail_pages_timeout_count": 0,
            "etenders_tenderdetails_links_found_count": 1,
        }

    monkeypatch.setattr(tender_harvester, "_scan_source_acquisition_runtime", fake_scan)
    monkeypatch.setattr(
        tender_harvester,
        "_v64_resolve_buyer_pack_diagnostics_for_candidate",
        lambda *_args, **_kwargs: {
            "attempted": True,
            "downloaded": False,
            "buyer_pack_downloaded": False,
            "buyer_pack_path": "",
            "buyer_pack_download_timestamp": "",
            "failure_reason": "artifact_download_failed",
            "diagnostics": [],
            "downloads": [],
            "index_pages_fetched_count": 1,
            "index_pages_with_artifacts_count": 1,
            "artifact_candidates_found_count": 1,
            "artifact_download_attempts_count": 1,
            "artifact_download_success_count": 0,
            "artifact_candidates_total": 1,
            "artifact_candidates_attempted": 1,
            "artifact_candidates_rejected_before_fetch": 0,
            "artifact_candidates_by_classification": {"likely_download_endpoint": 1},
            "artifact_rejections_by_reason": {},
            "artifact_resolved_to_html_count": 0,
            "artifact_binary_signature_success_count": 0,
            "etenders_endpoint_probe_count": 1,
            "etenders_endpoint_success_count": 1,
            "etenders_endpoint_failure_count": 0,
            "etenders_document_candidates_from_endpoints": 1,
            "etenders_endpoint_failures_by_reason": {},
            "index_page_no_artifacts_count": 0,
            "artifact_download_failed_count": 1,
            "fallback_used": False,
        },
    )
    result = tender_harvester.run_multi_portal_discovery(
        max_sources=1,
        max_per_source=1,
        dry_run=True,
        buyer_intelligence=False,
        opportunity_forecasting=False,
        forecast_watchlist=False,
        focus_productive_sources=False,
        repair_source_pack=False,
        source_names=["etenders"],
        source_health_file=tmp_path / "source_health.json",
    )

    assert result["etenders_detail_pages_attempted_count"] == 1
    assert result["etenders_tenderdetails_links_found_count"] == 1
    assert result["etenders_endpoint_probe_count"] == 1
