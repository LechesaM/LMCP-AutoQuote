from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.dashboard import dashboard_service
from app.monitoring.metrics_service import reset_test_metrics
from app.persistence import db as persistence_db
from app.persistence.repositories import reset_persistence_health
from app.services import audit_trail_service
from app.testing.e2e_rfq_harness import E2ERFQHarness
from app.testing.failure_injection import (
    simulate_db_write_unavailable,
    simulate_interrupted_lifecycle,
    simulate_invalid_transition,
    simulate_malformed_json_fixture,
    simulate_missing_pricing_file,
    simulate_missing_quote_pack,
    simulate_missing_source_file,
)
from app.testing.readiness_report import build_readiness_report, render_readiness_report_text
from app.testing.workflow_replay import replay_workflow_history
from app.domain.workflow import WorkflowStage


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "rfqs"


def _prepare_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audit_trail").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_OBSERVABILITY_ENABLED", "1")

    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    reset_test_metrics()
    reset_persistence_health()
    persistence_db._INITIALIZED = False
    persistence_db._INITIALIZED_PATH = None

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")

    monkeypatch.setattr(audit_trail_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", runtime_dir / "audit_trail")
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", runtime_dir / "audit_trail" / "audit_events.json")
    audit_trail_service.AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    async def _noop_publish_dashboard_event(**_: object) -> None:
        return None

    monkeypatch.setattr(audit_trail_service, "publish_dashboard_event", _noop_publish_dashboard_event)
    return runtime_dir


def _append_invalid_transition(tender_id: str, manual_dir: Path) -> None:
    event_path = manual_dir / "workflow_events.jsonl"
    item = {
        "tender_id": tender_id,
        "from_stage": WorkflowStage.EXTRACTED.value,
        "to_stage": WorkflowStage.DISCOVERED.value,
        "actor": "test",
        "reason": "invalid replay event",
        "details": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item) + "\n")


def test_valid_rfq_completes_to_proof_recorded(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")

    assert result["passed"] is True
    assert result["final_stage"] == WorkflowStage.PROOF_RECORDED.value
    assert result["blockers"] == []
    assert result["manual_submission_preserved"] is True
    assert result["persistence_verified"] is True
    assert result["audit_verified"] is True
    assert result["workflow_history"]
    assert "quality_summary" in result
    assert "rfq_extraction" in result["quality_summary"]
    assert any(path.endswith("__quote_pack.pdf") for path in result["artifacts_created"])
    assert any(path.endswith("__quote_pack.json") for path in result["artifacts_created"])
    assert any(path.endswith("_submission_pack_manifest.txt") for path in result["artifacts_created"])


def test_catering_rfq_is_refused(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "excluded_catering_rfq.json")

    assert result["passed"] is False
    assert result["final_stage"] == WorkflowStage.REFUSED.value
    assert "excluded category" in result["blockers"]


def test_below_margin_rfq_is_refused(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "below_margin_rfq.json")

    assert result["passed"] is False
    assert result["final_stage"] == WorkflowStage.REFUSED.value
    assert any("minimum profit" in blocker for blocker in result["blockers"])


def test_missing_source_document_blocks_lifecycle(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "missing_source_document_rfq.json")

    assert result["passed"] is False
    assert result["final_stage"] == WorkflowStage.REFUSED.value
    assert "missing source document" in result["blockers"]


def test_workflow_history_validates_correctly(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")
    replay = replay_workflow_history(result["tender_id"])

    assert replay["passed"] is True
    assert replay["invalid_transitions"] == []
    assert replay["missing_audit_events"] == []


def test_invalid_transition_is_detected(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    manual_dir = runtime_dir / "manual_production"
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")
    _append_invalid_transition(result["tender_id"], manual_dir)

    replay = replay_workflow_history(result["tender_id"])

    assert replay["passed"] is False
    assert replay["invalid_transitions"]


def test_persistence_is_verified(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")

    assert result["persistence_verified"] is True
    db_path = get_runtime_paths().manual_production_db_path
    assert db_path.exists()
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM workflow_state_records").fetchone()
        assert int(row[0]) >= 1
    finally:
        connection.close()


def test_audit_trail_is_verified(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")

    assert result["audit_verified"] is True
    audit_path = audit_trail_service.AUDIT_FILE
    assert audit_path.exists()
    events = json.loads(audit_path.read_text(encoding="utf-8"))
    assert any(item.get("event_type") == "workflow_transition" for item in events)


def test_readiness_report_calculates_score(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    report = build_readiness_report(str(FIXTURES_DIR))
    text = render_readiness_report_text(report)

    assert report["total_fixtures"] == 7
    assert report["passed_fixtures"] == 4
    assert report["refused_fixtures"] == 3
    assert report["failed_fixtures"] == 0
    assert report["production_readiness_score"] > 0
    assert report["manual_production_safety_status"] == "safe"
    assert "Production readiness score" in text


def test_manual_submission_remains_preserved(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")

    assert result["manual_submission_preserved"] is True
    assert result["final_stage"] == WorkflowStage.PROOF_RECORDED.value


def test_no_autonomous_final_submission_occurs(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()

    result = harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")

    assert result["manual_submission_preserved"] is True
    assert not any("final submission" in blocker.lower() for blocker in result["blockers"])


def test_dashboard_summary_reflects_fixture_workflow(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    harness = E2ERFQHarness()
    harness.run_fixture(FIXTURES_DIR / "valid_supply_delivery_rfq.json")

    summary = dashboard_service.get_dashboard_summary(limit=50)

    assert summary["counts_by_stage"][WorkflowStage.PROOF_RECORDED.value] == 1
    assert summary["pending_approvals"] == 0
    assert summary["pending_review_ready"] == 0
    assert summary["pending_proof_capture"] == 0


def test_failure_injection_helpers_return_blockers() -> None:
    assert simulate_missing_source_file("T-1", "/does/not/exist")["blockers"] == ["source file missing"]
    assert simulate_missing_pricing_file("T-2", "/does/not/exist")["blockers"] == ["pricing file missing"]
    assert simulate_db_write_unavailable("T-3")["blockers"] == ["db write unavailable"]
    assert simulate_malformed_json_fixture("T-4")["blockers"] == ["malformed json fixture"]
    assert simulate_invalid_transition("T-5")["blockers"] == ["invalid workflow transition"]
    assert simulate_interrupted_lifecycle("T-6")["interrupted"] is True
    assert simulate_missing_quote_pack("T-7")["blockers"] == ["quote pack missing"]
