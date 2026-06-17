from __future__ import annotations

import json
from pathlib import Path

from app.testing import dry_dispatch_evidence


class _Harness:
    def __init__(self, results):
        self._results = results

    def run_fixture(self, fixture_path: str):
        return self._results[Path(fixture_path).name]


def test_build_dry_dispatch_cycle_tracks_requested_metrics(tmp_path, monkeypatch) -> None:
    fixture_a = tmp_path / "valid_a.json"
    fixture_b = tmp_path / "valid_b.json"
    fixture_c = tmp_path / "missing_source.json"
    for path in (fixture_a, fixture_b, fixture_c):
        path.write_text("{}", encoding="utf-8")

    cycle = dry_dispatch_evidence.build_dry_dispatch_cycle(
        [fixture_a, fixture_b, fixture_c],
        tier_label="tier_10",
        week_ending="2026-06-07",
        manifest_metadata={
            "fixtures": [
                {"path": str(fixture_a), "expected_outcome": "pass"},
                {"path": str(fixture_b), "expected_outcome": "pass"},
                {"path": str(fixture_c), "expected_outcome": "refused"},
            ]
        },
        harness=_Harness(
            {
                "valid_a.json": {
                    "passed": True,
                    "final_stage": "proof_recorded",
                    "manual_submission_preserved": True,
                    "persistence_verified": True,
                    "audit_verified": True,
                    "quality_summary": {"quote_pack": {"quality_score": 0.92, "quote_pack": {"quote_pack_ready": True}}},
                    "tender_id": "A",
                },
                "valid_b.json": {
                    "passed": True,
                    "final_stage": "proof_recorded",
                    "manual_submission_preserved": True,
                    "persistence_verified": True,
                    "audit_verified": True,
                    "quality_summary": {"quote_pack": {"quality_score": 0.88, "quote_pack": {"quote_pack_ready": True}}},
                    "tender_id": "B",
                    "retry_count": 1,
                },
                "missing_source.json": {
                    "passed": False,
                    "final_stage": "refused",
                    "manual_submission_preserved": False,
                    "persistence_verified": False,
                    "audit_verified": False,
                    "blockers": ["missing source document"],
                    "quality_summary": {"quote_pack": {"quality_score": 0.0, "quote_pack": {"quote_pack_ready": False}}},
                    "tender_id": "C",
                    "rollback_count": 1,
                },
            }
        ),
    )

    assert cycle["summary"]["fixture_count"] == 3
    assert cycle["summary"]["pass_rate"] == 100.0
    assert cycle["summary"]["retry_rate"] == 33.33
    assert cycle["summary"]["rollback_rate"] == 33.33
    assert cycle["summary"]["top_failure_category"] == "None"
    assert cycle["summary"]["production_ready_status"] == "hold"
    assert cycle["defect_register"]["failure_counts"] == {}
    refused = next(item for item in cycle["fixtures"] if item["tender_id"] == "C")
    assert refused["expected_outcome"] == "refused"
    assert refused["actual_outcome"] == "refused"
    assert refused["consistency_matched"] is True
    assert refused["gate_score"] == 100.0
    assert refused["confidence_score"] == 100.0


def test_unexpected_refusal_remains_a_failure(tmp_path) -> None:
    fixture = tmp_path / "unexpected_refusal.json"
    fixture.write_text("{}", encoding="utf-8")
    summary = dry_dispatch_evidence.summarize_fixture_result(
        fixture,
        {
            "passed": False,
            "final_stage": "refused",
            "blockers": ["missing source document"],
            "quality_summary": {"quote_pack": {"quality_score": 0.0, "quote_pack": {"quote_pack_ready": False}}},
            "tender_id": "X",
        },
        manifest_entry={"path": str(fixture), "expected_outcome": "pass"},
    )
    assert summary["consistency_matched"] is False
    assert summary["gate_score"] == 0.0


