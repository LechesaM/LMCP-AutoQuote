from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from app.services.full_autonomous_cycle_service import (
    get_full_cycle_status,
    run_full_autonomous_cycle,
)

router = APIRouter(prefix="/full-autonomous-cycle", tags=["full-autonomous-cycle"])


@router.get("/status")
def full_cycle_status(limit: int = 20) -> Dict[str, Any]:
    return get_full_cycle_status(limit=limit)


@router.post("/run")
async def full_cycle_run(limit: int = 10, dry_run: bool = False) -> Dict[str, Any]:
    return await run_full_autonomous_cycle(limit=limit, dry_run=dry_run)


@router.post("/dry-run")
async def full_cycle_dry_run(limit: int = 10) -> Dict[str, Any]:
    return await run_full_autonomous_cycle(limit=limit, dry_run=True)
