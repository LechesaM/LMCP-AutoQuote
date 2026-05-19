from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_login_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "runtime"),
        "access_token": payload.get("access_token", ""),
        "token_type": payload.get("token_type", "bearer"),
        "expires_at": payload.get("expires_at", ""),
        "user": payload.get("user", {}),
        "permissions": payload.get("permissions", []),
    }


def build_me_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "runtime"),
        "authenticated": bool(payload.get("authenticated", True)),
        "user": payload.get("user", {}),
        "permissions": payload.get("permissions", []),
        "expires_at": payload.get("expires_at", ""),
    }


def build_permissions_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "runtime"),
        "role": payload.get("role", ""),
        "permissions": payload.get("permissions", []),
    }


def build_logout_response(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = payload or {}
    return {
        "status": data.get("status", "ok"),
        "generated_at": data.get("generated_at", _now_iso()),
        "data_source": data.get("data_source", "runtime"),
        "authenticated": bool(data.get("authenticated", False)),
    }

