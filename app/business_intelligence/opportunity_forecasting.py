from __future__ import annotations

from typing import Any, Dict

from ._shared import base_report, utc_now_iso


def build_opportunity_forecast(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "advisory_only": True,
        "summary": {
            "rfqs_harvested": report["procurement_funnel"]["rfqs_harvested"],
            "rfqs_eligible": report["procurement_funnel"]["rfqs_eligible"],
            "awards_won": report["award_intelligence"]["awards_won"],
        },
        "trends": [report["procurement_funnel"]["rfqs_harvested"], report["procurement_funnel"]["rfqs_eligible"]],
        "projections": [report["procurement_funnel"]["rfqs_quoted"], report["procurement_funnel"]["rfqs_submitted"]],
    }

