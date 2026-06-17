from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.core import workflow_state_engine
from app.domain.workflow import WorkflowStage
from app.orchestration import queue_monitor


def _items() -> List[dict[str, Any]]:
    items: List[dict[str, Any]] = []
    path = workflow_state_engine.WORKFLOW_STATE_LOG_FILE
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = __import__("json").loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                items.append(payload)
    return items


def get_workflow_summary(limit: int = 50) -> Dict[str, Any]:
    items = _items()[-max(1, int(limit or 50)) :]
    stage_counts: Dict[str, int] = {}
    for item in items:
        stage = str(item.get("stage") or item.get("workflow_stage") or "").strip()
        if stage:
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
    return {
        "total_workflows": len({item.get("tender_id") for item in items if item.get("tender_id")}),
        "stage_counts": stage_counts,
        "approvals_pending": stage_counts.get(WorkflowStage.APPROVAL_REQUIRED.value, 0),
        "queue_summary": queue_monitor.get_queue_summary(limit=limit),
    }


def find_stuck_workflows(stuck_after_minutes: int = 60, limit: int = 50) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stuck_after_minutes)
    items = []
    for item in _items()[-max(1, int(limit or 50)) :]:
        updated_at = str(item.get("updated_at") or "")
        if not updated_at:
            continue
        try:
            timestamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except Exception:
            continue
        if timestamp < cutoff:
            items.append(item)
    return {"count": len(items), "items": items}


def find_invalid_workflows(limit: int = 50) -> Dict[str, Any]:
    valid = {stage.value for stage in WorkflowStage}
    current_states = workflow_state_engine._STATE_BY_FILE.get(str(workflow_state_engine.WORKFLOW_STATE_LOG_FILE), {})  # type: ignore[attr-defined]
    items = []
    for item in _items()[-max(1, int(limit or 50)) :]:
        tender_id = str(item.get("tender_id") or "")
        stage = str(item.get("stage") or item.get("workflow_stage") or "")
        current_state = current_states.get(tender_id)
        if stage not in valid:
            items.append(item)
            continue
        if current_state is None:
            items.append(item)
            continue
        if current_state.stage.value != stage:
            items.append(item)
    return {"count": len(items), "items": items}
