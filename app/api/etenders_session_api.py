from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from app.services.etenders_persistent_session_service import (
    get_etenders_session_status,
    probe_persistent_session,
    classify_etenders_submission_readiness,
)

router = APIRouter(prefix="/etenders-session", tags=["etenders-session"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_etenders_session_status()


@router.post("/probe")
def probe(headless: bool = True) -> Dict[str, Any]:
    return probe_persistent_session(headless=headless)


@router.post("/submission-readiness")
def submission_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    return classify_etenders_submission_readiness(payload)


@router.get("/manual-login-instructions")
def manual_login_instructions():
    return {
        "status": "manual_login_required",
        "message": "Open eTenders manually, complete CAPTCHA/login, then run session probe.",
        "login_url": "https://www.etenders.gov.za/Login/Login",
        "profile_dir": "runtime/etenders_session/playwright_profile",
        "proof_dir": "runtime/etenders_session/proofs",
        "captcha_note": "CAPTCHA is not bypassed. Manual login/session reuse is required.",
    }
