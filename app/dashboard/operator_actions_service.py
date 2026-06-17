from __future__ import annotations

import asyncio
from typing import Any, Dict

from app.core import workflow_state_engine
from app.services import audit_trail_service


def _record_audit(event_type: str, payload: Dict[str, Any]) -> None:
    try:
        asyncio.run(audit_trail_service.record_audit_event(event_type=event_type, source="operator-dashboard", payload=payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(audit_trail_service.record_audit_event(event_type=event_type, source="operator-dashboard", payload=payload))
        finally:
            loop.close()


def archive_workflow(tender_id: str, actor: str, reason: str, details: Dict[str, Any]) -> Dict[str, Any]:
    current = workflow_state_engine.get_current_state(tender_id)
    if current.stage is not workflow_state_engine.WorkflowStage.ARCHIVED:
        state = workflow_state_engine.archive_workflow(tender_id, actor=actor, reason=reason, details=details)
    else:
        state = current
    _record_audit("operator_archive_workflow", {"tender_id": tender_id, "actor": actor, "reason": reason, "details": details})
    return {"tender_id": tender_id, "stage": state.stage.value, "actor": actor, "reason": reason, "details": details}


def refuse_workflow(tender_id: str, actor: str, reason: str, details: Dict[str, Any]) -> Dict[str, Any]:
    current = workflow_state_engine.get_current_state(tender_id)
    if current.stage is workflow_state_engine.WorkflowStage.ARCHIVED:
        raise ValueError("Archived workflows cannot be refused again.")
    state = workflow_state_engine.refuse_workflow(tender_id, actor=actor, reason=reason, details=details)
    _record_audit("operator_refuse_workflow", {"tender_id": tender_id, "actor": actor, "reason": reason, "details": details})
    return {"tender_id": tender_id, "stage": state.stage.value, "actor": actor, "reason": reason, "details": details}


def add_operator_note(tender_id: str, actor: str, note: str, details: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"tender_id": tender_id, "actor": actor, "note": note, "details": details}
    _record_audit("operator_note", payload)
    return {"status": "ok", **payload}


def acknowledge_warning(tender_id: str, actor: str, warning: str, details: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"tender_id": tender_id, "actor": actor, "warning": warning, "details": details}
    _record_audit("operator_acknowledge_warning", payload)
    return {"status": "ok", **payload}
