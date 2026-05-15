from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.csd_monthly_refresh_service import (
    get_csd_refresh_status,
    refresh_csd_report,
    run_monthly_csd_refresh_if_due,
)

router = APIRouter(prefix="/csd-monthly-refresh", tags=["CSD Monthly Refresh"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_csd_refresh_status()


@router.post("/run-if-due")
def run_if_due() -> Dict[str, Any]:
    return run_monthly_csd_refresh_if_due()


@router.post("/run-now")
def run_now(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    force = bool(payload.get("force", True))
    return refresh_csd_report(force=force)

