from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.csd_persistent_session_service import (
    clear_persistent_csd_session,
    get_persistent_csd_session_status,
    refresh_csd_report_with_persistent_session,
    start_manual_csd_login_session,
)

router = APIRouter(prefix="/csd-persistent-session", tags=["CSD Persistent Session"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_persistent_csd_session_status()


@router.post("/start-manual-login")
def start_manual_login(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return start_manual_csd_login_session(
        headless=payload.get("headless"),
        wait_seconds=int(payload.get("wait_seconds", 180)),
    )


@router.post("/refresh-report")
def refresh_report() -> Dict[str, Any]:
    return refresh_csd_report_with_persistent_session()


@router.post("/clear-session")
def clear_session() -> Dict[str, Any]:
    return clear_persistent_csd_session()
