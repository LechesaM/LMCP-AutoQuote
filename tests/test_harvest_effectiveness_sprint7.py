from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import run_harvest_effectiveness_sprint7 as module
from scripts.run_harvest_effectiveness_sprint7 import run_harvest_effectiveness


def _make_source(name: str, url: str, *, enabled: bool = True, category: str = "municipality") -> dict:
    return {
        "name": name,
        "source_name": name,
        "url": url,
        "list_url": url,
        "category": category,
        "source_group": category,
        "category_group": category,
        "enabled": enabled,
    }


def _make_snapshot(*rows: tuple[str, dict]) -> dict:
    snapshot: dict[str, dict] = {}
    for key, row in rows:
        snapshot[key.lower()] = row
    return snapshot


def test_duplicate_urls_are_counted_once(tmp_path: Path, monkeypatch) -> None:
    sources = [
        _make_source("Alpha Source", "https://alpha.example.com/list"),
        _make_source("Alpha Alias", "https://alpha.example.com/list"),
        _make_source("Beta Source", "https://beta.example.com/list"),
    ]
    snapshot = _make_snapshot(
        (
            "alpha source",
            {
                "source_name": "Alpha Source",
                "source_url": "https://alpha.example.com/list",
                "candidate_total": 4,
                "qualified_candidate_total": 2,
                "document_candidate_total": 1,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
        (
            "https://alpha.example.com/list",
            {
                "source_name": "Alpha Source",
                "source_url": "https://alpha.example.com/list",
                "candidate_total": 4,
                "qualified_candidate_total": 2,
                "document_candidate_total": 1,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
        (
            "beta source",
            {
                "source_name": "Beta Source",
                "source_url": "https://beta.example.com/list",
                "candidate_total": 1,
                "qualified_candidate_total": 1,
                "document_candidate_total": 0,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
        (
            "https://beta.example.com/list",
            {
                "source_name": "Beta Source",
                "source_url": "https://beta.example.com/list",
                "candidate_total": 1,
                "qualified_candidate_total": 1,
                "document_candidate_total": 0,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
    )

    monkeypatch.setattr(module, "_preflight_source", lambda _source, _timeout: {"status": "ok", "reachable": True})

    result = run_harvest_effectiveness(
        limit=10,
        timeout=1,
        output_dir=tmp_path / "harvest_effectiveness",
        dry_run=True,
        sources=sources,
        source_health_snapshot=snapshot,
    )

    metrics = result["coverage"]["metrics"]
    attempts = result["attempts"]["results"]

    assert metrics["configured_sources"] == 3
    assert metrics["enabled_sources"] == 3
    assert metrics["unique_urls"] == 2
    assert metrics["attempted_sources"] == 2
    assert metrics["reachable_sources"] == 2
    assert metrics["rfq_producing_sources"] == 2
    assert metrics["qualified_rfq_sources"] == 2
    assert metrics["submission_candidate_sources"] == 1
    assert attempts[-1]["failure_type"] == "duplicate_url"
    assert attempts[-1]["attempted"] is False


def test_dns_failed_is_classified_correctly() -> None:
    failure = module._classify_attempt_failure(  # noqa: SLF001
        preflight_status="dns_failed",
        error_message="nodename nor servname provided",
        source_health_row={},
        attempted=True,
    )
    assert failure == "dns_failed"


def test_timeout_is_classified_correctly() -> None:
    failure = module._classify_attempt_failure(  # noqa: SLF001
        preflight_status="timeout",
        error_message="request timed out after 20 seconds",
        source_health_row={},
        attempted=True,
    )
    assert failure == "timeout"


def test_python_dns_failure_with_curl_success_is_reachable_and_no_candidates(tmp_path: Path, monkeypatch) -> None:
    sources = [_make_source("Fallback Source", "https://fallback.example.com/list")]
    snapshot = _make_snapshot(
        (
            "fallback source",
            {
                "source_name": "Fallback Source",
                "source_url": "https://fallback.example.com/list",
                "candidate_total": 0,
                "qualified_candidate_total": 0,
                "document_candidate_total": 0,
                "health_status": "degraded",
                "acquisition_status": "no_candidates",
                "last_status": "ok_empty",
            },
        ),
        (
            "https://fallback.example.com/list",
            {
                "source_name": "Fallback Source",
                "source_url": "https://fallback.example.com/list",
                "candidate_total": 0,
                "qualified_candidate_total": 0,
                "document_candidate_total": 0,
                "health_status": "degraded",
                "acquisition_status": "no_candidates",
                "last_status": "ok_empty",
            },
        ),
    )

    monkeypatch.setattr(module, "_preflight_source", lambda _source, _timeout: {"status": "dns_failed", "reachable": False, "error_message": "nodename nor servname provided"})
    monkeypatch.setattr(module, "_curl_head_probe", lambda _source, _timeout: {"status": "ok", "reachable": True, "http_status_code": 200, "http_status": 200, "error_message": "", "fallback_used": True})

    result = run_harvest_effectiveness(
        limit=10,
        timeout=1,
        output_dir=tmp_path / "harvest_effectiveness",
        dry_run=True,
        sources=sources,
        source_health_snapshot=snapshot,
    )

    attempt = result["attempts"]["results"][0]
    assert attempt["reachable"] is True
    assert attempt["failure_type"] == "no_candidates"
    assert attempt["investigation_marker"] == "dns_runtime_suspected"
    assert result["coverage"]["metrics"]["reachable_sources"] == 1
    assert result["coverage"]["metrics"]["dns_runtime_suspected_sources"] == 1


def test_python_dns_failure_with_curl_failure_is_dns_failed(tmp_path: Path, monkeypatch) -> None:
    sources = [_make_source("Broken Fallback Source", "https://broken.example.com/list")]
    snapshot = _make_snapshot(
        (
            "broken fallback source",
            {
                "source_name": "Broken Fallback Source",
                "source_url": "https://broken.example.com/list",
                "candidate_total": 0,
                "qualified_candidate_total": 0,
                "document_candidate_total": 0,
                "health_status": "degraded",
                "acquisition_status": "dns_failed",
                "last_status": "failed",
            },
        ),
        (
            "https://broken.example.com/list",
            {
                "source_name": "Broken Fallback Source",
                "source_url": "https://broken.example.com/list",
                "candidate_total": 0,
                "qualified_candidate_total": 0,
                "document_candidate_total": 0,
                "health_status": "degraded",
                "acquisition_status": "dns_failed",
                "last_status": "failed",
            },
        ),
    )

    monkeypatch.setattr(module, "_preflight_source", lambda _source, _timeout: {"status": "dns_failed", "reachable": False, "error_message": "nodename nor servname provided"})
    monkeypatch.setattr(module, "_curl_head_probe", lambda _source, _timeout: {"status": "dns_failed", "reachable": False, "http_status_code": 0, "http_status": 0, "error_message": "Could not resolve host", "fallback_used": True})

    result = run_harvest_effectiveness(
        limit=10,
        timeout=1,
        output_dir=tmp_path / "harvest_effectiveness",
        dry_run=True,
        sources=sources,
        source_health_snapshot=snapshot,
    )

    attempt = result["attempts"]["results"][0]
    assert attempt["reachable"] is False
    assert attempt["failure_type"] == "dns_failed"
    assert attempt["investigation_marker"] == "dns_runtime_suspected"
    assert result["coverage"]["metrics"]["reachable_sources"] == 0


def test_curl_http_403_and_405_count_as_reachable(monkeypatch) -> None:
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="HTTP/1.1 403 Forbidden\n",
            stderr="",
        ),
    )
    result_403 = module._curl_head_probe(_make_source("Forbidden Source", "https://forbidden.example.com/list"), 1)  # noqa: SLF001
    assert result_403["reachable"] is True
    assert result_403["http_status_code"] == 403

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="HTTP/1.1 405 Method Not Allowed\n",
            stderr="",
        ),
    )
    result_405 = module._curl_head_probe(_make_source("Method Source", "https://method.example.com/list"), 1)  # noqa: SLF001
    assert result_405["reachable"] is True
    assert result_405["http_status_code"] == 405


def test_metrics_calculate_coverage_correctly(tmp_path: Path, monkeypatch) -> None:
    sources = [
        _make_source("Reachable Producer", "https://producer.example.com/list"),
        _make_source("Reachable Empty", "https://empty.example.com/list"),
        _make_source("Disabled Source", "https://disabled.example.com/list", enabled=False),
    ]
    snapshot = _make_snapshot(
        (
            "reachable producer",
            {
                "source_name": "Reachable Producer",
                "source_url": "https://producer.example.com/list",
                "candidate_total": 7,
                "qualified_candidate_total": 5,
                "document_candidate_total": 3,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
        (
            "https://producer.example.com/list",
            {
                "source_name": "Reachable Producer",
                "source_url": "https://producer.example.com/list",
                "candidate_total": 7,
                "qualified_candidate_total": 5,
                "document_candidate_total": 3,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
        (
            "reachable empty",
            {
                "source_name": "Reachable Empty",
                "source_url": "https://empty.example.com/list",
                "candidate_total": 0,
                "qualified_candidate_total": 0,
                "document_candidate_total": 0,
                "health_status": "degraded",
                "acquisition_status": "no_candidates",
                "last_status": "ok_empty",
            },
        ),
        (
            "https://empty.example.com/list",
            {
                "source_name": "Reachable Empty",
                "source_url": "https://empty.example.com/list",
                "candidate_total": 0,
                "qualified_candidate_total": 0,
                "document_candidate_total": 0,
                "health_status": "degraded",
                "acquisition_status": "no_candidates",
                "last_status": "ok_empty",
            },
        ),
    )

    monkeypatch.setattr(module, "_preflight_source", lambda _source, _timeout: {"status": "ok", "reachable": True})

    result = run_harvest_effectiveness(
        limit=200,
        timeout=1,
        output_dir=tmp_path / "harvest_effectiveness",
        dry_run=True,
        sources=sources,
        source_health_snapshot=snapshot,
    )

    metrics = result["coverage"]["metrics"]
    assert metrics["configured_sources"] == 3
    assert metrics["enabled_sources"] == 2
    assert metrics["attempted_sources"] == 2
    assert metrics["harvest_coverage_percent"] == 66.67
    assert metrics["rfq_producing_source_percent"] == 50.0
    assert dict(metrics["top_failure_types"])["no_candidates"] == 1


def test_output_files_are_created_and_governance_state_is_unchanged(tmp_path: Path, monkeypatch) -> None:
    sources = [_make_source("Governed Source", "https://governed.example.com/list")]
    snapshot = _make_snapshot(
        (
            "governed source",
            {
                "source_name": "Governed Source",
                "source_url": "https://governed.example.com/list",
                "candidate_total": 1,
                "qualified_candidate_total": 1,
                "document_candidate_total": 1,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
        (
            "https://governed.example.com/list",
            {
                "source_name": "Governed Source",
                "source_url": "https://governed.example.com/list",
                "candidate_total": 1,
                "qualified_candidate_total": 1,
                "document_candidate_total": 1,
                "health_status": "healthy",
                "acquisition_status": "success",
                "last_status": "ok",
            },
        ),
    )
    monkeypatch.setattr(module, "_preflight_source", lambda _source, _timeout: {"status": "ok", "reachable": True})

    governance_doc = Path("docs/operations_validation_pack/sprint_7_execution_log.md")
    registry_path = Path("app/data/harvest_sources.json")
    governance_doc_mtime = governance_doc.stat().st_mtime_ns
    registry_mtime = registry_path.stat().st_mtime_ns

    output_dir = tmp_path / "harvest_effectiveness"
    run_harvest_effectiveness(
        limit=200,
        timeout=1,
        output_dir=output_dir,
        dry_run=True,
        sources=sources,
        source_health_snapshot=snapshot,
    )

    assert (output_dir / "harvest_coverage_metrics.json").exists()
    assert (output_dir / "source_attempt_results.json").exists()
    assert (output_dir / "source_productivity_leaderboard.json").exists()
    assert (output_dir / "harvest_effectiveness_summary.md").exists()
    assert governance_doc.stat().st_mtime_ns == governance_doc_mtime
    assert registry_path.stat().st_mtime_ns == registry_mtime
