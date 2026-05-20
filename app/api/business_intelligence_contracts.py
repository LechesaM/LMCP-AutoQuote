from __future__ import annotations

from typing import Any, Dict

from app.business_intelligence.executive_dashboard import build_executive_dashboard
from app.business_intelligence.governance_trend_analytics import build_governance_trend_analytics
from app.business_intelligence.historical_trend_engine import build_historical_trend_engine
from app.business_intelligence.opportunity_forecasting import build_opportunity_forecast
from app.business_intelligence.operator_trend_analytics import build_operator_trend_analytics
from app.business_intelligence.profitability_analytics import build_profitability_analytics
from app.business_intelligence.report_exporter import build_report_export_bundle
from app.business_intelligence.revenue_projection import build_revenue_projection
from app.business_intelligence.rfq_conversion_analytics import build_rfq_conversion_analytics
from app.business_intelligence.source_roi_analytics import build_source_roi_analytics
from app.business_intelligence.strategic_reporting import build_strategic_report
from app.business_intelligence.workload_forecasting import build_workload_forecast


def build_business_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", ""),
        "data_source": payload.get("data_source", "fallback"),
        **payload,
    }


def build_executive_summary_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_executive_dashboard(limit=limit))


def build_profitability_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_profitability_analytics(limit=limit))


def build_rfq_conversion_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_rfq_conversion_analytics(limit=limit))


def build_source_roi_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_source_roi_analytics(limit=limit))


def build_operator_trends_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_operator_trend_analytics(limit=limit))


def build_governance_trends_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_governance_trend_analytics(limit=limit))


def build_workload_forecast_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_workload_forecast(limit=limit))


def build_opportunity_forecast_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_opportunity_forecast(limit=limit))


def build_revenue_projection_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_revenue_projection(limit=limit))


def build_historical_trends_response(limit: int = 100) -> Dict[str, Any]:
    report = build_executive_dashboard(limit=limit)
    return build_business_payload(report.get("historical_trends", {}))


def build_strategic_report_response(limit: int = 100) -> Dict[str, Any]:
    return build_business_payload(build_strategic_report(limit=limit))


def build_csv_export_response(limit: int = 100) -> Dict[str, Any]:
    bundle = build_report_export_bundle(limit=limit)
    return build_business_payload(
        {
            "status": bundle.get("status", "ok"),
            "generated_at": bundle.get("generated_at", ""),
            "data_source": bundle.get("data_source", "fallback"),
            "csv_export": bundle.get("csv", {}),
        }
    )


def build_pdf_summary_response(limit: int = 100) -> Dict[str, Any]:
    bundle = build_report_export_bundle(limit=limit)
    return build_business_payload(
        {
            "status": bundle.get("status", "ok"),
            "generated_at": bundle.get("generated_at", ""),
            "data_source": bundle.get("data_source", "fallback"),
            "pdf_summary": bundle.get("pdf_summary", {}),
        }
    )
