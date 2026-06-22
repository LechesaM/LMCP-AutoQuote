from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from scripts import run_etenders_connectivity_diagnostics as module
from scripts.run_etenders_connectivity_diagnostics import (
    _classify_root_cause,
    _diagnose_page_connectivity,
    run_etenders_connectivity_diagnostics,
)


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        url: str = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities",
        reason: str = "OK",
        headers: Dict[str, Any] | None = None,
        text: str = "{}",
        history: list["_FakeResponse"] | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.reason = reason
        self.headers = headers or {"content-type": "application/json"}
        self.text = text
        self.content = text.encode("utf-8")
        self.history = history or []

    def json(self) -> Dict[str, Any]:
        return {"data": [1, 2, 3]}


def test_diagnose_page_connectivity_records_stage_fields(monkeypatch) -> None:
    monkeypatch.setattr(module, "_probe_dns", lambda host, port, timeout: {"status": "failed", "resolved": False, "addresses": [], "error_class": "gaierror", "error_message": "nodename nor servname provided, or not known", "timeout_seconds": timeout})
    monkeypatch.setattr(module, "_probe_tcp", lambda host, port, timeout, dns_resolved: {"status": "skipped", "reachable": False, "error_class": "dns_failed", "error_message": "dns_failed", "timeout_seconds": timeout})
    monkeypatch.setattr(module, "_probe_tls", lambda host, port, timeout, scheme, tcp_reachable: {"status": "skipped", "tls_supported": False, "protocol": "", "cipher": [], "error_class": "tcp_unreachable", "error_message": "tcp_unreachable", "timeout_seconds": timeout})
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(
            status_code=404,
            url="https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0",
            reason="Not Found",
            headers={"content-type": "text/html", "location": ""},
            text="<html>captcha</html>",
            history=[_FakeResponse(status_code=302, url="https://www.etenders.gov.za/Home/opportunities", reason="Found")],
        ),
    )

    result = _diagnose_page_connectivity("https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?start=0", timeout=5)

    assert result["host"] == "www.etenders.gov.za"
    assert result["port"] == 443
    assert result["dns_resolution_result"]["status"] == "failed"
    assert result["timeout_result"]["status"] == "ok"
    assert result["redirect_result"]["hop_count"] == 1
    assert result["tls_result"]["status"] == "skipped"
    assert result["http_result"]["http_status"] == 404
    assert result["http_result"]["response_length"] == 0 or isinstance(result["http_result"]["response_length"], int)
    assert result["connectivity"]["root_cause"] == "dns"


def test_root_cause_classification_covers_requested_categories() -> None:
    assert _classify_root_cause({"status": "failed"}, {"status": "skipped"}, {"status": "skipped"}, {"http_status": 0, "exception_class": "", "exception_message": ""})[0] == "dns"
    assert _classify_root_cause({"status": "ok"}, {"status": "timeout", "error_message": "timed out"}, {"status": "skipped"}, {"http_status": 0, "exception_class": "TimeoutError", "exception_message": "timed out"})[0] == "network_connectivity"
    assert _classify_root_cause({"status": "ok"}, {"status": "ok"}, {"status": "failed"}, {"http_status": 0, "exception_class": "", "exception_message": ""})[0] == "tls_ssl"
    assert _classify_root_cause({"status": "ok"}, {"status": "ok"}, {"status": "skipped"}, {"http_status": 0, "exception_class": "ProxyError", "exception_message": "proxy tunnel failed"})[0] == "firewall_proxy"
    assert _classify_root_cause({"status": "ok"}, {"status": "ok"}, {"status": "skipped"}, {"http_status": 403, "exception_class": "", "exception_message": ""})[0] == "anti_bot"
    assert _classify_root_cause({"status": "ok"}, {"status": "ok"}, {"status": "skipped"}, {"http_status": 404, "exception_class": "", "exception_message": ""})[0] == "incorrect_url_pattern"


