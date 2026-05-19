from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.auth_contracts import build_login_response, build_logout_response, build_me_response, build_permissions_response
from app.auth.auth_service import authenticate_user, current_permissions, get_current_user, logout_user
from app.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: Optional[Dict[str, Any]] = Body(default=None)) -> JSONResponse:
    data = payload or {}
    email = str(data.get("email") or data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    try:
        result = authenticate_user(email, password)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    response = JSONResponse(content=build_login_response(result))
    response.set_cookie(
        "lmcp_auth_token",
        result.get("access_token", ""),
        httponly=True,
        secure=settings.operator_session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    result = logout_user(request)
    response = JSONResponse(content=build_logout_response(result))
    response.delete_cookie("lmcp_auth_token", path="/")
    return response


@router.get("/me")
def me(request: Request) -> Dict[str, Any]:
    return build_me_response(get_current_user(request))


@router.get("/permissions")
def permissions(request: Request) -> Dict[str, Any]:
    return build_permissions_response(current_permissions(request))
