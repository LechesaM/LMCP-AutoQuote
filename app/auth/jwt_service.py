from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.core.runtime_config import get_runtime_config

try:  # pragma: no cover - optional dependency
    import jwt as pyjwt
except Exception:  # pragma: no cover - optional dependency
    pyjwt = None

try:  # pragma: no cover - optional dependency
    from jose import jwt as jose_jwt
except Exception:  # pragma: no cover - optional dependency
    jose_jwt = None


def _secret_key() -> str:
    from app.config import get_settings

    return get_settings().secret_key or "lmcp-dev-secret"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode_fallback(payload: Dict[str, Any], secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"lmcp.{body}.{sig}"


def _decode_fallback(token: str, secret: str) -> Dict[str, Any]:
    if not token.startswith("lmcp."):
        raise ValueError("Unsupported token format")
    _, body, sig = token.split(".", 2)
    expected = base64.urlsafe_b64encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()).decode("ascii").rstrip("=")
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid token signature")
    padded = body + "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    exp = int(payload.get("exp") or 0)
    if exp and exp < int(_now().timestamp()):
        raise ValueError("Token expired")
    return payload


def encode_token(payload: Dict[str, Any], *, expires_seconds: int = 8 * 60 * 60, secret: str | None = None) -> str:
    secret_key = secret or _secret_key()
    issued_at = _now()
    full_payload = dict(payload)
    full_payload["iat"] = int(issued_at.timestamp())
    full_payload["exp"] = int((issued_at + timedelta(seconds=expires_seconds)).timestamp())
    if pyjwt is not None:  # pragma: no cover - optional dependency
        return str(pyjwt.encode(full_payload, secret_key, algorithm="HS256"))
    if jose_jwt is not None:  # pragma: no cover - optional dependency
        return str(jose_jwt.encode(full_payload, secret_key, algorithm="HS256"))
    return _encode_fallback(full_payload, secret_key)


def decode_token(token: str, *, secret: str | None = None) -> Dict[str, Any]:
    secret_key = secret or _secret_key()
    if pyjwt is not None:  # pragma: no cover - optional dependency
        return dict(pyjwt.decode(token, secret_key, algorithms=["HS256"]))
    if jose_jwt is not None:  # pragma: no cover - optional dependency
        return dict(jose_jwt.decode(token, secret_key, algorithms=["HS256"]))
    return _decode_fallback(token, secret_key)

