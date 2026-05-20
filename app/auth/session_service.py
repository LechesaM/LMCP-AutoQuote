from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

from fastapi import Request

from app.auth.auth_models import AuthContext, AuthUserRecord, DEMO_USERS
from app.auth.jwt_service import decode_token, encode_token
from app.auth.passwords import hash_password, verify_password
from app.auth.rbac import permissions_for_role
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths

_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _db_path() -> Path:
    return get_runtime_paths().operator_auth_db_path


def _db_conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def demo_users_enabled() -> bool:
    override = os.environ.get("LMCP_AUTH_ALLOW_DEMO_USERS")
    if override is not None:
        return _truthy(override)
    config = get_runtime_config()
    return config.environment not in {"production"} and config.mode.value not in {"locked_production"}


def ensure_auth_schema() -> None:
    with _LOCK:
        conn = _db_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES auth_users(user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);
                """
            )
            conn.commit()
        finally:
            conn.close()


def _clear_expired_sessions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM auth_sessions WHERE revoked_at IS NOT NULL OR expires_at <= ?", (_now_iso(),))


def _row_to_user(row: sqlite3.Row) -> AuthUserRecord:
    return AuthUserRecord(
        user_id=str(row["user_id"] or ""),
        email=str(row["email"] or ""),
        display_name=str(row["display_name"] or ""),
        role=str(row["role"] or "").lower(),
        password_hash=str(row["password_hash"] or ""),
        is_active=bool(int(row["is_active"] or 0)),
        created_at=str(row["created_at"] or ""),
        last_login_at=str(row["last_login_at"] or ""),
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _seed_demo_users(conn: sqlite3.Connection) -> None:
    if not demo_users_enabled():
        return
    row = conn.execute("SELECT COUNT(1) AS count FROM auth_users").fetchone()
    if row and int(row["count"] or 0) > 0:
        return
    created_at = _now_iso()
    for demo in DEMO_USERS:
        conn.execute(
            """
            INSERT OR REPLACE INTO auth_users (user_id, email, display_name, role, password_hash, is_active, created_at, last_login_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, NULL)
            """,
            (
                demo["user_id"],
                demo["email"],
                demo["display_name"],
                demo["role"],
                hash_password(demo["password"]),
                created_at,
            ),
        )
    conn.commit()


def seed_demo_users_if_needed() -> None:
    ensure_auth_schema()
    with _LOCK:
        conn = _db_conn()
        try:
            _seed_demo_users(conn)
        finally:
            conn.close()


def create_user(
    user_id: str,
    email: str,
    display_name: str,
    role: str,
    password: str,
    *,
    is_active: bool = True,
    overwrite: bool = False,
) -> AuthUserRecord:
    ensure_auth_schema()
    normalized_user_id = str(user_id or "").strip()
    normalized_email = str(email or "").strip().lower()
    normalized_display_name = str(display_name or "").strip()
    normalized_role = str(role or "").strip().lower()
    if not normalized_user_id:
        raise ValueError("user_id is required")
    if not normalized_email:
        raise ValueError("email is required")
    if not normalized_display_name:
        raise ValueError("display_name is required")
    if not normalized_role:
        raise ValueError("role is required")
    password_hash = hash_password(password)
    created_at = _now_iso()
    with _LOCK:
        conn = _db_conn()
        try:
            existing = conn.execute(
                """
                SELECT user_id, email, display_name, role, password_hash, is_active, created_at, last_login_at
                FROM auth_users
                WHERE lower(email) = lower(?) OR user_id = ?
                LIMIT 1
                """,
                (normalized_email, normalized_user_id),
            ).fetchone()
            if existing and not overwrite:
                return _row_to_user(existing)

            conn.execute(
                """
                INSERT OR REPLACE INTO auth_users (user_id, email, display_name, role, password_hash, is_active, created_at, last_login_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_user_id,
                    normalized_email,
                    normalized_display_name,
                    normalized_role,
                    password_hash,
                    1 if is_active else 0,
                    existing["created_at"] if existing and existing["created_at"] else created_at,
                    existing["last_login_at"] if existing and existing["last_login_at"] else "",
                ),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT user_id, email, display_name, role, password_hash, is_active, created_at, last_login_at
                FROM auth_users
                WHERE user_id = ?
                LIMIT 1
                """,
                (normalized_user_id,),
            ).fetchone()
            if not row:
                raise RuntimeError("Unable to create auth user.")
            return _row_to_user(row)
        finally:
            conn.close()


def list_users() -> List[AuthUserRecord]:
    seed_demo_users_if_needed()
    with _LOCK:
        conn = _db_conn()
        try:
            rows = conn.execute(
                "SELECT user_id, email, display_name, role, password_hash, is_active, created_at, last_login_at FROM auth_users ORDER BY role, email"
            ).fetchall()
            return [_row_to_user(row) for row in rows]
        finally:
            conn.close()


def find_user_by_email(email: str) -> Optional[AuthUserRecord]:
    seed_demo_users_if_needed()
    with _LOCK:
        conn = _db_conn()
        try:
            row = conn.execute(
                "SELECT user_id, email, display_name, role, password_hash, is_active, created_at, last_login_at FROM auth_users WHERE lower(email) = lower(?) LIMIT 1",
                (str(email or ""),),
            ).fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()


def find_user_by_id(user_id: str) -> Optional[AuthUserRecord]:
    seed_demo_users_if_needed()
    with _LOCK:
        conn = _db_conn()
        try:
            row = conn.execute(
                "SELECT user_id, email, display_name, role, password_hash, is_active, created_at, last_login_at FROM auth_users WHERE user_id = ? LIMIT 1",
                (str(user_id or ""),),
            ).fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()


def update_last_login(user_id: str) -> None:
    with _LOCK:
        conn = _db_conn()
        try:
            conn.execute("UPDATE auth_users SET last_login_at = ? WHERE user_id = ?", (_now_iso(), str(user_id or "")))
            conn.commit()
        finally:
            conn.close()


def create_session(user: AuthUserRecord, *, expires_seconds: int = 8 * 60 * 60) -> Tuple[str, str]:
    ensure_auth_schema()
    payload = {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "permissions": list(permissions_for_role(user.role)),
    }
    token = encode_token(payload, expires_seconds=expires_seconds)
    expires_at = (_now() + timedelta(seconds=expires_seconds)).isoformat()
    with _LOCK:
        conn = _db_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO auth_sessions (token_hash, user_id, created_at, expires_at, last_seen_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (_token_hash(token), user.user_id, _now_iso(), expires_at, _now_iso()),
            )
            conn.execute("UPDATE auth_users SET last_login_at = ? WHERE user_id = ?", (_now_iso(), user.user_id))
            conn.commit()
        finally:
            conn.close()
    return token, expires_at


def revoke_session(token: str) -> None:
    if not token:
        return
    with _LOCK:
        conn = _db_conn()
        try:
            conn.execute("UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ?", (_now_iso(), _token_hash(token)))
            conn.commit()
        finally:
            conn.close()


def _row_to_context(row: sqlite3.Row, token: str = "") -> AuthContext:
    permissions = permissions_for_role(str(row["role"] or ""))
    return AuthContext(
        user_id=str(row["user_id"] or ""),
        email=str(row["email"] or ""),
        display_name=str(row["display_name"] or ""),
        role=str(row["role"] or "").lower(),
        permissions=permissions,
        authenticated=True,
        auth_source="jwt",
        token=token,
        expires_at=str(row["expires_at"] or ""),
    )


def _session_user_from_token(token: str) -> Optional[AuthContext]:
    if not token:
        return None
    try:
        decode_token(token)
    except Exception:
        return None
    with _LOCK:
        conn = _db_conn()
        try:
            _clear_expired_sessions(conn)
            row = conn.execute(
                """
                SELECT u.user_id, u.email, u.display_name, u.role, s.expires_at
                FROM auth_sessions s
                JOIN auth_users u ON u.user_id = s.user_id
                WHERE s.token_hash = ?
                  AND s.revoked_at IS NULL
                  AND s.expires_at > ?
                  AND u.is_active = 1
                LIMIT 1
                """,
                (_token_hash(token), _now_iso()),
            ).fetchone()
            if not row:
                return None
            conn.execute("UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?", (_now_iso(), _token_hash(token)))
            conn.commit()
            return _row_to_context(row, token=token)
        finally:
            conn.close()


def authenticate_credentials(email: str, password: str) -> AuthContext:
    seed_demo_users_if_needed()
    user = find_user_by_email(email)
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password.")
    token, expires_at = create_session(user)
    return AuthContext(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        permissions=permissions_for_role(user.role),
        authenticated=True,
        auth_source="jwt",
        token=token,
        expires_at=expires_at,
    )


def get_token_from_request(request: Request | None) -> str:
    if request is None:
        return ""
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return str(request.cookies.get("lmcp_auth_token") or "").strip()


def get_current_user_from_request(request: Request | None) -> AuthContext:
    token = get_token_from_request(request)
    user = _session_user_from_token(token)
    if not user:
        raise ValueError("Authentication required.")
    return user


def permissions_for_current_user(request: Request | None):
    return get_current_user_from_request(request).permissions
