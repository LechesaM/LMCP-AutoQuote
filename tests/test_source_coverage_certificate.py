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
                "source_identity": name,
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


def test_aggregate_success_without_source_records_is_not_misclassified_as_failed() -> None:
    summary, records = build_run_summary(
        {
            "status": "ok",
            "harvest_status": "ok",
            "harvested_total": 25,
            "eligible_total": 9,
            "quote_ready_total": 3,
            "ingest": {"ingested_count": 9, "skipped_duplicates_count": 2},
            "mission_control": {},
            "safety": {},
        }
    )

    assert not any(record.attempted for record in records)
    assert summary.attempted_sources == 0
    assert summary.unique_sources_checked == 0
    assert summary.coverage_status == "PARTIAL"


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


def test_daily_aggregate_deduplicates_by_source_identity(tmp_path: Path) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=2, disabled=0)
    runtime_root = tmp_path / "runtime"
    first = make_result(
        run_id="run-identity-1",
        source_names=["alpha"],
        selected={"alpha"},
        attempted={"alpha"},
        successful={"alpha"},
    )
    first["selected_sources"] = [{"source_name": "alpha", "source_identity": "registry-123"}]
    first["source_results"][0]["source_identity"] = "registry-123"
    second = make_result(
        run_id="run-identity-2",
        source_names=["beta"],
        selected={"beta"},
        attempted={"beta"},
        successful={"beta"},
        started_at="2026-08-28T10:00:00Z",
        completed_at="2026-08-28T10:01:00Z",
    )
    second["selected_sources"] = [{"source_name": "beta", "source_identity": "registry-123"}]
    second["source_results"][0]["source_identity"] = "registry-123"

    write_run_certificate(first, registry_path=registry_path, runtime_root=str(runtime_root))
    write_run_certificate(second, registry_path=registry_path, runtime_root=str(runtime_root))
    daily = update_daily_coverage("2026-08-28", runtime_root=str(runtime_root))
    assert daily["unique_enabled_sources_attempted"] == 1
    assert daily["coverage_percentage"] == 50.0


def _capture_certificate(monkeypatch: pytest.MonkeyPatch, registry_path: Path, runtime_root: Path):
    captured: list[tuple[object, list[dict[str, object]], dict[str, object]]] = []

    def fake_writer(run_result: dict[str, object], **kwargs: object) -> object:
        summary, records = build_run_summary(
            run_result,
            registry_path=str(registry_path),
            runtime_root=str(runtime_root),
            git_commit="test-commit",
        )
        captured.append((summary, records, dict(run_result)))
        return summary

    monkeypatch.setattr("app.services.source_coverage_certificate.write_run_certificate", fake_writer)
    return captured


def _fake_candidate(name: str) -> dict[str, object]:
    return {
        "title": "RFQ for office supplies",
        "description": "Supply and delivery of office supplies",
        "source_name": name,
        "source_url": "https://example.invalid/%s" % name,
        "buyer_name": "Example Buyer",
        "closing_date": "2026-12-31",
        "submission_method": "portal",
        "document_urls": [],
    }


