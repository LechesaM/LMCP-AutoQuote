from __future__ import annotations

from typing import Any, Dict, Optional

from app.domain.workflow import WorkflowStage
from app.pilot.pilot_mode import PilotMode, get_pilot_mode


def _stage(value: Any) -> str:
    return str(value or "").strip()


def validate_pilot_operation(operation: Dict[str, Any], *, pilot_mode: PilotMode | None = None) -> Dict[str, Any]:
    mode = pilot_mode or get_pilot_mode()
    blockers = []
    if mode is PilotMode.DISABLED:
        blockers.append("pilot mode disabled")
    if operation.get("autonomous_submission") or operation.get("final_submission_attempted"):
        blockers.append("autonomous final submission is prohibited")
    if operation.get("workflow_skip") or operation.get("skip_workflow_stage"):
        blockers.append("workflow skipping is prohibited")
    if not operation.get("operator") and not operation.get("operator_name"):
        blockers.append("operator accountability is required")
    if operation.get("workflow_stage") == WorkflowStage.PROOF_RECORDED.value and not operation.get("proof_confirmed"):
        blockers.append("proof capture must be confirmed")
    if operation.get("workflow_stage") == WorkflowStage.REVIEW_READY.value and not operation.get("review_confirmed"):
        blockers.append("review checkpoint must be confirmed")
    if operation.get("workflow_stage") == WorkflowStage.APPROVED.value and not operation.get("approval_confirmed"):
        blockers.append("approval checkpoint must be confirmed")
    if operation.get("workflow_stage") == WorkflowStage.APPROVAL_REQUIRED.value and operation.get("review_confirmed"):
        blockers.append("review cannot replace approval")
    status = "ok" if not blockers else "blocked"
    return {
        "status": status,
        "pilot_mode": mode.value,
        "blockers": blockers,
        "operation": operation,
    }


def assert_pilot_guardrails(operation: Dict[str, Any], *, pilot_mode: PilotMode | None = None) -> None:
    result = validate_pilot_operation(operation, pilot_mode=pilot_mode)
    if result["blockers"]:
        raise ValueError("; ".join(result["blockers"]))
