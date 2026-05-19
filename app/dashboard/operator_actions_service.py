from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.core import workflow_state_engine
from app.services.audit_trail_service import record_audit_event


async def _emit_operator_audit(
    *,
    event_type: str,
    tender_id: str,
    actor: str,
    message: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return await record_audit_event(
        event_type=event_type,
        source="operator-dashboard",
        severity="info",
        title=event_type.replace("_", " ").title(),
        message=message,
        buyer_rfq_number=tender_id,
        payload=payload or {},
    )


def _dispatch_audit(event_type: str, tender_id: str, actor: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
    coroutine = _emit_operator_audit(
        event_type=event_type,
        tender_id=tender_id,
        actor=actor,
        message=message,
        payload=payload or {},
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coroutine)
        return
    loop.create_task(coroutine)


def refuse_workflow(tender_id: str, actor: str, reason: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = workflow_state_engine.refuse_workflow(tender_id=tender_id, actor=actor, reason=reason, details=details)
    try:
        _dispatch_audit(
            "operator_refuse_workflow",
            tender_id,
            actor,
            reason,
            {"details": details or {}, "stage": state.stage.value, "actor": actor},
        )
    except Exception:
        pass
    return state.to_jsonable_dict()


def archive_workflow(tender_id: str, actor: str, reason: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = workflow_state_engine.archive_workflow(tender_id=tender_id, actor=actor, reason=reason, details=details)
    try:
        _dispatch_audit(
            "operator_archive_workflow",
            tender_id,
            actor,
            reason,
            {"details": details or {}, "stage": state.stage.value, "actor": actor},
        )
    except Exception:
        pass
    return state.to_jsonable_dict()


def add_operator_note(tender_id: str, actor: str, note: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {"note": note, "details": details or {}, "actor": actor}
    try:
        _dispatch_audit("operator_note", tender_id, actor, note, payload)
    except Exception:
        pass
    return {"status": "ok", "tender_id": tender_id, "actor": actor, "note": note, "details": details or {}}


def acknowledge_warning(tender_id: str, actor: str, warning: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {"warning": warning, "details": details or {}, "actor": actor}
    try:
        _dispatch_audit("operator_acknowledge_warning", tender_id, actor, warning, payload)
    except Exception:
        pass
    return {"status": "ok", "tender_id": tender_id, "actor": actor, "warning": warning, "details": details or {}}
