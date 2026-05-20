from __future__ import annotations

from typing import Any, Dict

from app.analytics.tender_success_analytics import build_tender_success_analytics
from .forecasting_engine import build_forecasting_engine
from ._shared import now_iso, safe_float, safe_int


def build_opportunity_forecast(limit: int = 100) -> Dict[str, Any]:
    tender = build_tender_success_analytics(limit=limit)
    summary = tender.get("tender_outcome_summary", {})
    series = {
        "eligible": [safe_float(summary.get("eligible", 0)), safe_float(summary.get("eligible", 0))],
        "reviewed": [safe_float(summary.get("reviewed_packs", 0)), safe_float(summary.get("reviewed_packs", 0))],
        "submitted": [safe_float(summary.get("submitted_manually", 0)), safe_float(summary.get("submitted_manually", 0))],
    }
    forecast = build_forecasting_engine(series=series, horizon=4)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if summary.get("processed", 0) else "fallback",
        "summary": {
            "rfq_growth": safe_int(summary.get("processed", 0)),
            "review_demand": safe_int(summary.get("reviewed_packs", 0)),
            "source_growth": safe_int(summary.get("eligible", 0)),
            "opportunity_value_projection": safe_float(summary.get("processed", 0)) * 1000.0,
        },
        "forecast": forecast,
        "advisory_only": True,
    }

