from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.etenders_persistent_session_service import (
    classify_etenders_submission_readiness,
    get_etenders_session_status,
    launch_manual_login_browser,
    open_manual_login_instruction,
    probe_persistent_session,
)

router = APIRouter(prefix="/etenders-session", tags=["etenders-session"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_etenders_session_status()


@router.get("/manual-login-instructions")
def manual_login_instructions() -> Dict[str, Any]:
    return open_manual_login_instruction()


@router.post("/launch-manual-login")
def launch_manual_login(headless: bool = False) -> Dict[str, Any]:
    return launch_manual_login_browser(headless=headless)


@router.post("/probe")
def probe(headless: bool = True) -> Dict[str, Any]:
    return probe_persistent_session(headless=headless)


@router.post("/submission-readiness")
def submission_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    return classify_etenders_submission_readiness(payload)
