from __future__ import annotations

import json
from pathlib import Path

from scripts.build_source_maintenance_action_list import build_source_maintenance_action_list
from scripts.build_source_maintenance_action_list import write_source_maintenance_action_list


def _attempt_row(
    source_name: str,
    *,
    category: str = "soe",
    url: str = "https://example.com/",
    failure_type: str = "no_candidates",
    status: str = "no_candidates",
    rfqs_found: int = 0,
    qualified_rfqs: int = 0,
    submission_candidates: int = 0,
) -> dict:
    return {
        "source_name": source_name,
        "category": category,
        "url": url,
        "failure_type": failure_type,
        "status": status,
        "reachable": False,
        "rfqs_found": rfqs_found,
        "qualified_rfqs": qualified_rfqs,
        "submission_candidates": submission_candidates,
        "investigation_marker": "",
    }


def _action_row(
    source_name: str,
    *,
    category: str = "soe",
    url: str = "https://example.com/",
    action: str = "investigate_http",
    failure_type: str = "http_error",
    status: str = "http_failed",
    rfqs_found: int = 0,
    qualified_rfqs: int = 0,
    submission_candidates: int = 0,
) -> dict:
    return {
        "source_name": source_name,
        "category": category,
        "url": url,
        "action": action,
        "failure_type": failure_type,
        "status": status,
        "reachable": False,
        "rfqs_found": rfqs_found,
        "qualified_rfqs": qualified_rfqs,
        "submission_candidates": submission_candidates,
        "investigation_marker": "",
    }


