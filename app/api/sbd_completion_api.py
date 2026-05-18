from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from app.services.sbd_completion_engine import (
    build_lmcp_default_sbd_payload,
    evaluate_sbd_completion,
    get_sbd_completion_summary,
    record_sbd_completion,
)

router = APIRouter(prefix="/sbd-completion", tags=["sbd-completion"])


@router.get("/summary")
def sbd_completion_summary(limit: int = 50) -> Dict[str, Any]:
    return get_sbd_completion_summary(limit=limit)


@router.post("/evaluate")
def sbd_completion_evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    return evaluate_sbd_completion(payload)


@router.post("/record")
async def sbd_completion_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await record_sbd_completion(payload)


@router.post("/default-payload")
def sbd_default_payload(overrides: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": build_lmcp_default_sbd_payload(overrides),
    }
