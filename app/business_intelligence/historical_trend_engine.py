from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ._shared import utc_now_iso


def build_historical_trend_engine(records: Iterable[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    items = list(records or [])
    values = [float(item.get("estimated_profit") or item.get("value") or 0.0) for item in items]
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "advisory_only": True,
        "records": items,
        "trends": values,
        "projections": [round(sum(values) / len(values), 2)] if values else [0.0],
    }

