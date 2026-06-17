from __future__ import annotations

import os
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
SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED = (
    str(os.getenv("SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}
)


def _disabled_response(action: str) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "action": action,
        "message": "Safe autonomous scheduler API actions are disabled by default.",
        "api_enabled": SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED,
    }


@router.get("/status")
def status(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    payload = get_safe_scheduler_status(limit=int(limit))
    payload["api_enabled"] = SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED
    return payload


@router.post("/start-loop")
def start_loop() -> Dict[str, Any]:
    if not SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED:
        return _disabled_response("start-loop")
    return start_background_scheduler()


@router.post("/enable")
async def enable() -> Dict[str, Any]:
    if not SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED:
        return _disabled_response("enable")
    return await enable_safe_scheduler()


@router.post("/disable")
def disable() -> Dict[str, Any]:
    if not SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED:
        return _disabled_response("disable")
    return disable_safe_scheduler()


@router.post("/policy")
def update_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED:
        return _disabled_response("policy")
    return {"status": "ok", "state": update_scheduler_state(payload)}


@router.post("/run-once")
async def run_once(
    max_total: Optional[int] = Query(default=None, ge=1, le=100),
    max_submissions: Optional[int] = Query(default=None, ge=0, le=20),
    enable_submit: Optional[bool] = None,
    enable_quote_engine: Optional[bool] = None,
) -> Dict[str, Any]:
    if not SAFE_AUTONOMOUS_SCHEDULER_API_ENABLED:
        return _disabled_response("run-once")
    return await run_safe_autonomous_cycle(
        max_total=max_total,
        max_submissions=max_submissions,
        enable_submit=enable_submit,
        enable_quote_engine=enable_quote_engine,
        reason="manual_api",
    )


@router.get("/policy")
def get_policy():
    return get_safe_scheduler_status(limit=1).get("policy", {})

