from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.business_intelligence_contracts import (
    build_csv_export_response,
    build_executive_summary_response,
    build_governance_trends_response,
    build_historical_trends_response,
    build_opportunity_forecast_response,
    build_operator_trends_response,
    build_pdf_summary_response,
    build_profitability_response,
    build_revenue_projection_response,
    build_rfq_conversion_response,
    build_source_roi_response,
    build_strategic_report_response,
    build_workload_forecast_response,
)
from app.auth.auth_service import require_permission


router = APIRouter(prefix="/business", tags=["business-intelligence"])


@router.get("/executive-summary", dependencies=[Depends(require_permission("view_dashboard"))])
def get_executive_summary(limit: int = 100) -> dict:
    return build_executive_summary_response(limit=limit)


@router.get("/profitability", dependencies=[Depends(require_permission("view_dashboard"))])
def get_profitability(limit: int = 100) -> dict:
    return build_profitability_response(limit=limit)


@router.get("/rfq-conversion", dependencies=[Depends(require_permission("view_dashboard"))])
def get_rfq_conversion(limit: int = 100) -> dict:
    return build_rfq_conversion_response(limit=limit)


@router.get("/source-roi", dependencies=[Depends(require_permission("view_dashboard"))])
def get_source_roi(limit: int = 100) -> dict:
    return build_source_roi_response(limit=limit)


@router.get("/operator-trends", dependencies=[Depends(require_permission("view_dashboard"))])
def get_operator_trends(limit: int = 100) -> dict:
    return build_operator_trends_response(limit=limit)


@router.get("/governance-trends", dependencies=[Depends(require_permission("view_dashboard"))])
def get_governance_trends(limit: int = 100) -> dict:
    return build_governance_trends_response(limit=limit)


@router.get("/workload-forecast", dependencies=[Depends(require_permission("view_dashboard"))])
def get_workload_forecast(limit: int = 100) -> dict:
    return build_workload_forecast_response(limit=limit)


@router.get("/opportunity-forecast", dependencies=[Depends(require_permission("view_dashboard"))])
def get_opportunity_forecast(limit: int = 100) -> dict:
    return build_opportunity_forecast_response(limit=limit)


@router.get("/revenue-projection", dependencies=[Depends(require_permission("view_dashboard"))])
def get_revenue_projection(limit: int = 100) -> dict:
    return build_revenue_projection_response(limit=limit)


@router.get("/historical-trends", dependencies=[Depends(require_permission("view_dashboard"))])
def get_historical_trends(limit: int = 100) -> dict:
    return build_historical_trends_response(limit=limit)


@router.get("/strategic-report", dependencies=[Depends(require_permission("view_dashboard"))])
def get_strategic_report(limit: int = 100) -> dict:
    return build_strategic_report_response(limit=limit)


@router.get("/export/csv", dependencies=[Depends(require_permission("view_dashboard"))])
def get_export_csv(limit: int = 100) -> dict:
    return build_csv_export_response(limit=limit)


@router.get("/export/pdf-summary", dependencies=[Depends(require_permission("view_dashboard"))])
def get_export_pdf_summary(limit: int = 100) -> dict:
    return build_pdf_summary_response(limit=limit)

