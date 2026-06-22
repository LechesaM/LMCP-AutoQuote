from __future__ import annotations

import json
from pathlib import Path

from scripts.classify_harvest_effectiveness_sources import build_action_plan
from scripts.classify_harvest_effectiveness_sources import classify_source
from scripts.classify_harvest_effectiveness_sources import write_action_plan


def _row(
    source_name: str,
    *,
    category: str = "municipality",
    url: str = "https://example.com/list",
    failure_type: str = "no_candidates",
    status: str = "no_candidates",
    reachable: bool = True,
    rfqs_found: int = 0,
    qualified_rfqs: int = 0,
    submission_candidates: int = 0,
    marker: str = "",
    http_status_code: int | None = None,
) -> dict:
    row = {
        "source_name": source_name,
        "category": category,
        "url": url,
        "failure_type": failure_type,
        "status": status,
        "reachable": reachable,
        "rfqs_found": rfqs_found,
        "qualified_rfqs": qualified_rfqs,
        "submission_candidates": submission_candidates,
        "investigation_marker": marker,
    }
    if http_status_code is not None:
        row["http_status_code"] = http_status_code
    return row


def test_rfq_producing_source_is_promote() -> None:
    action = classify_source([_row("Producer", rfqs_found=3, qualified_rfqs=2, submission_candidates=1, failure_type="unknown_error", status="ok")])
    assert action.action == "promote"


def test_no_candidates_is_retry() -> None:
    action = classify_source([_row("Retry Source", failure_type="no_candidates", status="no_candidates", reachable=True)])
    assert action.action == "retry"


def test_http_error_is_investigate_http() -> None:
    action = classify_source([_row("HTTP Source", failure_type="http_error", status="http_failed", reachable=False, http_status_code=403)])
    assert action.action == "investigate_http"
    assert action.http_status_code == 403


def test_timeout_is_investigate_timeout() -> None:
    action = classify_source([_row("Timeout Source", failure_type="timeout", status="timeout", reachable=False)])
    assert action.action == "investigate_timeout"


def test_dns_runtime_suspected_is_investigate_runtime_dns() -> None:
    action = classify_source([_row("DNS Runtime Source", failure_type="dns_failed", status="dns_failed", reachable=False, marker="dns_runtime_suspected")])
    assert action.action == "investigate_runtime_dns"


def test_dns_failed_without_marker_is_quarantine_candidate() -> None:
    action = classify_source([_row("Quarantine Candidate", failure_type="dns_failed", status="dns_failed", reachable=False)])
    assert action.action == "quarantine_candidate"


def test_unknown_row_is_unknown_review() -> None:
    action = classify_source([_row("Unknown", failure_type="mystery", status="mystery", reachable=False)])
    assert action.action == "unknown_review"


def test_output_files_are_created_and_registry_is_not_mutated(tmp_path: Path) -> None:
    input_path = tmp_path / "source_attempt_results.json"
    output_dir = tmp_path / "harvest_effectiveness"
    input_payload = {
        "status": "ok",
        "generated_at": "2026-06-19T00:00:00+00:00",
        "count": 7,
        "results": [
            _row("Producer", url="https://producer.example.com", rfqs_found=2, qualified_rfqs=1, submission_candidates=1, failure_type="unknown_error", status="ok", reachable=True),
            _row("Retry Source", url="https://retry.example.com", failure_type="no_candidates", status="no_candidates", reachable=True),
            _row("HTTP Source", url="https://http.example.com", failure_type="http_error", status="http_failed", reachable=False, http_status_code=403),
            _row("Timeout Source", url="https://timeout.example.com", failure_type="timeout", status="timeout", reachable=False),
            _row("DNS Runtime Source", url="https://dns-runtime.example.com", failure_type="dns_failed", status="dns_failed", reachable=False, marker="dns_runtime_suspected"),
            _row("Quarantine Candidate", url="https://quarantine.example.com", failure_type="dns_failed", status="dns_failed", reachable=False),
            _row("Unknown", url="https://unknown.example.com", failure_type="mystery", status="mystery", reachable=False),
        ],
    }
    input_path.write_text(json.dumps(input_payload, indent=2), encoding="utf-8")

    registry_path = Path("app/data/harvest_sources.json")
    registry_mtime_before = registry_path.stat().st_mtime_ns

    result = write_action_plan(input_path=input_path, output_dir=output_dir)

    assert (output_dir / "source_action_plan.json").exists()
    assert (output_dir / "source_action_plan.md").exists()
    assert registry_path.stat().st_mtime_ns == registry_mtime_before

    payload = json.loads((output_dir / "source_action_plan.json").read_text(encoding="utf-8"))
    assert payload["counts"]["promote"] == 1
    assert payload["counts"]["retry"] == 1
    assert payload["counts"]["investigate_http"] == 1
    assert payload["counts"]["investigate_timeout"] == 1
    assert payload["counts"]["investigate_runtime_dns"] == 1
    assert payload["counts"]["quarantine_candidate"] == 1
    assert payload["counts"]["unknown_review"] == 1
    assert "No source was disabled by this classifier." in (output_dir / "source_action_plan.md").read_text(encoding="utf-8")
    assert result["payload"]["total_sources"] == 7


def test_build_action_plan_reads_expected_input_shape(tmp_path: Path) -> None:
    input_path = tmp_path / "source_attempt_results.json"
    input_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at": "2026-06-19T00:00:00+00:00",
                "count": 1,
                "results": [_row("Producer", rfqs_found=1, qualified_rfqs=1, submission_candidates=1, failure_type="unknown_error", status="ok", reachable=True)],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    plan = build_action_plan(input_path)
    assert plan["payload"]["total_sources"] == 1
    assert plan["counts"]["promote"] == 1
