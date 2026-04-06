from typing import Any, Dict, List


def calculate_intelligence_score(
    base_relevance_score: float,
    profile_summary: Dict[str, Any],
    behavior_summary: Dict[str, Any],
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    buyer_activity_score = float(profile_summary.get("buyer_activity_score", 0.0))
    repeat_buying_score = float(profile_summary.get("repeat_buying_score", 0.0))
    category_alignment_score = float(behavior_summary.get("category_alignment_score", 0.0))
    competition_favorability_score = float(
        behavior_summary.get("competition_favorability_score", 0.0)
    )

    signal_confidence_score = 0.0
    if signals:
        signal_confidence_score = max(signal.get("confidence_score", 0.0) for signal in signals) * 100.0

    intelligence_score = (
        (float(base_relevance_score) * 0.35)
        + (buyer_activity_score * 0.15)
        + (repeat_buying_score * 0.15)
        + (category_alignment_score * 0.15)
        + (signal_confidence_score * 0.10)
        + (competition_favorability_score * 0.10)
    )

    quote_ready = intelligence_score >= 70.0

    return {
        "buyer_activity_score": round(buyer_activity_score, 2),
        "repeat_buying_score": round(repeat_buying_score, 2),
        "category_alignment_score": round(category_alignment_score, 2),
        "competition_favorability_score": round(competition_favorability_score, 2),
        "signal_confidence_score": round(signal_confidence_score, 2),
        "intelligence_score": round(intelligence_score, 2),
        "quote_ready": quote_ready,
    }
