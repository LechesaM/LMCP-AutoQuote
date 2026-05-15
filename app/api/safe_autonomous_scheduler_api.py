from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.services.safe_autonomous_scheduler_service import (
    disable_safe_scheduler,
    enable_safe_scheduler,
    get_safe_scheduler_status,
    run_safe_autonomous_cycle,
    start_background_scheduler,
    update_scheduler_state,
)

router = APIRouter(prefix="/safe-autonomous-scheduler", tags=["safe-autonomous-scheduler"])


@router.get("/status")
def status(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return get_safe_scheduler_status(limit=limit)


@router.post("/start-loop")
def start_loop() -> Dict[str, Any]:
    return start_background_scheduler()


@router.post("/enable")
async def enable() -> Dict[str, Any]:
    return await enable_safe_scheduler()


@router.post("/disable")
def disable() -> Dict[str, Any]:
    return disable_safe_scheduler()


@router.post("/policy")
def update_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "ok", "state": update_scheduler_state(payload)}


@router.post("/run-once")
async def run_once(
    max_total: Optional[int] = Query(default=None, ge=1, le=100),
    max_submissions: Optional[int] = Query(default=None, ge=0, le=20),
    enable_submit: Optional[bool] = None,
    enable_quote_engine: Optional[bool] = None,
) -> Dict[str, Any]:
    return await run_safe_autonomous_cycle(
        max_total=max_total,
        max_submissions=max_submissions,
        enable_submit=enable_submit,
        enable_quote_engine=enable_quote_engine,
        reason="manual_api",
    )
