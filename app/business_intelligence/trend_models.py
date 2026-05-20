from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Sequence

from ._shared import rolling_average, safe_float


@dataclass
class TrendModel:
    label: str
    values: List[float]
    rolling_average: List[float]
    forecast_next: float
    direction: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_trend_model(label: str, values: Sequence[float], *, window: int = 3) -> Dict[str, Any]:
    numeric_values = [safe_float(value) for value in values]
    average_series = rolling_average(numeric_values, window=window)
    forecast_next = average_series[-1] if average_series else 0.0
    direction = "stable"
    if len(numeric_values) >= 2:
        if numeric_values[-1] > numeric_values[0]:
            direction = "up"
        elif numeric_values[-1] < numeric_values[0]:
            direction = "down"
    return TrendModel(
        label=label,
        values=numeric_values,
        rolling_average=average_series,
        forecast_next=round(forecast_next, 2),
        direction=direction,
    ).to_dict()


def build_trend_models(series: Dict[str, Sequence[float]] | None = None, *, window: int = 3) -> Dict[str, Any]:
    series = series or {}
    return {
        "status": "ok",
        "series": {key: build_trend_model(key, values, window=window) for key, values in series.items()},
    }
