from __future__ import annotations

from typing import Any, Dict, List

from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
from app.productivity.operator_workload_balancer import build_operator_workload_summary
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary
from .forecasting_engine import build_forecasting_engine
from ._shared import now_iso, safe_float, safe_int


def build_workload_forecast(limit: int = 100) -> Dict[str, Any]:
    capacity = get_operator_capacity_snapshot()
    workload = build_operator_workload_summary(limit=limit)
    queue = build_review_queue_optimization_summary(limit=limit)
    series = {
        "queue_depth": [safe_float(queue.get("summary", {}).get("total", 0.0)), safe_float(queue.get("summary", {}).get("total", 0.0))],
        "operator_utilization": [safe_float(capacity.get("assigned_today", 0)), safe_float(capacity.get("assigned_today", 0))],
    }
    forecast = build_forecasting_engine(series=series, horizon=4)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if workload else "fallback",
        "summary": {
            "queue_growth": safe_int(queue.get("summary", {}).get("total", 0)),
            "operator_workload": safe_int(capacity.get("assigned_today", 0)),
            "rfq_throughput": safe_float(workload.get("summary", {}).get("reviews_per_hour", 0.0)),
            "source_growth": safe_int(workload.get("summary", {}).get("operators", 0)),
            "estimated_review_demand": safe_int(queue.get("summary", {}).get("urgent", 0) + queue.get("summary", {}).get("high", 0)),
        },
        "forecast": forecast,
        "advisory_only": True,
    }

