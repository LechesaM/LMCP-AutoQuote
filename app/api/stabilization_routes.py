from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.stabilization_contracts import (
    build_stabilization_deployment_stability_response,
    build_stabilization_fallback_health_response,
    build_stabilization_governance_consistency_response,
    build_stabilization_operator_feedback_response,
    build_stabilization_operator_fatigue_response,
    build_stabilization_runtime_cleanup_dry_run_response,
    build_stabilization_runtime_cleanup_response,
    build_stabilization_runtime_response,
    build_stabilization_telemetry_noise_response,
)
from app.auth.auth_service import require_permission


router = APIRouter(prefix="/stabilization", tags=["stabilization"])


def _confirm(payload: Dict[str, Any]) -> None:
    if not bool(payload.get("confirmed", False)):
        raise HTTPException(status_code=400, detail="Explicit confirmation is required.")


@router.get("/runtime", dependencies=[Depends(require_permission("view_dashboard"))])
def get_runtime(limit: int = 100) -> dict:
    return build_stabilization_runtime_response(limit=limit)


@router.get("/fallback-health", dependencies=[Depends(require_permission("view_dashboard"))])
def get_fallback_health(limit: int = 100) -> dict:
    return build_stabilization_fallback_health_response(limit=limit)


@router.get("/telemetry-noise", dependencies=[Depends(require_permission("view_dashboard"))])
def get_telemetry_noise(limit: int = 100) -> dict:
    return build_stabilization_telemetry_noise_response(limit=limit)


@router.get("/governance-consistency", dependencies=[Depends(require_permission("view_governance"))])
def get_governance_consistency(limit: int = 100) -> dict:
    return build_stabilization_governance_consistency_response(limit=limit)


@router.get("/operator-fatigue", dependencies=[Depends(require_permission("view_dashboard"))])
def get_operator_fatigue(limit: int = 100) -> dict:
    return build_stabilization_operator_fatigue_response(limit=limit)


@router.get("/operator-feedback", dependencies=[Depends(require_permission("view_dashboard"))])
def get_operator_feedback(limit: int = 100) -> dict:
    return build_stabilization_operator_feedback_response(limit=limit)


@router.get("/runtime-cleanup", dependencies=[Depends(require_permission("view_dashboard"))])
def get_runtime_cleanup(limit: int = 100) -> dict:
    return build_stabilization_runtime_cleanup_response(limit=limit)


@router.get("/deployment-stability", dependencies=[Depends(require_permission("view_dashboard"))])
def get_deployment_stability(limit: int = 100) -> dict:
    return build_stabilization_deployment_stability_response(limit=limit)


@router.post("/runtime-cleanup/dry-run", dependencies=[Depends(require_permission("view_dashboard"))])
def post_runtime_cleanup_dry_run(
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> dict:
    data = payload or {}
    _confirm(data)
    return build_stabilization_runtime_cleanup_dry_run_response(limit=int(data.get("limit", 100)), confirmed=True)

