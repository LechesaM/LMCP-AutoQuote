from __future__ import annotations

from typing import Any, Dict

from app.core import workflow_state_engine
from app.domain.workflow import WorkflowStage


def scan_for_recovery_candidates(stuck_after_minutes: int = 60, limit: int = 50) -> Dict[str, Any]:
    items = []
    for tender_id, state in list(workflow_state_engine._STATE_BY_FILE.get(str(workflow_state_engine.WORKFLOW_STATE_LOG_FILE), {}).items())[:limit]:
        items.append({"tender_id": tender_id, "stage": state.stage.value})
    return {"recovery_candidates": items, "persistence_mismatch": [], "orphaned_workflows": []}


def generate_recovery_report(limit: int = 50) -> Dict[str, Any]:
    return {"recovery_candidates": scan_for_recovery_candidates(limit=limit)["recovery_candidates"]}


def recover_workflow(tender_id: str, actor: str, operator: str, reason: str) -> Dict[str, Any]:
    state = workflow_state_engine.get_current_state(tender_id)
    return {"tender_id": tender_id, "stage": state.stage.value}
