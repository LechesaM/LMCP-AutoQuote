from __future__ import annotations

import logging
import json
from pathlib import Path
import os
from datetime import datetime, timezone
from typing import Any, Dict

from app.services.autonomous_submission_loop_service import (
    get_autonomous_submission_loop_health,
    get_last_autonomous_submission_loop_run,
    run_autonomous_submission_loop,
)

logger = logging.getLogger(__name__)

DEFAULT_RETRY_LIMIT = int(str(os.getenv("SUBMISSION_RETRY_BATCH_LIMIT", "10")).strip() or "10")
AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED = (
    str(os.getenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", "true")).strip().lower() == "true"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()




# --- Worker/Beat Liveness Watchdog ---
HEARTBEAT_DIR = Path("runtime/watchdog")
HEARTBEAT_FILE = HEARTBEAT_DIR / "submission_scheduler_heartbeat.json"
STALE_SECONDS = int(str(os.getenv("SUBMISSION_SCHEDULER_STALE_SECONDS","600")).strip() or "600")

def _write_scheduler_heartbeat(status: str = "alive") -> None:
    try:
        HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_FILE.write_text(json.dumps({
            "status": status,
            "heartbeat_at": _utc_now_iso()
        }, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Failed writing scheduler heartbeat")

def _read_scheduler_heartbeat() -> Dict[str, Any]:
    try:
        if HEARTBEAT_FILE.exists():
            return json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed reading scheduler heartbeat")
    return {}

def _scheduler_stale_status() -> Dict[str, Any]:
    hb = _read_scheduler_heartbeat()
    heartbeat_at = hb.get("heartbeat_at")
    stale = False
    age_seconds = None
    if heartbeat_at:
        try:
            then = datetime.fromisoformat(str(heartbeat_at))
            age_seconds = int((datetime.now(timezone.utc)-then).total_seconds())
            stale = age_seconds > STALE_SECONDS
        except Exception:
            stale = True
    else:
        stale = True
    return {
        "watchdog_heartbeat": hb,
        "watchdog_stale": stale,
        "watchdog_age_seconds": age_seconds,
        "watchdog_stale_threshold_seconds": STALE_SECONDS,
    }

def get_submission_scheduler_health() -> Dict[str, Any]:
    base = get_autonomous_submission_loop_health()
    return {
        **base,
        **_scheduler_stale_status(),
        "default_retry_limit": DEFAULT_RETRY_LIMIT,
    }


def get_submission_scheduler_last_run() -> Dict[str, Any]:
    return get_last_autonomous_submission_loop_run()


def run_submission_retry_cycle(limit: int | None = None) -> Dict[str, Any]:
    if not AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED:
        return {
            "status": "disabled",
            "checked_at": _utc_now_iso(),
            "message": "Autonomous submission scheduler is disabled by environment flag.",
            "total_retried": 0,
            "retried": [],
            "skipped": [],
        }

    safe_limit = max(1, int(limit or DEFAULT_RETRY_LIMIT))
    _write_scheduler_heartbeat("alive")
    logger.info("Running autonomous submission loop from scheduler service | limit=%s", safe_limit)

    result = run_autonomous_submission_loop(limit=safe_limit)
    if not isinstance(result, dict):
        return {
            "status": "failed",
            "checked_at": _utc_now_iso(),
            "message": "Autonomous submission loop returned unexpected response.",
            "total_retried": 0,
            "retried": [],
            "skipped": [],
        }

    return {
        "status": str(result.get("status") or "ok"),
        "checked_at": str(result.get("checked_at") or _utc_now_iso()),
        "scheduler": str(result.get("scheduler") or "autonomous_submission_loop"),
        **result,
    }




