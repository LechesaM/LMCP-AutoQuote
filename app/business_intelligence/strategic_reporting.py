from __future__ import annotations

from typing import Any, Dict

from .executive_dashboard import build_executive_dashboard
from .governance_trend_analytics import build_governance_trend_analytics
from .opportunity_forecasting import build_opportunity_forecast
from .operator_trend_analytics import build_operator_trend_analytics
from .profitability_analytics import build_profitability_analytics
from .revenue_projection import build_revenue_projection
from .rfq_conversion_analytics import build_rfq_conversion_analytics
from .source_roi_analytics import build_source_roi_analytics
from .workload_forecasting import build_workload_forecast
from ._shared import now_iso


def build_strategic_report(limit: int = 100) -> Dict[str, Any]:
    executive = build_executive_dashboard(limit=limit)
    profitability = build_profitability_analytics(limit=limit)
    conversion = build_rfq_conversion_analytics(limit=limit)
    source_roi = build_source_roi_analytics(limit=limit)
    operator_trends = build_operator_trend_analytics(limit=limit)
    governance_trends = build_governance_trend_analytics(limit=limit)
    workload_forecast = build_workload_forecast(limit=limit)
    opportunity_forecast = build_opportunity_forecast(limit=limit)
    revenue_projection = build_revenue_projection(limit=limit)
    historical = executive.get("historical_trends", {})
    report = {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": executive.get("data_source", "fallback"),
        "executive_summary": executive.get("executive_summary", {}),
        "operational_health_report": {
            "sla": executive.get("sla", {}),
            "runtime_metrics": executive.get("runtime_metrics", {}),
            "workflow_summary": executive.get("workflow_summary", {}),
        },
        "governance_summary": governance_trends,
        "profitability_summary": profitability,
        "rfq_conversion_summary": conversion,
        "source_roi_summary": source_roi,
        "operator_trends": operator_trends,
        "workload_forecast": workload_forecast,
        "opportunity_forecast": opportunity_forecast,
        "revenue_projection": revenue_projection,
        "historical_trends": historical,
        "export_ready": True,
        "advisory_only": True,
    }
    return report
