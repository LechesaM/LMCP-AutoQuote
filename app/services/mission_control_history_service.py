from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from app.core.runtime_paths import get_runtime_paths


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _safe_date(value: Any) -> datetime.date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _snapshot_row(snapshot: Any) -> Dict[str, Any]:
    return snapshot if isinstance(snapshot, dict) else {}


def _province_activity(snapshot: Dict[str, Any]) -> float:
    distribution = _safe_dict(snapshot.get("provinceDistribution") or snapshot.get("province_distribution"))
    if not distribution:
        return 0.0
    return float(sum(1 for value in distribution.values() if _safe_float(value) > 0))


def _metric_value(snapshot: Dict[str, Any], key: str) -> float:
    if key == "rfqsHarvested":
        return float(_safe_int(snapshot.get("harvestedCount") or snapshot.get("harvested_count")))
    if key == "quotesSubmitted":
        return float(_safe_int(snapshot.get("submittedCount") or snapshot.get("submitted_count")))
    if key == "estimatedProfit":
        return _safe_float(snapshot.get("estimatedProfit") or snapshot.get("estimated_profit"))
    if key == "provinceActivity":
        return _province_activity(snapshot)
    return 0.0


def _direction_for_change(change: float) -> str:
    if abs(change) < 0.0001:
        return "flat"
    return "up" if change > 0 else "down"


def _percent_change(current: float, previous: float) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100.0, 2)


def _metric_trend(current: float, previous: float) -> Dict[str, Any]:
    change = _percent_change(current, previous)
    return {
        "current": round(current, 2),
        "previous": round(previous, 2),
        "change": change,
        "direction": _direction_for_change(change),
    }


def _insufficient_metric() -> Dict[str, Any]:
    return {"status": "insufficient_history"}


def _insufficient_window() -> Dict[str, Any]:
    return {
        "status": "insufficient_history",
        "rfqsHarvested": _insufficient_metric(),
        "quotesSubmitted": _insufficient_metric(),
        "estimatedProfit": _insufficient_metric(),
        "provinceActivity": _insufficient_metric(),
    }


def _ordered_history_entries(history: Dict[str, Any], current_snapshot: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    rows = [item for item in _safe_list(history.get("items")) if isinstance(item, dict)]
    if current_snapshot:
        generated_at = str(current_snapshot.get("generatedAt") or current_snapshot.get("generated_at") or _now_iso())
        current_day = generated_at[:10]
        rows = [row for row in rows if str(row.get("date") or "") != current_day]
        rows.append({"date": current_day, "generatedAt": generated_at, "snapshot": current_snapshot})

    rows = [row for row in rows if _safe_date(row.get("date")) is not None and isinstance(row.get("snapshot"), dict)]
    rows.sort(key=lambda row: str(row.get("date") or ""), reverse=False)
    return rows


def _window_metrics(rows: Sequence[Dict[str, Any]], window: int) -> Dict[str, Any]:
    if len(rows) < window * 2:
        return _insufficient_window()

    latest = _safe_date(rows[-1].get("date"))
    if latest is None:
        return _insufficient_window()

    expected_days = [latest - timedelta(days=index) for index in range(window * 2 - 1, -1, -1)]
    row_map = {str(row.get("date")): _snapshot_row(row.get("snapshot")) for row in rows}
    if any(day.isoformat() not in row_map for day in expected_days):
        return _insufficient_window()

    previous_days = expected_days[:window]
    current_days = expected_days[window:]

    def _sum_days(days: Iterable[datetime.date], key: str) -> float:
        return sum(_metric_value(row_map[day.isoformat()], key) for day in days)

    window_payload = {
        "status": "configured",
        "rfqsHarvested": _metric_trend(_sum_days(current_days, "rfqsHarvested"), _sum_days(previous_days, "rfqsHarvested")),
        "quotesSubmitted": _metric_trend(_sum_days(current_days, "quotesSubmitted"), _sum_days(previous_days, "quotesSubmitted")),
        "estimatedProfit": _metric_trend(_sum_days(current_days, "estimatedProfit"), _sum_days(previous_days, "estimatedProfit")),
        "provinceActivity": _metric_trend(_sum_days(current_days, "provinceActivity"), _sum_days(previous_days, "provinceActivity")),
    }
    return window_payload


def build_default_mission_control_trends() -> Dict[str, Any]:
    return {
        "status": "insufficient_history",
        "generatedAt": _now_iso(),
        "windows": {
            "7d": _insufficient_window(),
            "30d": _insufficient_window(),
        },
    }


def build_mission_control_trends(history: Dict[str, Any] | None = None, current_snapshot: Dict[str, Any] | None = None) -> Dict[str, Any]:
    history_payload = _safe_dict(history) if history is not None else _load_history()
    rows = _ordered_history_entries(history_payload, current_snapshot=current_snapshot)
    windows = {
        "7d": _window_metrics(rows, 7),
        "30d": _window_metrics(rows, 30),
    }
    status = "configured" if any(window.get("status") == "configured" for window in windows.values()) else "insufficient_history"
    return {
        "status": status,
        "generatedAt": _now_iso(),
        "windows": windows,
    }


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
