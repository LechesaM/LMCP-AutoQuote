from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.operator_ops.operator_action_models import new_operator_id
from app.operator_ops.operator_activity_feed import append_timeline_event, get_operator_timeline
from app.services.audit_trail_service import record_audit_event


async def _record_audit(event_type: str, operator_id: str, tender_id: str, message: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return await record_audit_event(
        event_type=event_type,
        source="operator-ops",
        severity="info",
        title=event_type.replace("_", " ").title(),
        message=message,
        buyer_rfq_number=tender_id,
        payload=payload or {},
    )


def record_timeline_event(*, event_type: str, operator_id: str, tender_id: str = "", title: str = "", severity: str = "info", reversible: bool = True, reviewable: bool = True, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {
        "event_id": new_operator_id("op-event"),
        "event_type": event_type,
        "operator_id": operator_id,
        "tender_id": tender_id,
        "title": title or event_type.replace("_", " ").title(),
        "severity": severity,
        "reversible": reversible,
        "reviewable": reviewable,
        "details": details or {},
    }
    append_timeline_event(payload)
    try:
        coroutine = _record_audit(event_type, operator_id, tender_id, title or event_type, payload)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coroutine)
        else:
            loop.create_task(coroutine)
    except Exception:
        pass
    return payload


def get_operator_audit_timeline(limit: int = 100) -> Dict[str, Any]:
    return get_operator_timeline(limit=limit)