def _patch_harvest_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.tender_harvester._v54_deep_extract_candidate",
        lambda item, source: {**dict(item), "source_name": source.get("name") or source.get("source_name"), "source_url": source.get("url") or source.get("list_url")},
    )
    monkeypatch.setattr(
        "app.services.tender_harvester._v54_qualification",
        lambda candidate: {
            **dict(candidate),
            "eligible": True,
            "quote_ready": True,
            "pipeline_status": "eligible",
            "qualification_score": 100,
            "confidence_score": 100,
            "qualification_reasons": [],
        },
    )
    monkeypatch.setattr("app.services.tender_harvester._v57_apply_candidate_memory_learning", lambda candidate, memory_files: candidate)
    monkeypatch.setattr("app.services.tender_harvester._lmcp_apply_v49_navigation_gate", lambda item: item)
    monkeypatch.setattr("app.services.tender_harvester._lmcp_apply_v50_7_etenders_navigation_gate", lambda item: item)
    monkeypatch.setattr("app.services.tender_harvester._lmcp_apply_docx_verified_quantity_gate", lambda item: item)
    monkeypatch.setattr("app.services.tender_harvester._lmcp_apply_real_buyer_pricing_gate", lambda item: item)
    monkeypatch.setattr("app.services.tender_harvester._lmcp_enforce_final_quantity_safety", lambda item: item)
    monkeypatch.setattr("app.services.tender_harvester._lmcp_apply_v50_7_verified_rfq_promotion_gate", lambda item, policy: item)
    monkeypatch.setattr("app.services.tender_harvester._rank_items", lambda items: items)
    monkeypatch.setattr("app.services.tender_harvester._v53_update_source_health_after_scan", lambda *args, **kwargs: {})
    monkeypatch.setattr("app.services.tender_harvester._save_source_health", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.tender_harvester._v57_update_discovery_memory", lambda *args, **kwargs: {"memory_sources_count": 0, "memory_buyers_count": 0, "memory_categories_count": 0, "boosted_priority_sources": [], "boosted_priority_buyers": [], "boosted_priority_categories": []})
    monkeypatch.setattr("app.services.tender_harvester._persist_live_store", lambda *args, **kwargs: {"status": "ok", "count": len(args[0]) if args else 0})


def _fake_registry_sources(*names: str) -> list[dict[str, object]]:
    sources: list[dict[str, object]] = []
    for index, name in enumerate(names, start=1):
        sources.append(
            {
                "name": name,
                "source_name": name,
                "url": "https://example.invalid/%s" % name,
                "list_url": "https://example.invalid/%s" % name,
                "type": "portal",
                "source_group": "test",
                "category_group": "test",
                "enabled": True,
                "priority": index,
                "intelligence_score": 100 - index,
            }
        )
    return sources


def _patch_fake_registry(monkeypatch: pytest.MonkeyPatch, *names: str) -> list[dict[str, object]]:
    sources = _fake_registry_sources(*names)
    monkeypatch.setattr("app.services.tender_harvester.load_harvest_sources", lambda source_file=None: list(sources))
    monkeypatch.delenv("LMCP_SOURCE_PACK_MODE", raising=False)
    return sources


def _patch_pack_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_select_sources_for_pack_rotation(
        sources: list[dict[str, object]],
        max_sources: int,
        include_bad_sources: bool = False,
        pack_mode: object = None,
    ) -> tuple[list[dict[str, object]], str, list[dict[str, object]], dict[str, object]]:
        selected = list(sources)[: max(1, int(max_sources))]
        strategy = {
            "active_pack_mode": "balanced",
            "packs": {},
            "source_rows": [
                {
                    "source_name": str(source.get("name") or source.get("source_name") or ""),
                    "source_url": source.get("url") or source.get("list_url") or "",
                    "source_type": source.get("type") or "",
                    "source_group": source.get("source_group") or source.get("category_group") or "",
                    "v58_yield_score": 100 - index,
                    "selected_this_cycle": True,
                }
                for index, source in enumerate(selected)
            ],
            "diagnostics": {"status": "ok"},
            "projected_highest_yield_pack": "document_rich_pack",
        }
        return selected, "test-pack-batch", [], strategy

    monkeypatch.setattr("app.services.tender_harvester._v58_select_sources_for_pack_rotation", fake_select_sources_for_pack_rotation)


def _patch_service_store(monkeypatch: pytest.MonkeyPatch, service: RfqLifecycleService) -> None:
    service.store.update_many = lambda *args, **kwargs: None  # type: ignore[assignment]
    service.store.append_audit_events = lambda *args, **kwargs: None  # type: ignore[assignment]


def _fake_harvest_cycle_result() -> dict[str, object]:
    source_results = [
        {
            "source_name": "source-0001",
            "source_identity": "registry-001",
            "source_url": "https://example.invalid/source-0001",
            "source_type": "portal",
            "enabled": True,
            "selected": True,
            "attempted": True,
            "success": True,
            "started_at": "2026-08-28T09:00:00Z",
            "completed_at": "2026-08-28T09:00:01Z",
            "response_time_ms": 100.0,
            "http_status": 200,
            "candidates_found": 0,
            "qualifying_candidates": 0,
        },
        {
            "source_name": "source-0002",
            "source_identity": "registry-002",
            "source_url": "https://example.invalid/source-0002",
            "source_type": "portal",
            "enabled": True,
            "selected": True,
            "attempted": True,
            "success": True,
            "started_at": "2026-08-28T09:00:00Z",
            "completed_at": "2026-08-28T09:00:02Z",
            "response_time_ms": 150.0,
            "http_status": 200,
            "candidates_found": 1,
            "qualifying_candidates": 1,
        },
        {
            "source_name": "source-0003",
            "source_identity": "registry-003",
            "source_url": "https://example.invalid/source-0003",
            "source_type": "portal",
            "enabled": True,
            "selected": True,
            "attempted": False,
            "success": False,
            "started_at": None,
            "completed_at": None,
            "response_time_ms": 0.0,
            "http_status": None,
            "candidates_found": 0,
            "qualifying_candidates": 0,
        },
    ]
    return {
        "status": "ok",
        "harvest_status": "ok",
        "selected_sources": [
            {"source_name": "source-0001", "source_identity": "registry-001"},
            {"source_name": "source-0002", "source_identity": "registry-002"},
            {"source_name": "source-0003", "source_identity": "registry-003"},
        ],
        "source_results": source_results,
        "eligible_items": [_fake_candidate("source-0002")],
        "harvested_total": 1,
        "eligible_total": 1,
        "quote_ready_total": 0,
    }


def test_wrapped_discovery_cycle_emits_real_source_results_and_partial_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=3, disabled=0)
    runtime_root = tmp_path / "runtime"
    captured = _capture_certificate(monkeypatch, registry_path, runtime_root)
    monkeypatch.setattr("app.services.tender_harvester.run_national_tender_radar", lambda **kwargs: _fake_harvest_cycle_result())
    monkeypatch.setattr(RfqLifecycleService, "ingest_discovered_items", lambda self, items, source="discovered": {"status": "ok", "ingested_count": len(items), "skipped_duplicates_count": 0, "items": [], "skipped_duplicates": [], "qualified_count": len(items), "discovered_count": len(items)}, raising=False)
    _patch_harvest_pipeline(monkeypatch)

    service = RfqLifecycleService()
    _patch_service_store(monkeypatch, service)
    result = service.run_discovery_cycle(max_total=1, max_per_source=1, max_sources=3)
    assert result["status"] == "ok"
    assert len(captured) == 1

    summary, records, run_result = captured[0]
    assert summary.coverage_status == "PARTIAL"
    assert summary.attempted_sources == 2
    assert summary.unique_sources_checked == 2
    assert summary.selected_sources == 3
    assert summary.skipped_sources == 1
    zero = next(record for record in records if record.source_name == "source-0001")
    skipped = next(record for record in records if record.source_name == "source-0003")
    assert zero.attempted is True
    assert zero.success is True
    assert zero.candidates_found == 0
    assert skipped.selected is True
    assert skipped.attempted is False
    assert run_result["selected_sources"]
    assert run_result["source_results"]


