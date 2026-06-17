from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.domain.workflow import WorkflowStage
from app.core.runtime_paths import get_runtime_paths


RUNTIME_DIR = get_runtime_paths().runtime_root
MANUAL_PRODUCTION_DIR = Path(os.getenv("LMCP_MANUAL_PRODUCTION_DIR", str(RUNTIME_DIR / "manual_production")))
WORKFLOW_EVENT_LOG_FILE = MANUAL_PRODUCTION_DIR / "workflow_events.jsonl"
WORKFLOW_STATE_LOG_FILE = MANUAL_PRODUCTION_DIR / "workflow_state.jsonl"

_STATE_BY_FILE: Dict[str, Dict[str, "WorkflowState"]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_audit_event(**_: Any) -> None:
    return None


@dataclass
class WorkflowState:
    tender_id: str
    stage: WorkflowStage
    actor: str = ""
    reason: str = ""
    details: Dict[str, Any] = None  # type: ignore[assignment]
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["stage"] = self.stage.value
        data["details"] = self.details or {}
        if not data.get("updated_at"):
            data["updated_at"] = _now_iso()
        return data


def _state_bucket() -> Dict[str, WorkflowState]:
    key = str(WORKFLOW_STATE_LOG_FILE)
    bucket = _STATE_BY_FILE.get(key)
    if bucket is None:
        bucket = {}
        _STATE_BY_FILE[key] = bucket
    return bucket


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _write_state_event(payload: Dict[str, Any]) -> None:
    _append_jsonl(WORKFLOW_STATE_LOG_FILE, payload)


def _write_workflow_event(payload: Dict[str, Any]) -> None:
    _append_jsonl(WORKFLOW_EVENT_LOG_FILE, payload)


def _record(
    tender_id: str,
    stage: WorkflowStage,
    actor: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
    previous_stage: Optional[WorkflowStage] = None,
) -> WorkflowState:
    state = WorkflowState(
        tender_id=tender_id,
        stage=stage,
        actor=actor,
        reason=reason,
        details=dict(details or {}),
        updated_at=_now_iso(),
    )
    _state_bucket()[tender_id] = state
    payload = state.to_dict()
    _write_state_event(payload)
    workflow_event_payload = {
        "tender_id": tender_id,
        "stage": stage.value,
        "from_stage": (previous_stage.value if previous_stage else ""),
        "to_stage": stage.value,
        "actor": actor,
        "reason": reason,
        "details": details or {},
        "created_at": payload["updated_at"],
    }
    _write_workflow_event(workflow_event_payload)
    try:
        from app.persistence import db as persistence_db
        from app.persistence.repositories import record_persistence_write_failure, record_persistence_write_success

        persistence_db.insert_json_record("workflow_state_records", payload)
        persistence_db.insert_json_record("workflow_event_records", workflow_event_payload)
        record_persistence_write_success()
    except Exception:
        try:
            from app.persistence.repositories import record_persistence_write_failure
            record_persistence_write_failure()
        except Exception:
            pass
    _emit_audit_event(event_type="workflow_transition", payload=payload)
    return state


_ALLOWED_TRANSITIONS: Dict[WorkflowStage, List[WorkflowStage]] = {
    WorkflowStage.DISCOVERED: [WorkflowStage.EXTRACTED],
    WorkflowStage.EXTRACTED: [WorkflowStage.EVALUATED],
    WorkflowStage.EVALUATED: [WorkflowStage.PRICED],
    WorkflowStage.PRICED: [WorkflowStage.QUOTE_GENERATED],
    WorkflowStage.QUOTE_GENERATED: [WorkflowStage.APPROVAL_REQUIRED],
    WorkflowStage.APPROVAL_REQUIRED: [WorkflowStage.APPROVED, WorkflowStage.REFUSED],
    WorkflowStage.APPROVED: [WorkflowStage.REVIEW_READY, WorkflowStage.REFUSED],
    WorkflowStage.REVIEW_READY: [WorkflowStage.PROOF_RECORDED, WorkflowStage.ARCHIVED],
    WorkflowStage.PROOF_RECORDED: [WorkflowStage.ARCHIVED],
}


def assert_can_transition(current: WorkflowStage, target: WorkflowStage) -> None:
    if target in {WorkflowStage.REFUSED, WorkflowStage.ARCHIVED}:
        return
    allowed = _ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ValueError(f"Transition from {current.value} to {target.value} is not allowed.")


def record_transition(
    tender_id: str,
    current_stage: WorkflowStage,
    next_stage: WorkflowStage,
    actor: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    current = get_current_state(tender_id).stage
    if current != current_stage:
        # keep the check permissive for fresh records when callers pass DISCOVERED as the starting point
        if current != WorkflowStage.DISCOVERED or current_stage != WorkflowStage.DISCOVERED:
            raise ValueError(f"Current stage for {tender_id} is {current.value}; expected {current_stage.value}.")
    assert_can_transition(current_stage, next_stage)
    return _record(tender_id, next_stage, actor, reason, details, previous_stage=current_stage)


def refuse_workflow(tender_id: str, actor: str, reason: str, details: Optional[Dict[str, Any]] = None) -> WorkflowState:
    current = get_current_state(tender_id).stage
    return _record(tender_id, WorkflowStage.REFUSED, actor, reason, details, previous_stage=current)


def archive_workflow(tender_id: str, actor: str, reason: str, details: Optional[Dict[str, Any]] = None) -> WorkflowState:
    current = get_current_state(tender_id).stage
    if current not in {WorkflowStage.REFUSED, WorkflowStage.PROOF_RECORDED, WorkflowStage.REVIEW_READY}:
        raise ValueError(f"Workflow {tender_id} cannot be archived from stage {current.value}.")
    return _record(tender_id, WorkflowStage.ARCHIVED, actor, reason, details, previous_stage=current)


def get_current_state(tender_id: str) -> WorkflowState:
    return _state_bucket().get(tender_id) or WorkflowState(tender_id=tender_id, stage=WorkflowStage.DISCOVERED, actor="", reason="", details={}, updated_at="")


def get_transition_history(tender_id: str) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if WORKFLOW_STATE_LOG_FILE.exists():
        for line in WORKFLOW_STATE_LOG_FILE.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if str(payload.get("tender_id") or "") == tender_id:
                items.append(payload)
    return {"status": "ok", "tender_id": tender_id, "items": items}
