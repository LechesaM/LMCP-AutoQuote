from __future__ import annotations

from typing import Any, Dict

from ._shared import base_report, utc_now_iso


def build_workload_forecast(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    procurement = report["procurement_funnel"]
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "advisory_only": True,
        "summary": {
            "rfqs_harvested": procurement["rfqs_harvested"],
            "rfqs_quoted": procurement["rfqs_quoted"],
            "rfqs_submitted": procurement["rfqs_submitted"],
        },
        "trends": [procurement["rfqs_harvested"], procurement["rfqs_quoted"], procurement["rfqs_submitted"]],
        "projections": [procurement["rfqs_eligible"], procurement["rfqs_approved"]],
    }

