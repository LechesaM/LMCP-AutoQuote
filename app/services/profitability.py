from __future__ import annotations

from typing import Any, Dict, Optional


def to_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert numeric-like values to float.
    """
    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    try:
        text = str(value).strip().replace(",", "")
        text = text.replace("R", "").replace("$", "").strip()
        return float(text)
    except Exception:
        return default


def calculate_profitability(
    estimated_cost: Any,
    estimated_revenue: Any,
) -> Dict[str, float]:
    """
    Calculate margin and markup metrics.
    """
    cost = to_float(estimated_cost, 0.0)
    revenue = to_float(estimated_revenue, 0.0)

    gross_profit = revenue - cost
    gross_margin_percent = (gross_profit / revenue * 100.0) if revenue > 0 else 0.0
    markup_percent = (gross_profit / cost * 100.0) if cost > 0 else 0.0

    return {
        "estimated_cost": round(cost, 2),
        "estimated_revenue": round(revenue, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_percent": round(gross_margin_percent, 2),
        "markup_percent": round(markup_percent, 2),
    }


def profitability_decision(
    *,
    estimated_cost: Any,
    estimated_revenue: Any,
    minimum_margin_percent: float = 12.0,
) -> Dict[str, Any]:
    """
    Decide whether to approve or skip a tender based on margin.
    """
    metrics = calculate_profitability(
        estimated_cost=estimated_cost,
        estimated_revenue=estimated_revenue,
    )

    approved = metrics["gross_margin_percent"] >= minimum_margin_percent

    return {
        **metrics,
        "minimum_margin_percent": round(minimum_margin_percent, 2),
        "approved": approved,
        "decision": "APPROVED" if approved else "SKIPPED_LOW_MARGIN",
    }


def extract_cost_and_revenue_from_pricing_result(pricing_result: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """
    Try to extract cost and revenue from a pricing result structure.
    This is defensive because different pricing engines may use different keys.
    """
    pricing_result = pricing_result or {}

    cost_candidates = [
        pricing_result.get("estimated_cost"),
        pricing_result.get("total_cost"),
        pricing_result.get("subtotal_cost"),
        pricing_result.get("base_cost"),
        pricing_result.get("supplier_total"),
    ]

    revenue_candidates = [
        pricing_result.get("estimated_revenue"),
        pricing_result.get("total_sell_price"),
        pricing_result.get("total_amount"),
        pricing_result.get("grand_total"),
        pricing_result.get("quote_total"),
        pricing_result.get("sell_price"),
    ]

    estimated_cost = 0.0
    estimated_revenue = 0.0

    for value in cost_candidates:
        number = to_float(value, 0.0)
        if number > 0:
            estimated_cost = number
            break

    for value in revenue_candidates:
        number = to_float(value, 0.0)
        if number > 0:
            estimated_revenue = number
            break

    return {
        "estimated_cost": round(estimated_cost, 2),
        "estimated_revenue": round(estimated_revenue, 2),
    }


def evaluate_pricing_result_profitability(
    pricing_result: Optional[Dict[str, Any]],
    minimum_margin_percent: float = 12.0,
) -> Dict[str, Any]:
    """
    Evaluate profitability directly from pricing_result.
    """
    extracted = extract_cost_and_revenue_from_pricing_result(pricing_result)
    return profitability_decision(
        estimated_cost=extracted["estimated_cost"],
        estimated_revenue=extracted["estimated_revenue"],
        minimum_margin_percent=minimum_margin_percent,
    )
