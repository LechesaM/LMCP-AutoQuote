from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowStage
from app.services import manual_approval_service, submission_proof_service, submission_review_service


def _patch_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()

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
    return runtime_dir


def _advance_to_approval_required(tender_id: str) -> None:
    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "system", "discover")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "system", "extract")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.EVALUATED, WorkflowStage.PRICED, "system", "evaluate")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "system", "price")
    workflow_state_engine.record_transition(
        tender_id,
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        "system",
        "quote generated",
    )


def test_valid_transition_sequence(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-001"

    _advance_to_approval_required(tender_id)
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "op-1", "approved")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVED, WorkflowStage.REVIEW_READY, "op-1", "review ready")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.REVIEW_READY, WorkflowStage.PROOF_RECORDED, "op-1", "proof recorded")

    current = workflow_state_engine.get_current_state(tender_id)
    assert current.stage is WorkflowStage.PROOF_RECORDED
    assert current.tender_id == tender_id


def test_invalid_transition_rejected(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        workflow_state_engine.record_transition(
            "T-002",
            WorkflowStage.DISCOVERED,
            WorkflowStage.PRICED,
            "system",
            "skip stages",
        )


def test_refuse_from_active_stage(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-003"

    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "system", "discover")
    refused = workflow_state_engine.refuse_workflow(tender_id, actor="op-2", reason="manual refusal", details={"note": "blocked"})

    assert refused.stage is WorkflowStage.REFUSED
    assert workflow_state_engine.get_current_state(tender_id).stage is WorkflowStage.REFUSED


def test_archive_from_refused(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-004"

    workflow_state_engine.refuse_workflow(tender_id, actor="op-3", reason="refused", details={})
    archived = workflow_state_engine.archive_workflow(tender_id, actor="op-3", reason="archive refused", details={})

    assert archived.stage is WorkflowStage.ARCHIVED


def test_archive_from_proof_recorded(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-005"

    _advance_to_approval_required(tender_id)
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "system", "approved")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVED, WorkflowStage.REVIEW_READY, "system", "review ready")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.REVIEW_READY, WorkflowStage.PROOF_RECORDED, "system", "proof recorded")
    archived = workflow_state_engine.archive_workflow(tender_id, actor="op-4", reason="archive proof", details={})

    assert archived.stage is WorkflowStage.ARCHIVED


def test_review_ready_requires_approved() -> None:
    with pytest.raises(ValueError):
        workflow_state_engine.assert_can_transition(WorkflowStage.QUOTE_GENERATED, WorkflowStage.REVIEW_READY)


def test_proof_recorded_requires_review_ready() -> None:
    with pytest.raises(ValueError):
        workflow_state_engine.assert_can_transition(WorkflowStage.APPROVED, WorkflowStage.PROOF_RECORDED)


def test_manual_approval_service_records_workflow_transition(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-006"
    _advance_to_approval_required(tender_id)

    record = manual_approval_service.build_manual_approval_record(
        {"tender_id": tender_id, "quote_pack_quality_status": "approval_ready", "warnings": []},
        tender_id=tender_id,
        tender_root=str(tmp_path / "tender"),
        pricing_file=str(tmp_path / "tender" / "pricing.json"),
        operator_name="Operator A",
        confirm_approval=True,
    )
    manual_approval_service.append_manual_approval(record)

    assert workflow_state_engine.get_current_state(tender_id).stage is WorkflowStage.APPROVED
    lines = (tmp_path / "runtime" / "manual_production" / "workflow_state.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["stage"] == "approved"


def test_submission_review_service_records_workflow_transition(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-007"
    _advance_to_approval_required(tender_id)
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "system", "approved")

    record = {
        "tender_id": tender_id,
        "tender_root": str(tmp_path / "tender"),
        "pricing_file": str(tmp_path / "tender" / "pricing.json"),
        "operator_name": "Reviewer",
        "submission_review_ready": True,
        "review_blockers": [],
        "status": "review_ready",
    }
    submission_review_service.append_submission_review(record)

    assert workflow_state_engine.get_current_state(tender_id).stage is WorkflowStage.REVIEW_READY
    lines = (tmp_path / "runtime" / "manual_production" / "workflow_state.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["stage"] == "review_ready"


def test_submission_proof_service_records_workflow_transition(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-008"
    _advance_to_approval_required(tender_id)
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "system", "approved")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVED, WorkflowStage.REVIEW_READY, "system", "review ready")

    record = {
        "tender_id": tender_id,
        "tender_root": str(tmp_path / "tender"),
        "portal_name": "eTenders",
        "submission_reference": "SUB-1",
        "submitted_by": "Operator",
        "proof_file": str(tmp_path / "tender" / "proof.pdf"),
        "proof_file_present": True,
        "submission_review_status": "review_ready",
        "submission_review_ready": True,
        "final_submission_attempted": False,
        "manual_submission_recorded": True,
        "blockers": [],
        "status": "recorded",
    }
    submission_proof_service.append_submission_proof(record)

    assert workflow_state_engine.get_current_state(tender_id).stage is WorkflowStage.PROOF_RECORDED
    lines = (tmp_path / "runtime" / "manual_production" / "workflow_state.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["stage"] == "proof_recorded"


def test_workflow_logs_are_append_only(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-009"

    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "system", "discover")
    event_file = tmp_path / "runtime" / "manual_production" / "workflow_events.jsonl"
    state_file = tmp_path / "runtime" / "manual_production" / "workflow_state.jsonl"
    first_events = event_file.read_text(encoding="utf-8").splitlines()
    first_states = state_file.read_text(encoding="utf-8").splitlines()

    workflow_state_engine.record_transition(tender_id, WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "system", "extract")

    second_events = event_file.read_text(encoding="utf-8").splitlines()
    second_states = state_file.read_text(encoding="utf-8").splitlines()

    assert len(second_events) == len(first_events) + 1
    assert len(second_states) == len(first_states) + 1
    assert second_events[: len(first_events)] == first_events
    assert second_states[: len(first_states)] == first_states


def test_current_state_returns_latest_stage(monkeypatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    tender_id = "T-010"

    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "system", "discover")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "system", "extract")

    assert workflow_state_engine.get_current_state(tender_id).stage is WorkflowStage.EVALUATED
