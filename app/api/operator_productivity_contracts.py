from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from app.domain.base import StrictBaseModel, Field
from app.productivity.bulk_review_actions import (
    bulk_acknowledge_alerts,
    bulk_assign_operators,
    bulk_archive_reviewed,
)
from app.productivity.evidence_review_accelerator import build_evidence_acceleration_summary
from app.productivity.operator_focus_sessions import build_focus_session_summary
from app.productivity.operator_shortcuts import build_operator_shortcut_catalog
from app.productivity.operator_workload_balancer import build_operator_workload_summary, recommend_workload_rebalance
from app.productivity.queue_heatmap import build_queue_heatmap_summary
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics
from app.productivity.review_priority_engine import build_review_priority_summary
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BulkProductivityActionRequest(StrictBaseModel):
    operator_id: str
    tender_ids: List[str] = Field(default_factory=list)
    target_operator_id: str = ""
    confirmed: bool = False
    note: str = ""

    @classmethod
    def validate_payload(cls, payload: Dict[str, Any]) -> "BulkProductivityActionRequest":
        return super().validate_payload(payload)  # type: ignore[return-value]


def _safe_payload(items: Iterable[Any]) -> List[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def build_operator_productivity_workload(limit: int = 200) -> Dict[str, Any]:
    return build_operator_workload_summary(limit=limit)


def build_operator_productivity_queue_optimization(limit: int = 200) -> Dict[str, Any]:
    return build_review_queue_optimization_summary(limit=limit)


def build_operator_productivity_review_efficiency(limit: int = 200) -> Dict[str, Any]:
    return build_review_efficiency_analytics(limit=limit)


def build_operator_productivity_focus_sessions(limit: int = 200) -> Dict[str, Any]:
    return build_focus_session_summary(limit=limit)


def build_operator_productivity_queue_heatmap(limit: int = 200) -> Dict[str, Any]:
    return build_queue_heatmap_summary(limit=limit)


def build_operator_productivity_review_priorities(limit: int = 200) -> Dict[str, Any]:
    return build_review_priority_summary(limit=limit)


def build_operator_productivity_evidence_acceleration(limit: int = 200) -> Dict[str, Any]:
    return build_evidence_acceleration_summary(limit=limit)


def build_operator_productivity_shortcuts() -> Dict[str, Any]:
    return build_operator_shortcut_catalog()


def build_bulk_assign_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = BulkProductivityActionRequest.validate_payload(payload)
    tender_ids = _safe_payload(request.tender_ids)
    return bulk_assign_operators(
        operator_id=request.operator_id,
        tender_ids=tender_ids,
        target_operator_id=request.target_operator_id or request.operator_id,
        confirmed=request.confirmed,
        note=request.note,
    )


def build_bulk_acknowledge_alert_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = BulkProductivityActionRequest.validate_payload(payload)
    return bulk_acknowledge_alerts(
        operator_id=request.operator_id,
        tender_ids=_safe_payload(request.tender_ids),
        confirmed=request.confirmed,
        note=request.note,
    )


def build_bulk_archive_reviewed_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = BulkProductivityActionRequest.validate_payload(payload)
    return bulk_archive_reviewed(
        operator_id=request.operator_id,
        tender_ids=_safe_payload(request.tender_ids),
        confirmed=request.confirmed,
        note=request.note,
    )

