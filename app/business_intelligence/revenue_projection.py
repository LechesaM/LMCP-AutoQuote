from __future__ import annotations

from typing import Any, Dict

from app.analytics.tender_success_analytics import build_tender_success_analytics
from .profitability_analytics import build_profitability_analytics
from ._shared import now_iso, safe_float, safe_int


def build_revenue_projection(limit: int = 100) -> Dict[str, Any]:
    tender = build_tender_success_analytics(limit=limit)
    profitability = build_profitability_analytics(limit=limit)
    summary = tender.get("tender_outcome_summary", {})
    estimated_value = safe_float(profitability.get("summary", {}).get("estimated_total_profit", 0.0))
    margin_opportunity = safe_float(profitability.get("summary", {}).get("average_margin", 0.0))
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if summary.get("processed", 0) else "fallback",
        "estimated": True,
        "non_financial_advice": True,
        "heuristic": True,
        "summary": {
            "projected_rfq_opportunity_value": estimated_value,
            "projected_margin_opportunity": margin_opportunity,
            "source_based_opportunity_projection": safe_int(summary.get("eligible", 0)),
        },
        "projection_notes": [
            "Projection is heuristic and advisory only.",
            "No accounting or financial advice is implied.",
        ],
    }

