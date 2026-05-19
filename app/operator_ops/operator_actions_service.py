from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.operator_ops.operator_action_models import OperatorActionRecord, OperatorActionRequest, new_operator_id
from app.operator_ops.operator_activity_feed import append_timeline_event, get_operator_timeline
from app.operator_ops.operator_assignment_service import create_assignment, get_operator_assignments, recommend_operator_assignments
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
from app.operator_ops.operator_notifications import get_operator_notifications
from app.operator_ops.operator_audit_timeline import record_timeline_event
from app.services.audit_trail_service import record_audit_event
from app.core.runtime_paths import get_runtime_paths


ALLOWED_ACTIONS = {
    "assign_operator",
    "mark_reviewed",
    "request_clarification",
    "archive_rfq",
    "mark_evidence_incomplete",
    "mark_supplier_quote_received",
    "mark_waiting_pricing",
    "escalate_review",
    "reopen_review",
    "acknowledge_alert",
}

ACTION_HANDLERS = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _action_path() -> Path:
    return get_runtime_paths().manual_production_file("operator_actions.jsonl")


def _append(path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _read(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _dispatch_audit(event_type: str, request: OperatorActionRequest, record: Dict[str, Any]) -> None:
    coroutine = record_audit_event(
        event_type=event_type,
        source="operator-ops",
        severity="info",
        title=event_type.replace("_", " ").title(),
        message=request.note or event_type,
        buyer_rfq_number=request.tender_id,
        payload=record,
    )
    try:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coroutine)
        else:
            loop.create_task(coroutine)
    except Exception:
        pass


def _record_action(action: str, request: OperatorActionRequest, *, severity: str = "info", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not request.operator_id:
        raise ValueError("operator_id is required")
    if not request.tender_id and action != "acknowledge_alert":
        raise ValueError("tender_id is required")
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported operator action: {action}")

    record = OperatorActionRecord(
        action_id=new_operator_id("action"),
        action=action,
        operator_id=request.operator_id,
        tender_id=request.tender_id,
        target_type=request.target_type or "rfq",
        note=request.note,
        status="queued_for_manual_followup",
        reversible=True,
        reviewable=True,
        audit_event_id="",
        details={"requested_action": action, **(extra or {}), **(request.details or {})},
    ).to_jsonable_dict()
    record["created_at"] = _now_iso()
    record["updated_at"] = record["created_at"]
    _append(_action_path(), record)
    _dispatch_audit(f"operator_{action}", request, record)
    record_timeline_event(
        event_type=f"operator_{action}",
        operator_id=request.operator_id,
        tender_id=request.tender_id,
        title=f"Operator {action.replace('_', ' ')}",
        severity=severity,
        details=record,
    )
    return record


def list_operator_actions(limit: int = 100) -> Dict[str, Any]:
    records = _read(_action_path())
    items = records[-max(1, int(limit or 100)) :]
    return {"status": "ok", "generated_at": _now_iso(), "data_source": "runtime" if items else "fallback", "actions": items, "total": len(records)}


def assign_operator(request: OperatorActionRequest) -> Dict[str, Any]:
    record = _record_action("assign_operator", request, extra={"assignment": True})
    assignment = create_assignment(operator_id=request.operator_id, tender_id=request.tender_id, recommendation="manual", source="operator_action", details=record)
    record["assignment"] = assignment
    return record


def mark_reviewed(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("mark_reviewed", request)


def request_clarification(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("request_clarification", request, severity="warning")


def archive_rfq(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("archive_rfq", request, severity="warning")


def mark_evidence_incomplete(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("mark_evidence_incomplete", request, severity="warning")


def mark_supplier_quote_received(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("mark_supplier_quote_received", request)


def mark_waiting_pricing(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("mark_waiting_pricing", request, severity="warning")


def escalate_review(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("escalate_review", request, severity="critical")


def reopen_review(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("reopen_review", request, severity="warning")


def acknowledge_alert(request: OperatorActionRequest) -> Dict[str, Any]:
    return _record_action("acknowledge_alert", request)


def get_operator_actions(limit: int = 100) -> Dict[str, Any]:
    return list_operator_actions(limit=limit)


def dispatch_operator_action(request: OperatorActionRequest) -> Dict[str, Any]:
    action = str(request.action or "").strip()
    handler = {
        "assign_operator": assign_operator,
        "mark_reviewed": mark_reviewed,
        "request_clarification": request_clarification,
        "archive_rfq": archive_rfq,
        "mark_evidence_incomplete": mark_evidence_incomplete,
        "mark_supplier_quote_received": mark_supplier_quote_received,
        "mark_waiting_pricing": mark_waiting_pricing,
        "escalate_review": escalate_review,
        "reopen_review": reopen_review,
        "acknowledge_alert": acknowledge_alert,
    }.get(action)
    if handler is None:
        raise ValueError(f"Unsupported operator action: {action}")
    return handler(request)
