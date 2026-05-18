from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


@dataclass
class PricingV2Policy:
    minimum_profit_required: float = 30000.0
    minimum_margin_percent: float = 25.0
    max_margin_percent_single_line: float = 45.0
    max_margin_percent_multi_line: float = 55.0
    max_markup_percent_single_line: float = 80.0
    max_markup_percent_multi_line: float = 120.0
    vat_rate: float = 15.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace("R", "").replace("ZAR", "").replace("zar", "").replace(",", "").replace("%", "").strip()
            if not value:
                return default
        return float(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _money(value: float) -> float:
    return round(float(value or 0.0), 2)


def _policy_from_payload(payload: Dict[str, Any]) -> PricingV2Policy:
    pricing_summary = payload.get("pricing_summary") if isinstance(payload.get("pricing_summary"), dict) else {}
    return PricingV2Policy(
        minimum_profit_required=_safe_float(payload.get("minimum_profit_required") or pricing_summary.get("minimum_profit_required") or 30000.0, 30000.0),
        minimum_margin_percent=_safe_float(payload.get("minimum_margin_percent") or payload.get("margin_percent") or pricing_summary.get("minimum_margin_percent") or 25.0, 25.0),
        max_margin_percent_single_line=_safe_float(payload.get("max_margin_percent_single_line") or 45.0, 45.0),
        max_margin_percent_multi_line=_safe_float(payload.get("max_margin_percent_multi_line") or 55.0, 55.0),
        max_markup_percent_single_line=_safe_float(payload.get("max_markup_percent_single_line") or 80.0, 80.0),
        max_markup_percent_multi_line=_safe_float(payload.get("max_markup_percent_multi_line") or 120.0, 120.0),
        vat_rate=_safe_float(payload.get("vat_rate") or 15.0, 15.0),
    )


def _get_lines(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_lines = (
        payload.get("line_items")
        or payload.get("items")
        or payload.get("buyer_schedule")
        or payload.get("buyer_pricing_schedule")
        or payload.get("pricing_schedule_items")
        or []
    )

    lines: List[Dict[str, Any]] = []
    for idx, raw in enumerate(_safe_list(raw_lines), start=1):
        if not isinstance(raw, dict):
            continue

        qty = _safe_float(raw.get("quantity") or raw.get("qty") or 1.0, 1.0)
        qty = qty if qty > 0 else 1.0

        description = _safe_str(raw.get("description") or raw.get("item_description") or raw.get("title"), "Supply item")
        unit = _safe_str(raw.get("unit") or raw.get("uom") or raw.get("unit_of_measure"), "Each")

        unit_cost = _safe_float(
            raw.get("supplier_unit_cost")
            or raw.get("landed_unit_cost")
            or raw.get("unit_cost")
            or raw.get("cost")
            or raw.get("supplier_price")
            or 0.0,
            0.0,
        )

        if unit_cost <= 0:
            existing_unit_price = _safe_float(raw.get("unit_price") or raw.get("rate_excl_vat") or raw.get("selling_unit_price_excl_vat"), 0.0)
            if existing_unit_price > 0:
                # Existing price becomes market estimate; reverse conservative margin.
                unit_cost = existing_unit_price / 1.25

        lines.append(
            {
                "line_number": str(raw.get("line_number") or raw.get("line_no") or raw.get("row_no") or idx),
                "item_code": _safe_str(raw.get("item_code") or raw.get("schedule_item_code")),
                "description": description,
                "unit": unit,
                "quantity": qty,
                "unit_cost": _money(unit_cost),
                "quote_reference": _safe_str(raw.get("quote_reference")),
            }
        )

    if not lines:
        estimated_cost = _safe_float(payload.get("estimated_cost"), 0.0)
        estimated_revenue = _safe_float(payload.get("estimated_revenue") or payload.get("quotation_total") or payload.get("grand_total"), 0.0)
        if estimated_cost <= 0 and estimated_revenue > 0:
            estimated_cost = estimated_revenue / 1.25

        lines.append(
            {
                "line_number": "1",
                "item_code": "",
                "description": _safe_str(payload.get("title") or payload.get("description"), "Supply item"),
                "unit": "Each",
                "quantity": 1.0,
                "unit_cost": _money(estimated_cost),
                "quote_reference": "",
            }
        )

    return lines


def _cap_price(unit_cost: float, requested_price: float, is_single_line: bool, policy: PricingV2Policy) -> Tuple[float, Dict[str, Any]]:
    if unit_cost <= 0:
        return 0.0, {
            "pricing_quality": "manual_review_required",
            "manual_review_reason": "Missing supplier or market unit cost.",
            "capped": True,
        }

    min_margin_rate = max(policy.minimum_margin_percent / 100.0, 0.0)
    max_margin_rate = (policy.max_margin_percent_single_line if is_single_line else policy.max_margin_percent_multi_line) / 100.0
    max_markup_rate = (policy.max_markup_percent_single_line if is_single_line else policy.max_markup_percent_multi_line) / 100.0

    min_price = unit_cost / max(1.0 - min_margin_rate, 0.01)
    max_margin_price = unit_cost / max(1.0 - max_margin_rate, 0.01)
    max_markup_price = unit_cost * (1.0 + max_markup_rate)
    cap = min(max_margin_price, max_markup_price)

    final_price = min(max(requested_price, min_price), cap)
    capped = requested_price > cap

    return _money(final_price), {
        "pricing_quality": "capped_realistic" if capped else "target_met",
        "requested_price": _money(requested_price),
        "minimum_margin_price": _money(min_price),
        "realistic_cap_price": _money(cap),
        "max_margin_price": _money(max_margin_price),
        "max_markup_price": _money(max_markup_price),
        "capped": capped,
    }


def apply_realistic_pricing_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    policy = _policy_from_payload(payload)
    lines = _get_lines(payload)
    is_single_line = len(lines) == 1

    total_cost = sum(line["unit_cost"] * line["quantity"] for line in lines)
    if total_cost <= 0:
        payload["pricing_engine_status"] = "manual_review_required"
        payload["pricing_engine_version"] = "PRICING_V2_REALISTIC_MARGIN"
        payload["quote_ready"] = False
        payload["eligible"] = False
        payload["submission_status"] = "manual_review_required"
        payload["submission_message"] = "Pricing V2 blocked auto-submission because supplier or market cost is missing."
        payload["pricing_summary"] = {
            "currency": "ZAR",
            "line_count": len(lines),
            "total_cost_excl_vat": 0.0,
            "total_sell_excl_vat": 0.0,
            "total_vat": 0.0,
            "total_sell_incl_vat": 0.0,
            "total_profit": 0.0,
            "achieved_margin_percent": 0.0,
            "minimum_margin_percent": policy.minimum_margin_percent,
            "minimum_profit_required": policy.minimum_profit_required,
            "pricing_quality": "manual_review_required",
            "manual_review_required": True,
            "manual_review_reasons": ["Missing supplier or market cost."],
            "engine_version": "PRICING_V2_REALISTIC_MARGIN",
            "priced_at": _now(),
        }
        return payload

    target_profit = max(policy.minimum_profit_required, total_cost * (policy.minimum_margin_percent / 100.0))
    priced_lines: List[Dict[str, Any]] = []
    total_sell = 0.0
    total_profit = 0.0
    any_capped = False

    for idx, line in enumerate(lines, start=1):
        qty = line["quantity"]
        line_cost_total = line["unit_cost"] * qty
        weight = line_cost_total / total_cost if total_cost else 0.0
        target_profit_for_line = target_profit * weight
        target_profit_per_unit = target_profit_for_line / max(qty, 1.0)
        requested_unit_price = line["unit_cost"] + target_profit_per_unit

        unit_price, notes = _cap_price(
            unit_cost=line["unit_cost"],
            requested_price=requested_unit_price,
            is_single_line=is_single_line,
            policy=policy,
        )

        if notes.get("capped"):
            any_capped = True

        line_total = unit_price * qty
        line_profit = line_total - line_cost_total
        vat_amount = line_total * (policy.vat_rate / 100.0)

        total_sell += line_total
        total_profit += line_profit

        priced_lines.append(
            {
                "line_number": line["line_number"],
                "item_code": line["item_code"],
                "description": line["description"],
                "unit": line["unit"],
                "quantity": qty,
                "supplier_unit_cost": _money(line["unit_cost"]),
                "landed_unit_cost": _money(line["unit_cost"]),
                "unit_price": _money(unit_price),
                "selling_unit_price_excl_vat": _money(unit_price),
                "line_total": _money(line_total),
                "line_total_excl_vat": _money(line_total),
                "vat_amount": _money(vat_amount),
                "amount_incl_vat": _money(line_total + vat_amount),
                "line_profit": _money(line_profit),
                "margin_percent": round((line_profit / line_total * 100.0) if line_total > 0 else 0.0, 2),
                "markup_percent": round(((unit_price - line["unit_cost"]) / line["unit_cost"] * 100.0) if line["unit_cost"] > 0 else 0.0, 2),
                "source": "pricing_v2_realistic_margin",
                "quote_reference": line["quote_reference"],
                "pricing_notes": notes,
            }
        )

    vat_total = total_sell * (policy.vat_rate / 100.0)
    achieved_margin = (total_profit / total_sell * 100.0) if total_sell > 0 else 0.0
    profit_gap = max(policy.minimum_profit_required - total_profit, 0.0)
    profit_target_met = profit_gap <= 0.01

    manual_review_required = bool(any_capped and not profit_target_met)
    pricing_quality = "manual_review_profit_gap" if manual_review_required else ("capped_but_target_met" if any_capped else "target_met")

    buyer_schedule = []
    for idx, line in enumerate(priced_lines, start=1):
        buyer_schedule.append(
            {
                "row_no": idx,
                "item_code": line["item_code"],
                "description": line["description"],
                "quantity": line["quantity"],
                "unit": line["unit"],
                "rate_excl_vat": line["unit_price"],
                "amount_excl_vat": line["line_total_excl_vat"],
                "vat_amount": line["vat_amount"],
                "amount_incl_vat": line["amount_incl_vat"],
                "source": line["source"],
                "quote_reference": line["quote_reference"],
            }
        )

    manual_reasons = []
    if manual_review_required:
        manual_reasons.append(
            f"R{policy.minimum_profit_required:,.2f} profit target would create unrealistic pricing. Achievable capped profit: R{_money(total_profit):,.2f}."
        )

    pricing_summary = {
        "currency": "ZAR",
        "line_count": len(priced_lines),
        "total_cost_excl_vat": _money(total_cost),
        "total_sell_excl_vat": _money(total_sell),
        "total_vat": _money(vat_total),
        "total_sell_incl_vat": _money(total_sell + vat_total),
        "total_profit": _money(total_profit),
        "achieved_margin_percent": round(achieved_margin, 2),
        "minimum_margin_percent": policy.minimum_margin_percent,
        "minimum_profit_required": policy.minimum_profit_required,
        "profit_target_met": profit_target_met,
        "profit_gap": _money(profit_gap),
        "pricing_quality": pricing_quality,
        "manual_review_required": manual_review_required,
        "manual_review_reasons": manual_reasons,
        "max_margin_percent_applied": policy.max_margin_percent_single_line if is_single_line else policy.max_margin_percent_multi_line,
        "max_markup_percent_applied": policy.max_markup_percent_single_line if is_single_line else policy.max_markup_percent_multi_line,
        "engine_version": "PRICING_V2_REALISTIC_MARGIN",
        "priced_at": _now(),
    }

    payload["items"] = priced_lines
    payload["line_items"] = priced_lines
    payload["buyer_schedule"] = buyer_schedule
    payload["buyer_pricing_schedule"] = buyer_schedule
    payload["pricing_schedule_items"] = buyer_schedule
    payload["pricing_summary"] = pricing_summary
    payload["totals"] = {
        "subtotal_excl_vat": pricing_summary["total_sell_excl_vat"],
        "vat_amount": pricing_summary["total_vat"],
        "total_incl_vat": pricing_summary["total_sell_incl_vat"],
    }
    payload["subtotal"] = pricing_summary["total_sell_excl_vat"]
    payload["vat_amount"] = pricing_summary["total_vat"]
    payload["grand_total"] = pricing_summary["total_sell_incl_vat"]
    payload["quotation_total"] = pricing_summary["total_sell_incl_vat"]
    payload["pricing_engine_status"] = "manual_review_required" if manual_review_required else "ok"
    payload["pricing_engine_version"] = "PRICING_V2_REALISTIC_MARGIN"
    payload["quote_ready"] = not manual_review_required
    payload["eligible"] = bool(payload.get("eligible", True)) and not manual_review_required

    if manual_review_required:
        payload["submission_status"] = "manual_review_required"
        payload["submission_message"] = "Pricing V2 blocked auto-submission because required profit target would create unrealistic pricing."

    return payload


def price_payload_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    return apply_realistic_pricing_v2(payload)
