from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter
from app.services.audit_trail_service import get_audit_events, get_audit_summary, record_audit_event

router = APIRouter(prefix="/audit-trail", tags=["audit-trail"])

@router.get("/events")
def audit_events(limit: int = 80) -> Dict[str, Any]:
    return get_audit_events(limit=limit)

@router.get("/summary")
def audit_summary() -> Dict[str, Any]:
    return get_audit_summary()

@router.post("/events")
async def create_audit_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = await record_audit_event(
        event_type=payload.get("event_type") or "manual_audit_event",
        source=payload.get("source") or "dashboard",
        severity=payload.get("severity") or "info",
        title=payload.get("title") or "",
        message=payload.get("message") or "",
        buyer_rfq_number=payload.get("buyer_rfq_number") or "",
        quote_number=payload.get("quote_number") or "",
        payload=payload.get("payload") or payload,
    )
    return {"status": "ok", "message": "Audit event recorded.", "item": item}
