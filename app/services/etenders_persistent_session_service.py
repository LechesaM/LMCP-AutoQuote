from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

RUNTIME_DIR = Path("runtime")
DIR = RUNTIME_DIR / "etenders_session"

STATUS_FILE = DIR / "status.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _save(data: Dict[str, Any]):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(data, indent=2))
    return data


def get_etenders_session_status() -> Dict[str, Any]:
    if STATUS_FILE.exists():
        try:
            data = json.loads(STATUS_FILE.read_text())
        except:
            data = {}
    else:
        data = {}

    return {
        "status": "ok",
        "session": data,
        "message": "Manual login session required. CAPTCHA is not bypassed.",
        "updated_at": _now(),
    }


def probe_persistent_session(headless: bool = True) -> Dict[str, Any]:
    return _save({
        "status": "ok",
        "likely_logged_in": False,
        "login_required": True,
        "message": "Session probe placeholder. Use manual login via Playwright profile.",
        "checked_at": _now(),
    })


def classify_etenders_submission_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    rfq = payload.get("buyer_rfq_number") or ""

    return {
        "status": "manual_action_required",
        "buyer_rfq_number": rfq,
        "reason": "eTenders requires manual login/CAPTCHA. Portal submission cannot be automated safely.",
        "checked_at": _now(),
    }
