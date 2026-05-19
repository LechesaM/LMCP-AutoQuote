from __future__ import annotations

from fastapi import APIRouter

from app.api.telemetry_contracts import (
    build_dashboard_telemetry_response,
    build_operational_health_telemetry_response,
    build_qualification_telemetry_response,
    build_review_queue_telemetry_response,
    build_source_health_telemetry_response,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/dashboard")
def get_dashboard_telemetry(limit: int = 100) -> dict:
    return build_dashboard_telemetry_response(limit=limit)


@router.get("/source-health")
def get_source_health_telemetry(limit: int = 100) -> dict:
    return build_source_health_telemetry_response(limit=limit)


@router.get("/review-queue")
def get_review_queue_telemetry(limit: int = 100) -> dict:
    return build_review_queue_telemetry_response(limit=limit)


@router.get("/qualification")
def get_qualification_telemetry(limit: int = 100) -> dict:
    return build_qualification_telemetry_response(limit=limit)


@router.get("/operational-health")
def get_operational_health_telemetry(limit: int = 100) -> dict:
    return build_operational_health_telemetry_response(limit=limit)
