from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
STATE_DIR = RUNTIME_DIR / "system_state"
STATE_FILE = STATE_DIR / "system_state.json"
V48_STATE_FILE = RUNTIME_DIR / "system_control" / "v48_autonomous_state.json"
V48_POLICY_FILE = RUNTIME_DIR / "full_autonomous_v48" / "policy.json"

# RLock prevents deadlock when a write path needs to read/normalize state
# within the same thread before persisting.
_STATE_LOCK = RLock()

DEFAULT_STATE: Dict[str, Any] = {
    "system_on": True,
    "harvest_paused": False,
    "submission_paused": False,
    "emergency_stop": False,
    "updated_at": None,
    "reason": "",
    "last_changed_by": "system",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _resolve_control_mode(state: Dict[str, Any]) -> str:
    candidate_sources = (
        state.get("control_mode"),
        state.get("mode"),
        state.get("policy", {}).get("mode") if isinstance(state.get("policy"), dict) else None,
        _read_json(V48_STATE_FILE).get("policy", {}).get("mode"),
        _read_json(V48_POLICY_FILE).get("mode"),
    )
    for raw_mode in candidate_sources:
        mode = str(raw_mode or "").strip().lower()
        if mode:
            return mode
    return "on"


def _ensure_runtime_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_state(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state = deepcopy(DEFAULT_STATE)
    if isinstance(data, dict):
        state.update(data)

    state["system_on"] = bool(state.get("system_on", True))
    state["harvest_paused"] = bool(state.get("harvest_paused", False))
    state["submission_paused"] = bool(state.get("submission_paused", False))
    state["emergency_stop"] = bool(state.get("emergency_stop", False))
    state["updated_at"] = state.get("updated_at") or _utc_now_iso()
    state["reason"] = str(state.get("reason") or "")
    state["last_changed_by"] = str(state.get("last_changed_by") or "system")
    control_mode = _resolve_control_mode(state)
    if not state["system_on"] or state["emergency_stop"]:
        effective_system_status = "off"
    elif control_mode == "controlled":
        effective_system_status = "controlled"
    else:
        effective_system_status = "on"
    state["control_mode"] = control_mode
    state["effective_system_status"] = effective_system_status
    return state


def _write_state_unlocked(state: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_runtime_dir()
    normalized = _normalize_state(state)
    STATE_FILE.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized


def _read_state_unlocked() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return _write_state_unlocked(DEFAULT_STATE)

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        normalized = _normalize_state(data)
        if normalized != data:
            return _write_state_unlocked(normalized)
        return normalized
    except Exception:
        return _write_state_unlocked(DEFAULT_STATE)


def initialize_system_state() -> Dict[str, Any]:
    with _STATE_LOCK:
        return _read_state_unlocked()


def get_system_state() -> Dict[str, Any]:
    with _STATE_LOCK:
        return _read_state_unlocked()


def save_system_state(
    *,
    system_on: Optional[bool] = None,
    harvest_paused: Optional[bool] = None,
    submission_paused: Optional[bool] = None,
    emergency_stop: Optional[bool] = None,
    reason: Optional[str] = None,
    last_changed_by: str = "api",
) -> Dict[str, Any]:
    with _STATE_LOCK:
        current = _read_state_unlocked()

        if system_on is not None:
            current["system_on"] = bool(system_on)
        if harvest_paused is not None:
            current["harvest_paused"] = bool(harvest_paused)
        if submission_paused is not None:
            current["submission_paused"] = bool(submission_paused)
        if emergency_stop is not None:
            current["emergency_stop"] = bool(emergency_stop)

        if reason is not None:
            current["reason"] = str(reason)
        current["last_changed_by"] = str(last_changed_by or "api")
        current["updated_at"] = _utc_now_iso()

        return _write_state_unlocked(current)


def set_system_on(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        system_on=True,
        emergency_stop=False,
        reason=reason or "system turned on",
        last_changed_by=last_changed_by,
    )


def set_system_off(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        system_on=False,
        reason=reason or "system turned off",
        last_changed_by=last_changed_by,
    )


def pause_harvest(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        harvest_paused=True,
        reason=reason or "harvest paused",
        last_changed_by=last_changed_by,
    )


def resume_harvest(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        harvest_paused=False,
        reason=reason or "harvest resumed",
        last_changed_by=last_changed_by,
    )


def pause_submissions(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        submission_paused=True,
        reason=reason or "submissions paused",
        last_changed_by=last_changed_by,
    )


def resume_submissions(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        submission_paused=False,
        reason=reason or "submissions resumed",
        last_changed_by=last_changed_by,
    )


def set_emergency_stop(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        emergency_stop=True,
        system_on=False,
        reason=reason or "emergency stop activated",
        last_changed_by=last_changed_by,
    )


def clear_emergency_stop(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        emergency_stop=False,
        reason=reason or "emergency stop cleared",
        last_changed_by=last_changed_by,
    )


def resume_all(reason: str = "", last_changed_by: str = "api") -> Dict[str, Any]:
    return save_system_state(
        system_on=True,
        harvest_paused=False,
        submission_paused=False,
        emergency_stop=False,
        reason=reason or "all services resumed",
        last_changed_by=last_changed_by,
    )


def is_system_enabled() -> bool:
    state = get_system_state()
    return bool(state.get("system_on")) and not bool(state.get("emergency_stop"))


def can_run_harvest() -> bool:
    state = get_system_state()
    return (
        bool(state.get("system_on"))
        and not bool(state.get("emergency_stop"))
        and not bool(state.get("harvest_paused"))
    )


def can_run_submissions() -> bool:
    state = get_system_state()
    return (
        bool(state.get("system_on"))
        and not bool(state.get("emergency_stop"))
        and not bool(state.get("submission_paused"))
    )


def get_block_reason(scope: str = "system") -> Optional[str]:
    state = get_system_state()

    if state.get("emergency_stop"):
        return "emergency_stop"

    if not state.get("system_on"):
        return "system_off"

    if scope == "harvest" and state.get("harvest_paused"):
        return "harvest_paused"

    if scope == "submission" and state.get("submission_paused"):
        return "submission_paused"

    return None


initialize_system_state()
