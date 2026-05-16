from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.operator_auth_service import (
    OPERATOR_AUTH_ALLOW_DEV_FALLBACK,
    OperatorAuthError,
    apply_login_cookie,
    bootstrap_admin,
    clear_login_cookie,
    get_session_payload,
    login_operator,
    logout_request,
)


router = APIRouter(prefix="/operator-auth", tags=["Operator Auth"])


@router.post("/bootstrap-admin")
def operator_auth_bootstrap_admin(payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    try:
        return bootstrap_admin(payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already configured" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/login")
def operator_auth_login(payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    try:
        result = login_operator(payload)
    except OperatorAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    token = result.pop("session_token", "")
    response = JSONResponse(content=result)
    if token:
        apply_login_cookie(response, {"_session_token": token})
    return response


@router.post("/logout")
def operator_auth_logout(request: Request) -> JSONResponse:
    try:
        result = logout_request(request)
    except OperatorAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    response = JSONResponse(content=result)
    clear_login_cookie(response)
    return response


@router.get("/session")
def operator_auth_session(request: Request) -> Dict[str, Any]:
    try:
        return get_session_payload(request)
    except OperatorAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/status")
def operator_auth_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "operator_auth",
        "dev_fallback_enabled": OPERATOR_AUTH_ALLOW_DEV_FALLBACK,
    }
