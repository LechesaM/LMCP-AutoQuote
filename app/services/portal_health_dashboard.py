import json
import math
import os
from pathlib import Path
import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

RUNTIME_DIR = os.getenv("LMCP_RUNTIME_DIR", "runtime")

_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str] = None) -> Path:
    return Path(runtime_dir or RUNTIME_DIR)


def _portal_health_file(runtime_dir: Optional[str] = None) -> Path:
    return _runtime_dir(runtime_dir) / "portal_health_state.json"


def _ensure_runtime_dir(runtime_dir: Optional[str] = None) -> None:
    _runtime_dir(runtime_dir).mkdir(parents=True, exist_ok=True)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _round(value: float, digits: int = 2) -> float:
    try:
        return round(float(value), digits)
    except Exception:
        return 0.0


def _default_state() -> Dict[str, Any]:
    return {
        "updated_at": _utc_now_iso(),
        "portals": {}
    }


def _default_portal_record(portal_slug: str, portal_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "portal_slug": portal_slug,
        "portal_name": portal_name or portal_slug,
        "status": "unknown",               # healthy | slow | isolated | error | unknown
        "is_isolated": False,
        "last_checked_at": None,
        "last_success_at": None,
        "last_error_at": None,
        "last_error": None,
        "last_http_status": None,
        "last_duration_seconds": None,
        "avg_duration_seconds": None,
        "total_checks": 0,
        "success_count": 0,
        "failure_count": 0,
        "consecutive_failures": 0,
        "success_rate": 0.0,
        "total_opportunities_seen": 0,
        "notes": None,
    }


