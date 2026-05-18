from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        return float(str(v).replace("R", "").replace(",", "").strip())
    except:
        return default


def apply_pricing_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})

    items = payload.get("items") or payload.get("line_items") or []
    if not items:
        return payload

    MIN_PROFIT = 30000.0
    MIN_MARGIN = 0.25

    MAX_MARGIN_SINGLE = 0.45
    MAX_MARGIN_MULTI = 0.55

    VAT = 0.15

    is_single = len(items) == 1

    total_cost = 0.0
    clean_items: List[Dict[str, Any]] = []

    for i, item in enumerate(items, start=1):
        qty = _safe_float(item.get("quantity") or 1, 1)
        cost = _safe_float(
            item.get("supplier_unit_cost")
            or item.get("unit_cost")
            or item.get("cost")
            or 0
        )

        if cost <= 0:
            # fallback safe estimate
            cost = 100.0

        total_cost += cost * qty

        clean_items.append({
            "description": item.get("description", "Item"),
            "quantity": qty,
            "unit_cost": cost,
        })

    # Determine realistic target
    target_profit = max(MIN_PROFIT, total_cost * MIN_MARGIN)

    total_sell = 0.0
    total_profit = 0.0
    output_items = []

    for item in clean_items:
        qty = item["quantity"]
        cost = item["unit_cost"]
        line_cost = cost * qty

        weight = line_cost / total_cost if total_cost else 0
        target_line_profit = target_profit * weight

        requested_unit_price = cost + (target_line_profit / max(qty, 1))

        # Apply caps
        max_margin = MAX_MARGIN_SINGLE if is_single else MAX_MARGIN_MULTI

        min_price = cost / (1 - MIN_MARGIN)
        max_price = cost / (1 - max_margin)

        final_price = max(min_price, min(requested_unit_price, max_price))

        line_total = final_price * qty
        line_profit = line_total - line_cost

        total_sell += line_total
        total_profit += line_profit

        output_items.append({
            "description": item["description"],
            "quantity": qty,
            "unit_price": round(final_price, 2),
            "line_total": round(line_total, 2),
            "line_profit": round(line_profit, 2),
        })

    achieved_margin = (total_profit / total_sell * 100) if total_sell else 0
    profit_gap = max(0, MIN_PROFIT - total_profit)

    manual_review = profit_gap > 0

    payload["items"] = output_items
    payload["pricing_summary"] = {
        "total_cost": round(total_cost, 2),
        "total_sell": round(total_sell, 2),
        "total_profit": round(total_profit, 2),
        "margin_percent": round(achieved_margin, 2),
        "minimum_profit_required": MIN_PROFIT,
        "profit_gap": round(profit_gap, 2),
        "manual_review_required": manual_review,
        "engine": "PRICING_V2_SAFE",
        "timestamp": _now(),
    }

    payload["quote_ready"] = not manual_review

    if manual_review:
        payload["submission_status"] = "manual_review_required"
        payload["submission_message"] = "Profit target cannot be reached without unrealistic pricing."

    return payload