def test_runner_writes_outputs_and_preserves_registry(tmp_path: Path, monkeypatch) -> None:
    registry_path = Path("app/data/harvest_sources.json")
    before = registry_path.stat().st_mtime_ns

    calls: list[str] = []

    def fake_probe(page_url: str, *, timeout: int, browser_mode: bool = False, browser_screenshot_dir=None) -> Dict[str, Any]:
        calls.append(page_url)
        index = len(calls) - 1
        root_cause = "dns" if index == 0 else "incorrect_url_pattern"
        return {
            "page_url": page_url,
            "target_url": page_url,
            "host": "www.etenders.gov.za",
            "port": 443,
            "scheme": "https",
            "fetch_mode": "browser" if browser_mode else "requests",
            "status": "failed" if index == 0 else "ok",
            "http_status": 404 if index == 0 else 200,
            "final_url": page_url,
            "redirect_chain": [{"url": page_url, "status_code": 200, "reason": "OK"}],
            "response_length": 128 if index == 0 else 256,
            "response_hash": "abc123",
            "response_text_preview": "<html></html>",
            "response_json_present": False,
            "response_rows": 0,
            "content_type": "text/html",
            "exception_class": "ConnectionError" if index == 0 else "",
            "exception_message": "could not connect" if index == 0 else "",
            "screenshot_path": str(tmp_path / f"shot_{index}.png") if browser_mode else "",
            "elapsed_seconds": 0.123,
            "raw_fetch_result": {
                "status": "failed" if index == 0 else "ok",
                "http_status": 404 if index == 0 else 200,
                "final_url": page_url,
                "redirect_chain": [{"url": page_url, "status_code": 200, "reason": "OK"}],
                "response_length": 128 if index == 0 else 256,
                "response_hash": "abc123",
                "response_text_preview": "<html></html>",
                "response_json_present": False,
                "response_rows": 0,
                "content_type": "text/html",
                "exception_class": "ConnectionError" if index == 0 else "",
                "exception_message": "could not connect" if index == 0 else "",
                "response_headers": {"content-type": "text/html"},
                "anti_bot_signals": False,
            },
            "dns_resolution_result": {"status": "failed" if index == 0 else "ok", "resolved": index != 0, "addresses": [], "error_class": "gaierror" if index == 0 else "", "error_message": "dns failed" if index == 0 else ""},
            "connection_result": {"status": "skipped" if index == 0 else "ok", "reachable": index != 0, "error_class": "dns_failed" if index == 0 else "", "error_message": "dns_failed" if index == 0 else ""},
            "timeout_result": {"status": "ok", "stage": "", "error_class": "", "error_message": ""},
            "redirect_result": {"status": "none", "hop_count": 0, "chain": [{"url": page_url, "status_code": 200, "reason": "OK"}], "final_url": page_url},
            "tls_result": {"status": "skipped", "tls_supported": False, "protocol": "", "cipher": [], "error_class": "", "error_message": "", "timeout_seconds": timeout},
            "http_result": {"status": "failed" if index == 0 else "ok", "http_status": 404 if index == 0 else 200, "final_url": page_url, "redirect_chain": [{"url": page_url, "status_code": 200, "reason": "OK"}], "response_length": 128 if index == 0 else 256, "response_hash": "abc123", "response_text_preview": "<html></html>", "response_json_present": False, "response_rows": 0, "content_type": "text/html", "exception_class": "ConnectionError" if index == 0 else "", "exception_message": "could not connect" if index == 0 else "", "anti_bot_signals": False},
            "connectivity": {"root_cause": root_cause, "root_cause_detail": "detail"},
        }

    result = run_etenders_connectivity_diagnostics(
        pages=2,
        limit=10,
        timeout=5,
        output_dir=tmp_path / "harvest_recovery",
        browser_mode=True,
        probe_page_fn=fake_probe,
    )

    assert len(calls) == 2
    diagnostics = result["diagnostics"]
    assert diagnostics["metrics"]["pages_requested"] == 2
    assert diagnostics["metrics"]["pages_failed"] == 1
    assert diagnostics["metrics"]["pages_fetched"] == 1
    assert diagnostics["metrics"]["dns_failed_pages"] == 1
    assert diagnostics["metrics"]["incorrect_url_pages"] == 1
    assert diagnostics["metrics"]["browser_mode_pages"] == 2
    assert diagnostics["metrics"]["screenshot_count"] == 2
    assert (tmp_path / "harvest_recovery" / "etenders_connectivity_diagnostics.json").exists()
    assert (tmp_path / "harvest_recovery" / "etenders_connectivity_diagnostics.md").exists()
    payload = json.loads((tmp_path / "harvest_recovery" / "etenders_connectivity_diagnostics.json").read_text(encoding="utf-8"))
    assert payload["guardrails"]["portal_submission_disabled"] is True
    assert payload["guardrails"]["human_approval_required"] is True
    assert payload["guardrails"]["autonomous_submission_enabled"] is False
    assert payload["page_results"][0]["host"] == "www.etenders.gov.za"
    assert payload["page_results"][0]["dns_resolution_result"]["status"] == "failed"
    assert payload["page_results"][0]["http_result"]["http_status"] == 404
    assert payload["page_results"][1]["connectivity"]["root_cause"] == "incorrect_url_pattern"
    assert registry_path.stat().st_mtime_ns == before
