from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from app.core import workflow_state_engine
from app.core.runtime_paths import get_runtime_paths
from app.persistence import db as persistence_db
from app.services import audit_trail_service, manual_approval_service, submission_proof_service, submission_review_service


def _patch_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    get_runtime_paths.cache_clear()

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    monkeypatch.setattr(workflow_state_engine, "_emit_audit_event", lambda **_: None)

    monkeypatch.setattr(manual_approval_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(manual_approval_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(manual_approval_service, "APPROVAL_LOG_FILE", manual_dir / "approvals.jsonl")

    monkeypatch.setattr(submission_review_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(submission_review_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(submission_review_service, "SUBMISSION_REVIEW_LOG_FILE", manual_dir / "submission_reviews.jsonl")

    monkeypatch.setattr(submission_proof_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(submission_proof_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(submission_proof_service, "SUBMISSION_PROOF_LOG_FILE", manual_dir / "submission_proofs.jsonl")

    monkeypatch.setattr(audit_trail_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", runtime_dir / "audit_trail")
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", runtime_dir / "audit_trail" / "audit_events.json")
    audit_trail_service.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _table_count(path: Path, table: str) -> int:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0] if row else 0)
    finally:
        connection.close()


def test_db_initializes_correctly(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _patch_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"

    created = persistence_db.initialize_database()

    assert created == db_path
    assert db_path.exists()
    connection = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert "workflow_state_records" in tables
    assert "workflow_event_records" in tables
    assert "audit_event_entities" in tables


def test_workflow_event_and_state_persist(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _patch_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"

    state = workflow_state_engine.record_transition(
        "T-100",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "system",
        "discover",
    )

    assert state.stage.value == "extracted"
    assert _table_count(db_path, "workflow_event_records") == 1
    assert _table_count(db_path, "workflow_state_records") == 1
    assert workflow_state_engine.get_current_state("T-100").stage.value == "extracted"


def test_approval_review_proof_persist(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _patch_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"

    approval = manual_approval_service.build_manual_approval_record(
        {"tender_id": "T-200", "quote_pack_quality_status": "approval_ready", "warnings": []},
        tender_id="T-200",
        tender_root=str(tmp_path / "tender"),
        pricing_file=str(tmp_path / "tender" / "pricing.json"),
        operator_name="Operator A",
        confirm_approval=True,
    )
    manual_approval_service.append_manual_approval(approval)

    review = {
        "tender_id": "T-200",
        "tender_root": str(tmp_path / "tender"),
        "pricing_file": str(tmp_path / "tender" / "pricing.json"),
        "operator_name": "Reviewer",
        "submission_review_ready": True,
        "review_blockers": [],
        "status": "review_ready",
    }
    submission_review_service.append_submission_review(review)

    proof = {
        "tender_id": "T-200",
        "tender_root": str(tmp_path / "tender"),
        "portal_name": "eTenders",
        "submission_reference": "SUB-200",
        "submitted_by": "Operator A",
        "proof_file": str(tmp_path / "tender" / "proof.pdf"),
        "proof_file_present": True,
        "submission_review_status": "review_ready",
        "submission_review_ready": True,
        "final_submission_attempted": False,
        "manual_submission_recorded": True,
        "blockers": [],
        "status": "recorded",
    }
    submission_proof_service.append_submission_proof(proof)

    assert _table_count(db_path, "approval_record_entities") == 1
    assert _table_count(db_path, "submission_review_entities") == 1
    assert _table_count(db_path, "submission_proof_entities") == 1


def test_audit_event_persists(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _patch_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"

    async def _noop(**_: object) -> None:
        return None

    monkeypatch.setattr(audit_trail_service, "publish_dashboard_event", _noop)
    asyncio.run(
        audit_trail_service.record_audit_event(
            event_type="workflow_transition",
            source="workflow-state-engine",
            severity="info",
            title="Workflow transition",
            message="recorded",
            buyer_rfq_number="T-300",
            payload={"tender_id": "T-300"},
        )
    )

    assert _table_count(db_path, "audit_event_entities") == 1


def test_db_unavailable_falls_back_safely(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _patch_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(persistence_db, "get_connection", _raise)

    state = workflow_state_engine.record_transition(
        "T-400",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "system",
        "discover",
    )

    assert state.stage.value == "extracted"
    assert workflow_state_engine.WORKFLOW_EVENT_LOG_FILE.exists()
    assert workflow_state_engine.WORKFLOW_STATE_LOG_FILE.exists()
    assert not db_path.exists() or _table_count(db_path, "workflow_state_records") == 0


def test_jsonl_compatibility_preserved(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _patch_runtime(monkeypatch, tmp_path)

    state = workflow_state_engine.record_transition(
        "T-500",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "system",
        "discover",
    )

    assert state.stage.value == "extracted"
    events = workflow_state_engine.WORKFLOW_EVENT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    states = workflow_state_engine.WORKFLOW_STATE_LOG_FILE.read_text(encoding="utf-8").splitlines()
    assert len(events) == 1
    assert len(states) == 1
    assert json.loads(events[0])["to_stage"] == "extracted"
    assert json.loads(states[0])["stage"] == "extracted"


def test_append_only_behavior_preserved(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)

    workflow_state_engine.record_transition(
        "T-600",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "system",
        "discover",
    )
    first_events = workflow_state_engine.WORKFLOW_EVENT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    first_states = workflow_state_engine.WORKFLOW_STATE_LOG_FILE.read_text(encoding="utf-8").splitlines()

    workflow_state_engine.record_transition(
        "T-600",
        workflow_state_engine.WorkflowStage.EXTRACTED,
        workflow_state_engine.WorkflowStage.EVALUATED,
        "system",
        "extract",
    )
    second_events = workflow_state_engine.WORKFLOW_EVENT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    second_states = workflow_state_engine.WORKFLOW_STATE_LOG_FILE.read_text(encoding="utf-8").splitlines()

    assert len(second_events) == len(first_events) + 1
    assert len(second_states) == len(first_states) + 1
    assert second_events[: len(first_events)] == first_events
    assert second_states[: len(first_states)] == first_states


def test_latest_workflow_state_retrieval_works(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)

    workflow_state_engine.record_transition(
        "T-700",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "system",
        "discover",
    )
    workflow_state_engine.record_transition(
        "T-700",
        workflow_state_engine.WorkflowStage.EXTRACTED,
        workflow_state_engine.WorkflowStage.EVALUATED,
        "system",
        "extract",
    )

    assert workflow_state_engine.get_current_state("T-700").stage.value == "evaluated"
