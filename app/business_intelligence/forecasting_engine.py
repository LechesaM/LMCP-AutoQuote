from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ._shared import utc_now_iso


def _series_values(payload: Dict[str, Any]) -> List[float]:
    for key in ("queue_depth", "values", "series", "history"):
        value = payload.get(key)
        if isinstance(value, list):
            try:
                return [float(item) for item in value]
            except Exception:
                continue
    return [0.0]


def build_forecasting_engine(payload: Dict[str, Any], horizon: int = 3) -> Dict[str, Any]:
    values = _series_values(payload or {})
    horizon = max(1, min(int(horizon or 3), 12))
    trend = sum(values[-3:]) / min(len(values), 3) if values else 0.0
    projections = [round(trend + index, 2) for index in range(1, horizon + 1)]
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "advisory_only": True,
        "trends": values[-horizon:],
        "projections": projections,
    }

