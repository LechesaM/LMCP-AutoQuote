from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core import workflow_state_engine
from app.services import audit_trail_service

from .operator_action_models import OperatorActionRequest


RUNTIME_DIR = Path("runtime")
OPERATOR_ACTION_DIR = RUNTIME_DIR / "operator_actions"
OPERATOR_ACTION_HISTORY_FILE = OPERATOR_ACTION_DIR / "operator_action_history.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_history() -> list[dict[str, Any]]:
    if not OPERATOR_ACTION_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(OPERATOR_ACTION_HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_history(items: list[dict[str, Any]]) -> None:
    OPERATOR_ACTION_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPERATOR_ACTION_HISTORY_FILE.write_text(json.dumps(items[-1000:], indent=2, default=str), encoding="utf-8")


def _record_audit_event_sync(event_type: str, payload: Dict[str, Any]) -> None:
    try:
        asyncio.run(audit_trail_service.record_audit_event(event_type=event_type, source="operator-action-center", payload=payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                audit_trail_service.record_audit_event(event_type=event_type, source="operator-action-center", payload=payload)
            )
        finally:
            loop.close()


def _record(action: str, request: OperatorActionRequest, reversible: bool = True, reviewable: bool = True) -> Dict[str, Any]:
    item = {
        "action": action,
        "operator_id": request.operator_id,
        "tender_id": request.tender_id,
        "note": request.note,
        "details": dict(request.details or {}),
        "target_operator_id": request.target_operator_id,
        "reversible": reversible,
        "reviewable": reviewable,
        "created_at": _now_iso(),
    }
    history = _load_history()
    history.append(item)
    _save_history(history)
    _record_audit_event_sync(f"operator_{action}", item)
    return item


def assign_operator(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record("assign_operator", request, reversible=False, reviewable=True)


def mark_reviewed(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record("mark_reviewed", request, reversible=True, reviewable=True)


def request_clarification(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record("request_clarification", request, reversible=True, reviewable=True)


def escalate(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record("escalate", request, reversible=False, reviewable=True)


def archive(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record("archive", request, reversible=True, reviewable=False)


def acknowledge_alert(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record("acknowledge_alert", request, reversible=True, reviewable=True)


def dispatch_operator_action(request: OperatorActionRequest) -> Dict[str, Any]:
    action = str(request.action or "").strip()
    if action == "assign_operator":
        return assign_operator(request)
    if action == "mark_reviewed":
        return mark_reviewed(request)
    if action == "request_clarification":
        return request_clarification(request)
    if action == "escalate":
        return escalate(request)
    if action == "archive":
        return archive(request)
    if action == "acknowledge_alert":
        return acknowledge_alert(request)
    raise ValueError(f"Unsupported operator action: {action}")
