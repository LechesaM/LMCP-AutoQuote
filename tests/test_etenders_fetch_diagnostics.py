from __future__ import annotations

import json
from pathlib import Path

from scripts import run_etenders_fetch_diagnostics as module
from scripts.run_etenders_fetch_diagnostics import run_etenders_fetch_diagnostics


def test_multiple_pages_store_raw_fetch_results(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch(page_url: str, *, timeout: int, browser_mode: bool = False, browser_screenshot_dir=None) -> dict:
        calls.append(page_url)
        index = len(calls) - 1
        if index == 0:
            return {
                "page_url": page_url,
                "fetch_mode": "requests",
                "status": "ok",
                "http_status": 200,
                "final_url": page_url,
                "redirect_chain": [{"url": page_url, "status_code": 200, "reason": "OK"}],
                "response_length": 1200,
                "response_hash": "abc",
                "response_text_preview": '{"data":[1,2]}',
                "response_json_present": True,
                "response_rows": 2,
                "content_type": "application/json",
                "exception_class": "",
                "exception_message": "",
                "screenshot_path": "",
                "elapsed_seconds": 0.1,
            }
        return {
            "page_url": page_url,
            "fetch_mode": "requests",
            "status": "failed",
            "http_status": 0,
            "final_url": page_url,
            "redirect_chain": [],
            "response_length": 0,
            "response_hash": "",
            "response_text_preview": "",
            "response_json_present": False,
            "response_rows": 0,
            "content_type": "",
            "exception_class": "ConnectionError",
            "exception_message": "Could not resolve host",
            "screenshot_path": "",
            "elapsed_seconds": 0.1,
        }

    monkeypatch.setattr(module, "_fetch_page_diagnostics", fake_fetch)
    monkeypatch.setattr(module, "_load_registry_sources", lambda: ([{"name": "National Treasury eTenders", "source_name": "National Treasury eTenders", "url": "https://www.etenders.gov.za/Home/opportunities", "list_url": "https://www.etenders.gov.za/Home/opportunities", "enabled": True}], "/fake/registry.json", ["/fake/registry.json"]))

    result = run_etenders_fetch_diagnostics(pages=2, limit=10, timeout=5, output_dir=tmp_path / "harvest_recovery", fetch_page_fn=fake_fetch)

    diagnostics = result["diagnostics"]
    assert len(calls) == 2
    assert diagnostics["metrics"]["pages_requested"] == 2
    assert diagnostics["metrics"]["pages_fetched"] == 1
    assert diagnostics["metrics"]["pages_failed"] == 1
    assert diagnostics["metrics"]["rows_seen"] == 2
    assert diagnostics["guardrails"]["portal_submission_disabled"] is True
    assert diagnostics["guardrails"]["human_approval_required"] is True
    assert diagnostics["guardrails"]["autonomous_submission_enabled"] is False
    assert (tmp_path / "harvest_recovery" / "fetch_diagnostics.json").exists()
    assert (tmp_path / "harvest_recovery" / "fetch_diagnostics.md").exists()

    payload = json.loads((tmp_path / "harvest_recovery" / "fetch_diagnostics.json").read_text(encoding="utf-8"))
    assert payload["page_results"][0]["response_length"] == 1200
    assert payload["page_results"][1]["exception_class"] == "ConnectionError"


def test_fetch_diagnostics_registry_is_not_mutated(tmp_path: Path, monkeypatch) -> None:
    registry_path = Path("app/data/harvest_sources.json")
    before = registry_path.stat().st_mtime_ns

    def fake_fetch(page_url: str, *, timeout: int, browser_mode: bool = False, browser_screenshot_dir=None) -> dict:
        return {
            "page_url": page_url,
            "fetch_mode": "requests",
            "status": "ok",
            "http_status": 200,
            "final_url": page_url,
            "redirect_chain": [{"url": page_url, "status_code": 200, "reason": "OK"}],
            "response_length": 10,
            "response_hash": "abc",
            "response_text_preview": "{}",
            "response_json_present": True,
            "response_rows": 0,
            "content_type": "application/json",
            "exception_class": "",
            "exception_message": "",
            "screenshot_path": "",
            "elapsed_seconds": 0.1,
        }

    monkeypatch.setattr(module, "_fetch_page_diagnostics", fake_fetch)
    run_etenders_fetch_diagnostics(pages=1, limit=5, timeout=5, output_dir=tmp_path / "harvest_recovery", fetch_page_fn=fake_fetch)

    assert registry_path.stat().st_mtime_ns == before