def test_wrapped_golden_cycle_emits_real_source_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=2, disabled=0)
    runtime_root = tmp_path / "runtime"
    captured = _capture_certificate(monkeypatch, registry_path, runtime_root)
    monkeypatch.setattr("app.services.tender_harvester.MULTI_PORTAL_DISCOVERY_DIR", runtime_root / "multi_portal_discovery", raising=False)
    monkeypatch.setattr("app.services.tender_harvester.run_multi_portal_discovery", lambda **kwargs: _fake_harvest_cycle_result())
    monkeypatch.setattr(RfqLifecycleService, "ingest_discovered_items", lambda self, items, source="discovered": {"status": "ok", "ingested_count": len(items), "skipped_duplicates_count": 0}, raising=False)
    _patch_harvest_pipeline(monkeypatch)

    service = RfqLifecycleService()
    service.store.increment = lambda *args, **kwargs: None  # type: ignore[assignment]
    _patch_service_store(monkeypatch, service)
    service.recover_stuck = lambda timeout_minutes=120: {"status": "ok"}  # type: ignore[assignment]
    service.mission_control_summary = lambda: {"status": "ok"}  # type: ignore[assignment]
    result = service.run_golden_cycle(limit=1, dry_run=True)
    assert result["status"] == "ok"
    assert len(captured) == 1
    summary, records, run_result = captured[0]
    assert summary.coverage_status == "PARTIAL"
    assert summary.attempted_sources > 0
    assert summary.unique_sources_checked > 0
    assert run_result["selected_sources"]
    assert run_result["source_results"]


