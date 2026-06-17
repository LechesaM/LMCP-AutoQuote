from __future__ import annotations

from typing import Any, Dict, List

from ._shared import base_report, utc_now_iso


def build_governance_trend_analytics(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    governance_incidents: List[Dict[str, Any]] = []
    submission_status_counts = report["submission_metrics"].get("submission_status_counts", {})
    for status, count in submission_status_counts.items():
        if status not in {"submitted"}:
            governance_incidents.append({"type": status, "count": count})

    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "summary": {
            "manual_approval_required": True,
            "go_no_go": "GO" if report["procurement_funnel"]["rfqs_quoted"] else "HOLD",
            "incident_count": len(governance_incidents),
        },
        "governance_incidents": governance_incidents[:limit],
        "data_source": report["data_source"],
    }

