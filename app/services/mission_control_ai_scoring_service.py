from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from app.core.supply_target_config import SUPPLY_MIN_PROFIT_PER_WIN, SUPPLY_MIN_SCORE_TO_REVIEW, SUPPLY_MIN_SCORE_TO_SUBMIT
from app.services.live_rfq_store import LiveRFQStore
from app.services.opportunity_scorer import score_opportunity as score_supply_opportunity
from app.services.pricing_engine import PricingEngine
from app.services.province_enrichment import infer_province_code
from app.services.supply_classifier import classify_supply_rfq

_DEFAULT_SUMMARY = {
    "scoredCount": 0,
    "highPriorityCount": 0,
    "averageScore": 0,
    "topCategory": None,
}


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


def _dedupe_preserve(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    items: List[str] = []
    for value in values:
        text = _safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _extract_live_items() -> List[Dict[str, Any]]:
    try:
        payload = LiveRFQStore.get_all()
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []

    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _identifier_for_item(item: Mapping[str, Any], index: int) -> str:
    for key in ("rfq_id", "buyer_rfq_number", "rfq_number", "reference_number", "document_number"):
        value = _safe_str(item.get(key))
        if value:
            return value
    return f"MISSION-CONTROL-AI-{index:04d}"


def _title_for_item(item: Mapping[str, Any], identifier: str) -> str:
    return _safe_str(item.get("title") or item.get("description") or identifier, identifier)


def _buyer_for_item(item: Mapping[str, Any]) -> str:
    return _safe_str(
        item.get("buyer_name")
        or item.get("buyer")
        or item.get("organ_of_state")
        or item.get("issuer_name")
        or item.get("department")
        or "—",
        "—",
    )


def _build_pricing_adapter(
    *,
    pricing_result: Mapping[str, Any],
    classification: Mapping[str, Any],
) -> Dict[str, Any]:
    pricing_summary = _safe_dict(pricing_result.get("pricing_summary"))
    total_profit = _safe_float(pricing_summary.get("total_profit"))
    margin_percent = _safe_float(pricing_summary.get("achieved_margin_percent"))
    total_sell_excl_vat = _safe_float(pricing_summary.get("total_sell_excl_vat"))
    quote_ready = bool(pricing_result.get("quote_ready")) and bool(classification.get("eligible"))

    return {
        "can_quote": quote_ready,
        "selected_supplier": _safe_dict(pricing_result.get("selected_supplier")),
        "cost_breakdown": {
            "gross_profit": total_profit,
            "margin_percent": margin_percent,
            "quote_total_excl_vat": total_sell_excl_vat,
        },
        "profit_floor_passed": total_profit >= SUPPLY_MIN_PROFIT_PER_WIN,
        "recommended_submit": bool(
            quote_ready
            and total_profit >= SUPPLY_MIN_PROFIT_PER_WIN
            and margin_percent >= 25.0
        ),
        "rejection_reason": "; ".join(_safe_list(pricing_result.get("eligibility_reasons"))),
    }


def _hard_block_reasons(classification: Mapping[str, Any], quote: Mapping[str, Any], scoring: Mapping[str, Any]) -> List[str]:
    reasons: List[str] = []

    if classification.get("excluded"):
        reasons.append(f"Excluded category: {classification.get('excluded_category') or 'unknown'}.")
    if classification.get("is_construction"):
        reasons.append("Construction / works scope detected.")
    if not classification.get("supply_only"):
        reasons.append("Not clearly pure supply-and-delivery.")
    if classification.get("has_compulsory_briefing"):
        reasons.append("Compulsory briefing or site meeting detected.")
    if not classification.get("eligible"):
        reasons.append("RFQ did not pass supply eligibility rules.")
    if not quote.get("can_quote"):
        reasons.append("No valid pricing route is available.")
    if not quote.get("profit_floor_passed"):
        reasons.append(f"Estimated gross profit is below R{SUPPLY_MIN_PROFIT_PER_WIN:,.2f}.")
    if not quote.get("recommended_submit"):
        reasons.append("Pricing controls rejected the opportunity.")

    score = _safe_float(scoring.get("score"))
    raw_reasons = [str(reason) for reason in _safe_list(scoring.get("reasons"))]
    hard_reason_hits = any(reason.lower().startswith("rejected") for reason in raw_reasons) or score <= 0
    if hard_reason_hits and not reasons:
        reasons.extend(raw_reasons)

    return _dedupe_preserve(reasons)


def _risk_notes(
    *,
    province_code: str,
    classification: Mapping[str, Any],
    pricing_result: Mapping[str, Any],
    scoring: Mapping[str, Any],
    hard_blocked: bool,
) -> List[str]:
    risks: List[str] = []
    pricing_summary = _safe_dict(pricing_result.get("pricing_summary"))
    total_profit = _safe_float(pricing_summary.get("total_profit"))
    margin_percent = _safe_float(pricing_summary.get("achieved_margin_percent"))
    score = _safe_float(scoring.get("score"))

    if not province_code:
        risks.append("Province could not be inferred.")
    if pricing_summary.get("profit_floor_adjustment"):
        risks.append("Pricing uses a fallback estimate.")
    if total_profit < SUPPLY_MIN_PROFIT_PER_WIN:
        risks.append("Estimated profit is below the R30,000 target.")
    if margin_percent < 25.0:
        risks.append("Estimated margin is below the 25% assumption.")
    if classification.get("has_compulsory_briefing"):
        risks.append("Compulsory briefing increases execution risk.")
    if hard_blocked:
        risks.append("Opportunity is blocked by supply rules.")
    elif score < SUPPLY_MIN_SCORE_TO_REVIEW:
        risks.append("Opportunity needs human review before action.")

    return _dedupe_preserve(risks)


def _priority_and_action(score: float, hard_blocked: bool) -> tuple[str, str]:
    if hard_blocked:
        return "blocked", "skip"
    if score >= SUPPLY_MIN_SCORE_TO_SUBMIT:
        return "high", "quote"
    if score >= SUPPLY_MIN_SCORE_TO_REVIEW:
        return "medium", "review"
    if score > 0:
        return "low", "needs_human_check"
    return "blocked", "skip"


def _score_single_item(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    identifier = _identifier_for_item(item, index)
    title = _title_for_item(item, identifier)
    buyer = _buyer_for_item(item)

    base_row = dict(item)
    province_code = infer_province_code(base_row) or "Unknown"
    base_row["province"] = province_code if province_code != "Unknown" else ""
    base_row["buyer_name"] = buyer
    base_row["title"] = title
    base_row["estimated_profit"] = _safe_float(base_row.get("estimated_profit") or base_row.get("profit"))
    base_row["estimated_margin_percent"] = _safe_float(
        base_row.get("estimated_margin_percent")
        or base_row.get("margin_percent")
        or base_row.get("minimum_margin_percent")
    )

    classification = classify_supply_rfq(base_row)
    pricing_result = PricingEngine.price_rfq(base_row)
    pricing_adapter = _build_pricing_adapter(pricing_result=pricing_result, classification=classification)
    scoring = score_supply_opportunity(base_row, classification, pricing_adapter)

    score = _safe_float(scoring.get("score"))
    hard_blocked = bool(_hard_block_reasons(classification, pricing_adapter, scoring))
    priority, recommended_action = _priority_and_action(score, hard_blocked)

    category = _safe_str(
        classification.get("category")
        or classification.get("excluded_category")
        or "general_supply",
        "general_supply",
    )

    reasons = _dedupe_preserve(
        [
            *(_safe_list(scoring.get("reasons"))),
            *(_safe_list(classification.get("classification_reasons"))),
        ]
    )
    if not reasons:
        reasons = [f"Scored from live RFQ {identifier}."]

    hard_block_reasons = _hard_block_reasons(classification, pricing_adapter, scoring)
    risks = _risk_notes(
        province_code=province_code if province_code != "Unknown" else "",
        classification=classification,
        pricing_result=pricing_result,
        scoring=scoring,
        hard_blocked=hard_blocked,
    )

    if hard_blocked and hard_block_reasons:
        reasons = _dedupe_preserve([*hard_block_reasons, *reasons])

    return {
        "rfqId": identifier,
        "title": title,
        "buyer": buyer,
        "province": province_code,
        "category": category,
        "score": round(score, 2),
        "priority": priority,
        "estimatedProfit": round(_safe_float(pricing_adapter.get("cost_breakdown", {}).get("gross_profit")), 2),
        "marginEstimate": round(_safe_float(pricing_adapter.get("cost_breakdown", {}).get("margin_percent")), 2),
        "reasons": reasons,
        "risks": risks,
        "recommendedAction": recommended_action,
    }


def _sort_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    priority_order = {"high": 0, "medium": 1, "low": 2, "blocked": 3}
    return sorted(
        items,
        key=lambda item: (
            priority_order.get(str(item.get("priority") or "").lower(), 99),
            -_safe_float(item.get("score")),
            _safe_str(item.get("title")),
        ),
    )


def _summarize_items(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [item for item in items if str(item.get("priority") or "").lower() != "blocked"]
    high_priority = [item for item in scored if str(item.get("priority") or "").lower() == "high"]
    scores = [_safe_float(item.get("score")) for item in scored]

    category_counts: Dict[str, int] = {}
    for item in scored:
        category = _safe_str(item.get("category"))
        if not category:
            continue
        category_counts[category] = category_counts.get(category, 0) + 1

    top_category = None
    if category_counts:
        top_category = sorted(category_counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]

    return {
        "scoredCount": len(scored),
        "highPriorityCount": len(high_priority),
        "averageScore": round(mean(scores), 2) if scores else 0,
        "topCategory": top_category,
    }


def build_default_ai_scoring(status: str = "not_configured") -> Dict[str, Any]:
    return {
        "status": status,
        "generatedAt": _now_iso(),
        "summary": dict(_DEFAULT_SUMMARY),
        "items": [],
    }


def build_mission_control_ai_scoring(items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    try:
        source_items = [item for item in (items if items is not None else _extract_live_items()) if isinstance(item, dict)]
    except Exception:
        return build_default_ai_scoring(status="degraded")

    if not source_items:
        return build_default_ai_scoring(status="not_configured")

    scored_items: List[Dict[str, Any]] = []
    had_partial_failure = False

    for index, item in enumerate(source_items, start=1):
        try:
            scored_items.append(_score_single_item(item, index))
        except Exception:
            had_partial_failure = True
            identifier = _identifier_for_item(item, index)
            scored_items.append(
                {
                    "rfqId": identifier,
                    "title": _title_for_item(item, identifier),
                    "buyer": _buyer_for_item(item),
                    "province": infer_province_code(item) or "Unknown",
                    "category": _safe_str(item.get("category") or item.get("excluded_category") or "general_supply"),
                    "score": 0,
                    "priority": "blocked",
                    "estimatedProfit": 0,
                    "marginEstimate": 0,
                    "reasons": ["AI scoring failed for this RFQ."],
                    "risks": ["Scoring pipeline degraded for this item."],
                    "recommendedAction": "skip",
                }
            )

    sorted_items = _sort_items(scored_items)
    summary = _summarize_items(sorted_items)
    status = "degraded" if had_partial_failure else "configured"

    return {
        "status": status,
        "generatedAt": _now_iso(),
        "summary": summary,
        "items": sorted_items,
    }