def test_wrapped_live_pilot_emits_real_source_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=2, disabled=0)
    runtime_root = tmp_path / "runtime"
    captured = _capture_certificate(monkeypatch, registry_path, runtime_root)
    monkeypatch.setattr("app.services.tender_harvester.run_national_tender_radar", lambda **kwargs: _fake_harvest_cycle_result())
    monkeypatch.setattr(RfqLifecycleService, "_is_lifecycle_qualified", lambda self, row: False, raising=False)
    _patch_harvest_pipeline(monkeypatch)

    service = RfqLifecycleService()
    service._update_live_pilot_metrics = lambda result: {"status": "ok", "mode": "controlled_live_pilot_no_submission", "last_run_at": "", "success_rate": 0.0, "real_rfq_throughput": 0, "acquisition_success_rate": 0.0, "last_result": {}, "throughput_trend": []}  # type: ignore[assignment]
    _patch_service_store(monkeypatch, service)
    result = service.run_live_pilot(limit=3, timeout_seconds=1, max_concurrent_downloads=1, retry_backoff_seconds=0.0)
    assert result["status"] == "ok"
    assert len(captured) == 1
    summary, records, run_result = captured[0]
    assert summary.coverage_status == "PARTIAL"
    assert summary.attempted_sources > 0
    assert summary.unique_sources_checked > 0
    assert run_result["selected_sources"]
    assert run_result["source_results"]


def test_wrapped_ingest_discovered_emits_scanned_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = make_registry(tmp_path / "harvest_sources.json", enabled=2, disabled=0)
    runtime_root = tmp_path / "runtime"
    captured = _capture_certificate(monkeypatch, registry_path, runtime_root)
    monkeypatch.setenv("LMCP_HARVEST_SOURCES_PATH", str(registry_path))

    def fake_load_discovery_store(self: RfqLifecycleService, path: Path) -> list[dict[str, object]]:
        if path.name.endswith("one.json"):
            return [{"title": "Discovered one", "source_name": "store-one"}]
        return [{"title": "Discovered two", "source_name": "store-two"}]

    monkeypatch.setattr(RfqLifecycleService, "_load_discovery_store", fake_load_discovery_store, raising=False)
    monkeypatch.setattr(RfqLifecycleService, "ingest_discovered_items", lambda self, items, source="discovered": {"status": "ok", "ingested_count": len(items), "skipped_duplicates_count": 0}, raising=False)
    monkeypatch.setattr("app.services.rfq_lifecycle_service.DISCOVERY_STORE_CANDIDATES", [tmp_path / "one.json", tmp_path / "two.json"], raising=False)
    _patch_harvest_pipeline(monkeypatch)

    service = RfqLifecycleService()
    _patch_service_store(monkeypatch, service)
    result = service.ingest_discovered()
    assert result["status"] == "ok"
    assert len(captured) == 1
    summary, records, run_result = captured[0]
    assert summary.coverage_status == "PARTIAL"
    assert summary.attempted_sources > 0
    assert summary.unique_sources_checked > 0
    assert run_result["selected_sources"]
    assert run_result["source_results"]


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
