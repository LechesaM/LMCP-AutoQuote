from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import acknowledge_alert, archive_rfq
from app.operator_ops.operator_assignment_service import create_assignment
from app.operator_ops.operator_audit_timeline import record_timeline_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_tender_ids(tender_ids: Iterable[Any]) -> List[str]:
    return [str(item).strip() for item in tender_ids if str(item).strip()]


def build_bulk_action_preview(*, operator_id: str, tender_ids: Iterable[Any], target_operator_id: str = "", action: str = "", note: str = "") -> Dict[str, Any]:
    items = _safe_tender_ids(tender_ids)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "confirmed_required": True,
        "operator_id": operator_id,
        "target_operator_id": target_operator_id,
        "action": action,
        "note": note,
        "items": items,
        "item_count": len(items),
    }


def _record_bulk_event(action: str, operator_id: str, tender_id: str, note: str, details: Dict[str, Any]) -> Dict[str, Any]:
    return record_timeline_event(
        event_type=f"bulk_{action}",
        operator_id=operator_id,
        tender_id=tender_id,
        title=f"Bulk {action.replace('_', ' ')}",
        severity="warning" if action in {"archive", "acknowledge_alert"} else "info",
        details={"note": note, **details},
    )


def bulk_assign_operators(*, operator_id: str, tender_ids: Iterable[Any], target_operator_id: str, confirmed: bool, note: str = "") -> Dict[str, Any]:
    if not confirmed:
        raise ValueError("Bulk assignment requires explicit confirmation")
    items = _safe_tender_ids(tender_ids)
    if not items:
        raise ValueError("At least one tender_id is required")
    results: List[Dict[str, Any]] = []
    for tender_id in items:
        assignment = create_assignment(
            operator_id=target_operator_id,
            tender_id=tender_id,
            recommendation="manual",
            source="bulk_productivity",
            details={"acting_operator_id": operator_id, "bulk_action": True, "note": note},
        )
        result = {
            "action": "assign_operator",
            "operator_id": operator_id,
            "target_operator_id": target_operator_id,
            "tender_id": tender_id,
            "assignment": assignment,
            "note": note,
        }
        result["audit"] = _record_bulk_event("assign", operator_id, tender_id, note, result)
        results.append(result)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "confirmed": True,
        "action": "assign_operator",
        "operator_id": operator_id,
        "target_operator_id": target_operator_id,
        "items": results,
        "item_count": len(results),
    }


def bulk_acknowledge_alerts(*, operator_id: str, tender_ids: Iterable[Any], confirmed: bool, note: str = "") -> Dict[str, Any]:
    if not confirmed:
        raise ValueError("Bulk acknowledgement requires explicit confirmation")
    items = _safe_tender_ids(tender_ids)
    results: List[Dict[str, Any]] = []
    for tender_id in items:
        request = OperatorActionRequest(
            operator_id=operator_id,
            tender_id=tender_id,
            action="acknowledge_alert",
            note=note,
            target_type="rfq",
            details={"bulk_action": True},
        )
        result = acknowledge_alert(request)
        result["audit"] = _record_bulk_event("acknowledge_alert", operator_id, tender_id, note, result)
        results.append(result)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "confirmed": True,
        "action": "acknowledge_alert",
        "operator_id": operator_id,
        "items": results,
        "item_count": len(results),
    }


def bulk_archive_reviewed(*, operator_id: str, tender_ids: Iterable[Any], confirmed: bool, note: str = "") -> Dict[str, Any]:
    if not confirmed:
        raise ValueError("Bulk archive requires explicit confirmation")
    items = _safe_tender_ids(tender_ids)
    results: List[Dict[str, Any]] = []
    for tender_id in items:
        request = OperatorActionRequest(
            operator_id=operator_id,
            tender_id=tender_id,
            action="archive_rfq",
            note=note,
            target_type="rfq",
            details={"bulk_action": True, "review_status": "reviewed"},
        )
        result = archive_rfq(request)
        result["audit"] = _record_bulk_event("archive", operator_id, tender_id, note, result)
        results.append(result)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "confirmed": True,
        "action": "archive_rfq",
        "operator_id": operator_id,
        "items": results,
        "item_count": len(results),
    }
