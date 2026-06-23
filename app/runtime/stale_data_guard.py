from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.runtime_paths import get_runtime_paths


SAFE_FRESHNESS_MINUTES = 15


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_snapshot_path(name: str) -> Path:
    cleaned = str(name or "").strip() or "runtime_snapshot"
    return get_runtime_paths().health_dir / f"{cleaned}_safe_snapshot.json"

def _is_stale(payload: Dict[str, Any]) -> bool:
    freshness = payload.get("telemetry_freshness_minutes")
    if freshness is not None:
        try:
            if float(freshness) > SAFE_FRESHNESS_MINUTES:
                return True
        except Exception:
            return True
        return False
    status = str(payload.get("status") or "").strip().lower()
    if status and status not in {"ok", "healthy", "fresh"}:
        return True
    return False


def get_last_safe_snapshot(name: str) -> Dict[str, Any]:
    path = _safe_snapshot_path(name)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_stale_data_guard_report(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_path = _safe_snapshot_path(name)
    current = dict(payload or {})
    current.setdefault("generated_at", _utc_now_iso())
    current.setdefault("data_source", "runtime")
    stale = _is_stale(current)
    warnings = []
    last_safe_snapshot = get_last_safe_snapshot(name)
    if not stale:
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")
        last_safe_snapshot = dict(current)
        data_source = current.get("data_source") or "runtime"
    else:
        if not last_safe_snapshot:
            last_safe_snapshot = dict(current)
            last_safe_snapshot["status"] = "ok"
        data_source = "runtime_safe_fallback" if last_safe_snapshot else "fallback"
        warnings.append(f"{name} is stale; using the last safe snapshot")
    last_safe_snapshot_at = last_safe_snapshot.get("generated_at") or last_safe_snapshot.get("updated_at") or current.get("generated_at")
    return {
        "service_name": name,
        "stale": stale,
        "data_source": data_source,
        "generated_at": current.get("generated_at"),
        "last_safe_snapshot": last_safe_snapshot,
        "last_safe_snapshot_at": last_safe_snapshot_at,
        "warnings": warnings,
    }
