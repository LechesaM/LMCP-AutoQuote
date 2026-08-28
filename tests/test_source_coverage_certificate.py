from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.source_coverage_certificate import (
    attach_harvest_run_certificate_hooks,
    build_run_summary,
    failure_records_from_summary,
    load_daily_summary,
    load_latest_summary,
    update_daily_coverage,
    write_run_certificate,
)
from app.tools.source_coverage import main as source_coverage_main


def make_registry(path: Path, enabled: int, disabled: int) -> Path:
    entries = []
    for index in range(enabled + disabled):
        entries.append(
            {
                "source_name": "source-%04d" % (index + 1),
                "source_url": "https://example.invalid/source/%d" % (index + 1),
                "source_type": "portal",
                "enabled": index < enabled,
            }
        )
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def make_result(
    *,
    run_id: str,
    source_names: list[str],
    selected: Optional[set[str]] = None,
    attempted: Optional[set[str]] = None,
    successful: Optional[set[str]] = None,
    failed: Optional[set[str]] = None,
    execution_mode: str = "discovery",
    full_sweep_requested: bool = False,
    started_at: str = "2026-08-28T09:00:00Z",
    completed_at: str = "2026-08-28T09:01:00Z",
) -> dict[str, object]:
    selected = selected or set()
    attempted = attempted or set()
    successful = successful or set()
    failed = failed or set()
    source_results = []
    for name in source_names:
        source_results.append(
            {
                "source_name": name,
                "source_url": "https://example.invalid/source/%s" % name,
                "source_type": "portal",
                "enabled": True,
                "selected": name in selected,
                "attempted": name in attempted,
                "success": name in successful,
                "error_reason": "boom" if name in failed else None,
                "started_at": started_at,
                "completed_at": completed_at,
                "response_time_ms": 123.45,
                "http_status": 200 if name in successful else 500 if name in failed else None,
                "candidates_found": 2 if name in successful else 0,
                "qualifying_candidates": 1 if name in successful else 0,
                "run_id": run_id,
            }
        )
    return {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "execution_mode": execution_mode,
        "full_sweep_requested": full_sweep_requested,
        "source_results": source_results,
        "complete": True,
    }


def test_partial_run_summary_records_subset_and_denominator(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=970, disabled=355)
    enabled_names = ["source-%04d" % (index + 1) for index in range(25)]
    result = make_result(
        run_id="run-partial",
        source_names=enabled_names,
        selected=set(enabled_names),
        attempted=set(enabled_names),
        successful=set(enabled_names),
        execution_mode="rotation",
        full_sweep_requested=False,
    )
    summary = write_run_certificate(result, registry_path=registry_path, runtime_root=str(tmp_path / "runtime"), git_commit="abc123")
    assert summary.registry_total == 1325
    assert summary.enabled_sources == 970
    assert summary.disabled_sources == 355
    assert summary.selected_sources == 25
    assert summary.attempted_sources == 25
    assert summary.successful_sources == 25
    assert summary.failed_sources == 0
    assert summary.skipped_sources == 945
    assert summary.unique_sources_checked == 25
    assert summary.coverage_percentage == 2.58
    assert summary.coverage_status == "PARTIAL"

    run_dir = tmp_path / "runtime" / "2026-08-28" / "run-partial"
    assert (run_dir / "coverage_summary.json").exists()
    assert (run_dir / "source_results.jsonl").exists()
    latest = load_latest_summary(str(tmp_path / "runtime"))
    assert latest["run_id"] == "run-partial"
    daily = load_daily_summary("2026-08-28", str(tmp_path / "runtime"))
    assert daily["unique_enabled_sources_attempted"] == 25
    assert daily["coverage_status"] == "PARTIAL"


def test_full_sweep_requires_explicit_records_for_every_enabled_source(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=970, disabled=355)
    all_enabled_names = ["source-%04d" % (index + 1) for index in range(970)]
    result = make_result(
        run_id="run-full",
        source_names=all_enabled_names,
        selected=set(all_enabled_names),
        attempted=set(all_enabled_names),
        successful=set(all_enabled_names),
        execution_mode="full_sweep",
        full_sweep_requested=True,
    )
    summary = write_run_certificate(result, registry_path=registry_path, runtime_root=str(tmp_path / "runtime"), git_commit="def456")
    assert summary.registry_total == 1325
    assert summary.enabled_sources == 970
    assert summary.attempted_sources == 970
    assert summary.unique_sources_checked == 970
    assert summary.coverage_percentage == 100.0
    assert summary.coverage_status == "FULL"


def test_failed_sources_count_as_attempted_and_are_listed(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=1, disabled=0)
    result = make_result(
        run_id="run-failed",
        source_names=["source-0001"],
        selected={"source-0001"},
        attempted={"source-0001"},
        failed={"source-0001"},
        execution_mode="discovery",
        full_sweep_requested=False,
    )
    summary = write_run_certificate(result, registry_path=registry_path, runtime_root=str(tmp_path / "runtime"))
    assert summary.attempted_sources == 1
    assert summary.failed_sources == 1
    assert summary.successful_sources == 0
    failures = failure_records_from_summary(summary.to_dict())
    assert len(failures) == 1
    assert failures[0]["source_name"] == "source-0001"
    assert failures[0]["error_reason"] == "boom"


def test_disabled_sources_are_excluded_from_denominator(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=3, disabled=2)
    names = ["source-%04d" % (index + 1) for index in range(3)]
    result = make_result(
        run_id="run-denominator",
        source_names=names,
        selected=set(names),
        attempted=set(names),
        successful=set(names),
        execution_mode="discovery",
        full_sweep_requested=True,
    )
    summary = write_run_certificate(result, registry_path=registry_path, runtime_root=str(tmp_path / "runtime"))
    assert summary.registry_total == 5
    assert summary.enabled_sources == 3
    assert summary.disabled_sources == 2
    assert summary.coverage_percentage == 100.0
    assert summary.coverage_status == "FULL"


