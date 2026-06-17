from __future__ import annotations

from typing import Any, Dict

from ._shared import base_report, utc_now_iso


def build_revenue_projection(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    financial = report["financial_funnel"]
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "advisory_only": True,
        "summary": financial,
        "trends": [financial["submitted_value"], financial["awarded_value"]],
        "projections": [financial["estimated_award_value"], financial["expected_gross_profit"]],
    }

