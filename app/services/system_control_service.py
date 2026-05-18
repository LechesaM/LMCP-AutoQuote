from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
CONTROL_DIR = RUNTIME_DIR / "system_control"
STATE_FILE = CONTROL_DIR / "state.json"
HARVESTER_PAUSE_FILE = RUNTIME_DIR / "harvester.paused"
SUBMISSION_PAUSE_FILE = RUNTIME_DIR / "submission.paused"
EMERGENCY_STOP_FILE = RUNTIME_DIR / "emergency.stop"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SystemControlState:
    system_enabled: bool = True
    autonomous_enabled: bool = True
    harvester_enabled: bool = True
    submission_scheduler_enabled: bool = True
    last_action: str = "initialized"
    updated_at: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data.get("updated_at"):
            data["updated_at"] = _utc_now_iso()
        return data


class SystemControlService:
    def __init__(self) -> None:
        CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> SystemControlState:
        return SystemControlState(updated_at=_utc_now_iso())

    def _normalize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Accept BOTH schemas:
        # old schema: system_enabled / harvester_enabled / submission_scheduler_enabled
        # new schema: system_on / harvest_paused / submission_paused / emergency_stop
        system_enabled = bool(
            state["system_enabled"] if "system_enabled" in state else state.get("system_on", True)
        )

        if "harvester_enabled" in state:
            harvester_enabled = bool(state.get("harvester_enabled", True))
        else:
            harvester_enabled = not bool(state.get("harvest_paused", False))

        if "submission_scheduler_enabled" in state:
            submission_scheduler_enabled = bool(state.get("submission_scheduler_enabled", True))
        else:
            submission_scheduler_enabled = not bool(state.get("submission_paused", False))

        autonomous_enabled = bool(
            state.get("autonomous_enabled", system_enabled)
        )

        emergency_stop = bool(
            state.get(
                "emergency_stop",
                (not system_enabled and not harvester_enabled and not submission_scheduler_enabled),
            )
        )

        last_action = str(state.get("last_action") or "").strip()
        reason = str(state.get("reason") or last_action or "").strip()
        updated_at = str(state.get("updated_at") or _utc_now_iso()).strip()

        normalized = {
            "system_enabled": system_enabled,
            "autonomous_enabled": autonomous_enabled,
            "harvester_enabled": harvester_enabled,
            "submission_scheduler_enabled": submission_scheduler_enabled,
            "last_action": last_action or ("turned_on" if system_enabled else "turned_off"),
            "updated_at": updated_at,
            "reason": reason,
            # mirrored new-schema fields
            "system_on": system_enabled,
            "harvest_paused": not harvester_enabled,
            "submission_paused": not submission_scheduler_enabled,
            "emergency_stop": emergency_stop,
            "last_changed_by": str(state.get("last_changed_by") or "api").strip() or "api",
        }
        return normalized

    def _sync_flag_files(self, state: Dict[str, Any]) -> None:
        normalized = self._normalize_state(state)

        if normalized["harvest_paused"] or not normalized["system_on"]:
            HARVESTER_PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
            HARVESTER_PAUSE_FILE.touch(exist_ok=True)
        elif HARVESTER_PAUSE_FILE.exists():
            HARVESTER_PAUSE_FILE.unlink()

        if normalized["submission_paused"] or not normalized["system_on"]:
            SUBMISSION_PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
            SUBMISSION_PAUSE_FILE.touch(exist_ok=True)
        elif SUBMISSION_PAUSE_FILE.exists():
            SUBMISSION_PAUSE_FILE.unlink()

        if normalized["emergency_stop"]:
            EMERGENCY_STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
            EMERGENCY_STOP_FILE.touch(exist_ok=True)
        elif EMERGENCY_STOP_FILE.exists():
            EMERGENCY_STOP_FILE.unlink()

    def _write_state(self, state: SystemControlState) -> Dict[str, Any]:
        payload = self._normalize_state(state.to_dict())
        CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._sync_flag_files(payload)
        return payload

    def _read_state(self) -> Dict[str, Any]:
        if not STATE_FILE.exists():
            return self._write_state(self._default_state())
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("State file payload is not a dictionary.")
            normalized = self._normalize_state(raw)
            self._sync_flag_files(normalized)
            return normalized
        except Exception:
            repaired = self._default_state()
            repaired.last_action = "repaired_corrupt_state"
            repaired.reason = "State file was unreadable and was recreated automatically."
            return self._write_state(repaired)

    def get_status(self) -> Dict[str, Any]:
        state = self._read_state()
        state["harvester_pause_file_exists"] = HARVESTER_PAUSE_FILE.exists()
        state["submission_pause_file_exists"] = SUBMISSION_PAUSE_FILE.exists()
        state["emergency_stop_file_exists"] = EMERGENCY_STOP_FILE.exists()
        state["pause_file"] = str(HARVESTER_PAUSE_FILE)
        state["submission_pause_file"] = str(SUBMISSION_PAUSE_FILE)
        state["emergency_stop_file"] = str(EMERGENCY_STOP_FILE)
        state["state_file"] = str(STATE_FILE)
        state["effective_system_status"] = "on" if state.get("system_on") else "off"
        return state

    def is_system_enabled(self) -> bool:
        return bool(self._read_state().get("system_on", True))

    def turn_off(self, reason: str = "Manual shutdown from dashboard") -> Dict[str, Any]:
        state = SystemControlState(
            system_enabled=False,
            autonomous_enabled=False,
            harvester_enabled=False,
            submission_scheduler_enabled=False,
            last_action="turned_off",
            updated_at=_utc_now_iso(),
            reason=reason,
        )
        result = self._write_state(state)
        result["message"] = "LMCP system turned OFF successfully."
        result["effective_system_status"] = "off"
        return result

    def turn_on(self, reason: str = "Manual startup from dashboard") -> Dict[str, Any]:
        state = SystemControlState(
            system_enabled=True,
            autonomous_enabled=True,
            harvester_enabled=True,
            submission_scheduler_enabled=True,
            last_action="turned_on",
            updated_at=_utc_now_iso(),
            reason=reason,
        )
        result = self._write_state(state)
        result["message"] = "LMCP system turned ON successfully."
        result["effective_system_status"] = "on"
        return result

    def toggle(self, reason: str = "Manual toggle from dashboard") -> Dict[str, Any]:
        current = self.get_status()
        if current.get("system_on"):
            return self.turn_off(reason=reason)
        return self.turn_on(reason=reason)

    def pause_harvest(self, reason: str = "harvest paused") -> Dict[str, Any]:
        current = self._read_state()
        current["harvester_enabled"] = False
        current["harvest_paused"] = True
        current["updated_at"] = _utc_now_iso()
        current["last_action"] = "harvest_paused"
        current["reason"] = reason
        STATE_FILE.write_text(json.dumps(self._normalize_state(current), indent=2), encoding="utf-8")
        return self.get_status()

    def resume_harvest(self, reason: str = "harvest resumed") -> Dict[str, Any]:
        current = self._read_state()
        current["harvester_enabled"] = True
        current["harvest_paused"] = False
        current["updated_at"] = _utc_now_iso()
        current["last_action"] = "harvest_resumed"
        current["reason"] = reason
        STATE_FILE.write_text(json.dumps(self._normalize_state(current), indent=2), encoding="utf-8")
        return self.get_status()

    def pause_submissions(self, reason: str = "submissions paused") -> Dict[str, Any]:
        current = self._read_state()
        current["submission_scheduler_enabled"] = False
        current["submission_paused"] = True
        current["updated_at"] = _utc_now_iso()
        current["last_action"] = "submissions_paused"
        current["reason"] = reason
        STATE_FILE.write_text(json.dumps(self._normalize_state(current), indent=2), encoding="utf-8")
        return self.get_status()

    def resume_submissions(self, reason: str = "submissions resumed") -> Dict[str, Any]:
        current = self._read_state()
        current["submission_scheduler_enabled"] = True
        current["submission_paused"] = False
        current["updated_at"] = _utc_now_iso()
        current["last_action"] = "submissions_resumed"
        current["reason"] = reason
        STATE_FILE.write_text(json.dumps(self._normalize_state(current), indent=2), encoding="utf-8")
        return self.get_status()

    def emergency_stop(self, reason: str = "emergency stop activated") -> Dict[str, Any]:
        current = self._read_state()
        current["system_enabled"] = False
        current["autonomous_enabled"] = False
        current["harvester_enabled"] = False
        current["submission_scheduler_enabled"] = False
        current["system_on"] = False
        current["harvest_paused"] = True
        current["submission_paused"] = True
        current["emergency_stop"] = True
        current["updated_at"] = _utc_now_iso()
        current["last_action"] = "emergency_stop"
        current["reason"] = reason
        STATE_FILE.write_text(json.dumps(self._normalize_state(current), indent=2), encoding="utf-8")
        return self.get_status()

    def clear_emergency_stop(self, reason: str = "emergency stop cleared") -> Dict[str, Any]:
        current = self._read_state()
        current["emergency_stop"] = False
        current["updated_at"] = _utc_now_iso()
        current["last_action"] = "emergency_stop_cleared"
        current["reason"] = reason
        STATE_FILE.write_text(json.dumps(self._normalize_state(current), indent=2), encoding="utf-8")
        return self.get_status()

    def resume_all(self, reason: str = "all services resumed") -> Dict[str, Any]:
        return self.turn_on(reason=reason)


