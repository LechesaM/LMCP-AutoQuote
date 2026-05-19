from __future__ import annotations

import base64
import hashlib
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Request, Response

from app.config import settings
RUNTIME_DIR = settings.runtime_dir
OPERATOR_AUTH_DB = settings.operator_auth_db_path
OPERATOR_AUTH_DIR = OPERATOR_AUTH_DB.parent
OPERATOR_SESSION_COOKIE_NAME = settings.operator_session_cookie_name
OPERATOR_SESSION_TIMEOUT_SECONDS = settings.operator_session_timeout_seconds
OPERATOR_SESSION_COOKIE_SECURE = settings.operator_session_cookie_secure
OPERATOR_AUTH_ALLOW_DEV_FALLBACK = settings.operator_auth_allow_dev_fallback
ALLOWED_OPERATOR_ROLES = ("preparer", "reviewer", "submitter", "admin")
OPERATOR_ACTION_ALLOWED_ROLES = {
    "submission_proof_save": ("submitter", "admin"),
    "submission_proof_load": ("submitter", "admin"),
    "submission_proof_export": ("submitter", "admin"),
    "compliance_archive_create": ("admin",),
    "compliance_archive_zip_export": ("admin",),
    "dashboard_archive_workflow": ("reviewer", "admin"),
    "dashboard_refuse_workflow": ("reviewer", "admin"),
    "dashboard_operator_note": ("preparer", "reviewer", "submitter", "admin"),
    "dashboard_acknowledge_warning": ("preparer", "reviewer", "submitter", "admin"),
}
OPERATOR_ACTION_LABELS = {
    "submission_proof_save": "save manual submission proof",
    "submission_proof_load": "load manual submission proof",
    "submission_proof_export": "export manual submission proof",
    "compliance_archive_create": "create compliance archives",
    "compliance_archive_zip_export": "export compliance archive ZIP files",
}

_DB_LOCK = threading.Lock()


