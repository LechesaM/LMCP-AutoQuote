from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List

from ._shared import base_report, utc_now_iso


def _series_from_counts(values: Iterable[int], length: int = 7) -> List[Dict[str, Any]]:
    series = list(values)[-length:]
    if not series:
        series = [0]
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][-len(series):]
    return [{"label": label, "value": value} for label, value in zip(labels, series)]


def build_executive_dashboard(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    summary = report["summary"]
    weekly = [
        summary["rfqs_harvested"],
        summary["rfqs_eligible"],
        summary["rfqs_quoted"],
        summary["rfqs_submitted"],
        summary["awards_won"],
    ]
    monthly = [
        summary["award_value"],
        summary["expected_gross_profit"],
        summary["actual_gross_profit"],
    ]

    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "data_source": report["data_source"],
        "executive_summary": summary,
        "weekly_trend": _series_from_counts(weekly, length=min(5, len(weekly))),
        "monthly_trend": _series_from_counts(monthly, length=min(3, len(monthly))),
        "weekly_operations": report,
    }