def test_append_and_evaluate_live_submission_gate(tmp_path, monkeypatch) -> None:
    registry_dir = tmp_path / "runtime" / "execution_evidence"
    monkeypatch.setattr(dry_dispatch_evidence, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(dry_dispatch_evidence, "EVIDENCE_DIR", registry_dir)
    monkeypatch.setattr(dry_dispatch_evidence, "DRY_DISPATCH_REGISTRY_FILE", registry_dir / "weekly_dry_dispatch_registry.jsonl")
    monkeypatch.setattr(dry_dispatch_evidence, "LATEST_DRY_DISPATCH_REPORT_FILE", registry_dir / "latest_dry_dispatch_report.json")

    for week in range(4):
        cycle = {
            "week_ending": f"2026-06-0{week + 1}",
            "tier_label": "tier_25",
            "summary": {
                "pass_rate": 95.0,
                "confidence_score": 91.0,
                "gate_score": 90.0,
                "rollback_rate": 0.0,
                "critical_failures": 0,
            },
        }
        dry_dispatch_evidence.append_dry_dispatch_cycle(cycle)

    recorded = dry_dispatch_evidence.read_dry_dispatch_cycles()
    assert len(recorded) == 4
    latest = json.loads(dry_dispatch_evidence.LATEST_DRY_DISPATCH_REPORT_FILE.read_text(encoding="utf-8"))
    assert latest["week_ending"] == "2026-06-04"

    gate = dry_dispatch_evidence.evaluate_live_submission_gate(recorded, stable_weeks_required=4)
    assert gate["status"] == "eligible_for_supervised_live"
    assert gate["stable_weeks_observed"] == 4


def test_duplicate_weekly_run_marks_previous_cycle_superseded(tmp_path, monkeypatch) -> None:
    registry_dir = tmp_path / "runtime" / "execution_evidence"
    monkeypatch.setattr(dry_dispatch_evidence, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(dry_dispatch_evidence, "EVIDENCE_DIR", registry_dir)
    monkeypatch.setattr(dry_dispatch_evidence, "DRY_DISPATCH_REGISTRY_FILE", registry_dir / "weekly_dry_dispatch_registry.jsonl")
    monkeypatch.setattr(dry_dispatch_evidence, "LATEST_DRY_DISPATCH_REPORT_FILE", registry_dir / "latest_dry_dispatch_report.json")

    first = dry_dispatch_evidence.append_dry_dispatch_cycle(
        {
            "cycle_label": "weekly_dry_dispatch",
            "tier_label": "tier_10",
            "week_ending": "2026-06-07",
            "summary": {"pass_rate": 70.0, "confidence_score": 68.25, "gate_score": 63.0, "rollback_rate": 0.0, "critical_failures": 1},
        }
    )
    second = dry_dispatch_evidence.append_dry_dispatch_cycle(
        {
            "cycle_label": "weekly_dry_dispatch",
            "tier_label": "tier_10",
            "week_ending": "2026-06-07",
            "summary": {"pass_rate": 100.0, "confidence_score": 98.25, "gate_score": 93.0, "rollback_rate": 0.0, "critical_failures": 0},
        }
    )

    active = dry_dispatch_evidence.read_dry_dispatch_cycles()
    all_cycles = dry_dispatch_evidence.read_dry_dispatch_cycles(include_superseded=True)
    assert len(active) == 1
    assert active[0]["run_id"] == second["run_id"]
    assert active[0]["corrects_run_id"] == first["run_id"]
    superseded = next(item for item in all_cycles if item["run_id"] == first["run_id"])
    assert superseded["run_status"] == "superseded"
    assert superseded["superseded_by_run_id"] == second["run_id"]


def test_normalize_legacy_duplicate_records_and_gate_counts(tmp_path, monkeypatch) -> None:
    registry_dir = tmp_path / "runtime" / "execution_evidence"
    monkeypatch.setattr(dry_dispatch_evidence, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(dry_dispatch_evidence, "EVIDENCE_DIR", registry_dir)
    monkeypatch.setattr(dry_dispatch_evidence, "DRY_DISPATCH_REGISTRY_FILE", registry_dir / "weekly_dry_dispatch_registry.jsonl")
    monkeypatch.setattr(dry_dispatch_evidence, "LATEST_DRY_DISPATCH_REPORT_FILE", registry_dir / "latest_dry_dispatch_report.json")

    legacy_records = [
        {
            "cycle_label": "weekly_dry_dispatch",
            "tier_label": "tier_10",
            "week_ending": "2026-06-07",
            "generated_at": "2026-06-07T01:26:23.152976+00:00",
            "summary": {"pass_rate": 70.0, "confidence_score": 68.25, "gate_score": 63.0, "rollback_rate": 0.0, "critical_failures": 1},
        },
        {
            "cycle_label": "weekly_dry_dispatch",
            "tier_label": "tier_10",
            "week_ending": "2026-06-07",
            "generated_at": "2026-06-07T01:43:45.473567+00:00",
            "summary": {"pass_rate": 100.0, "confidence_score": 98.25, "gate_score": 93.0, "rollback_rate": 0.0, "critical_failures": 0},
        },
        {
            "cycle_label": "weekly_dry_dispatch",
            "tier_label": "tier_10",
            "week_ending": "2026-06-14",
            "generated_at": "2026-06-07T10:54:34.828863+00:00",
            "summary": {"pass_rate": 100.0, "confidence_score": 98.25, "gate_score": 93.0, "rollback_rate": 0.0, "critical_failures": 0},
        },
    ]
    dry_dispatch_evidence._write_jsonl_records(dry_dispatch_evidence.DRY_DISPATCH_REGISTRY_FILE, legacy_records)

    active = dry_dispatch_evidence.read_dry_dispatch_cycles()
    all_cycles = dry_dispatch_evidence.read_dry_dispatch_cycles(include_superseded=True)
    assert len(active) == 2
    old = next(item for item in all_cycles if item["week_ending"] == "2026-06-07" and item["summary"]["pass_rate"] == 70.0)
    corrected = next(item for item in all_cycles if item["week_ending"] == "2026-06-07" and item["summary"]["pass_rate"] == 100.0)
    assert old["run_status"] == "superseded"
    assert corrected["run_status"] == "active"
    gate = dry_dispatch_evidence.evaluate_live_submission_gate(active, stable_weeks_required=4)
    assert gate["status"] == "hold"
    assert gate["qualifying_active_weeks"] == 2


def test_manifest_helpers_resolve_tier_files(tmp_path) -> None:
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_dir / "tier_10.json"
    manifest_path.write_text(
        json.dumps(
            {
                "tier_label": "tier_10",
                "fixtures": [
                    {"path": "/tmp/a.json"},
                    "/tmp/b.json",
                ],
            }
        ),
        encoding="utf-8",
    )

    resolved = dry_dispatch_evidence.resolve_tier_manifest_path("tier_10", manifests_dir)
    assert resolved == manifest_path
    metadata = dry_dispatch_evidence.read_fixture_manifest(manifest_path)
    fixtures = dry_dispatch_evidence.load_fixture_manifest(manifest_path)
    assert metadata["tier_label"] == "tier_10"
    assert [str(item) for item in fixtures] == ["/tmp/a.json", "/tmp/b.json"]
