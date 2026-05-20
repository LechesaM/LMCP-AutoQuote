from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

try:  # pragma: no cover - optional dependency
    from passlib.hash import pbkdf2_sha256 as _passlib_pbkdf2
except Exception:  # pragma: no cover - optional dependency
    _passlib_pbkdf2 = None


def hash_password(password: str) -> str:
    value = str(password or "")
    if not value:
        raise ValueError("password is required")
    if _passlib_pbkdf2 is not None:
        return _passlib_pbkdf2.hash(value)
    salt = secrets.token_bytes(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, password_hash: str) -> bool:
    value = str(password or "")
    stored = str(password_hash or "")
    if not value or not stored:
        return False
    if _passlib_pbkdf2 is not None and (stored.startswith("pbkdf2_sha256$") or stored.startswith("$pbkdf2-sha256$")):
        try:
            return bool(_passlib_pbkdf2.verify(value, stored))
        except Exception:
            return False
    try:
        algorithm, iterations_text, salt_b64, digest_b64 = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = max(100_000, int(iterations_text))
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
        digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False
