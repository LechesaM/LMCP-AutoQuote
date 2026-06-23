from __future__ import annotations

import importlib
import json
from pathlib import Path


class _DummyStabilityService:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def latest_stability(self):
        return {
            "status": "ok",
            "stability_score": 100.0,
            "stability_grade": "stable",
            "stability": {"cycle_count": 3, "rehearsal_count": 1},
            "warning_indicators": {},
            "drift_warnings": [],
            "latest_cycle": {"generated_at": "2026-06-23T11:30:52+00:00"},
        }

    def stability_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "cycles": [{"cycle_id": "cycle-1"}],
            "rehearsals": [{"run_id": "rehearsal-1"}],
            "stability": {"cycle_count": 3, "rehearsal_count": 1},
            "warning_indicators": {},
        }


def _write_cycle(root: Path, cycle_id: str, generated_at: str, readiness_score: float = 100.0) -> None:
    cycle_dir = root / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "governance_export": {
            "readiness_summary": {
                "readiness_score": readiness_score,
                "readiness_grade": "ready" if readiness_score >= 85 else "watch",
                "cadence": {"runs_last_7_days": 1, "average_gap_hours": 0.0},
            }
        },
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_export(root: Path, export_id: str, generated_at: str, readiness_score: float = 100.0) -> None:
    export_dir = root / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "export_id": export_id,
        "generated_at": generated_at,
        "readiness_summary": {
            "readiness_score": readiness_score,
            "readiness_grade": "ready" if readiness_score >= 85 else "watch",
            "cadence": {"runs_last_7_days": 1, "average_gap_hours": 0.0},
        },
        "rehearsal_history_summary": {"runs": [{"run_id": "rehearsal-1"}]},
    }
    (export_dir / "pilot_rehearsal_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_pilot_cadence_service_reports_compliant_schedule(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_cadence_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-1", "2026-06-23T11:30:52+00:00", 100.0)
    _write_cycle(cycle_root, "cycle-2", "2026-06-20T11:30:52+00:00", 100.0)
    _write_export(export_root, "export-1", "2026-06-23T11:09:09+00:00", 100.0)
    monkeypatch.setattr(module, "OperationalStabilityService", _DummyStabilityService)

    service = module.PilotCadenceService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_cadence()
    history = service.cadence_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["cadence_score"] >= 85
    assert latest["cadence"]["pilot_cycle_cadence"]["compliant"] is True
    assert latest["cadence"]["governance_review_cadence"]["compliant"] is True
    assert latest["cadence"]["stability_trend_checkpoints"]["cadence_compliant"] is True
    assert history["count"] == len(history["checkpoints"])
    assert history["cycles"]
    assert history["governance_reviews"]


def test_pilot_cadence_service_warns_on_overdue_items(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_cadence_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-old", "2026-06-01T11:30:52+00:00", 100.0)
    _write_export(export_root, "export-old", "2026-06-01T11:09:09+00:00", 100.0)
    monkeypatch.setattr(module, "OperationalStabilityService", _DummyStabilityService)

    service = module.PilotCadenceService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_cadence()

    assert latest["status"] == "watch"
    assert latest["warning_indicators"]["missed_cycle_warning"] is True
    assert latest["warning_indicators"]["overdue_governance_review_warning"] is True
