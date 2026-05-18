from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

RUNTIME_DIR = Path("runtime")
SECURITY_DIR = RUNTIME_DIR / "security"
SECURITY_DIR.mkdir(parents=True, exist_ok=True)
SECURITY_EVENTS_FILE = SECURITY_DIR / "security_events.log"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_operator_pin() -> str:
    return os.getenv("LMCP_OPERATOR_PIN") or os.getenv("OPERATOR_PIN") or "2468"


def verify_operator_pin(pin: str) -> Dict[str, Any]:
    ok = str(pin or "").strip() == str(get_operator_pin()).strip()
    return {
        "status": "ok" if ok else "failed",
        "authorized": ok,
        "message": "Authorized" if ok else "Invalid operator PIN",
    }


def require_operator_pin(x_operator_pin: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    result = verify_operator_pin(x_operator_pin or "")
    if not result["authorized"]:
        raise HTTPException(
            status_code=401,
            detail="Operator PIN required or invalid. Send header: X-Operator-Pin",
        )
    return result


def security_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "operator_pin_configured": bool(get_operator_pin()),
        "pin_source": "environment_or_default",
        "header_name": "X-Operator-Pin",
        "events_file": str(SECURITY_EVENTS_FILE),
        "updated_at": _now_iso(),
    }
