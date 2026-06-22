from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_http_failures import analyze_http_failures
from scripts.analyze_http_failures import _classify_http_bucket  # noqa: SLF001


def _source(name: str, url: str) -> dict:
    return {
        "source_name": name,
        "category": "soe",
        "url": url,
        "action": "investigate_http",
        "failure_type": "http_error",
        "status": "http_failed",
        "reachable": False,
        "rfqs_found": 0,
        "qualified_rfqs": 0,
        "submission_candidates": 0,
        "investigation_marker": "",
    }


def test_http_bucket_classifier_maps_expected_codes() -> None:
    assert _classify_http_bucket(301, "") == "HTTP 301"
    assert _classify_http_bucket(302, "") == "HTTP 302"
    assert _classify_http_bucket(401, "") == "HTTP 401"
    assert _classify_http_bucket(403, "") == "HTTP 403"
    assert _classify_http_bucket(404, "") == "HTTP 404"
    assert _classify_http_bucket(405, "") == "HTTP 405"
    assert _classify_http_bucket(500, "") == "HTTP 500"
    assert _classify_http_bucket(None, "SSL certificate problem") == "SSL Error"
    assert _classify_http_bucket(None, "Maximum (number of) redirects followed") == "Redirect Loop"
    assert _classify_http_bucket(None, "") == "Unknown HTTP"


def test_http_failure_analysis_writes_outputs_and_counts(tmp_path: Path) -> None:
    input_path = tmp_path / "source_action_plan.json"
    output_dir = tmp_path / "harvest_effectiveness"
    payload = {
        "status": "ok",
        "generated_at": "2026-06-19T00:00:00+00:00",
        "counts": {"investigate_http": 8},
        "sources": [
            _source("Code 301", "https://example.com/301"),
            _source("Code 302", "https://example.com/302"),
            _source("Code 401", "https://example.com/401"),
            _source("Code 403", "https://example.com/403"),
            _source("Code 404", "https://example.com/404"),
            _source("Code 405", "https://example.com/405"),
            _source("Code 500", "https://example.com/500"),
            _source("SSL", "https://example.com/ssl"),
        ],
    }
    input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    probe_map = {
        "https://example.com/301": {"http_status_code": 301, "error_message": "", "reachable": True},
        "https://example.com/302": {"http_status_code": 302, "error_message": "", "reachable": True},
        "https://example.com/401": {"http_status_code": 401, "error_message": "", "reachable": True},
        "https://example.com/403": {"http_status_code": 403, "error_message": "", "reachable": True},
        "https://example.com/404": {"http_status_code": 404, "error_message": "", "reachable": True},
        "https://example.com/405": {"http_status_code": 405, "error_message": "", "reachable": True},
        "https://example.com/500": {"http_status_code": 500, "error_message": "", "reachable": True},
        "https://example.com/ssl": {"http_status_code": None, "error_message": "SSL certificate problem", "reachable": False},
    }

    def probe_fn(url: str, timeout: int) -> dict:
        return probe_map[url]

    result = analyze_http_failures(input_path=input_path, output_dir=output_dir, timeout=1, probe_fn=probe_fn)

    assert (output_dir / "http_failure_summary.json").exists()
    assert (output_dir / "http_failure_summary.md").exists()
    assert Path(result["docs_path"]).exists()

    summary = json.loads((output_dir / "http_failure_summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["HTTP 301"] == 1
    assert summary["counts"]["HTTP 302"] == 1
    assert summary["counts"]["HTTP 401"] == 1
    assert summary["counts"]["HTTP 403"] == 1
    assert summary["counts"]["HTTP 404"] == 1
    assert summary["counts"]["HTTP 405"] == 1
    assert summary["counts"]["HTTP 500"] == 1
    assert summary["counts"]["SSL Error"] == 1
    assert summary["counts"]["Redirect Loop"] == 0
    assert summary["counts"]["Unknown HTTP"] == 0
    assert "No source was disabled by this analysis." in (output_dir / "http_failure_summary.md").read_text(encoding="utf-8")


def test_http_failure_analysis_registry_is_not_mutated(tmp_path: Path) -> None:
    input_path = tmp_path / "source_action_plan.json"
    output_dir = tmp_path / "harvest_effectiveness"
    input_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-19T00:00:00+00:00",
                "counts": {"investigate_http": 1},
                "sources": [_source("Code 403", "https://example.com/403")],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    registry_path = Path("app/data/harvest_sources.json")
    before = registry_path.stat().st_mtime_ns

    analyze_http_failures(
        input_path=input_path,
        output_dir=output_dir,
        timeout=1,
        probe_fn=lambda _url, _timeout: {"http_status_code": 403, "error_message": "", "reachable": True},
    )

    assert registry_path.stat().st_mtime_ns == before

