from __future__ import annotations

from fastapi import APIRouter

from app.business_intelligence.csv_exporter import build_csv_export
from app.business_intelligence.executive_dashboard import build_executive_dashboard
from app.business_intelligence.forecasting_engine import build_forecasting_engine
from app.business_intelligence.governance_trend_analytics import build_governance_trend_analytics
from app.business_intelligence.historical_trend_engine import build_historical_trend_engine
from app.business_intelligence.opportunity_forecasting import build_opportunity_forecast
from app.business_intelligence.pdf_summary_exporter import build_pdf_summary_export
from app.business_intelligence.profitability_analytics import build_profitability_analytics
from app.business_intelligence.revenue_projection import build_revenue_projection
from app.business_intelligence.report_exporter import build_report_export_bundle
from app.business_intelligence.source_roi_analytics import build_source_roi_analytics
from app.business_intelligence.strategic_reporting import build_strategic_report
from app.business_intelligence.workload_forecasting import build_workload_forecast
from app.services.weekly_operations_report_service import build_weekly_operations_report


router = APIRouter(prefix="/business", tags=["Business Intelligence"])


@router.get("/weekly-operations")
def weekly_operations_report(window_days: int = 7, limit: int = 25):
    return build_weekly_operations_report(window_days=window_days, limit=limit)


@router.get("/executive-summary")
def executive_summary(limit: int = 25):
    return build_executive_dashboard(limit=limit)


@router.get("/profitability")
def profitability(limit: int = 25):
    return build_profitability_analytics(limit=limit)


@router.get("/rfq-conversion")
def rfq_conversion(limit: int = 25):
    report = build_weekly_operations_report(window_days=7, limit=limit)
    return {
        "status": report["status"],
        "generated_at": report["generated_at"],
        "summary": report["summary"],
        "weekly_operations": report,
    }


@router.get("/source-roi")
def source_roi(limit: int = 25):
    return build_source_roi_analytics(limit=limit)


@router.get("/operator-trends")
def operator_trends(limit: int = 25):
    return build_workload_forecast(limit=limit)


@router.get("/governance-trends")
def governance_trends(limit: int = 25):
    return build_governance_trend_analytics(limit=limit)


@router.get("/workload-forecast")
def workload_forecast(limit: int = 25):
    return build_workload_forecast(limit=limit)


@router.get("/opportunity-forecast")
def opportunity_forecast(limit: int = 25):
    return build_opportunity_forecast(limit=limit)


@router.get("/revenue-projection")
def revenue_projection(limit: int = 25):
    return build_revenue_projection(limit=limit)


@router.get("/historical-trends")
def historical_trends(limit: int = 25):
    return build_historical_trend_engine([{"estimated_profit": 0.0} for _ in range(max(1, limit))])


@router.get("/strategic-report")
def strategic_report(limit: int = 25):
    return build_strategic_report(limit=limit)


@router.get("/export/csv")
def export_csv(limit: int = 25):
    return build_csv_export(build_strategic_report(limit=limit))


@router.get("/export/pdf-summary")
def export_pdf_summary(limit: int = 25):
    return build_pdf_summary_export(build_strategic_report(limit=limit))

