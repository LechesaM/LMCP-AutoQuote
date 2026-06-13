from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _history_path() -> Path:
    explicit = str(os.getenv("LMCP_MISSION_CONTROL_HISTORY_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return get_runtime_paths().runtime_root / "mission_control" / "mission_control_history.json"


def _empty_history(status: str = "insufficient_history", days: int = 30) -> Dict[str, Any]:
    return {
        "status": status,
        "generatedAt": _now_iso(),
        "days": days,
        "items": [],
    }


def _load_history() -> Dict[str, Any]:
    path = _history_path()
    if not path.exists():
        return _empty_history()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_history()

    if not isinstance(payload, dict):
        return _empty_history()

    items = [item for item in _safe_list(payload.get("items")) if isinstance(item, dict)]
    items.sort(key=lambda item: str(item.get("date") or item.get("generatedAt") or ""), reverse=True)
    return {
        "status": str(payload.get("status") or ("configured" if items else "insufficient_history")),
        "generatedAt": str(payload.get("generatedAt") or payload.get("updatedAt") or _now_iso()),
        "items": items,
    }


def _write_history(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {
        "status": "configured" if items else "insufficient_history",
        "generatedAt": _now_iso(),
        "updatedAt": _now_iso(),
        "items": items,
    }
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return payload


def _day_key(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return _now_iso()[:10]


def record_mission_control_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(snapshot)
    generated_at = str(payload.get("generatedAt") or payload.get("generated_at") or _now_iso())
    day = _day_key(generated_at)
    entry = {
        "date": day,
        "generatedAt": generated_at,
        "snapshot": payload,
    }

    history = _load_history()
    items = [item for item in _safe_list(history.get("items")) if str(item.get("date") or "") != day]
    items.append(entry)
    items.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    return _write_history(items)


def get_mission_control_history(days: int = 30) -> Dict[str, Any]:
    try:
        window = max(1, min(int(days or 30), 365))
    except Exception:
        window = 30

    history = _load_history()
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=window - 1)).isoformat()
    items = [
        item
        for item in _safe_list(history.get("items"))
        if str(item.get("date") or "") >= cutoff
    ]
    items.sort(key=lambda item: str(item.get("date") or ""), reverse=True)

    if not items:
        return _empty_history(days=window)

    return {
        "status": "configured",
        "generatedAt": _now_iso(),
        "days": window,
        "items": items,
    }
