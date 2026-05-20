from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from app.core.runtime_paths import get_runtime_paths

logger = logging.getLogger(__name__)

SAFE_STATUSES = {"healthy", "ok", "fresh", "runtime"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, set):
        return [_safe_value(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _snapshot_path(name: str) -> Path:
    return get_runtime_paths().manual_production_file(f"safe_{name}.jsonl")


def _append_record(path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _read_records(path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception as exc:
        logger.exception("Failed to read safe telemetry records from %s: %s", path, exc)
        return []
    return records[-max(1, int(limit or 100)) :]


def _parse_iso(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _snapshot_age_minutes(snapshot: Mapping[str, Any]) -> float:
    generated_at = snapshot.get("generated_at") or snapshot.get("last_safe_snapshot_at")
    parsed = _parse_iso(generated_at)
    if parsed is None:
        return 0.0
    return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60.0), 2)


def _normalise_payload(payload: Mapping[str, Any] | None) -> Dict[str, Any]:
    return _safe_value(dict(payload or {}))


def _is_snapshot_safe(snapshot: Mapping[str, Any], *, stale_after_minutes: int = 15) -> bool:
    status = str(snapshot.get("status") or "").strip().lower()
    if status and status not in SAFE_STATUSES:
        return False
    if bool(snapshot.get("stale_telemetry")):
        return False
    freshness = snapshot.get("telemetry_freshness_minutes")
    try:
        if freshness is not None and float(freshness) > float(stale_after_minutes):
            return False
    except Exception:
        return False
    return True


def is_snapshot_stale(snapshot: Mapping[str, Any], *, stale_after_minutes: int = 15) -> bool:
    if not snapshot:
        return True
    if bool(snapshot.get("stale_telemetry")):
        return True
    return not _is_snapshot_safe(snapshot, stale_after_minutes=stale_after_minutes)


def record_safe_snapshot(category: str, snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    payload = _normalise_payload(snapshot)
    record = {
        "snapshot_id": f"{category}-{datetime.now(timezone.utc).timestamp()}",
        "category": category,
        "generated_at": _now_iso(),
        "payload": payload,
    }
    try:
        return _append_record(_snapshot_path(category), record)
    except Exception as exc:
        logger.exception("Failed to persist safe snapshot for %s: %s", category, exc)
        return {
            "snapshot_id": record["snapshot_id"],
            "category": category,
            "generated_at": record["generated_at"],
            "payload": payload,
            "status": "degraded",
            "warning": f"failed to persist safe snapshot: {exc}",
        }


def get_last_safe_snapshot(category: str, *, limit: int = 1) -> Dict[str, Any]:
    records = _read_records(_snapshot_path(category), limit=limit)
    if not records:
        return {
            "status": "fallback",
            "generated_at": _now_iso(),
            "category": category,
            "payload": {},
            "stale": True,
            "available": False,
        }
    latest = records[-1]
    payload = _normalise_payload(latest.get("payload") or {})
    return {
        "status": "healthy" if _is_snapshot_safe(payload) else "degraded",
        "generated_at": latest.get("generated_at", _now_iso()),
        "category": category,
        "payload": payload,
        "snapshot_id": latest.get("snapshot_id", ""),
        "available": True,
        "stale": is_snapshot_stale(payload),
        "age_minutes": _snapshot_age_minutes(latest),
    }


def build_stale_data_guard_report(
    category: str,
    current_snapshot: Mapping[str, Any] | None,
    *,
    stale_after_minutes: int = 15,
    warnings: Iterable[str] | None = None,
    blockers: Iterable[str] | None = None,
) -> Dict[str, Any]:
    current = _normalise_payload(current_snapshot)
    last_safe = get_last_safe_snapshot(category)
    current_safe = _is_snapshot_safe(current, stale_after_minutes=stale_after_minutes)
    current_stale = is_snapshot_stale(current, stale_after_minutes=stale_after_minutes)
    report_warnings = [str(value).strip() for value in (warnings or []) if str(value).strip()]
    report_blockers = [str(value).strip() for value in (blockers or []) if str(value).strip()]

    if current_safe:
        persisted = record_safe_snapshot(category, current)
        last_safe = {
            "status": "healthy",
            "generated_at": persisted.get("generated_at", _now_iso()),
            "category": category,
            "payload": current,
            "snapshot_id": persisted.get("snapshot_id", ""),
            "available": True,
            "stale": False,
            "age_minutes": 0.0,
        }
        return {
            "status": str(current.get("status") or "healthy"),
            "generated_at": _now_iso(),
            "data_source": str(current.get("data_source") or "runtime"),
            "stale": False,
            "current_snapshot": current,
            "effective_snapshot": current,
            "last_safe_snapshot": current,
            "last_safe_snapshot_at": current.get("generated_at") or _now_iso(),
            "warnings": report_warnings,
            "blockers": report_blockers,
            "recovery_success": True,
            "advisory_only": True,
        }

    effective_snapshot = last_safe.get("payload") or current
    status = str(current.get("status") or "degraded")
    if not current and not last_safe.get("available"):
        status = "failing"
        report_blockers.append("no safe telemetry snapshot is available")
    elif current_stale or not last_safe.get("available"):
        report_warnings.append("stale telemetry is being served from the last known safe snapshot")

    if last_safe.get("available"):
        report_warnings.append("last known safe telemetry has been preserved for operator visibility")
    if current.get("status") not in SAFE_STATUSES:
        report_blockers.append(f"runtime status is {current.get('status') or 'unknown'}")

    return {
        "status": status if report_blockers else ("degraded" if report_warnings else "healthy"),
        "generated_at": _now_iso(),
        "data_source": "runtime_safe_fallback" if last_safe.get("available") else "fallback",
        "stale": True,
        "current_snapshot": current,
        "effective_snapshot": effective_snapshot,
        "last_safe_snapshot": last_safe.get("payload", {}),
        "last_safe_snapshot_at": last_safe.get("generated_at"),
        "warnings": report_warnings,
        "blockers": report_blockers,
        "recovery_success": bool(last_safe.get("available")),
        "advisory_only": True,
    }

