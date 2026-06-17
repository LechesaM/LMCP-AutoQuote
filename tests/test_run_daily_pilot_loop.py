from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_queue(runtime_root: Path) -> None:
    live_queue = {
        "status": "ok",
        "updated_at": "2026-06-08T00:00:00+00:00",
        "count": 2,
        "items": [
            {
                "rfq_id": "RFQ_OLD",
                "title": "Old RFQ",
                "source_name": "Live Portal",
                "status": "Quote Ready",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
            },
            {
                "rfq_id": "RFQ_NEW",
                "title": "New RFQ",
                "source_name": "Smoke Fixture",
                "status": "Quote Ready",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
            },
        ],
    }
    (runtime_root / "live_rfqs.json").write_text(json.dumps(live_queue), encoding="utf-8")


def test_run_daily_pilot_loop_prefers_newest_fresh_candidate(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_daily_pilot_loop.py"), "run_daily_pilot_loop_newest")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    source_root = manual_root / "source_bundle_repairs"
    packages_root = manual_root / "submission_packages"
    source_root.mkdir(parents=True, exist_ok=True)
    packages_root.mkdir(parents=True, exist_ok=True)

    queue = {
        "status": "ok",
        "updated_at": "2026-06-08T00:00:00+00:00",
        "count": 2,
        "items": [
            {
                "rfq_id": "RFQ_OLD_FRESH",
                "title": "Old Fresh",
                "source_name": "Live Portal",
                "status": "live",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
                "created_at": "2026-06-08T00:00:00+00:00",
            },
            {
                "rfq_id": "RFQ_NEW_FRESH",
                "title": "New Fresh",
                "source_name": "Smoke Fixture",
                "status": "live",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
                "created_at": "2026-06-08T00:05:00+00:00",
            },
        ],
    }
    (runtime_root / "live_rfqs.json").write_text(json.dumps(queue), encoding="utf-8")

    old_bundle = source_root / "RFQ_OLD_FRESH"
    old_bundle.mkdir(parents=True, exist_ok=True)
    old_bundle.joinpath("RFQ_OLD_FRESH_overview.txt").write_text("overview", encoding="utf-8")
    old_package = packages_root / "RFQ_OLD_FRESH"
    old_package.mkdir(parents=True, exist_ok=True)
    old_package.joinpath("RFQ_OLD_FRESH__manual_pricing.json").write_text(json.dumps({"items": [{"unit_price": 100, "line_total": 1000}]}), encoding="utf-8")

    new_bundle = source_root / "RFQ_NEW_FRESH"
    new_bundle.mkdir(parents=True, exist_ok=True)
    new_bundle.joinpath("RFQ_NEW_FRESH_overview.txt").write_text("overview", encoding="utf-8")
    new_package = packages_root / "RFQ_NEW_FRESH"
    new_package.mkdir(parents=True, exist_ok=True)
    new_pricing = new_package / "RFQ_NEW_FRESH__manual_pricing.json"
    new_pricing.write_text(json.dumps({"items": [{"unit_price": 110, "line_total": 1100}]}), encoding="utf-8")

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "MANUAL_PRODUCTION_ROOT", manual_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", runtime_root / "live_rfqs.json")
    monkeypatch.setattr(module, "SOURCE_BUNDLE_ROOT", source_root)
    monkeypatch.setattr(module, "SUBMISSION_PACKAGE_ROOT", packages_root)
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", manual_root / "daily_pilot_loop_report.json")
    monkeypatch.setattr(module, "build_controlled_operation_readiness_report", lambda limit=20: {
        "controlled_operation_ready": True,
        "thresholds": {"readiness_score": 100.0},
        "pilot_summary": {"total_runs": 2, "successful_runs": 2, "failed_runs": 0},
    })

    captured = {}

    def _fake_run_supervised_pilot_week(**kwargs):
        captured.update(kwargs)
        return {
            "dry_run_status": "pending_human_approval",
            "quote_pack_quality_status": "approval_ready",
            "approval_status": "recorded",
            "proof_status": "recorded",
            "next_step": "pilot flow complete",
            "manual_approval_recorded": True,
            "manual_submission_recorded": True,
        }

    monkeypatch.setattr(module, "run_supervised_pilot_week", _fake_run_supervised_pilot_week)

    payload = module.run_daily_pilot_loop(
        workspace_root=str(manual_root),
        operator_name="Supervisor",
        queue_file=str(runtime_root / "live_rfqs.json"),
        report_file=str(manual_root / "daily_pilot_loop_report.json"),
        allow_repeat=False,
    )

    assert payload["selected"]["tender_id"] == "RFQ_NEW_FRESH"
    assert captured["tender_id"] == "RFQ_NEW_FRESH"
    assert captured["pricing_file"] == str(new_pricing)


def test_run_daily_pilot_loop_prefers_fresh_candidate(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_daily_pilot_loop.py"), "run_daily_pilot_loop")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    source_root = manual_root / "source_bundle_repairs"
    packages_root = manual_root / "submission_packages"
    source_root.mkdir(parents=True, exist_ok=True)
    packages_root.mkdir(parents=True, exist_ok=True)
    _seed_queue(runtime_root)

    # Mark the first RFQ as already completed so the selector prefers the fresh one.
    (manual_root / "pilot_runs.jsonl").write_text(
        json.dumps({"tender_id": "RFQ_OLD", "outcome": "completed", "status": "recorded"}) + "\n",
        encoding="utf-8",
    )

    fresh_bundle = source_root / "RFQ_NEW"
    fresh_bundle.mkdir(parents=True, exist_ok=True)
    fresh_bundle.joinpath("RFQ_NEW_overview.txt").write_text("overview", encoding="utf-8")
    fresh_package = packages_root / "RFQ_NEW"
    fresh_package.mkdir(parents=True, exist_ok=True)
    fresh_pricing = fresh_package / "RFQ_NEW__manual_pricing.json"
    fresh_pricing.write_text(json.dumps({"items": [{"unit_price": 120, "line_total": 1200}]}), encoding="utf-8")

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "MANUAL_PRODUCTION_ROOT", manual_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", runtime_root / "live_rfqs.json")
    monkeypatch.setattr(module, "SOURCE_BUNDLE_ROOT", source_root)
    monkeypatch.setattr(module, "SUBMISSION_PACKAGE_ROOT", packages_root)
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", manual_root / "daily_pilot_loop_report.json")
    monkeypatch.setattr(module, "build_controlled_operation_readiness_report", lambda limit=20: {
        "controlled_operation_ready": True,
        "thresholds": {"readiness_score": 100.0},
        "pilot_summary": {"total_runs": 1, "successful_runs": 1, "failed_runs": 0},
    })

    captured = {}

    def _fake_run_supervised_pilot_week(**kwargs):
        captured.update(kwargs)
        return {
            "dry_run_status": "pending_human_approval",
            "quote_pack_quality_status": "approval_ready",
            "approval_status": "recorded",
            "proof_status": "recorded",
            "next_step": "pilot flow complete",
            "manual_approval_recorded": True,
            "manual_submission_recorded": True,
        }

    monkeypatch.setattr(module, "run_supervised_pilot_week", _fake_run_supervised_pilot_week)

    payload = module.run_daily_pilot_loop(
        workspace_root=str(manual_root),
        operator_name="Supervisor",
        queue_file=str(runtime_root / "live_rfqs.json"),
        report_file=str(manual_root / "daily_pilot_loop_report.json"),
    )

    assert payload["selected"]["tender_id"] == "RFQ_NEW"
    assert payload["selected"]["repeat_run"] is False
    assert payload["report"]["candidate_mode"] == "fresh"


def test_run_daily_pilot_loop_skips_unpriced_candidate(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_daily_pilot_loop.py"), "run_daily_pilot_loop_skip_zero_pricing")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    source_root = manual_root / "source_bundle_repairs"
    packages_root = manual_root / "submission_packages"
    source_root.mkdir(parents=True, exist_ok=True)
    packages_root.mkdir(parents=True, exist_ok=True)

    queue = {
        "status": "ok",
        "updated_at": "2026-06-09T00:00:00+00:00",
        "count": 2,
        "items": [
            {
                "rfq_id": "RFQ_BAD",
                "title": "Bad Pricing",
                "source_name": "Smoke Fixture",
                "status": "live",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
                "created_at": "2026-06-09T00:10:00+00:00",
            },
            {
                "rfq_id": "RFQ_GOOD",
                "title": "Good Pricing",
                "source_name": "Smoke Fixture",
                "status": "live",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
                "created_at": "2026-06-09T00:05:00+00:00",
            },
        ],
    }
    (runtime_root / "live_rfqs.json").write_text(json.dumps(queue), encoding="utf-8")

    bad_bundle = source_root / "RFQ_BAD"
    bad_bundle.mkdir(parents=True, exist_ok=True)
    bad_bundle.joinpath("RFQ_BAD_overview.txt").write_text("overview", encoding="utf-8")
    bad_package = packages_root / "RFQ_BAD"
    bad_package.mkdir(parents=True, exist_ok=True)
    (bad_package / "RFQ_BAD__manual_pricing.json").write_text(json.dumps({"items": [{"unit_price": 0, "line_total": 0}]}), encoding="utf-8")

    good_bundle = source_root / "RFQ_GOOD"
    good_bundle.mkdir(parents=True, exist_ok=True)
    good_bundle.joinpath("RFQ_GOOD_overview.txt").write_text("overview", encoding="utf-8")
    good_package = packages_root / "RFQ_GOOD"
    good_package.mkdir(parents=True, exist_ok=True)
    good_pricing = good_package / "RFQ_GOOD__manual_pricing.json"
    good_pricing.write_text(json.dumps({"items": [{"unit_price": 100, "line_total": 1000}]}), encoding="utf-8")

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "MANUAL_PRODUCTION_ROOT", manual_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", runtime_root / "live_rfqs.json")
    monkeypatch.setattr(module, "SOURCE_BUNDLE_ROOT", source_root)
    monkeypatch.setattr(module, "SUBMISSION_PACKAGE_ROOT", packages_root)
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", manual_root / "daily_pilot_loop_report.json")
    monkeypatch.setattr(module, "build_controlled_operation_readiness_report", lambda limit=20: {
        "controlled_operation_ready": True,
        "thresholds": {"readiness_score": 100.0},
        "pilot_summary": {"total_runs": 1, "successful_runs": 1, "failed_runs": 0},
    })

    captured = {}

    def _fake_run_supervised_pilot_week(**kwargs):
        captured.update(kwargs)
        return {
            "dry_run_status": "pending_human_approval",
            "quote_pack_quality_status": "approval_ready",
            "approval_status": "recorded",
            "proof_status": "recorded",
            "next_step": "pilot flow complete",
            "manual_approval_recorded": True,
            "manual_submission_recorded": True,
        }

    monkeypatch.setattr(module, "run_supervised_pilot_week", _fake_run_supervised_pilot_week)

    payload = module.run_daily_pilot_loop(
        workspace_root=str(manual_root),
        operator_name="Supervisor",
        queue_file=str(runtime_root / "live_rfqs.json"),
        report_file=str(manual_root / "daily_pilot_loop_report.json"),
        allow_repeat=False,
    )

    assert payload["selected"]["tender_id"] == "RFQ_GOOD"
    assert captured["tender_id"] == "RFQ_GOOD"
    assert payload["report"]["selection_summary"]["fresh_runnable_candidates"] == 1
    assert captured["tender_root"] == str(good_bundle)
    assert captured["pricing_file"] == str(good_pricing)
    assert captured["record_proof"] is True
    assert payload["report"]["next_step"] == "pilot flow complete"
    assert payload["report"]["operator_actions_next"]
    report_path = manual_root / "daily_pilot_loop_report.json"
    assert report_path.exists()
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["selected"]["tender_id"] == "RFQ_GOOD"
    assert saved["report"]["operator_actions_next"]


def test_run_daily_pilot_loop_reports_when_no_candidate_exists(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_daily_pilot_loop.py"), "run_daily_pilot_loop_empty")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    manual_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "live_rfqs.json").write_text(json.dumps({"status": "ok", "count": 0, "items": []}), encoding="utf-8")

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "MANUAL_PRODUCTION_ROOT", manual_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", runtime_root / "live_rfqs.json")
    monkeypatch.setattr(module, "SOURCE_BUNDLE_ROOT", manual_root / "source_bundle_repairs")
    monkeypatch.setattr(module, "SUBMISSION_PACKAGE_ROOT", manual_root / "submission_packages")
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", manual_root / "daily_pilot_loop_report.json")
    monkeypatch.setattr(module, "build_controlled_operation_readiness_report", lambda limit=20: {
        "controlled_operation_ready": False,
        "thresholds": {"readiness_score": 70.0},
        "pilot_summary": {"total_runs": 0, "successful_runs": 0, "failed_runs": 0},
    })

    payload = module.run_daily_pilot_loop(
        workspace_root=str(manual_root),
        operator_name="Supervisor",
        allow_repeat=False,
        queue_file=str(runtime_root / "live_rfqs.json"),
        report_file=str(manual_root / "daily_pilot_loop_report.json"),
    )

    assert payload["selected"] is None
    assert payload["report"]["status"] == "no_candidate"
    assert payload["report"]["selection_summary"]["fresh_runnable_candidates"] == 0
    assert (manual_root / "daily_pilot_loop_report.json").exists()
    assert payload["report"]["operator_actions_next"]


def test_run_daily_pilot_loop_fresh_only_rejects_repeat_fallback(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_daily_pilot_loop.py"), "run_daily_pilot_loop_fresh_only")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    source_root = manual_root / "source_bundle_repairs"
    packages_root = manual_root / "submission_packages"
    source_root.mkdir(parents=True, exist_ok=True)
    packages_root.mkdir(parents=True, exist_ok=True)
    _seed_queue(runtime_root)

    repeat_bundle = source_root / "RFQ_OLD"
    repeat_bundle.mkdir(parents=True, exist_ok=True)
    repeat_bundle.joinpath("RFQ_OLD_overview.txt").write_text("overview", encoding="utf-8")
    repeat_package = packages_root / "RFQ_OLD"
    repeat_package.mkdir(parents=True, exist_ok=True)
    repeat_pricing = repeat_package / "RFQ_OLD__manual_pricing.json"
    repeat_pricing.write_text(json.dumps({"items": [{"unit_price": 80, "line_total": 800}]}), encoding="utf-8")

    (manual_root / "pilot_runs.jsonl").write_text(
        json.dumps({"tender_id": "RFQ_OLD", "outcome": "completed", "status": "recorded"}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "MANUAL_PRODUCTION_ROOT", manual_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", runtime_root / "live_rfqs.json")
    monkeypatch.setattr(module, "SOURCE_BUNDLE_ROOT", source_root)
    monkeypatch.setattr(module, "SUBMISSION_PACKAGE_ROOT", packages_root)
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", manual_root / "daily_pilot_loop_report.json")
    monkeypatch.setattr(module, "build_controlled_operation_readiness_report", lambda limit=20: {
        "controlled_operation_ready": True,
        "thresholds": {"readiness_score": 100.0},
        "pilot_summary": {"total_runs": 1, "successful_runs": 1, "failed_runs": 0},
    })

    payload = module.run_daily_pilot_loop(
        workspace_root=str(manual_root),
        operator_name="Supervisor",
        allow_repeat=False,
        allow_bundle_fallback=False,
        queue_file=str(runtime_root / "live_rfqs.json"),
        report_file=str(manual_root / "daily_pilot_loop_report.json"),
    )

    assert payload["selected"] is None
    assert payload["report"]["status"] == "no_candidate"
    assert payload["report"]["selection_summary"]["repeat_runnable_candidates"] == 1


def test_run_daily_pilot_loop_rotates_repeat_candidates_with_cursor(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_daily_pilot_loop.py"), "run_daily_pilot_loop_cursor")
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    source_root = manual_root / "source_bundle_repairs"
    packages_root = manual_root / "submission_packages"
    source_root.mkdir(parents=True, exist_ok=True)
    packages_root.mkdir(parents=True, exist_ok=True)

    queue = {
        "status": "ok",
        "updated_at": "2026-06-09T00:00:00+00:00",
        "count": 2,
        "items": [
            {
                "rfq_id": "RFQ_CURSOR_OLD",
                "title": "Cursor Old",
                "source_name": "Smoke Fixture",
                "status": "Quote Ready",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
                "created_at": "2026-06-09T00:10:00+00:00",
            },
            {
                "rfq_id": "RFQ_CURSOR_NEW",
                "title": "Cursor New",
                "source_name": "Smoke Fixture",
                "status": "Quote Ready",
                "pipeline_status": "quote_ready_validated",
                "eligible": True,
                "quote_ready": True,
                "created_at": "2026-06-09T00:20:00+00:00",
            },
        ],
    }
    (runtime_root / "live_rfqs.json").write_text(json.dumps(queue), encoding="utf-8")
    (manual_root / "pilot_runs.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"tender_id": "RFQ_CURSOR_OLD", "outcome": "completed", "status": "recorded"}),
                json.dumps({"tender_id": "RFQ_CURSOR_NEW", "outcome": "completed", "status": "recorded"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    for tender_id, price in [("RFQ_CURSOR_OLD", 90), ("RFQ_CURSOR_NEW", 110)]:
        bundle = source_root / tender_id
        bundle.mkdir(parents=True, exist_ok=True)
        bundle.joinpath(f"{tender_id}_overview.txt").write_text("overview", encoding="utf-8")
        package = packages_root / tender_id
        package.mkdir(parents=True, exist_ok=True)
        package.joinpath(f"{tender_id}__manual_pricing.json").write_text(
            json.dumps({"items": [{"unit_price": price, "line_total": price * 10}]}),
            encoding="utf-8",
        )

    cursor_path = manual_root / "daily_pilot_loop_cursor.json"
    cursor_path.write_text(json.dumps({"last_selected_tender_id": "RFQ_CURSOR_NEW"}), encoding="utf-8")

    monkeypatch.setattr(module, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(module, "MANUAL_PRODUCTION_ROOT", manual_root)
    monkeypatch.setattr(module, "LIVE_QUEUE_PATH", runtime_root / "live_rfqs.json")
    monkeypatch.setattr(module, "SOURCE_BUNDLE_ROOT", source_root)
    monkeypatch.setattr(module, "SUBMISSION_PACKAGE_ROOT", packages_root)
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", manual_root / "daily_pilot_loop_report.json")
    monkeypatch.setattr(module, "build_controlled_operation_readiness_report", lambda limit=20: {
        "controlled_operation_ready": True,
        "thresholds": {"readiness_score": 100.0},
        "pilot_summary": {"total_runs": 2, "successful_runs": 2, "failed_runs": 0},
    })

    captured = {}

    def _fake_run_supervised_pilot_week(**kwargs):
        captured.update(kwargs)
        return {
            "dry_run_status": "pending_human_approval",
            "quote_pack_quality_status": "approval_ready",
            "approval_status": "recorded",
            "proof_status": "recorded",
            "next_step": "pilot flow complete",
            "manual_approval_recorded": True,
            "manual_submission_recorded": True,
        }

    monkeypatch.setattr(module, "run_supervised_pilot_week", _fake_run_supervised_pilot_week)

    payload = module.run_daily_pilot_loop(
        workspace_root=str(manual_root),
        operator_name="Supervisor",
        queue_file=str(runtime_root / "live_rfqs.json"),
        report_file=str(manual_root / "daily_pilot_loop_report.json"),
    )

    assert payload["selected"]["tender_id"] == "RFQ_CURSOR_OLD"
    assert captured["tender_id"] == "RFQ_CURSOR_OLD"
    saved_cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert saved_cursor["last_selected_tender_id"] == "RFQ_CURSOR_OLD"
