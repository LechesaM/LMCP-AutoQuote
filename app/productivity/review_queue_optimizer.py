from __future__ import annotations

from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Any, Dict, List, Tuple

from app.dashboard.workflow_queue_service import get_pending_approval_queue, get_proof_capture_queue, get_review_ready_queue


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _queue_records(limit: int = 200) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for row in get_review_ready_queue(limit=limit) + get_pending_approval_queue(limit=limit) + get_proof_capture_queue(limit=limit):
        if isinstance(row, dict):
            records.append(row)
    return records


def _priority_group(score: float) -> str:
    if score >= 80:
        return "urgent"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _queue_age_minutes(record: Dict[str, Any]) -> float:
    updated = _parse_iso(record.get("updated_at") or record.get("created_at") or record.get("approved_at"))
    if not updated:
        return 0.0
    return round(max(0.0, (_now() - updated).total_seconds() / 60.0), 2)


def _closing_urgency(record: Dict[str, Any]) -> float:
    closing = _parse_iso(record.get("closing_date") or record.get("closingDate"))
    if not closing:
        return 10.0
    minutes = (closing - _now()).total_seconds() / 60.0
    if minutes <= 0:
        return 40.0
    if minutes <= 24 * 60:
        return 30.0
    if minutes <= 3 * 24 * 60:
        return 18.0
    return 5.0


def _risk_weight(record: Dict[str, Any]) -> float:
    risk = _safe_float(record.get("risk_score") or record.get("riskScore") or record.get("qualification_risk_score"))
    if risk:
        return min(35.0, risk / 2.0)
    risk_level = _safe_str(record.get("risk_level") or record.get("riskLevel"), "medium").lower()
    return {"critical": 30.0, "high": 24.0, "medium": 14.0, "low": 5.0}.get(risk_level, 10.0)


def _pricing_weight(record: Dict[str, Any]) -> float:
    completeness = _safe_float(record.get("pricing_evidence_completeness") or record.get("pricingEvidenceCompleteness") or 0.0)
    confidence = _safe_float(record.get("pricing_confidence") or record.get("pricingConfidence") or 0.0)
    if completeness and confidence:
        return (completeness + confidence) / 4.0
    if completeness:
        return completeness / 2.0
    return 8.0


def _governance_weight(record: Dict[str, Any]) -> float:
    blockers = int(bool(record.get("manual_review_required") or record.get("review_ready_required") or record.get("proof_capture_required")))
    return 18.0 if blockers else 0.0


def build_review_queue_optimization_summary(limit: int = 200) -> Dict[str, Any]:
    records = _queue_records(limit=limit)
    from app.stabilization.operator_fatigue_monitor import build_operator_fatigue_report

    fatigue = build_operator_fatigue_report(limit=limit)
    optimized: List[Dict[str, Any]] = []
    for index, record in enumerate(records):
        recommendation = _safe_str(record.get("recommendation") or record.get("qualification_recommendation"), "MANUAL_REVIEW")
        queue_age = _queue_age_minutes(record)
        score = (
            _closing_urgency(record)
            + min(25.0, queue_age / 6.0)
            + _risk_weight(record)
            + _pricing_weight(record)
            + _governance_weight(record)
        )
        if recommendation == "GO":
            score += 20.0
        elif recommendation == "REJECT":
            score += 5.0
        priority_group = _priority_group(score)
        optimized.append(
            {
                "tender_id": _safe_str(record.get("tender_id") or record.get("id") or f"row-{index}"),
                "title": _safe_str(record.get("title") or record.get("name"), "Unknown RFQ"),
                "buyer": _safe_str(record.get("buyer") or record.get("buyer_name"), "Unknown buyer"),
                "province": _safe_str(record.get("province"), "Unknown"),
                "closing_date": _safe_str(record.get("closing_date") or record.get("closingDate")),
                "workflow_stage": _safe_str(record.get("workflow_stage") or record.get("stage"), "review_ready"),
                "review_status": _safe_str(record.get("review_status") or record.get("status"), "pending"),
                "pricing_confidence": _safe_float(record.get("pricing_confidence") or record.get("pricingConfidence")),
                "queue_age_minutes": queue_age,
                "priority_score": round(score, 2),
                "priority_group": priority_group,
                "priority_reason": "closing urgency and queue age" if priority_group in {"urgent", "high"} else "normal queue order",
                "risk_level": _safe_str(record.get("risk_level") or record.get("riskLevel"), "medium"),
                "stale_evidence": bool(record.get("stale_evidence") or record.get("staleEvidence")),
                "review_readiness": _safe_str(record.get("qualification_status") or record.get("review_readiness"), "manual"),
                "governance_blocked": bool(record.get("governance_blocked") or record.get("manual_review_required")),
                "submission_method": _safe_str(record.get("submission_method") or record.get("submissionMethod"), "unknown"),
                "source_tier": _safe_str(record.get("source_tier") or record.get("sourceTier"), "Tier 4"),
                "data_source": _safe_str(record.get("data_source") or "runtime"),
            }
        )

    optimized.sort(key=lambda row: (-float(row["priority_score"]), float(row["queue_age_minutes"]), str(row["tender_id"])))
    priority_groups = {"urgent": [], "high": [], "medium": [], "low": []}
    for item in optimized:
        priority_groups[item["priority_group"]].append(item)
    overdue_reviews = [item for item in optimized if item["queue_age_minutes"] >= 240.0 or item["priority_group"] == "urgent"]
    stale_rfqs = [item for item in optimized if item["stale_evidence"] or item["queue_age_minutes"] >= 120.0]
    return {
        "status": "ok" if optimized else "degraded",
        "generated_at": _now_iso(),
        "data_source": "runtime" if optimized else "fallback",
        "optimized_queue": optimized[: max(1, int(limit or 200))],
        "priority_groups": priority_groups,
        "overdue_reviews": overdue_reviews,
        "stale_rfqs": stale_rfqs,
        "overloaded_queue": len(optimized) >= 1000,
        "summary": {
            "total": len(optimized),
            "urgent": len(priority_groups["urgent"]),
            "high": len(priority_groups["high"]),
            "medium": len(priority_groups["medium"]),
            "low": len(priority_groups["low"]),
            "average_priority_score": round(mean([item["priority_score"] for item in optimized]) if optimized else 0.0, 2),
            "average_queue_age_minutes": round(mean([item["queue_age_minutes"] for item in optimized]) if optimized else 0.0, 2),
        },
        "fatigue_signals": fatigue.get("signals", {}),
        "fatigue_warnings": fatigue.get("warnings", []),
    }
