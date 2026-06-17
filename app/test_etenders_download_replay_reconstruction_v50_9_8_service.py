from __future__ import annotations

from pathlib import Path

import pytest

from app.services.etenders_download_replay_reconstruction_v50_9_8_service import (
    _resp_summary,
    build_replay_candidates,
    replay_one,
)


SUPPORT_DOCUMENT_ID = "1e2e2c94-22f2-4bff-acd9-85fb2ea7faf7"


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        headers: dict[str, str] | None = None,
        content: bytes = b"",
        text: str = "",
        history: list["FakeResponse"] | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}
        self.content = content
        self.text = text
        self.history = history or []
        self.ok = 200 <= status_code < 400

    def json(self):
        raise ValueError("no json")


def test_build_replay_candidates_prioritizes_exact_support_document_routes():
    candidates = build_replay_candidates("158964", SUPPORT_DOCUMENT_ID, [], {})
    urls = [candidate["url"] for candidate in candidates[:12]]

    assert urls[:4] == [
        f"https://www.etenders.gov.za/Home/DownloadSupportDocument?supportDocumentID={SUPPORT_DOCUMENT_ID}",
        f"https://www.etenders.gov.za/Home/DownloadSupportDocument?documentId={SUPPORT_DOCUMENT_ID}",
        f"https://www.etenders.gov.za/home/DownloadSupportDocument?supportDocumentID={SUPPORT_DOCUMENT_ID}",
        f"https://www.etenders.gov.za/home/DownloadSupportDocument?documentId={SUPPORT_DOCUMENT_ID}",
    ]
    assert [
        candidate["url"]
        for candidate in candidates
        if candidate["method"] == "GET" and "DownloadSpec" in candidate["url"]
    ][:4] == [
        f"https://www.etenders.gov.za/Home/DownloadSpec?supportDocumentID={SUPPORT_DOCUMENT_ID}",
        f"https://www.etenders.gov.za/Home/DownloadSpec?documentId={SUPPORT_DOCUMENT_ID}",
        f"https://www.etenders.gov.za/home/DownloadSpec?supportDocumentID={SUPPORT_DOCUMENT_ID}",
        f"https://www.etenders.gov.za/home/DownloadSpec?documentId={SUPPORT_DOCUMENT_ID}",
    ]


def test_resp_summary_records_first_bytes_and_redirect_location():
    redirect = FakeResponse(
        status_code=302,
        url="https://www.etenders.gov.za/Home/DownloadSupportDocument?supportDocumentID=1",
        headers={"location": "https://www.etenders.gov.za/Home/DownloadSpec?documentId=99"},
    )
    resp = FakeResponse(
        status_code=200,
        url="https://www.etenders.gov.za/Home/DownloadSpec?documentId=99",
        headers={
            "content-type": "application/pdf",
            "content-disposition": 'attachment; filename="buyer-pack.pdf"',
            "content-length": "12",
        },
        content=b"%PDF-1.7\nabc",
        text="",
        history=[redirect],
    )

    summary = _resp_summary(resp, "https://www.etenders.gov.za/Home/DownloadSpec?documentId=99", "GET")

    assert summary["status_code"] == 200
    assert summary["content_type"] == "application/pdf"
    assert summary["content_disposition"] == 'attachment; filename="buyer-pack.pdf"'
    assert summary["content_length"] == "12"
    assert summary["first_bytes_hex"].startswith("25504446")
    assert summary["redirect_location"] == "https://www.etenders.gov.za/Home/DownloadSpec?documentId=99"


def test_replay_one_support_document_id_saves_buyer_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    first_url = f"https://www.etenders.gov.za/Home/DownloadSupportDocument?supportDocumentID={SUPPORT_DOCUMENT_ID}"
    second_url = f"https://www.etenders.gov.za/Home/DownloadSupportDocument?documentId={SUPPORT_DOCUMENT_ID}"

    calls: list[str] = []

    def fake_get(url, headers=None, timeout=None, allow_redirects=None):
        calls.append(url)
        if url == first_url:
            return FakeResponse(
                status_code=404,
                url=url,
                headers={"content-type": "text/html"},
                content=b"<html>missing</html>",
                text="<html>missing</html>",
            )
        if url == second_url:
            return FakeResponse(
                status_code=200,
                url=url,
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="buyer-pack.pdf"',
                    "content-length": "12",
                },
                content=b"%PDF-1.7\nabc",
                text="",
            )
        return FakeResponse(
            status_code=404,
            url=url,
            headers={"content-type": "text/html"},
            content=b"<html>unexpected</html>",
            text="<html>unexpected</html>",
        )

    monkeypatch.setattr(
        "app.services.etenders_download_replay_reconstruction_v50_9_8_service.requests.get",
        fake_get,
    )

    result = replay_one(
        {
            "tender_id": "158964",
            "supportDocumentID": SUPPORT_DOCUMENT_ID,
            "output_dir": str(tmp_path),
        }
    )

    assert calls[:2] == [first_url, second_url]
    assert result["status"] == "ok"
    assert result["safe_to_process"] is True
    assert result["buyer_pack_path"]
    assert Path(result["buyer_pack_path"]).exists()
    assert Path(result["buyer_pack_path"]).read_bytes().startswith(b"%PDF")