def _load_state(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    portal_health_file = _portal_health_file(runtime_dir)
    _ensure_runtime_dir(runtime_dir)
    if not portal_health_file.exists():
        return _default_state()

    try:
        with open(portal_health_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return _default_state()
            if "portals" not in data or not isinstance(data["portals"], dict):
                data["portals"] = {}
            return data
    except Exception:
        return _default_state()


def _save_state(state: Dict[str, Any], runtime_dir: Optional[str] = None) -> None:
    portal_health_file = _portal_health_file(runtime_dir)
    _ensure_runtime_dir(runtime_dir)
    state["updated_at"] = _utc_now_iso()
    tmp_file = portal_health_file.with_name(f"{portal_health_file.name}.tmp")

    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    os.replace(tmp_file, portal_health_file)


def _get_or_create_portal_record(
    state: Dict[str, Any],
    portal_slug: str,
    portal_name: Optional[str] = None,
) -> Dict[str, Any]:
    portals = state.setdefault("portals", {})
    if portal_slug not in portals:
        portals[portal_slug] = _default_portal_record(portal_slug, portal_name)
    else:
        if portal_name and not portals[portal_slug].get("portal_name"):
            portals[portal_slug]["portal_name"] = portal_name
    return portals[portal_slug]


def _recalculate_portal_metrics(record: Dict[str, Any]) -> None:
    total_checks = _safe_int(record.get("total_checks"))
    success_count = _safe_int(record.get("success_count"))
    failure_count = _safe_int(record.get("failure_count"))

    if total_checks <= 0:
        record["success_rate"] = 0.0
    else:
        record["success_rate"] = _round((success_count / total_checks) * 100.0, 2)

    duration = record.get("avg_duration_seconds")
    is_isolated = bool(record.get("is_isolated"))

    if is_isolated:
        record["status"] = "isolated"
    elif failure_count > 0 and success_count == 0:
        record["status"] = "error"
    elif duration is not None and _safe_float(duration) >= 10.0:
        record["status"] = "slow"
    elif success_count > 0:
        record["status"] = "healthy"
    else:
        record["status"] = "unknown"


def register_portal(
    portal_slug: str,
    portal_name: Optional[str] = None,
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    with _LOCK:
        state = _load_state(runtime_dir=runtime_dir)
        record = _get_or_create_portal_record(state, portal_slug, portal_name)
        _recalculate_portal_metrics(record)
        _save_state(state, runtime_dir=runtime_dir)
        return deepcopy(record)


def record_portal_success(
    portal_slug: str,
    portal_name: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    http_status: Optional[int] = 200,
    opportunities_seen: int = 0,
    notes: Optional[str] = None,
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    with _LOCK:
        state = _load_state(runtime_dir=runtime_dir)
        record = _get_or_create_portal_record(state, portal_slug, portal_name)

        record["last_checked_at"] = _utc_now_iso()
        record["last_success_at"] = _utc_now_iso()
        record["last_http_status"] = http_status
        record["last_error"] = None
        record["last_error_at"] = None
        record["notes"] = notes
        record["is_isolated"] = False

        if duration_seconds is not None:
            duration_seconds = _safe_float(duration_seconds)
            record["last_duration_seconds"] = _round(duration_seconds, 3)

            previous_avg = record.get("avg_duration_seconds")
            success_count = _safe_int(record.get("success_count"))

            if previous_avg is None or success_count <= 0:
                record["avg_duration_seconds"] = _round(duration_seconds, 3)
            else:
                new_avg = ((float(previous_avg) * success_count) + duration_seconds) / (success_count + 1)
                record["avg_duration_seconds"] = _round(new_avg, 3)

        record["total_checks"] = _safe_int(record.get("total_checks")) + 1
        record["success_count"] = _safe_int(record.get("success_count")) + 1
        record["consecutive_failures"] = 0
        record["total_opportunities_seen"] = (
            _safe_int(record.get("total_opportunities_seen")) + _safe_int(opportunities_seen)
        )

        _recalculate_portal_metrics(record)
        _save_state(state, runtime_dir=runtime_dir)
        return deepcopy(record)


def record_portal_failure(
    portal_slug: str,
    portal_name: Optional[str] = None,
    error: Optional[str] = None,
    http_status: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    isolated: bool = False,
    notes: Optional[str] = None,
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    with _LOCK:
        state = _load_state(runtime_dir=runtime_dir)
        record = _get_or_create_portal_record(state, portal_slug, portal_name)

        record["last_checked_at"] = _utc_now_iso()
        record["last_error_at"] = _utc_now_iso()
        record["last_error"] = (error or "Unknown portal failure")[:1000]
        record["last_http_status"] = http_status
        record["notes"] = notes
        record["is_isolated"] = isolated or bool(record.get("is_isolated"))

        if duration_seconds is not None:
            record["last_duration_seconds"] = _round(_safe_float(duration_seconds), 3)

        record["total_checks"] = _safe_int(record.get("total_checks")) + 1
        record["failure_count"] = _safe_int(record.get("failure_count")) + 1
        record["consecutive_failures"] = _safe_int(record.get("consecutive_failures")) + 1

        _recalculate_portal_metrics(record)
        _save_state(state, runtime_dir=runtime_dir)
        return deepcopy(record)


def set_portal_isolation(
    portal_slug: str,
    portal_name: Optional[str] = None,
    isolated: bool = True,
    reason: Optional[str] = None,
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    with _LOCK:
        state = _load_state(runtime_dir=runtime_dir)
        record = _get_or_create_portal_record(state, portal_slug, portal_name)

        record["is_isolated"] = bool(isolated)
        record["last_checked_at"] = _utc_now_iso()

        if isolated:
            record["status"] = "isolated"
            record["last_error_at"] = _utc_now_iso()
            record["last_error"] = (reason or "Portal isolated by watchdog")[:1000]
        else:
            if record.get("last_error") == "Portal isolated by watchdog":
                record["last_error"] = None

        _recalculate_portal_metrics(record)
        _save_state(state, runtime_dir=runtime_dir)
        return deepcopy(record)


def _try_load_known_portals() -> List[Dict[str, Any]]:
    """
    Best-effort import so this file can plug into your current system
    without forcing changes to existing registry files.
    """
    known_portals: List[Dict[str, Any]] = []

    # Option 1: app.services.portal_registry.get_all_portals()
    try:
        from app.services.portal_registry import get_all_portals  # type: ignore

        portals = get_all_portals()
        if isinstance(portals, list):
            for portal in portals:
                if isinstance(portal, dict):
                    slug = portal.get("portal_slug") or portal.get("slug")
                    if slug:
                        known_portals.append({
                            "portal_slug": slug,
                            "portal_name": portal.get("portal_name") or portal.get("name") or slug,
                        })
    except Exception:
        pass

    # Option 2: app.services.portal_registry.PORTALS
    if not known_portals:
        try:
            from app.services.portal_registry import PORTALS  # type: ignore

            if isinstance(PORTALS, list):
                for portal in PORTALS:
                    if isinstance(portal, dict):
                        slug = portal.get("portal_slug") or portal.get("slug")
                        if slug:
                            known_portals.append({
                                "portal_slug": slug,
                                "portal_name": portal.get("portal_name") or portal.get("name") or slug,
                            })
        except Exception:
            pass

    # De-duplicate
    deduped = {}
    for p in known_portals:
        deduped[p["portal_slug"]] = p

    return list(deduped.values())


def build_portal_health_dashboard(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    with _LOCK:
        state = _load_state(runtime_dir=runtime_dir)

    known_portals = _try_load_known_portals()

    # Ensure all known portals appear even if no checks yet
    merged_portals: Dict[str, Dict[str, Any]] = {}

    for portal in known_portals:
        slug = portal["portal_slug"]
        merged_portals[slug] = _default_portal_record(
            portal_slug=slug,
            portal_name=portal.get("portal_name") or slug,
        )

    for slug, record in state.get("portals", {}).items():
        base = merged_portals.get(slug, _default_portal_record(slug, record.get("portal_name")))
        base.update(record)
        _recalculate_portal_metrics(base)
        merged_portals[slug] = base

    portal_rows = list(merged_portals.values())

    healthy_count = sum(1 for p in portal_rows if p.get("status") == "healthy")
    slow_count = sum(1 for p in portal_rows if p.get("status") == "slow")
    isolated_count = sum(1 for p in portal_rows if p.get("status") == "isolated")
    error_count = sum(1 for p in portal_rows if p.get("status") == "error")
    unknown_count = sum(1 for p in portal_rows if p.get("status") == "unknown")

    total_portals = len(portal_rows)
    total_checks = sum(_safe_int(p.get("total_checks")) for p in portal_rows)
    total_successes = sum(_safe_int(p.get("success_count")) for p in portal_rows)
    total_failures = sum(_safe_int(p.get("failure_count")) for p in portal_rows)

    overall_success_rate = 0.0
    if total_checks > 0:
        overall_success_rate = _round((total_successes / total_checks) * 100.0, 2)

    avg_response_times = [
        _safe_float(p.get("avg_duration_seconds"))
        for p in portal_rows
        if p.get("avg_duration_seconds") is not None
    ]
    fleet_avg_response_seconds = _round(sum(avg_response_times) / len(avg_response_times), 3) if avg_response_times else 0.0

    portal_rows.sort(
        key=lambda p: (
            0 if p.get("status") == "isolated" else
            1 if p.get("status") == "error" else
            2 if p.get("status") == "slow" else
            3 if p.get("status") == "healthy" else
            4,
            (p.get("portal_name") or p.get("portal_slug") or "").lower(),
        )
    )

    return {
        "dashboard": "portal_health_dashboard",
        "generated_at": _utc_now_iso(),
        "source_file": str(_portal_health_file(runtime_dir)),
        "summary": {
            "total_portals": total_portals,
            "healthy_portals": healthy_count,
            "slow_portals": slow_count,
            "isolated_portals": isolated_count,
            "error_portals": error_count,
            "unknown_portals": unknown_count,
            "total_checks": total_checks,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_success_rate": overall_success_rate,
            "fleet_avg_response_seconds": fleet_avg_response_seconds,
        },
        "portals": portal_rows,
    }
