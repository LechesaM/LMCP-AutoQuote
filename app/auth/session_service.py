from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .rbac import ROLE_PERMISSIONS
from app.core.runtime_paths import get_runtime_paths


RUNTIME_DIR = get_runtime_paths().runtime_root
AUTH_DIR = RUNTIME_DIR / "auth"
AUTH_FILE = AUTH_DIR / "users.json"


@dataclass
class AuthUser:
    user_id: str
    email: str
    display_name: str
    role: str
    password_hash: str


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)


def _load_users() -> Dict[str, Dict[str, Any]]:
    if not AUTH_FILE.exists():
        return {}
    try:
        data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        pass
    return {}


def _save_users(users: Dict[str, Dict[str, Any]]) -> None:
    _ensure_dir()
    AUTH_FILE.write_text(json.dumps(users, indent=2, sort_keys=True), encoding="utf-8")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def demo_users_enabled() -> bool:
    return os.getenv("LMCP_AUTH_ALLOW_DEMO_USERS", "1").strip().lower() in {"1", "true", "yes", "on"}


def _default_demo_users() -> Dict[str, Dict[str, Any]]:
    seeds = [
        ("admin", "admin@lmcp.local", "Admin", "admin", "admin"),
        ("supervisor", "supervisor@lmcp.local", "Supervisor", "supervisor", "supervisor"),
        ("operator", "operator@lmcp.local", "Operator", "operator", "operator"),
        ("read_only", "readonly@lmcp.local", "Read Only", "read_only", "read_only"),
    ]
    return {
        email.lower(): {
            "user_id": user_id,
            "email": email.lower(),
            "display_name": display_name,
            "role": role,
            "password_hash": _hash_password(password),
            "created_at": _now_iso(),
        }
        for user_id, email, display_name, role, password in seeds
    }


def seed_demo_users_if_needed() -> None:
    if not demo_users_enabled():
        return
    users = _load_users()
    changed = False
    for email, record in _default_demo_users().items():
        if email not in users:
            users[email] = record
            changed = True
    if changed:
        _save_users(users)


def create_user(
    user_id: str,
    email: str,
    display_name: str,
    role: str,
    password: str,
    overwrite: bool = False,
) -> AuthUser:
    users = _load_users()
    key = email.lower()
    if key in users and not overwrite:
        raise ValueError(f"User already exists: {email}")
    users[key] = {
        "user_id": user_id,
        "email": key,
        "display_name": display_name,
        "role": role,
        "password_hash": _hash_password(password),
        "created_at": users.get(key, {}).get("created_at") or _now_iso(),
    }
    _save_users(users)
    return AuthUser(
        user_id=user_id,
        email=key,
        display_name=display_name,
        role=role,
        password_hash=users[key]["password_hash"],
    )


def find_user_by_email(email: str) -> Optional[AuthUser]:
    users = _load_users()
    record = users.get(email.lower())
    if not record:
        return None
    return AuthUser(
        user_id=str(record.get("user_id") or ""),
        email=str(record.get("email") or email.lower()),
        display_name=str(record.get("display_name") or ""),
        role=str(record.get("role") or ""),
        password_hash=str(record.get("password_hash") or ""),
    )


def verify_user_password(email: str, password: str) -> bool:
    user = find_user_by_email(email)
    if not user:
        return False
    return user.password_hash == _hash_password(password)


def permissions_for_role(role: str) -> list[str]:
    return list(ROLE_PERMISSIONS.get(role, ()))
