from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from app.harvest.operator_capacity import OperatorCapacityConfig, calculate_remaining_capacity
from app.harvest.source_tiers import HarvestTier, is_passive_tier


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    priority_score: float
    suppression_reason: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _recommendation_rank(recommendation: str) -> float:
    recommendation = str(recommendation or "").upper()
    if recommendation == "GO":
        return 100.0
    if recommendation == "MANUAL_REVIEW":
        return 70.0
    return 0.0


def _confidence_score(candidate: Dict[str, Any]) -> float:
    values = [
        candidate.get("qualification_score"),
        candidate.get("automation_suitability_score"),
        candidate.get("supplier_match_score"),
        candidate.get("pricing_confidence", {}).get("overall_pricing_confidence") if isinstance(candidate.get("pricing_confidence"), dict) else None,
        candidate.get("supplier_evidence_score"),
    ]
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return 0.0
    return round(sum(numeric) / len(numeric), 2)


def _closing_date_urgency(candidate: Dict[str, Any]) -> float:
    closing_date = candidate.get("closing_date") or candidate.get("submission_deadline")
    if not closing_date:
        return 0.0
    try:
        if isinstance(closing_date, str):
            closing_date = datetime.fromisoformat(closing_date.replace("Z", "+00:00"))
        if closing_date.tzinfo is None:
            closing_date = closing_date.replace(tzinfo=timezone.utc)
        delta_days = (closing_date - _now()).total_seconds() / 86400.0
        if delta_days <= 1:
            return 10.0
        if delta_days <= 3:
            return 8.0
        if delta_days <= 7:
            return 5.0
        if delta_days <= 14:
            return 2.5
    except Exception:
        return 0.0
    return 0.0


def _priority_score(candidate: Dict[str, Any]) -> float:
    recommendation = _recommendation_rank(candidate.get("recommendation"))
    automation = float(candidate.get("automation_suitability_score") or 0.0)
    estimated_profit = float(candidate.get("estimated_profit") or candidate.get("viability", {}).get("estimated_profit") or 0.0)
    margin_confidence = float(candidate.get("pricing_confidence", {}).get("margin_confidence") or 0.0) if isinstance(candidate.get("pricing_confidence"), dict) else 0.0
    submission_method = str(candidate.get("submission_method", {}).get("method") or candidate.get("submission_method") or "").lower()
    risk_level = str(candidate.get("risk_level") or candidate.get("risk_breakdown", {}).get("risk_level") or "").lower()
    supplier_confidence = float(candidate.get("supplier_match_score") or 0.0)
    evidence_confidence = float(candidate.get("supplier_evidence_score") or 0.0)
    confidence = _confidence_score(candidate)
    urgency = _closing_date_urgency(candidate)
    submission_bonus = {"email": 10.0, "portal": 7.5, "e-submission": 8.0, "physical": -8.0, "courier": -10.0, "dropbox": -10.0}.get(submission_method, 0.0)
    risk_bonus = {"low": 10.0, "medium": 4.0, "high": -8.0, "blocked": -20.0}.get(risk_level, 0.0)
    score = (
        (recommendation * 0.35)
        + (automation * 0.20)
        + (min(estimated_profit, 150000.0) / 150000.0) * 10.0
        + (margin_confidence * 0.08)
        + submission_bonus
        + risk_bonus
        + (supplier_confidence * 0.08)
        + (evidence_confidence * 0.08)
        + (confidence * 0.06)
        + urgency
    )
    return round(max(0.0, min(100.0, score)), 2)


def prioritize_promotions(
    candidates: Iterable[Dict[str, Any]],
    *,
    already_promoted_count: int = 0,
    capacity_config: OperatorCapacityConfig | None = None,
) -> Dict[str, Any]:
    config = capacity_config or OperatorCapacityConfig()
    remaining_capacity = calculate_remaining_capacity(already_promoted_count, config)
    normalized: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []

    for candidate in candidates:
        item = dict(candidate or {})
        tier = HarvestTier.from_value(item.get("source_tier") or item.get("tier"))
        recommendation = str(item.get("recommendation") or item.get("qualification", {}).get("recommendation") or "MANUAL_REVIEW").upper()
        confidence = _confidence_score(item)
        priority_score = _priority_score(item)
        item["priority_score"] = priority_score
        if is_passive_tier(tier):
            item["promotion_status"] = "suppressed"
            item["suppression_reason"] = "tier 4 is passive discovery only"
            suppressed.append(item)
            continue
        if recommendation == "REJECT":
            item["promotion_status"] = "suppressed"
            item["suppression_reason"] = "rejected during qualification"
            suppressed.append(item)
            continue
        if confidence < 45.0 or bool(item.get("low_confidence")):
            item["promotion_status"] = "suppressed"
            item["suppression_reason"] = "low-confidence opportunity"
            suppressed.append(item)
            continue
        if recommendation not in {"GO", "MANUAL_REVIEW"}:
            item["promotion_status"] = "suppressed"
            item["suppression_reason"] = "not promotion eligible"
            suppressed.append(item)
            continue
        item["promotion_status"] = "pending"
        normalized.append(item)

    normalized.sort(key=lambda item: (0 if str(item.get("recommendation", "")).upper() == "GO" else 1, -float(item.get("priority_score") or 0.0)))
    promoted: List[Dict[str, Any]] = []
    for item in normalized:
        if remaining_capacity <= 0:
            item["promotion_status"] = "suppressed"
            item["suppression_reason"] = "operator review capacity exhausted"
            suppressed.append(item)
            continue
        item["promotion_status"] = "promoted"
        item["promoted_at"] = _now().isoformat()
        promoted.append(item)
        remaining_capacity -= 1

    return {
        "promoted": promoted,
        "suppressed": suppressed,
        "remaining_capacity": remaining_capacity,
        "total_promoted": len(promoted),
        "capacity_snapshot": {
            "team_size": config.team_size,
            "max_reviews_per_operator_per_day": config.max_reviews_per_operator_per_day,
            "total_daily_review_capacity": config.total_daily_review_capacity,
            "already_promoted_count": already_promoted_count,
        },
    }
