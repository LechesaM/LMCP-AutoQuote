from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Sequence


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text or default
    except Exception:
        return default


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = _safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _priority_for_score(score: float) -> str:
    if score >= 90:
        return "high"
    if score >= 75:
        return "medium"
    return "low"


def _recommendation(
    *,
    rec_type: str,
    priority: str,
    title: str,
    description: str,
    source: str,
    target_route: str,
    related_rfq_id: str = "",
    score: float = 0.0,
    estimated_profit: float = 0.0,
    reasons: Sequence[str] | None = None,
    recommended_action: str = "review",
) -> Dict[str, Any]:
    return {
        "id": f"{rec_type}-{related_rfq_id or _safe_str(title, 'recommendation')}".replace(" ", "-").lower(),
        "type": rec_type,
        "priority": priority,
        "title": title,
        "description": description,
        "source": source,
        "targetRoute": target_route,
        "relatedRfqId": related_rfq_id,
        "score": round(_safe_float(score), 2),
        "estimatedProfit": round(_safe_float(estimated_profit), 2),
        "reasons": _dedupe(reasons or []),
        "recommendedAction": recommended_action,
    }


def build_default_mission_control_recommendations(status: str = "insufficient_history") -> Dict[str, Any]:
    return {
        "status": status,
        "generatedAt": _now_iso(),
        "items": [],
    }


def _ai_scoring_recommendations(ai_scoring: Mapping[str, Any]) -> List[Dict[str, Any]]:
    items = [item for item in _safe_list(ai_scoring.get("items")) if isinstance(item, dict)]
    recommendations: List[Dict[str, Any]] = []

    for item in items[:3]:
        # keep recommendations anchored to the already scored item list
        score = _safe_float(item.get("score"))
        recommended_action = _safe_str(item.get("recommendedAction"), "review").lower()
        priority = _priority_for_score(score)
        related_rfq_id = _safe_str(item.get("rfqId") or item.get("rfq_id") or item.get("id"))
        title = _safe_str(item.get("title") or related_rfq_id or "Review scored opportunity")
        description = _safe_str(
            item.get("description")
            or item.get("summary")
            or f"Follow the AI-scored opportunity for {title}.",
            f"Follow the AI-scored opportunity for {title}.",
        )
        reasons = _safe_list(item.get("reasons"))
        risks = _safe_list(item.get("risks"))
        estimated_profit = _safe_float(item.get("estimatedProfit"))

        if recommended_action == "quote":
            recommendations.append(
                _recommendation(
                    rec_type="quote",
                    priority="high" if score >= 85 else priority,
                    title=f"Quote {title}",
                    description=description,
                    source="ai_scoring",
                    target_route="/supplier-quote-intelligence",
                    related_rfq_id=related_rfq_id,
                    score=score,
                    estimated_profit=estimated_profit,
                    reasons=[*reasons, *risks],
                    recommended_action="quote",
                )
            )
        elif recommended_action == "review":
            recommendations.append(
                _recommendation(
                    rec_type="review",
                    priority="high" if score >= 85 else "medium",
                    title=f"Review {title}",
                    description=description,
                    source="ai_scoring",
                    target_route="/review",
                    related_rfq_id=related_rfq_id,
                    score=score,
                    estimated_profit=estimated_profit,
                    reasons=[*reasons, *risks],
                    recommended_action="review",
                )
            )
        elif recommended_action == "needs_human_check":
            recommendations.append(
                _recommendation(
                    rec_type="review",
                    priority="medium",
                    title=f"Check {title}",
                    description=description,
                    source="ai_scoring",
                    target_route="/review",
                    related_rfq_id=related_rfq_id,
                    score=score,
                    estimated_profit=estimated_profit,
                    reasons=[*reasons, *risks],
                    recommended_action="review",
                )
            )

    return recommendations


