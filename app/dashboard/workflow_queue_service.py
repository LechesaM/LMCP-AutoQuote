from __future__ import annotations

from typing import Any, Dict, List

from app.core import workflow_state_engine
from app.orchestration import queue_monitor
from app.domain.workflow import WorkflowStage


def _states() -> Dict[str, workflow_state_engine.WorkflowState]:
    return workflow_state_engine._STATE_BY_FILE.get(str(workflow_state_engine.WORKFLOW_STATE_LOG_FILE), {})  # type: ignore[attr-defined]


def _items_for(stage: WorkflowStage) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for tender_id, state in _states().items():
        if state.stage is stage:
            items.append({"tender_id": tender_id, "stage": stage.value, "updated_at": state.updated_at})
    return items


def get_pending_approval_queue() -> List[Dict[str, Any]]:
    return _items_for(WorkflowStage.APPROVAL_REQUIRED)


def get_review_ready_queue() -> List[Dict[str, Any]]:
    return _items_for(WorkflowStage.APPROVED)


def get_proof_capture_queue() -> List[Dict[str, Any]]:
    return _items_for(WorkflowStage.REVIEW_READY)


def get_refused_queue() -> List[Dict[str, Any]]:
    return _items_for(WorkflowStage.REFUSED)


def get_archived_queue() -> List[Dict[str, Any]]:
    return _items_for(WorkflowStage.ARCHIVED)


def get_queue_overview(limit: int = 50) -> Dict[str, Any]:
    return {
        "summary": queue_monitor.get_queue_summary(limit=limit),
        "pending_approval": get_pending_approval_queue(),
        "review_ready": get_review_ready_queue(),
        "proof_capture": get_proof_capture_queue(),
        "refused": get_refused_queue(),
        "archived": get_archived_queue(),
    }
