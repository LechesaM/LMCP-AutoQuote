from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict

from fastapi import HTTPException, Request

from app.auth.auth_models import AuthContext
from app.auth.rbac import role_has_permission
from app.auth.session_service import authenticate_credentials, get_current_user_from_request, permissions_for_current_user, revoke_session, seed_demo_users_if_needed
from app.monitoring.metrics_service import increment_metric


class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = 401) -> None:
        super().__init__(status_code=status_code, detail=detail)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    seed_demo_users_if_needed()
    try:
        user = authenticate_credentials(email, password)
    except ValueError as exc:
        increment_metric("auth_failures")
        raise AuthError(str(exc), status_code=401) from exc
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "permissions": list(user.permissions),
        },
        "permissions": list(user.permissions),
        "access_token": user.token,
        "token_type": "bearer",
        "expires_at": user.expires_at,
    }


def create_access_token_for_user(user: AuthContext) -> Dict[str, Any]:
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "access_token": user.token,
        "token_type": "bearer",
        "expires_at": user.expires_at,
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "permissions": list(user.permissions),
        },
    }


def get_current_user(request: Request) -> Dict[str, Any]:
    try:
        user = get_current_user_from_request(request)
    except ValueError as exc:
        increment_metric("auth_failures")
        raise AuthError(str(exc), status_code=401) from exc
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "permissions": list(user.permissions),
        },
        "permissions": list(user.permissions),
        "authenticated": True,
        "expires_at": user.expires_at,
    }


def get_current_auth_context(request: Request) -> AuthContext:
    try:
        return get_current_user_from_request(request)
    except ValueError as exc:
        raise AuthError(str(exc), status_code=401) from exc


def require_permission(permission: str) -> Callable[[Request], AuthContext]:
    def dependency(request: Request) -> AuthContext:
        user = get_current_auth_context(request)
        if not role_has_permission(user.role, permission):
            raise AuthError(f"Permission '{permission}' required.", status_code=403)
        return user

    return dependency


def require_role(role: str) -> Callable[[Request], AuthContext]:
    normalized = str(role or "").lower()

    def dependency(request: Request) -> AuthContext:
        user = get_current_auth_context(request)
        if str(user.role or "").lower() != normalized:
            raise AuthError(f"Role '{normalized}' required.", status_code=403)
        return user

    return dependency


def logout_user(request: Request) -> Dict[str, Any]:
    token = str(request.headers.get("Authorization") or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        token = str(request.cookies.get("lmcp_auth_token") or "").strip()
    if token:
        revoke_session(token)
    return {"status": "ok", "generated_at": _now_iso(), "data_source": "runtime", "authenticated": False}


def current_permissions(request: Request) -> Dict[str, Any]:
    user = get_current_auth_context(request)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "role": user.role,
        "permissions": list(user.permissions),
    }


def demo_users_allowed() -> bool:
    from app.auth.session_service import demo_users_enabled

    return demo_users_enabled()
