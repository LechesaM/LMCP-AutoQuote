from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from app.services.weekly_operations_report_service import build_weekly_operations_report


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_report(limit: int = 25) -> Dict[str, Any]:
    return build_weekly_operations_report(limit=limit)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ("password", "secret", "token", "key")):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        text = value
        for token in ("password=", "token=", "secret="):
            if token in text.lower():
                return "[redacted]"
        return text
    return value


def json_safe(payload: Any) -> Any:
    return json.loads(json.dumps(payload, default=str))