def test_daily_aggregate_deduplicates_repeated_sources(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=2, disabled=0)
    runtime_root = tmp_path / "runtime"
    first = make_result(
        run_id="run-1",
        source_names=["source-0001"],
        selected={"source-0001"},
        attempted={"source-0001"},
        successful={"source-0001"},
    )
    second = make_result(
        run_id="run-2",
        source_names=["source-0001"],
        selected={"source-0001"},
        attempted={"source-0001"},
        successful={"source-0001"},
        started_at="2026-08-28T10:00:00Z",
        completed_at="2026-08-28T10:01:00Z",
    )
    write_run_certificate(first, registry_path=registry_path, runtime_root=str(runtime_root))
    write_run_certificate(second, registry_path=registry_path, runtime_root=str(runtime_root))
    daily = update_daily_coverage("2026-08-28", runtime_root=str(runtime_root))
    assert daily["unique_enabled_sources_attempted"] == 1
    assert daily["coverage_percentage"] == 50.0
    assert daily["coverage_status"] == "PARTIAL"


def test_stale_artifacts_outside_source_coverage_tree_do_not_count(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=1, disabled=0)
    runtime_root = tmp_path / "runtime"
    stale_root = runtime_root / "multi_portal_discovery" / "2026-08-27"
    stale_root.mkdir(parents=True, exist_ok=True)
    (stale_root / "coverage_summary.json").write_text(json.dumps({"run_id": "stale", "unique_sources_checked": 1}), encoding="utf-8")
    result = make_result(
        run_id="current",
        source_names=["source-0001"],
        selected={"source-0001"},
        attempted={"source-0001"},
        successful={"source-0001"},
    )
    summary = write_run_certificate(result, registry_path=registry_path, runtime_root=str(runtime_root))
    daily = load_daily_summary("2026-08-28", str(runtime_root))
    assert daily["unique_enabled_sources_attempted"] == 1
    assert summary.run_id == "current"


def test_missing_run_data_cannot_return_full(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=2, disabled=0)
    summary, _ = build_run_summary(
        {
            "run_id": "incomplete",
            "started_at": "2026-08-28T09:00:00Z",
            "completed_at": "2026-08-28T09:01:00Z",
            "execution_mode": "discovery",
            "full_sweep_requested": True,
        },
        registry_path=registry_path,
        runtime_root=str(tmp_path / "runtime"),
        git_commit="abc",
    )
    assert summary.coverage_status in {"PARTIAL", "FAILED"}
    assert summary.coverage_status != "FULL"


def test_cli_latest_date_and_failures_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=1, disabled=0)
    runtime_root = tmp_path / "runtime"
    result = make_result(
        run_id="cli-run",
        source_names=["source-0001"],
        selected={"source-0001"},
        attempted={"source-0001"},
        failed={"source-0001"},
        execution_mode="discovery",
    )
    write_run_certificate(result, registry_path=registry_path, runtime_root=str(runtime_root))

    source_coverage_main(["--latest", "--runtime-root", str(runtime_root), "--failures"])
    out = capsys.readouterr().out
    assert "DATE" in out
    assert "STATUS" in out
    assert "FAILURES" in out


def test_cli_failures_without_scope_defaults_to_latest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=1, disabled=0)
    runtime_root = tmp_path / "runtime"
    result = make_result(
        run_id="cli-run-no-scope",
        source_names=["source-0001"],
        selected={"source-0001"},
        attempted={"source-0001"},
        failed={"source-0001"},
        execution_mode="discovery",
    )
    write_run_certificate(result, registry_path=registry_path, runtime_root=str(runtime_root))

    source_coverage_main(["--failures", "--runtime-root", str(runtime_root)])
    out = capsys.readouterr().out
    assert "DATE" in out
    assert "FAILURES" in out


def test_only_harvest_and_discovery_methods_are_wrapped() -> None:
    attach_harvest_run_certificate_hooks()
    wrapped_methods = {
        name
        for name in (
            "ingest_discovered",
            "run_discovery_cycle",
            "run_golden_cycle",
            "run_live_pilot",
        )
        if getattr(getattr(RfqLifecycleService, name), "_source_coverage_certificate_wrapped", False)
    }
    assert wrapped_methods == {
        "ingest_discovered",
        "run_discovery_cycle",
        "run_golden_cycle",
        "run_live_pilot",
    }
    assert not getattr(RfqLifecycleService.run_scale_simulation, "_source_coverage_certificate_wrapped", False)


def test_failed_run_writes_failed_certificate_and_reraises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: List[Dict[str, Any]] = []

    def fake_writer(run_result: Mapping[str, Any], **kwargs: Any) -> object:
        calls.append(dict(run_result))
        return object()

    def boom(self: object) -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr(RfqLifecycleService, "run_discovery_cycle", boom, raising=False)
    monkeypatch.setattr(RfqLifecycleService, "_source_coverage_certificate_hooked", False, raising=False)
    monkeypatch.setattr("app.services.source_coverage_certificate.write_run_certificate", fake_writer)
    attach_harvest_run_certificate_hooks()

    dummy = object.__new__(RfqLifecycleService)
    with pytest.raises(RuntimeError, match="boom"):
        RfqLifecycleService.run_discovery_cycle(dummy)

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["complete"] is False


def test_cli_reports_no_certificate_recorded_when_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source_coverage_main(["--latest", "--runtime-root", str(tmp_path / "runtime")])
    out = capsys.readouterr().out.strip()
    assert out == "no certificate recorded"
