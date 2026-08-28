"""Fail-closed authorization for autonomous submission work.

This module is intentionally the single authority for scheduler, retry, and
pending-submission execution.  Manual submission entry points use the
separate system-control-only helper below so a scheduler flag never changes a
human-authorized submission workflow.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable

from app.services.system_control_service import get_system_control_state


def _explicit_true_environment_flag(name: str) -> bool:
    """Return true only for an explicit, unambiguous ``true`` value."""
    value = os.getenv(name)
    return isinstance(value, str) and value.strip().lower() == "true"


def _state_boolean(state: Dict[str, Any], key: str) -> bool:
    """Accept only literal booleans; missing and malformed state is unsafe."""
    return type(state.get(key)) is bool and state[key] is True


def _state_false(state: Dict[str, Any], key: str) -> bool:
    """Require an explicit false pause/stop field rather than assuming it."""
    return type(state.get(key)) is bool and state[key] is False


def _blocked(reason: str, state: Any = None) -> Dict[str, Any]:
    return {
        "authorized": False,
        "reason": reason,
        "system_control_state": state if isinstance(state, dict) else {},
    }


def autonomous_submission_authorization(*, require_pending_stage: bool = False) -> Dict[str, Any]:
    """Evaluate autonomous submission authority freshly at the call site.

    Authorization is granted iff every required deployment flag is explicitly
    ``true`` and the live system-control state explicitly contains literal
    booleans with ``system_on``, ``autonomous_enabled``, and
    ``submission_scheduler_enabled`` all true, and ``submission_paused`` and
    ``emergency_stop`` both false.  Missing, unreadable, stale-normalized, or
    malformed values therefore deny execution.
    """
    required_flags: Iterable[str] = ("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED",)
    if require_pending_stage:
        required_flags = (*required_flags, "AUTONOMOUS_PENDING_STAGE_ENABLED")
    for flag in required_flags:
        if not _explicit_true_environment_flag(flag):
            return _blocked("environment_flag_not_explicitly_enabled:%s" % flag)

    try:
        state = get_system_control_state()
    except Exception as exc:
        return _blocked("system_control_unreadable:%s" % exc)
    if not isinstance(state, dict):
        return _blocked("system_control_unreadable", state)

    for key in ("system_on", "autonomous_enabled", "submission_scheduler_enabled"):
        if not _state_boolean(state, key):
            return _blocked("system_control_not_authorized:%s" % key, state)
    for key in ("submission_paused", "emergency_stop"):
        if not _state_false(state, key):
            return _blocked("system_control_not_authorized:%s" % key, state)

    return {"authorized": True, "reason": "authorized", "system_control_state": state}


def submission_system_control_authorization() -> Dict[str, Any]:
    """Fail-closed master-control check used by manual-capable submission APIs.

    This intentionally does not require autonomous scheduler flags: a manual
    submission remains governed by the master switch and explicit pauses, not
    by whether background automation is enabled.
    """
    try:
        state = get_system_control_state()
    except Exception as exc:
        return _blocked("system_control_unreadable:%s" % exc)
    if not isinstance(state, dict):
        return _blocked("system_control_unreadable", state)
    if not _state_boolean(state, "system_on"):
        return _blocked("system_control_not_authorized:system_on", state)
    for key in ("submission_paused", "emergency_stop"):
        if not _state_false(state, key):
            return _blocked("system_control_not_authorized:%s" % key, state)
    return {"authorized": True, "reason": "authorized", "system_control_state": state}


def system_master_authorization() -> Dict[str, Any]:
    """Fail-closed master-switch authorization for non-submission automation."""
    try:
        state = get_system_control_state()
    except Exception as exc:
        return _blocked("system_control_unreadable:%s" % exc)
    if not isinstance(state, dict):
        return _blocked("system_control_unreadable", state)
    if not _state_boolean(state, "system_on"):
        return _blocked("system_control_not_authorized:system_on", state)
    if not _state_false(state, "emergency_stop"):
        return _blocked("system_control_not_authorized:emergency_stop", state)
    return {"authorized": True, "reason": "authorized", "system_control_state": state}


# Compatibility name for the existing autonomous-engine entry point.
autonomous_engine_system_control_authorization = system_master_authorization
