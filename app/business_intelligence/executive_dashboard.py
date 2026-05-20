from __future__ import annotations

from typing import Any, Dict, List

from app.analytics.operator_performance_analytics import build_operator_performance_analytics
from app.analytics.review_queue_analytics import build_review_queue_analytics
from app.analytics.source_reliability_analytics import build_source_reliability_analytics
from app.operations.runtime_metrics import get_runtime_metrics
from app.operations.runtime_alerts import get_runtime_alerts
from app.observability.sla_monitor import build_sla_monitoring_report
from app.quality.context import build_quality_context
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.persistence.persistence_reliability_report import build_persistence_reliability_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.monitoring.metrics_service import get_metrics_snapshot
from app.analytics.tender_success_analytics import build_tender_success_analytics, get_tender_outcome_history
from ._shared import group_trend_records, now_iso, safe_float, safe_int
from .historical_trend_engine import build_historical_trend_engine
from .profitability_analytics import build_profitability_analytics
from .rfq_conversion_analytics import build_rfq_conversion_analytics
from .source_roi_analytics import build_source_roi_analytics
from .operator_trend_analytics import build_operator_trend_analytics
from .governance_trend_analytics import build_governance_trend_analytics
from .workload_forecasting import build_workload_forecast
from .opportunity_forecasting import build_opportunity_forecast
from .revenue_projection import build_revenue_projection


def _summarize_trend(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    weekly = group_trend_records(records, window="week", limit=8)
    monthly = group_trend_records(records, window="month", limit=8)
    return {
        "weekly": weekly,
        "monthly": monthly,
        "rolling_averages": {
            "weekly_total": [round(entry.get("total", 0.0), 2) for entry in weekly],
            "monthly_total": [round(entry.get("total", 0.0), 2) for entry in monthly],
        },
    }


def build_executive_dashboard(limit: int = 100) -> Dict[str, Any]:
    workflow = get_workflow_summary(limit=limit)
    metrics = get_metrics_snapshot().get("metrics", {})
    runtime_metrics = get_runtime_metrics(limit=limit)
    tender_analytics = build_tender_success_analytics(limit=limit)
    source_roi = build_source_roi_analytics(limit=limit)
    operator_trends = build_operator_trend_analytics(limit=limit)
    governance_trends = build_governance_trend_analytics(limit=limit)
    workload_forecast = build_workload_forecast(limit=limit)
    opportunity_forecast = build_opportunity_forecast(limit=limit)
    revenue_projection = build_revenue_projection(limit=limit)
    profitability = build_profitability_analytics(limit=limit)
    rfq_conversion = build_rfq_conversion_analytics(limit=limit)
    historical = build_historical_trend_engine(get_tender_outcome_history(limit=limit))
    productivity = build_review_queue_analytics(limit=limit)
    source_reliability = build_source_reliability_analytics(limit=limit)
    pilot = build_pilot_readiness_report(limit=limit)
    sla = build_sla_monitoring_report(limit=limit)
    quality_context = build_quality_context(limit=limit)
    records = get_tender_outcome_history(limit=limit)
    trend_summary = _summarize_trend(records)
    rfqs_harvested = safe_int(metrics.get("rfqs_discovered", workflow.get("total_workflows", 0)))
    rfqs_qualified = safe_int(tender_analytics.get("tender_outcome_summary", {}).get("eligible", 0))
    rfqs_reviewed = safe_int(tender_analytics.get("tender_outcome_summary", {}).get("reviewed_packs", 0))
    go_manual_reject = workflow.get("stage_counts", {})
    executive_summary = {
        "rfqs_harvested": rfqs_harvested,
        "rfqs_qualified": rfqs_qualified,
        "rfqs_reviewed": rfqs_reviewed,
        "go_trend": safe_int(go_manual_reject.get("approved", 0)),
        "manual_review_trend": safe_int(go_manual_reject.get("review_ready", 0)),
        "reject_trend": safe_int(go_manual_reject.get("refused", 0)),
        "estimated_profitability": safe_float(profitability.get("summary", {}).get("estimated_total_profit", 0.0)),
        "operator_throughput": safe_float(operator_trends.get("summary", {}).get("average_reviews_per_operator", 0.0)),
        "queue_pressure": safe_float(productivity.get("summary", {}).get("queue_lag_minutes", 0.0)),
        "governance_incidents": safe_int(governance_trends.get("summary", {}).get("governance_incidents", 0)),
        "source_reliability": safe_float(source_reliability.get("summary", {}).get("harvest_success_rate", 0.0)) * 100.0,
        "sla_health": sla.get("status", "healthy"),
        "qualified_rate": safe_float(rfq_conversion.get("summary", {}).get("qualified_rate", 0.0)),
        "manual_governance_integrity_score": safe_float(pilot.get("manual_governance_integrity_score", 0.0)),
        "operational_reliability_score": safe_float(pilot.get("operational_reliability_score", 0.0)),
        "quality_score": safe_float(quality_context.get("quality_score", 0.0)),
    }
    return {
        "status": "ok" if pilot.get("status") == "healthy" else "degraded",
        "generated_at": now_iso(),
        "data_source": "mixed" if records else "fallback",
        "executive_summary": executive_summary,
        "weekly_trend": trend_summary["weekly"],
        "monthly_trend": trend_summary["monthly"],
        "rolling_averages": trend_summary["rolling_averages"],
        "profitability": profitability,
        "rfq_conversion": rfq_conversion,
        "source_roi": source_roi,
        "operator_trends": operator_trends,
        "governance_trends": governance_trends,
        "workload_forecast": workload_forecast,
        "opportunity_forecast": opportunity_forecast,
        "revenue_projection": revenue_projection,
        "historical_trends": historical,
        "productivity": productivity,
        "source_reliability": source_reliability,
        "sla": sla,
        "runtime_metrics": runtime_metrics,
        "workflow_summary": workflow,
        "pilot_readiness": pilot,
        "tender_success_analytics": tender_analytics,
        "observability_summary": {
            "runtime_alerts": len(get_runtime_alerts(limit=limit).get("alerts", [])),
            "telemetry_freshness_minutes": runtime_metrics.get("telemetry_freshness_minutes", 0),
            "queue_pressure": productivity.get("summary", {}).get("queue_lag_minutes", 0.0),
            "source_reliability": source_reliability.get("summary", {}),
        },
        "strategic_highlights": [
            "Executive analytics are advisory only.",
            "Manual approval, review_ready and proof capture remain required.",
        ],
    }
