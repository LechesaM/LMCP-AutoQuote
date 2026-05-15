from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    from app.services.self_clean_archive_service import (
        get_self_clean_archive_status,
        run_self_clean_archive,
    )
except Exception:
    get_self_clean_archive_status = None
    run_self_clean_archive = None

BASE_DIR = Path(os.getenv("LMCP_BASE_DIR", "/app"))
RUNTIME_DIR = BASE_DIR / "runtime"
CONTROL_DIR = RUNTIME_DIR / "system_control"
CONTROL_DIR.mkdir(parents=True, exist_ok=True)

DISK_GUARD_FILE = CONTROL_DIR / "disk_guard_status.json"
PAUSE_FILE = CONTROL_DIR / "SYSTEM_PAUSED_LOW_DISK.json"
SCHEDULER_STATUS_FILE = CONTROL_DIR / "self_clean_scheduler_status.json"

MIN_FREE_GB = float(os.getenv("LMCP_MIN_FREE_GB", "10"))
RESUME_FREE_GB = float(os.getenv("LMCP_RESUME_FREE_GB", "15"))
ARCHIVE_EVERY_MINUTES = int(os.getenv("LMCP_ARCHIVE_EVERY_MINUTES", "30"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def get_free_space_gb(path: Path = BASE_DIR) -> float:
    target = path if path.exists() else Path("/")
    usage = shutil.disk_usage(str(target))
    return round(usage.free / (1024 ** 3), 2)


def is_system_paused_for_low_disk() -> bool:
    return PAUSE_FILE.exists()


def get_disk_guard_status() -> Dict[str, Any]:
    free_gb = get_free_space_gb(BASE_DIR)
    paused = is_system_paused_for_low_disk()

    status = "ok"
    action = "continue"

    if paused:
        if free_gb >= RESUME_FREE_GB:
            status = "resume_available"
            action = "resume_allowed"
        else:
            status = "paused_low_disk"
            action = "blocked"
    elif free_gb < MIN_FREE_GB:
        status = "warning_low_disk"
        action = "archive_required"

    payload = {
        "status": status,
        "service_version": "LMCP_DISK_GUARD_V1",
        "free_space_gb": free_gb,
        "min_free_gb": MIN_FREE_GB,
        "resume_free_gb": RESUME_FREE_GB,
        "paused": paused,
        "action": action,
        "pause_file": str(PAUSE_FILE),
        "checked_at": _now(),
    }
    _write_json(DISK_GUARD_FILE, payload)
    return payload


def pause_system_for_low_disk(reason: str = "Low disk space") -> Dict[str, Any]:
    payload = {
        "status": "paused_low_disk",
        "service_version": "LMCP_DISK_GUARD_V1",
        "reason": reason,
        "free_space_gb": get_free_space_gb(BASE_DIR),
        "min_free_gb": MIN_FREE_GB,
        "resume_free_gb": RESUME_FREE_GB,
        "paused_at": _now(),
        "pause_file": str(PAUSE_FILE),
    }
    _write_json(PAUSE_FILE, payload)
    _write_json(DISK_GUARD_FILE, payload)
    return payload


def resume_system_if_safe(force: bool = False) -> Dict[str, Any]:
    free_gb = get_free_space_gb(BASE_DIR)

    if not force and free_gb < RESUME_FREE_GB:
        return {
            "status": "blocked",
            "message": "System cannot resume yet. Free space is still below resume threshold.",
            "free_space_gb": free_gb,
            "resume_free_gb": RESUME_FREE_GB,
            "force_available": True,
            "checked_at": _now(),
        }

    if PAUSE_FILE.exists():
        PAUSE_FILE.unlink()

    status = get_disk_guard_status()
    status["status"] = "resumed"
    status["message"] = "System resumed. Disk guard pause removed."
    status["resumed_at"] = _now()
    _write_json(DISK_GUARD_FILE, status)
    return status


def enforce_disk_guard(auto_archive: bool = True, dry_run: bool = False) -> Dict[str, Any]:
    before = get_disk_guard_status()
    archive_result = None

    if before["free_space_gb"] < MIN_FREE_GB and auto_archive:
        if run_self_clean_archive is None:
            archive_result = {"status": "error", "message": "self_clean_archive_service is not installed."}
        else:
            archive_result = run_self_clean_archive(
                days_to_keep_live=7,
                keep_proofs_live_days=30,
                min_free_gb=MIN_FREE_GB,
                dry_run=dry_run,
            )

    after = get_disk_guard_status()

    if after["free_space_gb"] < MIN_FREE_GB:
        pause = pause_system_for_low_disk(
            reason=f"Free disk space {after['free_space_gb']}GB is below minimum {MIN_FREE_GB}GB."
        )
        final_status = "paused_low_disk"
    else:
        pause = None
        final_status = "ok"

    payload = {
        "status": final_status,
        "service_version": "LMCP_DISK_GUARD_V1",
        "before": before,
        "archive_result": archive_result,
        "after": get_disk_guard_status(),
        "pause_result": pause,
        "dry_run": dry_run,
        "checked_at": _now(),
    }
    _write_json(DISK_GUARD_FILE, payload)
    return payload


def run_scheduled_self_clean(dry_run: bool = False) -> Dict[str, Any]:
    previous = _read_json(SCHEDULER_STATUS_FILE, {})
    free_before = get_free_space_gb(BASE_DIR)

    if run_self_clean_archive is None:
        result = {"status": "error", "message": "self_clean_archive_service is not installed.", "checked_at": _now()}
        _write_json(SCHEDULER_STATUS_FILE, result)
        return result

    archive_result = run_self_clean_archive(
        days_to_keep_live=7,
        keep_proofs_live_days=30,
        min_free_gb=MIN_FREE_GB,
        dry_run=dry_run,
    )
    guard_result = enforce_disk_guard(auto_archive=False, dry_run=dry_run)
    free_after = get_free_space_gb(BASE_DIR)

    result = {
        "status": "ok" if guard_result.get("status") != "paused_low_disk" else "paused_low_disk",
        "service_version": "LMCP_SELF_CLEAN_SCHEDULER_V1",
        "dry_run": dry_run,
        "archive_every_minutes": ARCHIVE_EVERY_MINUTES,
        "free_before_gb": free_before,
        "free_after_gb": free_after,
        "archive_result": archive_result,
        "guard_result": guard_result,
        "previous_run": previous.get("last_run_at"),
        "last_run_at": _now(),
    }
    _write_json(SCHEDULER_STATUS_FILE, result)
    return result


def get_self_clean_scheduler_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "LMCP_SELF_CLEAN_SCHEDULER_V1",
        "archive_every_minutes": ARCHIVE_EVERY_MINUTES,
        "disk_guard": get_disk_guard_status(),
        "scheduler": _read_json(SCHEDULER_STATUS_FILE, {}),
        "archive_status": get_self_clean_archive_status() if get_self_clean_archive_status else {},
        "updated_at": _now(),
    }


def assert_disk_safe_or_block() -> Dict[str, Any]:
    status = get_disk_guard_status()
    if status.get("paused") or status.get("free_space_gb", 0) < MIN_FREE_GB:
        if not status.get("paused"):
            pause_system_for_low_disk("Disk guard blocked operation before LMCP run.")
        return {
            "allowed": False,
            "status": "blocked_low_disk",
            "message": "LMCP operation blocked because disk space is below safe threshold.",
            "disk_guard": get_disk_guard_status(),
        }
    return {"allowed": True, "status": "ok", "message": "Disk safe.", "disk_guard": status}
