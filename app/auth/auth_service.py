from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request

from .auth_models import AuthPermission
from .jwt_service import decode_token, encode_token
from .rbac import ROLE_PERMISSIONS
from .session_service import (
    create_user,
    demo_users_enabled,
    find_user_by_email,
    permissions_for_role,
    seed_demo_users_if_needed,
    verify_user_password,
)


def _permission_value(permission: str | AuthPermission) -> str:
    return permission.value if isinstance(permission, AuthPermission) else str(permission)


def _user_payload(user) -> Dict[str, Any]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
    }


def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    seed_demo_users_if_needed()
    user = find_user_by_email(email)
    if not user or not verify_user_password(email, password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    permissions = permissions_for_role(user.role)
    payload = {
        "user": _user_payload(user),
        "permissions": permissions,
        "role": user.role,
        "email": user.email,
        "token_type": "bearer",
    }
    payload["access_token"] = encode_token(payload)
    return payload


def _extract_token(request: Request) -> str:
    auth_header = str(request.headers.get("authorization") or request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    cookie_token = str(request.cookies.get("access_token") or request.cookies.get("token") or "").strip()
    return cookie_token


def get_current_user(request: Request) -> Dict[str, Any]:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token.")
    payload = decode_token(token)
    if not isinstance(payload, dict) or "user" not in payload:
        raise HTTPException(status_code=401, detail="Invalid access token.")
    return payload


def require_permission(permission: str | AuthPermission) -> Callable[[Request], Dict[str, Any]]:
    permission_value = _permission_value(permission)

    def dependency(request: Request) -> Dict[str, Any]:
        payload = get_current_user(request)
        permissions = set(payload.get("permissions") or [])
        if permission_value not in permissions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission_value}")
        return payload

    return dependency


def get_demo_users_enabled() -> bool:
    return demo_users_enabled()


def seed_demo_users_if_needed_wrapper() -> None:
    seed_demo_users_if_needed()

