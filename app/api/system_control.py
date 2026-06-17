from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body

from app.services.system_state_service import (
    clear_emergency_stop,
    get_system_state,
    pause_harvest,
    pause_submissions,
    resume_all,
    resume_harvest,
    resume_submissions,
    set_emergency_stop,
    set_system_off,
    set_system_on,
)

router = APIRouter(prefix="/system/control", tags=["System Control"])


def _ok_response(state: dict, message: str) -> dict:
    return {
        "status": "ok",
        "message": message,
        "state": state,
    }


@router.get("/status")
def system_control_status() -> dict:
    state = get_system_state()
    return _ok_response(state, "system control status fetched")


@router.post("/on")
def system_control_on(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = set_system_on(reason=reason or "system turned on", last_changed_by="api")
    return _ok_response(state, "system turned on")


@router.post("/off")
def system_control_off(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = set_system_off(reason=reason or "system turned off", last_changed_by="api")
    return _ok_response(state, "system turned off")


@router.post("/pause-harvest")
def system_control_pause_harvest(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = pause_harvest(reason=reason or "harvest paused", last_changed_by="api")
    return _ok_response(state, "harvest paused")


@router.post("/resume-harvest")
def system_control_resume_harvest(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = resume_harvest(reason=reason or "harvest resumed", last_changed_by="api")
    return _ok_response(state, "harvest resumed")


@router.post("/pause-submissions")
def system_control_pause_submissions(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = pause_submissions(
        reason=reason or "submissions paused",
        last_changed_by="api",
    )
    return _ok_response(state, "submissions paused")


@router.post("/resume-submissions")
def system_control_resume_submissions(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = resume_submissions(
        reason=reason or "submissions resumed",
        last_changed_by="api",
    )
    return _ok_response(state, "submissions resumed")


@router.post("/emergency-stop")
def system_control_emergency_stop(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = set_emergency_stop(
        reason=reason or "emergency stop activated",
        last_changed_by="api",
    )
    return _ok_response(state, "emergency stop activated")


@router.post("/clear-emergency-stop")
def system_control_clear_emergency_stop(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = clear_emergency_stop(
        reason=reason or "emergency stop cleared",
        last_changed_by="api",
    )
    return _ok_response(state, "emergency stop cleared")


@router.post("/resume-all")
def system_control_resume_all(reason: Optional[str] = Body(default=None, embed=True)) -> dict:
    state = resume_all(reason=reason or "all services resumed", last_changed_by="api")
    return _ok_response(state, "all services resumed")




@router.get("/policy")
def get_policy():
    return {
        "status": "ok",
        "enabled": False,
        "mode": "safe",
        "allow_final_submit": False,
        "manual_review_required": True,
        "source": "system_control_compat_get_policy",
    }

