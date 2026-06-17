from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from fastapi import APIRouter, Body, HTTPException

from .operator_ops_contracts import (
    build_operator_actions_response,
    build_operator_assignments_response,
    build_operator_capacity_response,
    build_operator_notifications_response,
    build_operator_timeline_response,
)
from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import (
    acknowledge_alert,
    archive,
    assign_operator,
    dispatch_operator_action,
    escalate,
    mark_reviewed,
    request_clarification,
)


router = APIRouter(tags=["operator-ops"])


def get_operator_actions():
    return build_operator_actions_response()


def get_operator_assignments():
    return build_operator_assignments_response()


def get_operator_timeline():
    return build_operator_timeline_response()


def get_operator_notifications():
    return build_operator_notifications_response()


def get_operator_capacity():
    return build_operator_capacity_response()


def _validate_operator_action(payload: Optional[Mapping[str, Any]], action: str) -> OperatorActionRequest:
    data = dict(payload or {})
    data["action"] = action
    try:
        return OperatorActionRequest.validate_payload(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/operator/actions")
def operator_actions() -> Dict[str, Any]:
    return get_operator_actions()


@router.get("/operator/assignments")
def operator_assignments() -> Dict[str, Any]:
    return get_operator_assignments()


@router.get("/operator/timeline")
def operator_timeline() -> Dict[str, Any]:
    return get_operator_timeline()


@router.get("/operator/notifications")
def operator_notifications() -> Dict[str, Any]:
    return get_operator_notifications()


@router.get("/operator/capacity")
def operator_capacity() -> Dict[str, Any]:
    return get_operator_capacity()


@router.post("/operator/action/assign")
def operator_action_assign(payload: Optional[Mapping[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    request = _validate_operator_action(payload, "assign_operator")
    return {"status": "ok", "item": assign_operator(request)}


@router.post("/operator/action/reviewed")
def operator_action_reviewed(payload: Optional[Mapping[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    request = _validate_operator_action(payload, "mark_reviewed")
    return {"status": "ok", "item": mark_reviewed(request)}


@router.post("/operator/action/escalate")
def operator_action_escalate(payload: Optional[Mapping[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    request = _validate_operator_action(payload, "escalate")
    return {"status": "ok", "item": escalate(request)}


@router.post("/operator/action/archive")
def operator_action_archive(payload: Optional[Mapping[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    request = _validate_operator_action(payload, "archive")
    return {"status": "ok", "item": archive(request)}


@router.post("/operator/action/request-clarification")
def operator_action_request_clarification(payload: Optional[Mapping[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    request = _validate_operator_action(payload, "request_clarification")
    return {"status": "ok", "item": request_clarification(request)}


@router.post("/operator/action/acknowledge-alert")
def operator_action_acknowledge_alert(payload: Optional[Mapping[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    request = _validate_operator_action(payload, "acknowledge_alert")
    return {"status": "ok", "item": acknowledge_alert(request)}
