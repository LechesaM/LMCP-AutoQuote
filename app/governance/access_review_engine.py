from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.auth.session_service import list_users
from app.core.runtime_paths import get_runtime_paths

from ._shared import now_iso


def _db_path() -> str:
    return str(get_runtime_paths().operator_auth_db_path)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _load_sessions() -> List[Dict[str, Any]]:
    path = get_runtime_paths().operator_auth_db_path
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT s.token_hash, s.user_id, s.created_at, s.expires_at, s.last_seen_at, s.revoked_at, u.email, u.display_name, u.role
            FROM auth_sessions s
            JOIN auth_users u ON u.user_id = s.user_id
            ORDER BY s.last_seen_at DESC, s.created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def build_access_review_report() -> Dict[str, Any]:
    users = list_users()
    sessions = _load_sessions()
    privileged_roles = {"admin", "supervisor", "governance"}
    now = datetime.now(timezone.utc)
    stale_sessions: List[Dict[str, Any]] = []
    active_sessions: List[Dict[str, Any]] = []
    for session in sessions:
        expires_at = _parse_iso(session.get("expires_at"))
        last_seen_at = _parse_iso(session.get("last_seen_at"))
        revoked_at = _parse_iso(session.get("revoked_at"))
        session_payload = {
            "user_id": session.get("user_id", ""),
            "email": session.get("email", ""),
            "display_name": session.get("display_name", ""),
            "role": session.get("role", ""),
            "expires_at": session.get("expires_at", ""),
            "last_seen_at": session.get("last_seen_at", ""),
            "revoked": bool(revoked_at),
        }
        if revoked_at or (expires_at and expires_at <= now) or (last_seen_at and (now - last_seen_at) > timedelta(days=30)):
            stale_sessions.append(session_payload)
        else:
            active_sessions.append(session_payload)
    role_distribution = Counter(user.role for user in users)
    privileged_access = [user.to_jsonable_dict() for user in users if user.role in privileged_roles]
    warnings: List[str] = []
    if stale_sessions:
        warnings.append("Stale sessions detected.")
    if privileged_access:
        warnings.append("Privileged access should be reviewed periodically.")
    return {
        "status": "ok" if not stale_sessions else "degraded",
        "generated_at": now_iso(),
        "data_source": "runtime" if users else "fallback",
        "active_users": [user.to_jsonable_dict() for user in users if user.is_active],
        "total_users": len(users),
        "role_distribution": dict(role_distribution),
        "privileged_access": privileged_access,
        "supervisor_admin_assignments": [user.to_jsonable_dict() for user in users if user.role in {"admin", "supervisor"}],
        "governance_role_usage": [user.to_jsonable_dict() for user in users if user.role == "governance"],
        "active_sessions": active_sessions,
        "stale_sessions": stale_sessions,
        "warnings": warnings,
        "stale_access_warnings": len(stale_sessions),
        "requires_manual_review": True,
        "no_automatic_revocation": True,
    }

