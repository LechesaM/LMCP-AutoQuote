from __future__ import annotations

from typing import Any, Dict, List

from app.core.supply_target_config import (
    SUPPLY_MIN_PROFIT_PER_WIN,
    SUPPLY_MIN_SCORE_TO_REVIEW,
    SUPPLY_MIN_SCORE_TO_SUBMIT,
)


EXCLUDED_SCORING_CATEGORIES = {
    "medical_consumables",
    "it_equipment",
    "petrol_diesel_supply",
}


def _score_submission_mode(mode: str) -> float:
    mode = (mode or "").lower()
    if mode == "email":
        return 2.0
    if mode == "portal":
        return 1.8
    return 0.8


def _score_eligibility(classification: Dict[str, Any]) -> float:
    score = 0.0
    if classification.get("eligible"):
        score += 2.5
    if classification.get("supply_only"):
        score += 1.5
    if not classification.get("has_compulsory_briefing"):
        score += 1.5
    return score


def _score_supplier_strength(quote: Dict[str, Any]) -> float:
    if not quote.get("can_quote"):
        return 0.0

    supplier = quote.get("selected_supplier") or {}
    stock = float(supplier.get("available_stock", 0))
    lead_time_days = float(supplier.get("lead_time_days", 99))

    score = 0.0
    if stock > 10000:
        score += 1.8
    elif stock > 1000:
        score += 1.4
    elif stock > 100:
        score += 1.0
    else:
        score += 0.5

    if lead_time_days <= 2:
        score += 1.6
    elif lead_time_days <= 5:
        score += 1.1
    else:
        score += 0.4

    return score


def _score_profitability(quote: Dict[str, Any]) -> float:
    if not quote.get("can_quote"):
        return 0.0

    breakdown = quote.get("cost_breakdown", {})
    total = float(breakdown.get("quote_total_excl_vat", 0))
    gross_profit = float(breakdown.get("gross_profit", 0))
    margin_percent = float(breakdown.get("margin_percent", 0))

    score = 0.0

    if total >= 5_000_000:
        score += 2.0
    elif total >= 1_000_000:
        score += 1.5
    elif total >= 250_000:
        score += 1.0
    else:
        score += 0.5

    if gross_profit >= (SUPPLY_MIN_PROFIT_PER_WIN * 3):
        score += 1.8
    elif gross_profit >= (SUPPLY_MIN_PROFIT_PER_WIN * 2):
        score += 1.4
    elif gross_profit >= SUPPLY_MIN_PROFIT_PER_WIN:
        score += 1.0
    else:
        score += 0.0

    if margin_percent >= 25:
        score += 1.2
    elif margin_percent >= 15:
        score += 0.8
    else:
        score += 0.4

    return score


def _score_competition(rfq: Dict[str, Any]) -> float:
    title = str(rfq.get("title", "")).lower()
    description = str(rfq.get("description", "")).lower()
    text = f"{title} {description}"

    highly_competitive_terms = ["national", "framework", "term contract", "panel"]
    niche_terms = ["district", "local municipality", "clinic", "school", "regional office"]

    score = 1.0
    if any(term in text for term in highly_competitive_terms):
        score = 0.75
    if any(term in text for term in niche_terms):
        score = 1.35
    return score


def score_opportunity(
    rfq: Dict[str, Any],
    classification: Dict[str, Any],
    quote: Dict[str, Any],
) -> Dict[str, Any]:
    excluded_category = classification.get("excluded_category")
    is_construction = bool(classification.get("is_construction", False))
    supply_only = bool(classification.get("supply_only", False))
    has_compulsory_briefing = bool(classification.get("has_compulsory_briefing", False))
    eligible = bool(classification.get("eligible", False))
    profit_floor_passed = bool(quote.get("profit_floor_passed", False))
    recommended_submit_by_pricing = bool(quote.get("recommended_submit", False))

    reasons: List[str] = []

    if excluded_category in EXCLUDED_SCORING_CATEGORIES:
        reasons.append(f"Rejected because category '{excluded_category}' is excluded.")
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    if is_construction:
        reasons.append("Rejected because construction / works / installation / maintenance scope was detected.")
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    if not supply_only:
        reasons.append("Rejected because RFQ is not clearly pure supply-and-delivery.")
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    if has_compulsory_briefing:
        reasons.append("Rejected because RFQ includes a compulsory or mandatory briefing/site meeting.")
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    if not eligible:
        reasons.append("Rejected because RFQ did not pass supply eligibility rules.")
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    if not quote.get("can_quote"):
        reasons.append("Rejected because no valid supplier/pricing route is available.")
        if quote.get("rejection_reason"):
            reasons.append(str(quote.get("rejection_reason")))
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    if not profit_floor_passed:
        reasons.append(
            f"Rejected because estimated gross profit is below R{SUPPLY_MIN_PROFIT_PER_WIN:,.2f} floor."
        )
        if quote.get("rejection_reason"):
            reasons.append(str(quote.get("rejection_reason")))
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    if not recommended_submit_by_pricing:
        reasons.append("Rejected by pricing controls.")
        if quote.get("rejection_reason"):
            reasons.append(str(quote.get("rejection_reason")))
        return {
            "rfq_id": rfq.get("rfq_id"),
            "score": 0.0,
            "priority": "LOW",
            "recommended_action": "SKIP",
            "profit_floor_passed": False,
            "reasons": reasons,
        }

    submission_mode_score = _score_submission_mode(classification.get("submission_mode", "unknown"))
    eligibility_score = _score_eligibility(classification)
    supplier_score = _score_supplier_strength(quote)
    profitability_score = _score_profitability(quote)
    competition_modifier = _score_competition(rfq)

    raw_score = (
        submission_mode_score
        + eligibility_score
        + supplier_score
        + profitability_score
    ) * competition_modifier

    final_score = min(round(raw_score, 2), 10.0)

    if final_score >= SUPPLY_MIN_SCORE_TO_SUBMIT:
        priority = "HIGH"
        action = "SUBMIT"
    elif final_score >= SUPPLY_MIN_SCORE_TO_REVIEW:
        priority = "MEDIUM"
        action = "REVIEW"
    else:
        priority = "LOW"
        action = "SKIP"

    reasons.append("RFQ passed pure supply-and-delivery eligibility rules.")

    if classification.get("submission_mode") == "email":
        reasons.append("Email submission is operationally efficient.")
    elif classification.get("submission_mode") == "portal":
        reasons.append("Portal submission supported.")

    reasons.append("Supplier and pricing route available.")

    gross_profit = quote.get("cost_breakdown", {}).get("gross_profit", 0)
    margin = quote.get("cost_breakdown", {}).get("margin_percent", 0)
    reasons.append(f"Estimated gross profit: R{float(gross_profit):,.2f}.")
    reasons.append(f"Estimated margin: {float(margin):.2f}%.")

    return {
        "rfq_id": rfq.get("rfq_id"),
        "score": final_score,
        "priority": priority,
        "recommended_action": action,
        "profit_floor_passed": True,
        "reasons": reasons,
    }
