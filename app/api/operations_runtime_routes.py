from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.operations_runtime_contracts import (
    build_backup_validation_response,
    build_incidents_response,
    build_operator_analytics_response,
    build_runtime_alerts_response,
    build_runtime_metrics_response,
    build_source_reliability_response,
)
from app.auth.auth_service import require_permission


router = APIRouter(prefix="/operations", tags=["operations-runtime"])


@router.get("/runtime-metrics", dependencies=[Depends(require_permission("view_dashboard"))])
def runtime_metrics(limit: int = 100) -> dict:
    return build_runtime_metrics_response(limit=limit)


@router.get("/operator-analytics", dependencies=[Depends(require_permission("view_dashboard"))])
def operator_analytics(limit: int = 100) -> dict:
    return build_operator_analytics_response(limit=limit)


@router.get("/source-reliability", dependencies=[Depends(require_permission("view_dashboard"))])
def source_reliability(limit: int = 100) -> dict:
    return build_source_reliability_response(limit=limit)


@router.get("/incidents", dependencies=[Depends(require_permission("view_dashboard"))])
def incidents(limit: int = 100) -> dict:
    return build_incidents_response(limit=limit)


@router.get("/runtime-alerts", dependencies=[Depends(require_permission("view_dashboard"))])
def runtime_alerts(limit: int = 100) -> dict:
    return build_runtime_alerts_response(limit=limit)


@router.get("/backup-validation", dependencies=[Depends(require_permission("view_dashboard"))])
def backup_validation() -> dict:
    return build_backup_validation_response()

