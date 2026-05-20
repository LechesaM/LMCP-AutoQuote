from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence

from ._shared import group_trend_records, now_iso, parse_iso, safe_float, safe_int


def build_historical_trend_engine(records: Sequence[Dict[str, Any]] | None = None, *, windows: Sequence[str] = ("week", "month")) -> Dict[str, Any]:
    source_records = list(records or [])
    trend_windows: Dict[str, List[Dict[str, Any]]] = {}
    for window in windows:
        trend_windows[window] = group_trend_records(source_records, window=window, limit=12)
    totals = [safe_float(record.get("estimated_profit") or record.get("gross_profit")) for record in source_records]
    timestamps = [parse_iso(record.get("created_at") or record.get("updated_at")) for record in source_records]
    seasonal_pattern = defaultdict(int)
    for timestamp in timestamps:
        if timestamp:
            seasonal_pattern[timestamp.weekday()] += 1
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if source_records else "fallback",
        "summary": {
            "record_count": len(source_records),
            "rolling_average_profit": round(sum(totals) / max(1, len(totals)), 2) if totals else 0.0,
            "seasonal_pattern": dict(sorted(seasonal_pattern.items())),
            "anomaly_trend_count": safe_int(sum(1 for record in source_records if str(record.get("status") or "").lower() in {"failed", "blocked", "degraded"})),
        },
        "trend_windows": trend_windows,
        "rolling_averages": {
            "profit": [round(sum(totals[: index + 1]) / max(1, index + 1), 2) for index in range(len(totals))],
        },
    }

