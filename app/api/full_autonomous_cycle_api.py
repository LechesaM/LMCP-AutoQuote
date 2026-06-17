from __future__ import annotations

import os
from typing import Any, Dict
from fastapi import APIRouter

from app.services.full_autonomous_cycle_service import (
    get_full_cycle_status,
    run_full_autonomous_cycle,
)

router = APIRouter(prefix="/full-autonomous-cycle", tags=["full-autonomous-cycle"])
FULL_AUTONOMOUS_CYCLE_API_ENABLED = (
    str(os.getenv("FULL_AUTONOMOUS_CYCLE_API_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}
)


def _disabled_response(action: str) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "action": action,
        "message": "Full autonomous cycle API actions are disabled by default.",
        "api_enabled": FULL_AUTONOMOUS_CYCLE_API_ENABLED,
    }


@router.get("/status")
def full_cycle_status(limit: int = 20) -> Dict[str, Any]:
    payload = get_full_cycle_status(limit=limit)
    payload["api_enabled"] = FULL_AUTONOMOUS_CYCLE_API_ENABLED
    return payload


@router.post("/run")
async def full_cycle_run(limit: int = 10, dry_run: bool = False) -> Dict[str, Any]:
    if not FULL_AUTONOMOUS_CYCLE_API_ENABLED:
        return _disabled_response("run")
    return await run_full_autonomous_cycle(limit=limit, dry_run=dry_run)


@router.post("/dry-run")
async def full_cycle_dry_run(limit: int = 10) -> Dict[str, Any]:
    if not FULL_AUTONOMOUS_CYCLE_API_ENABLED:
        return _disabled_response("dry-run")
    return await run_full_autonomous_cycle(limit=limit, dry_run=True)
