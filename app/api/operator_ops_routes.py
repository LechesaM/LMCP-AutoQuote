from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.api.operator_ops_contracts import (
    build_operator_actions_response,
    build_operator_assignments_response,
    build_operator_capacity_response,
    build_operator_notifications_response,
    build_operator_timeline_response,
)
from app.auth.auth_service import require_permission
from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import dispatch_operator_action

router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/actions", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_actions(limit: int = 100) -> dict:
    return build_operator_actions_response(limit=limit)


@router.get("/assignments", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_assignments(limit: int = 100) -> dict:
    return build_operator_assignments_response(limit=limit)


@router.get("/timeline", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_timeline(limit: int = 100) -> dict:
    return build_operator_timeline_response(limit=limit)


@router.get("/notifications", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_notifications(limit: int = 100) -> dict:
    return build_operator_notifications_response(limit=limit)


@router.get("/capacity", dependencies=[Depends(require_permission("view_operator_queue"))])
def get_capacity() -> dict:
    return build_operator_capacity_response()


def _parse(payload: dict) -> OperatorActionRequest:
    return OperatorActionRequest.validate_payload(payload)


@router.post("/action/assign", dependencies=[Depends(require_permission("assign_operator"))])
def post_assign(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/reviewed", dependencies=[Depends(require_permission("mark_reviewed"))])
def post_reviewed(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/escalate", dependencies=[Depends(require_permission("escalate_review"))])
def post_escalate(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/archive", dependencies=[Depends(require_permission("archive_rfq"))])
def post_archive(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/request-clarification", dependencies=[Depends(require_permission("mark_reviewed"))])
def post_request_clarification(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/acknowledge-alert", dependencies=[Depends(require_permission("acknowledge_alert"))])
def post_acknowledge_alert(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))
