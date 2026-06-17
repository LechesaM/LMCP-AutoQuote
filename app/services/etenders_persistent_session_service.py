from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

DEFAULT_RUNTIME_DIR = Path("runtime")


def _runtime_dir(runtime_dir: str | None = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _status_file(runtime_dir: str | None = None) -> Path:
    return _runtime_dir(runtime_dir) / "etenders_session" / "status.json"


_status_file().parent.mkdir(parents=True, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _save(data: Dict[str, Any], runtime_dir: str | None = None):
    status_file = _status_file(runtime_dir)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(data, indent=2))
    return data


def get_etenders_session_status(runtime_dir: str | None = None) -> Dict[str, Any]:
    status_file = _status_file(runtime_dir)
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text())
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


def probe_persistent_session(headless: bool = True, runtime_dir: str | None = None) -> Dict[str, Any]:
    return _save({
        "status": "ok",
        "likely_logged_in": False,
        "login_required": True,
        "message": "Session probe placeholder. Use manual login via Playwright profile.",
        "checked_at": _now(),
    }, runtime_dir=runtime_dir)


def classify_etenders_submission_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    rfq = payload.get("buyer_rfq_number") or ""

    return {
        "status": "manual_action_required",
        "buyer_rfq_number": rfq,
        "reason": "eTenders requires manual login/CAPTCHA. Portal submission cannot be automated safely.",
        "checked_at": _now(),
    }
