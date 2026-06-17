from __future__ import annotations

import base64
import json
from typing import Any, Dict


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def encode_token(payload: Dict[str, Any]) -> str:
    return _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def decode_token(token: str) -> Dict[str, Any]:
    raw = _b64decode(str(token))
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Token payload is invalid.")
    return data
