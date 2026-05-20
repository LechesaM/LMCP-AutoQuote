from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.api.observability_contracts import (
    build_observability_alerts_response,
    build_observability_anomalies_response,
    build_observability_grafana_response,
    build_observability_logs_response,
    build_observability_performance_response,
    build_observability_prometheus_response,
    build_observability_sentry_response,
    build_observability_sla_response,
    build_observability_uptime_response,
)
from app.auth.auth_service import require_permission


router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/prometheus", dependencies=[Depends(require_permission("view_dashboard"))], response_class=PlainTextResponse)
def get_prometheus(limit: int = 100) -> PlainTextResponse:
    payload = build_observability_prometheus_response(limit=limit)
    return PlainTextResponse(payload.get("text", ""), media_type="text/plain; version=0.0.4")


@router.get("/grafana", dependencies=[Depends(require_permission("view_dashboard"))])
def get_grafana(limit: int = 100) -> dict:
    return build_observability_grafana_response(limit=limit)


@router.get("/sentry", dependencies=[Depends(require_permission("view_dashboard"))])
def get_sentry() -> dict:
    return build_observability_sentry_response()


@router.get("/sla", dependencies=[Depends(require_permission("view_dashboard"))])
def get_sla(limit: int = 100) -> dict:
    return build_observability_sla_response(limit=limit)


@router.get("/anomalies", dependencies=[Depends(require_permission("view_dashboard"))])
def get_anomalies(limit: int = 100) -> dict:
    return build_observability_anomalies_response(limit=limit)


@router.get("/alerts", dependencies=[Depends(require_permission("view_dashboard"))])
def get_alerts(limit: int = 100) -> dict:
    return build_observability_alerts_response(limit=limit)


@router.get("/logs", dependencies=[Depends(require_permission("view_dashboard"))])
def get_logs(limit: int = 100) -> dict:
    return build_observability_logs_response(limit=limit)


@router.get("/uptime", dependencies=[Depends(require_permission("view_dashboard"))])
def get_uptime(limit: int = 100) -> dict:
    return build_observability_uptime_response(limit=limit)


@router.get("/performance", dependencies=[Depends(require_permission("view_dashboard"))])
def get_performance(limit: int = 100) -> dict:
    return build_observability_performance_response(limit=limit)