class OperatorAuthError(PermissionError):
    def __init__(self, message: str, status_code: int = 401, audit_payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.audit_payload = dict(audit_payload or {})


class OperatorPermissionError(OperatorAuthError):
    def __init__(self, message: str, audit_payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=403, audit_payload=audit_payload)


@dataclass(frozen=True)
class OperatorContext:
    operator_id: str
    display_name: str
    role: str
    authenticated: bool
    auth_source: str
    session_token: str = ""
    session_expires_at: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_text(value: Any, max_length: int = 160) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return ""
    return text[:max_length]


def _normalize_role(value: Any) -> str:
    return _safe_text(value, 40).lower()


def _db_conn() -> sqlite3.Connection:
    OPERATOR_AUTH_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(OPERATOR_AUTH_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema() -> None:
    with _DB_LOCK:
        conn = _db_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS operators (
                    operator_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_token_hash TEXT PRIMARY KEY,
                    operator_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(operator_id) REFERENCES operators(operator_id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_operator_id ON sessions(operator_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
                """
            )
            conn.commit()
        finally:
            conn.close()


def ensure_operator_auth_schema() -> None:
    _ensure_schema()


def _hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = secrets.token_bytes(16)
    if hasattr(hashlib, "scrypt"):
        n = 2 ** 14
        r = 8
        p = 1
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
        return "scrypt$%d$%d$%d$%s$%s" % (
            n,
            r,
            p,
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    iterations = 600000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        parts = password_hash.split("$")
        algorithm = parts[0]
        if algorithm == "scrypt" and len(parts) == 6 and hasattr(hashlib, "scrypt"):
            _, n_text, r_text, p_text, salt_b64, digest_b64 = parts
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(digest_b64.encode("ascii"))
            digest = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=max(2 ** 14, int(n_text)),
                r=max(8, int(r_text)),
                p=max(1, int(p_text)),
            )
            return secrets.compare_digest(digest, expected)
        if algorithm == "pbkdf2_sha256" and len(parts) == 4:
            _, iterations_text, salt_b64, digest_b64 = parts
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(digest_b64.encode("ascii"))
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                max(100000, int(iterations_text)),
            )
            return secrets.compare_digest(digest, expected)
        return False
    except Exception:
        return False


def _session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _operator_audit_payload(operator: Optional[OperatorContext]) -> Dict[str, Any]:
    if not operator:
        return {"auth_source": "anonymous"}
    return {
        "operator_id": operator.operator_id,
        "operator_display_name": operator.display_name,
        "operator_name": operator.display_name,
        "operator_role": operator.role,
        "auth_source": operator.auth_source,
        "authenticated": operator.authenticated,
    }


def operator_audit_payload(operator: Optional[OperatorContext]) -> Dict[str, Any]:
    return _operator_audit_payload(operator)


def _session_payload(operator: OperatorContext) -> Dict[str, Any]:
    return {
        "status": "authenticated",
        "authenticated": True,
        "operator": {
            "operator_id": operator.operator_id,
            "display_name": operator.display_name,
            "role": operator.role,
        },
        "auth_source": operator.auth_source,
        "session_expires_at": operator.session_expires_at,
        "dev_fallback_enabled": OPERATOR_AUTH_ALLOW_DEV_FALLBACK,
    }


def _delete_expired_sessions(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM sessions WHERE revoked_at IS NOT NULL OR expires_at <= ?",
        (_now_iso(),),
    )


def _row_to_operator_context(row: sqlite3.Row, session_token: str = "", auth_source: str = "session") -> OperatorContext:
    return OperatorContext(
        operator_id=_safe_text(row["operator_id"], 160),
        display_name=_safe_text(row["display_name"], 160),
        role=_normalize_role(row["role"]),
        authenticated=True,
        auth_source=auth_source,
        session_token=session_token,
        session_expires_at=_safe_text(row["expires_at"], 80),
    )


def _read_dev_fallback_operator(request: Request) -> Optional[OperatorContext]:
    role = _normalize_role(request.headers.get("X-LMCP-Operator-Role"))
    display_name = _safe_text(request.headers.get("X-LMCP-Operator-Name"), 160)
    if not role and not display_name:
        return None
    if role not in ALLOWED_OPERATOR_ROLES:
        raise OperatorAuthError(
            f"Unknown operator role '{_safe_text(request.headers.get('X-LMCP-Operator-Role'), 80) or 'missing'}'. Allowed roles: {', '.join(ALLOWED_OPERATOR_ROLES)}.",
            audit_payload={"auth_source": "dev_fallback", "operator_role": role or "", "operator_display_name": display_name},
        )
    if not display_name:
        raise OperatorAuthError(
            "Operator name is required via X-LMCP-Operator-Name.",
            audit_payload={"auth_source": "dev_fallback", "operator_role": role},
        )
    return OperatorContext(
        operator_id=f"dev-fallback:{display_name.lower().replace(' ', '-')[:80]}",
        display_name=display_name,
        role=role,
        authenticated=False,
        auth_source="dev_fallback",
        session_expires_at="",
    )


def require_operator_access(action: str, operator: Optional[OperatorContext]) -> OperatorContext:
    if not operator:
        raise OperatorAuthError(
            "Login required. Operator session is missing or expired.",
            audit_payload={"auth_source": "anonymous", "session_present": False},
        )
    if operator.role not in ALLOWED_OPERATOR_ROLES:
        raise OperatorPermissionError(
            f"Unknown operator role '{operator.role}'. Allowed roles: {', '.join(ALLOWED_OPERATOR_ROLES)}.",
            audit_payload=_operator_audit_payload(operator),
        )
    allowed_roles = OPERATOR_ACTION_ALLOWED_ROLES.get(action, ())
    if operator.role not in allowed_roles:
        label = OPERATOR_ACTION_LABELS.get(action, action.replace("_", " "))
        raise OperatorPermissionError(
            f"Operator role '{operator.role}' cannot {label}.",
            audit_payload=_operator_audit_payload(operator),
        )
    return operator


def bootstrap_admin(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_schema()
    data = payload or {}
    operator_id = _safe_text(data.get("operator_id"), 120)
    display_name = _safe_text(data.get("display_name"), 160)
    password = str(data.get("password") or "")
    if not operator_id:
        raise ValueError("operator_id is required.")
    if not display_name:
        raise ValueError("display_name is required.")
    if not password:
        raise ValueError("password is required.")
    password_hash = _hash_password(password)
    created_at = _now_iso()
    with _DB_LOCK:
        conn = _db_conn()
        try:
            _delete_expired_sessions(conn)
            existing_admin = conn.execute("SELECT 1 FROM operators WHERE role = 'admin' LIMIT 1").fetchone()
            if existing_admin:
                raise ValueError("Bootstrap admin is already configured.")
            conn.execute(
                """
                INSERT INTO operators (operator_id, display_name, role, password_hash, is_active, created_at, last_login_at)
                VALUES (?, ?, 'admin', ?, 1, ?, NULL)
                """,
                (operator_id, display_name, password_hash, created_at),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "status": "ok",
        "message": "Bootstrap admin created locally.",
        "operator": {
            "operator_id": operator_id,
            "display_name": display_name,
            "role": "admin",
            "is_active": True,
            "created_at": created_at,
            "last_login_at": None,
        },
        "dev_fallback_enabled": OPERATOR_AUTH_ALLOW_DEV_FALLBACK,
    }


def login_operator(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_schema()
    data = payload or {}
    operator_id = _safe_text(data.get("operator_id"), 120)
    password = str(data.get("password") or "")
    if not operator_id or not password:
        raise OperatorAuthError("operator_id and password are required.")
    with _DB_LOCK:
        conn = _db_conn()
        try:
            _delete_expired_sessions(conn)
            row = conn.execute(
                """
                SELECT operator_id, display_name, role, password_hash, is_active, created_at, last_login_at
                FROM operators
                WHERE operator_id = ?
                LIMIT 1
                """,
                (operator_id,),
            ).fetchone()
            if not row or not int(row["is_active"] or 0):
                raise OperatorAuthError("Invalid operator ID or password.")
            if not _verify_password(password, str(row["password_hash"] or "")):
                raise OperatorAuthError("Invalid operator ID or password.")
            token = secrets.token_urlsafe(32)
            created_at = _now()
            expires_at = created_at + timedelta(seconds=OPERATOR_SESSION_TIMEOUT_SECONDS)
            token_hash = _session_token_hash(token)
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (session_token_hash, operator_id, created_at, expires_at, last_seen_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (token_hash, operator_id, created_at.isoformat(), expires_at.isoformat(), created_at.isoformat()),
            )
            conn.execute(
                "UPDATE operators SET last_login_at = ? WHERE operator_id = ?",
                (created_at.isoformat(), operator_id),
            )
            conn.commit()
            operator = OperatorContext(
                operator_id=operator_id,
                display_name=_safe_text(row["display_name"], 160),
                role=_normalize_role(row["role"]),
                authenticated=True,
                auth_source="session",
                session_token=token,
                session_expires_at=expires_at.isoformat(),
            )
            return {
                **_session_payload(operator),
                "session_token": token,
                "message": "Operator login successful.",
                "session_timeout_seconds": OPERATOR_SESSION_TIMEOUT_SECONDS,
            }
        finally:
            conn.close()


def _session_token_from_request(request: Request) -> str:
    cookie_token = _safe_text(request.cookies.get(OPERATOR_SESSION_COOKIE_NAME), 400)
    if cookie_token:
        return cookie_token
    auth_header = _safe_text(request.headers.get("Authorization"), 500)
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _get_session_operator(token: str, *, extend_session: bool = True) -> Optional[OperatorContext]:
    if not token:
        return None
    _ensure_schema()
    token_hash = _session_token_hash(token)
    with _DB_LOCK:
        conn = _db_conn()
        try:
            _delete_expired_sessions(conn)
            row = conn.execute(
                """
                SELECT
                    operators.operator_id,
                    operators.display_name,
                    operators.role,
                    operators.is_active,
                    sessions.expires_at
                FROM sessions
                JOIN operators ON operators.operator_id = sessions.operator_id
                WHERE sessions.session_token_hash = ?
                  AND sessions.revoked_at IS NULL
                  AND sessions.expires_at > ?
                LIMIT 1
                """,
                (token_hash, _now_iso()),
            ).fetchone()
            if not row or not int(row["is_active"] or 0):
                return None
            if extend_session:
                new_expiry = (_now() + timedelta(seconds=OPERATOR_SESSION_TIMEOUT_SECONDS)).isoformat()
                conn.execute(
                    "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE session_token_hash = ?",
                    (_now_iso(), new_expiry, token_hash),
                )
                conn.commit()
                row = dict(row)
                row["expires_at"] = new_expiry
                return _row_to_operator_context(row, session_token=token)
            return _row_to_operator_context(row, session_token=token)
        finally:
            conn.close()


def get_session_from_request(request: Request) -> OperatorContext:
    token = _session_token_from_request(request)
    operator = _get_session_operator(token)
    if operator:
        return operator
    raise OperatorAuthError(
        "Login required. Operator session is missing or expired.",
        audit_payload={"auth_source": "session", "session_present": bool(token)},
    )


def resolve_request_operator(request: Request, action: str) -> OperatorContext:
    token = _session_token_from_request(request)
    if token:
        operator = _get_session_operator(token)
        if not operator:
            raise OperatorAuthError(
                "Login required. Operator session is missing or expired.",
                audit_payload={"auth_source": "session", "session_present": True},
            )
        return require_operator_access(action, operator)

    if OPERATOR_AUTH_ALLOW_DEV_FALLBACK:
        fallback_operator = _read_dev_fallback_operator(request)
        if fallback_operator:
            return require_operator_access(action, fallback_operator)

    raise OperatorAuthError(
        "Login required. Operator session is missing or expired.",
        audit_payload={"auth_source": "anonymous", "session_present": False},
    )


def get_session_payload(request: Request) -> Dict[str, Any]:
    operator = get_session_from_request(request)
    return {
        **_session_payload(operator),
        "message": "Authenticated operator session loaded.",
        "session_timeout_seconds": OPERATOR_SESSION_TIMEOUT_SECONDS,
    }


def logout_request(request: Request) -> Dict[str, Any]:
    token = _session_token_from_request(request)
    if not token:
        raise OperatorAuthError(
            "Login required. Operator session is missing or expired.",
            audit_payload={"auth_source": "session", "session_present": False},
        )
    operator = _get_session_operator(token, extend_session=False)
    if not operator:
        raise OperatorAuthError(
            "Login required. Operator session is missing or expired.",
            audit_payload={"auth_source": "session", "session_present": True},
        )
    with _DB_LOCK:
        conn = _db_conn()
        try:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE session_token_hash = ?",
                (_now_iso(), _session_token_hash(token)),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "status": "ok",
        "authenticated": False,
        "message": "Operator session ended.",
        "operator": {
            "operator_id": operator.operator_id,
            "display_name": operator.display_name,
            "role": operator.role,
        },
    }


def apply_login_cookie(response: Response, session_payload: Dict[str, Any], request: Optional[Request] = None) -> None:
    operator = session_payload.get("operator") if isinstance(session_payload, dict) else {}
    token = ""
    if request:
        token = _session_token_from_request(request)
    if not token and isinstance(session_payload, dict):
        token = _safe_text(session_payload.get("session_token"), 500)
    if not token:
        token = _safe_text(session_payload.get("_session_token"), 500) if isinstance(session_payload, dict) else ""
    if not token:
        return
    secure = OPERATOR_SESSION_COOKIE_SECURE
    response.set_cookie(
        OPERATOR_SESSION_COOKIE_NAME,
        token,
        max_age=OPERATOR_SESSION_TIMEOUT_SECONDS,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_login_cookie(response: Response) -> None:
    response.delete_cookie(OPERATOR_SESSION_COOKIE_NAME, path="/")


def audit_identity_from_request(request: Request) -> Dict[str, Any]:
    token = _session_token_from_request(request)
    operator = _get_session_operator(token, extend_session=False) if token else None
    if operator:
        return _operator_audit_payload(operator)
    if OPERATOR_AUTH_ALLOW_DEV_FALLBACK:
        try:
            fallback_operator = _read_dev_fallback_operator(request)
        except OperatorAuthError as exc:
            return dict(exc.audit_payload or {})
        if fallback_operator:
            return _operator_audit_payload(fallback_operator)
    return {"auth_source": "anonymous"}
