from __future__ import annotations

from fastapi import APIRouter, Body

from app.api.operator_ops_contracts import (
    build_operator_actions_response,
    build_operator_assignments_response,
    build_operator_capacity_response,
    build_operator_notifications_response,
    build_operator_timeline_response,
)
from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import dispatch_operator_action

router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/actions")
def get_actions(limit: int = 100) -> dict:
    return build_operator_actions_response(limit=limit)


@router.get("/assignments")
def get_assignments(limit: int = 100) -> dict:
    return build_operator_assignments_response(limit=limit)


@router.get("/timeline")
def get_timeline(limit: int = 100) -> dict:
    return build_operator_timeline_response(limit=limit)


@router.get("/notifications")
def get_notifications(limit: int = 100) -> dict:
    return build_operator_notifications_response(limit=limit)


@router.get("/capacity")
def get_capacity() -> dict:
    return build_operator_capacity_response()


def _parse(payload: dict) -> OperatorActionRequest:
    return OperatorActionRequest.validate_payload(payload)


@router.post("/action/assign")
def post_assign(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/reviewed")
def post_reviewed(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/escalate")
def post_escalate(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/archive")
def post_archive(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/request-clarification")
def post_request_clarification(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))


@router.post("/action/acknowledge-alert")
def post_acknowledge_alert(payload: dict = Body(...)) -> dict:
    return dispatch_operator_action(_parse(payload))
