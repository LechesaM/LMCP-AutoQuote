from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.operator_workflow_contracts import (
    get_operator_workflow_detail,
    get_operator_workflow_rows,
    get_pricing_evidence_overview,
    get_qualification_insights,
    get_source_health_details,
)
from app.auth.auth_service import require_permission

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/rfqs", dependencies=[Depends(require_permission("view_rfqs"))])
def list_rfqs(limit: int = 100) -> dict:
    return get_operator_workflow_rows(limit=limit)


@router.get("/rfqs/{tender_id}", dependencies=[Depends(require_permission("view_rfqs"))])
def get_rfq_detail(tender_id: str) -> dict:
    return get_operator_workflow_detail(tender_id)


@router.get("/qualification-insights", dependencies=[Depends(require_permission("view_rfqs"))])
def qualification_insights(limit: int = 100) -> dict:
    return get_qualification_insights(limit=limit)


@router.get("/pricing-evidence", dependencies=[Depends(require_permission("view_rfqs"))])
def pricing_evidence(limit: int = 100) -> dict:
    return get_pricing_evidence_overview(limit=limit)


@router.get("/source-health-details", dependencies=[Depends(require_permission("view_rfqs"))])
def source_health_details(limit: int = 100) -> dict:
    return get_source_health_details(limit=limit)