def test_source_maintenance_action_list_classifies_expected_actions(tmp_path: Path) -> None:
    action_plan_path = tmp_path / "source_action_plan.json"
    http_summary_path = tmp_path / "http_failure_summary.json"
    attempt_results_path = tmp_path / "source_attempt_results.json"
    output_dir = tmp_path / "harvest_effectiveness"
    doc_path = tmp_path / "docs" / "operations_validation_pack" / "sprint_7_source_maintenance_decision_memo.md"

    action_plan_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-19T00:00:00+00:00",
                "counts": {},
                "sources": [
                    _action_row("404 Source", url="https://example.com/404"),
                    _action_row("301 Source", url="https://example.com/301"),
                    _action_row("Loop Source", url="https://example.com/loop"),
                    _action_row("Auth Source", url="https://example.com/auth"),
                    _action_row("Unknown Source", url="https://example.com/unknown"),
                    _action_row("Retry Source", action="retry", failure_type="no_candidates", status="no_candidates", url="https://example.com/retry"),
                    _action_row("Producer Source", action="promote", failure_type="unknown_error", status="ok", rfqs_found=3, qualified_rfqs=2, submission_candidates=1, url="https://example.com/prod"),
                    _action_row("Timeout Source", action="investigate_timeout", failure_type="timeout", status="timeout", url="https://example.com/timeout"),
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    http_summary_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-19T00:00:00+00:00",
                "counts": {
                    "HTTP 301": 1,
                    "HTTP 302": 0,
                    "HTTP 401": 1,
                    "HTTP 403": 0,
                    "HTTP 404": 1,
                    "HTTP 405": 0,
                    "HTTP 500": 0,
                    "SSL Error": 0,
                    "Redirect Loop": 1,
                    "Unknown HTTP": 1,
                },
                "sources": [
                    {"source_name": "404 Source", "category": "soe", "url": "https://example.com/404", "bucket": "HTTP 404", "http_status_code": 404, "error_message": "", "action": "investigate_http", "investigation_marker": "", "reachable": False, "rfqs_found": 0, "qualified_rfqs": 0, "submission_candidates": 0},
                    {"source_name": "301 Source", "category": "soe", "url": "https://example.com/301", "bucket": "HTTP 301", "http_status_code": 301, "error_message": "", "action": "investigate_http", "investigation_marker": "", "reachable": False, "rfqs_found": 0, "qualified_rfqs": 0, "submission_candidates": 0},
                    {"source_name": "Loop Source", "category": "soe", "url": "https://example.com/loop", "bucket": "Redirect Loop", "http_status_code": None, "error_message": "", "action": "investigate_http", "investigation_marker": "", "reachable": False, "rfqs_found": 0, "qualified_rfqs": 0, "submission_candidates": 0},
                    {"source_name": "Auth Source", "category": "soe", "url": "https://example.com/auth", "bucket": "HTTP 401", "http_status_code": 401, "error_message": "", "action": "investigate_http", "investigation_marker": "", "reachable": False, "rfqs_found": 0, "qualified_rfqs": 0, "submission_candidates": 0},
                    {"source_name": "Unknown Source", "category": "soe", "url": "https://example.com/unknown", "bucket": "Unknown HTTP", "http_status_code": None, "error_message": "", "action": "investigate_http", "investigation_marker": "", "reachable": False, "rfqs_found": 0, "qualified_rfqs": 0, "submission_candidates": 0},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    attempt_results_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-19T00:00:00+00:00",
                "results": [
                    _attempt_row("Retry Source", failure_type="no_candidates", status="no_candidates", url="https://example.com/retry"),
                    _attempt_row("Producer Source", failure_type="unknown_error", status="ok", rfqs_found=3, qualified_rfqs=2, submission_candidates=1, url="https://example.com/prod"),
                    _attempt_row("Timeout Source", failure_type="timeout", status="timeout", url="https://example.com/timeout"),
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    registry_path = Path("app/data/harvest_sources.json")
    registry_mtime_before = registry_path.stat().st_mtime_ns

    result = write_source_maintenance_action_list(
        action_plan_path=action_plan_path,
        http_summary_path=http_summary_path,
        attempt_results_path=attempt_results_path,
        output_dir=output_dir,
        doc_path=doc_path,
    )

    json_path = output_dir / "source_maintenance_action_list.json"
    md_path = output_dir / "source_maintenance_action_list.md"
    assert json_path.exists()
    assert md_path.exists()
    assert doc_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    actions = {row["source_name"]: row for row in payload["sources"]}
    assert actions["404 Source"]["action"] == "fix_404_url"
    assert actions["301 Source"]["action"] == "resolve_redirect"
    assert actions["Loop Source"]["action"] == "investigate_redirect_loop"
    assert actions["Auth Source"]["action"] == "investigate_auth"
    assert actions["Unknown Source"]["action"] == "manual_probe_unknown"
    assert actions["Retry Source"]["action"] == "keep_retry"
    assert actions["Producer Source"]["action"] == "promote"
    assert actions["Timeout Source"]["action"] == "keep_retry"
    assert all(row["disable_source"] is False for row in payload["sources"])
    assert registry_path.stat().st_mtime_ns == registry_mtime_before
    assert "No source was disabled by this action list." in md_path.read_text(encoding="utf-8")
    assert result["payload"]["total_sources"] == 8


def test_source_maintenance_action_list_uses_expected_counts(tmp_path: Path) -> None:
    action_plan_path = tmp_path / "source_action_plan.json"
    http_summary_path = tmp_path / "http_failure_summary.json"
    attempt_results_path = tmp_path / "source_attempt_results.json"

    action_plan_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-19T00:00:00+00:00",
                "counts": {},
                "sources": [
                    _action_row("404 Source", url="https://example.com/404"),
                    _action_row("Retry Source", action="retry", failure_type="no_candidates", status="no_candidates", url="https://example.com/retry"),
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    http_summary_path.write_text(
        json.dumps({"status": "ok", "generated_at": "2026-06-19T00:00:00+00:00", "counts": {"HTTP 404": 1}, "sources": [{"source_name": "404 Source", "category": "soe", "url": "https://example.com/404", "bucket": "HTTP 404", "http_status_code": 404, "error_message": "", "action": "investigate_http", "investigation_marker": "", "reachable": False, "rfqs_found": 0, "qualified_rfqs": 0, "submission_candidates": 0}]}, indent=2),
        encoding="utf-8",
    )
    attempt_results_path.write_text(json.dumps({"status": "ok", "generated_at": "2026-06-19T00:00:00+00:00", "results": []}, indent=2), encoding="utf-8")

    plan = build_source_maintenance_action_list(
        action_plan_path=action_plan_path,
        http_summary_path=http_summary_path,
        attempt_results_path=attempt_results_path,
    )
    assert plan["counts"]["fix_404_url"] == 1
    assert plan["counts"]["keep_retry"] == 1
    assert plan["payload"]["total_sources"] == 2
