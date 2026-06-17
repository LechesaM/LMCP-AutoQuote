from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.core import workflow_state_engine
from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowStage


def replay_workflow_history(tender_id: str) -> Dict[str, Any]:
    manual_dir = get_runtime_paths().manual_production_dir
    event_path = manual_dir / "workflow_events.jsonl"
    invalid_transitions = []
    if event_path.exists():
        for line in event_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if str(payload.get("tender_id") or "") != tender_id:
                continue
            from_stage = str(payload.get("from_stage") or "")
            to_stage = str(payload.get("to_stage") or "")
            if not from_stage or not to_stage:
                invalid_transitions.append(payload)
                continue
            try:
                workflow_state_engine.assert_can_transition(WorkflowStage(from_stage), WorkflowStage(to_stage))
            except Exception:
                invalid_transitions.append(payload)
    return {"passed": not invalid_transitions, "invalid_transitions": invalid_transitions, "missing_audit_events": []}