system_control_service = SystemControlService()


def get_system_control_status() -> Dict[str, Any]:
    return system_control_service.get_status()


def get_system_control_state() -> Dict[str, Any]:
    return system_control_service.get_status()


def system_is_enabled() -> bool:
    return system_control_service.is_system_enabled()


def turn_system_off(reason: str = "Manual shutdown from dashboard") -> Dict[str, Any]:
    return system_control_service.turn_off(reason=reason)


def turn_system_on(reason: str = "Manual startup from dashboard") -> Dict[str, Any]:
    return system_control_service.turn_on(reason=reason)


def pause_harvest(reason: str = "harvest paused") -> Dict[str, Any]:
    return system_control_service.pause_harvest(reason=reason)


def resume_harvest(reason: str = "harvest resumed") -> Dict[str, Any]:
    return system_control_service.resume_harvest(reason=reason)


def pause_submissions(reason: str = "submissions paused") -> Dict[str, Any]:
    return system_control_service.pause_submissions(reason=reason)


def resume_submissions(reason: str = "submissions resumed") -> Dict[str, Any]:
    return system_control_service.resume_submissions(reason=reason)


def emergency_stop(reason: str = "emergency stop activated") -> Dict[str, Any]:
    return system_control_service.emergency_stop(reason=reason)


def clear_emergency_stop(reason: str = "emergency stop cleared") -> Dict[str, Any]:
    return system_control_service.clear_emergency_stop(reason=reason)


def resume_all(reason: str = "all services resumed") -> Dict[str, Any]:
    return system_control_service.resume_all(reason=reason)


