from __future__ import annotations

from typing import Any, Dict, Sequence

from ._shared import now_iso, safe_float
from .trend_models import build_trend_models


def forecast_series(series: Dict[str, Sequence[float]] | None = None, *, horizon: int = 3, window: int = 3) -> Dict[str, Any]:
    series = series or {}
    trends = build_trend_models(series, window=window)
    projections = {}
    for name, model in trends["series"].items():
        baseline = safe_float(model.get("forecast_next", 0.0))
        values = [safe_float(value) for value in model.get("values", [])]
        slope = 0.0
        if len(values) >= 2:
            slope = (values[-1] - values[0]) / max(1, len(values) - 1)
        projections[name] = [round(baseline + slope * step, 2) for step in range(1, max(1, int(horizon)) + 1)]
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if series else "fallback",
        "trends": trends,
        "projections": projections,
        "advisory_only": True,
    }


def build_forecasting_engine(series: Dict[str, Sequence[float]] | None = None, *, horizon: int = 3, window: int = 3) -> Dict[str, Any]:
    return forecast_series(series=series, horizon=horizon, window=window)

