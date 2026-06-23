from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_pack(root: Path) -> Path:
    pack_dir = root / "20260623T104726Z-pilot-8f8f874c"
    pack_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pack_id": pack_dir.name,
        "generated_at": "2026-06-23T10:47:26+00:00",
        "summary_counts": {"PASS": 10, "WARN": 0, "FAIL": 0},
        "readiness_summary": {
            "readiness_score": 100.0,
            "readiness_grade": "ready",
            "thresholds": {"readiness_score": 85.0},
            "trend_summary": {"trend": "stable"},
            "cadence": {"runs_last_7_days": 1},
        },
        "rehearsal_history_summary": {
            "count": 1,
            "runs": [{"run_id": "run-1"}],
            "cadence": {"runs_last_7_days": 1},
            "trend_summary": {"trend": "stable"},
        },
        "PASS/WARN/FAIL trends": {"summary": {"PASS": 10, "WARN": 0, "FAIL": 0}},
        "rollback_evidence": {"status": "PASS", "evidence": {"scenario": "rollback_rehearsal"}},
        "queue_stability_evidence": {"status": "PASS", "evidence": {"scenario": "queue_congestion_rehearsal"}},
        "telemetry_health_evidence": {"status": "PASS", "evidence": {"scenario": "telemetry_validation_rehearsal"}},
        "submission_lock_verification": {"status": "PASS", "evidence": {"exists": True}},
        "dry_run_enforcement_verification": {"status": "PASS", "evidence": {"verified": True}},
        "operator_intervention_summary": {"status": "PASS", "evidence": {"operator_intervention_frequency": 0.0}},
        "artifact_paths": {"json": "pilot_evidence_pack.json", "markdown": "pilot_evidence_pack.md"},
    }
    (pack_dir / "pilot_evidence_pack.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (root / "latest_pilot_evidence_pack.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return pack_dir


def test_pilot_evidence_pack_service_exposes_latest_and_review(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_evidence_pack_service")
    root = tmp_path / "runtime" / "staging" / "evidence-packs"
    _write_pack(root)
    monkeypatch.setattr(module, "EVIDENCE_PACK_ROOT", root)

    service = module.PilotEvidencePackService()
    history = service.list_packs(limit=5)
    latest = service.latest_pack()
    review = service.governance_review()

    assert history["count"] == 1
    assert latest["status"] == "ok"
    assert latest["summary"]["readiness_score"] == 100.0
    assert review["pilot_authorization_status"] == "authorized"
    assert review["no_go_indicators"] == []
    assert review["submission_lock_verification"]["status"] == "PASS"
