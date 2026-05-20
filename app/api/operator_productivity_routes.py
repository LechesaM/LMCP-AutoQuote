from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.api.operator_productivity_contracts import (
    build_bulk_acknowledge_alert_response,
    build_bulk_archive_reviewed_response,
    build_bulk_assign_response,
    build_operator_productivity_evidence_acceleration,
    build_operator_productivity_focus_sessions,
    build_operator_productivity_queue_heatmap,
    build_operator_productivity_queue_optimization,
    build_operator_productivity_review_efficiency,
    build_operator_productivity_review_priorities,
    build_operator_productivity_shortcuts,
    build_operator_productivity_workload,
)
from app.auth.auth_service import AuthError, get_current_auth_context, require_permission

router = APIRouter(prefix="/productivity", tags=["productivity"])


def require_supervisor_or_admin():
    def dependency(request):
        user = get_current_auth_context(request)
        role = str(user.role or "").lower()
        if role not in {"supervisor", "admin"}:
            raise AuthError("Supervisor or admin role required.", status_code=403)
        return user

    return dependency


@router.get("/workload", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_workload(limit: int = 200) -> dict:
    return build_operator_productivity_workload(limit=limit)


@router.get("/queue-optimization", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_queue_optimization(limit: int = 200) -> dict:
    return build_operator_productivity_queue_optimization(limit=limit)


@router.get("/review-efficiency", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_review_efficiency(limit: int = 200) -> dict:
    return build_operator_productivity_review_efficiency(limit=limit)


@router.get("/focus-sessions", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_focus_sessions(limit: int = 200) -> dict:
    return build_operator_productivity_focus_sessions(limit=limit)


@router.get("/queue-heatmap", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_queue_heatmap(limit: int = 200) -> dict:
    return build_operator_productivity_queue_heatmap(limit=limit)


@router.get("/review-priorities", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_review_priorities(limit: int = 200) -> dict:
    return build_operator_productivity_review_priorities(limit=limit)


@router.get("/evidence-acceleration", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_evidence_acceleration(limit: int = 200) -> dict:
    return build_operator_productivity_evidence_acceleration(limit=limit)


@router.get("/shortcuts", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_shortcuts() -> dict:
    return build_operator_productivity_shortcuts()


@router.post("/bulk/assign", dependencies=[Depends(require_supervisor_or_admin())])
def post_bulk_assign(payload: dict = Body(...)) -> dict:
    return build_bulk_assign_response(payload)


@router.post("/bulk/acknowledge-alert", dependencies=[Depends(require_supervisor_or_admin())])
def post_bulk_acknowledge_alert(payload: dict = Body(...)) -> dict:
    return build_bulk_acknowledge_alert_response(payload)


@router.post("/bulk/archive-reviewed", dependencies=[Depends(require_supervisor_or_admin())])
def post_bulk_archive_reviewed(payload: dict = Body(...)) -> dict:
    return build_bulk_archive_reviewed_response(payload)