def _submission_recommendations(submission_readiness: Mapping[str, Any], pipeline_stages: Mapping[str, Any]) -> List[Dict[str, Any]]:
    readiness_state = _safe_str(submission_readiness.get("readiness_state") or submission_readiness.get("readinessState")).upper()
    blocking_issues = [issue for issue in _safe_list(submission_readiness.get("blocking_issues") or submission_readiness.get("blockingIssues")) if issue]
    blocked_count = _safe_float(pipeline_stages.get("Blocked"))

    if readiness_state == "READY" and not blocking_issues and blocked_count <= 0:
        return []

    description = "Review the current submission readiness blockers before attempting to submit."
    if blocking_issues:
        description = blocking_issues[0]

    return [
        _recommendation(
            rec_type="unblock",
            priority="high",
            title="Follow up on Blocked Submission",
            description=description,
            source="submission_readiness",
            target_route="/review",
            score=0.0,
            estimated_profit=0.0,
            reasons=blocking_issues or ["Submission readiness is not clear."],
            recommended_action="unblock",
        )
    ]


def _quote_intelligence_recommendations(quote_intelligence: Mapping[str, Any]) -> List[Dict[str, Any]]:
    if _safe_str(quote_intelligence.get("status"), "insufficient_history").lower() != "configured":
        return []

    supplier_coverage = _safe_float(quote_intelligence.get("supplierCoverage") or quote_intelligence.get("supplier_coverage"))
    pricing_freshness = _safe_float(quote_intelligence.get("pricingFreshness") or quote_intelligence.get("pricing_freshness"))
    award_signals = _safe_float(quote_intelligence.get("awardSignals") or quote_intelligence.get("award_signals"))
    competitor_signals = _safe_float(quote_intelligence.get("competitorSignals") or quote_intelligence.get("competitor_signals"))

    recommendations: List[Dict[str, Any]] = []
    if supplier_coverage and supplier_coverage < 60:
        recommendations.append(
            _recommendation(
                rec_type="supplier_gap",
                priority="high" if supplier_coverage < 35 else "medium",
                title="Investigate Supplier Coverage Gap",
                description="Supplier coverage is below the target threshold.",
                source="quote_intelligence",
                target_route="/supplier-quote-intelligence",
                score=supplier_coverage,
                reasons=["Supplier coverage is below the preferred threshold."],
                recommended_action="investigate",
            )
        )
    if pricing_freshness and pricing_freshness < 60:
        recommendations.append(
            _recommendation(
                rec_type="intelligence_gap",
                priority="medium",
                title="Refresh Pricing Signals",
                description="Pricing freshness is drifting and should be reviewed.",
                source="quote_intelligence",
                target_route="/supplier-quote-intelligence",
                score=pricing_freshness,
                reasons=["Pricing freshness is below the preferred threshold."],
                recommended_action="investigate",
            )
        )
    if award_signals and competitor_signals:
        recommendations.append(
            _recommendation(
                rec_type="intelligence_gap",
                priority="low",
                title="Monitor Award and Competitor Signals",
                description="Award and competitor activity are both present and should be watched.",
                source="quote_intelligence",
                target_route="/supplier-quote-intelligence",
                score=max(award_signals, competitor_signals),
                reasons=["Award signals and competitor signals are available."],
                recommended_action="investigate",
            )
        )

    return recommendations


def build_mission_control_recommendations(
    *,
    ai_scoring: Mapping[str, Any] | None = None,
    quote_intelligence: Mapping[str, Any] | None = None,
    submission_readiness: Mapping[str, Any] | None = None,
    pipeline_stages: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    ai_scoring = _safe_dict(ai_scoring)
    quote_intelligence = _safe_dict(quote_intelligence)
    submission_readiness = _safe_dict(submission_readiness)
    pipeline_stages = _safe_dict(pipeline_stages)

    items: List[Dict[str, Any]] = []
    items.extend(_submission_recommendations(submission_readiness, pipeline_stages))
    items.extend(_quote_intelligence_recommendations(quote_intelligence))
    items.extend(_ai_scoring_recommendations(ai_scoring))

    if not items:
        return build_default_mission_control_recommendations()

    items.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(_safe_str(item.get("priority")).lower(), 99),
            -_safe_float(item.get("score")),
            _safe_str(item.get("title")),
        )
    )

    return {
        "status": "configured",
        "generatedAt": _now_iso(),
        "items": items,
    }
