from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request

from app.services.operator_action_service import (
    force_quote,
    get_operator_action_summary,
    mark_review_complete,
    pause_source,
    reject_opportunity,
    retry_submission,
)
from app.services.audit_trail_service import record_audit_event
from app.services.operator_auth_service import audit_identity_from_request

router = APIRouter(prefix="/operator-actions", tags=["operator-actions"])


@router.get("/summary")
def operator_summary(limit: int = 30) -> Dict[str, Any]:
    return get_operator_action_summary(limit=limit)


@router.post("/force-quote")
async def operator_force_quote(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await force_quote(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/retry-submission")
async def operator_retry_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await retry_submission(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/reject-opportunity")
async def operator_reject_opportunity(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await reject_opportunity(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/mark-review-complete")
async def operator_mark_review_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await mark_review_complete(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/pause-source")
async def operator_pause_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await pause_source(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/audit")
async def operator_audit_action(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    operator_action = str(payload.get("operator_action") or payload.get("action") or "operator_supervised_action").strip() or "operator_supervised_action"
    workspace = str(payload.get("workspace") or payload.get("page") or "quote-pack-engine").strip() or "quote-pack-engine"
    rfq_reference = str(payload.get("rfq_reference") or payload.get("buyer_rfq_number") or "").strip()
    quote_pack_id = str(payload.get("quote_pack_id") or payload.get("pack_id") or "").strip()
    controlled_workflow_mode = str(payload.get("controlled_workflow_mode") or "supervised").strip() or "supervised"

    safety_flags = payload.get("safety_flags") if isinstance(payload.get("safety_flags"), dict) else {}
    merged_payload = {
        "timestamp": payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "operator_action": operator_action,
        "rfq_reference": rfq_reference,
        "buyer_rfq_number": rfq_reference,
        "quote_pack_id": quote_pack_id,
        "workspace": workspace,
        "controlled_workflow_mode": controlled_workflow_mode,
        "safety_flags": {
            "no_submission": bool(safety_flags.get("no_submission", True)),
            "no_upload": bool(safety_flags.get("no_upload", True)),
            "no_email": bool(safety_flags.get("no_email", True)),
            "final_submit_locked": bool(safety_flags.get("final_submit_locked", True)),
        },
        **audit_identity_from_request(request),
    }
    for key, value in payload.items():
        if key not in merged_payload:
            merged_payload[key] = value

    item = await record_audit_event(
        event_type="operator_supervised_ui_action",
        source=workspace,
        severity="info",
        title=operator_action,
        message=f"Supervised operator action recorded: {operator_action}",
        buyer_rfq_number=rfq_reference,
        quote_number=quote_pack_id,
        payload=merged_payload,
    )
    return {"status": "ok", "message": "Operator audit action recorded.", "item": item}

@router.get("/is-rejected/{buyer_rfq_number}")
def operator_is_rejected(buyer_rfq_number: str) -> Dict[str, Any]:
    from app.services.operator_action_service import is_opportunity_rejected
    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "rejected": is_opportunity_rejected(buyer_rfq_number),
    }


@router.get("/is-source-paused/{source_name}")
def operator_is_source_paused(source_name: str) -> Dict[str, Any]:
    from app.services.operator_action_service import is_source_paused
    return {
        "status": "ok",
        "source_name": source_name,
        "paused": is_source_paused(source_name),
    }
