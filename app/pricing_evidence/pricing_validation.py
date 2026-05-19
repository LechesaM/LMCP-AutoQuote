from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        if isinstance(value, str):
            value = value.replace("R", "").replace(",", "").strip()
        return float(value)
    except Exception:
        return float(default)


def _line_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("lines") or payload.get("line_items") or payload.get("quoted_items") or []
    return [item for item in items if isinstance(item, dict)]


def _line_amounts(line: Dict[str, Any]) -> Tuple[float, float, float, float, float]:
    quantity = _safe_float(line.get("quantity") or line.get("qty"), 0.0)
    unit_price = _safe_float(line.get("unit_price") or line.get("price") or line.get("unit_cost"), 0.0)
    delivery_cost = _safe_float(line.get("delivery_cost") or line.get("delivery"), 0.0)
    vat_amount = _safe_float(line.get("vat_amount") or line.get("vat"), 0.0)
    line_total = _safe_float(
        line.get("line_total") or line.get("total") or line.get("amount"),
        (quantity * unit_price) + delivery_cost + vat_amount,
    )
    return quantity, unit_price, delivery_cost, vat_amount, line_total


def validate_pricing_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    lines = _line_items(data)
    validation_warnings: List[str] = []
    validation_errors: List[str] = []
    manual_review_required = False

    if not lines:
        validation_warnings.append("price structure missing")
        manual_review_required = True

    computed_subtotal = 0.0
    computed_delivery = 0.0
    computed_vat = 0.0
    computed_total = 0.0
    quantity_mismatches = 0
    for line in lines:
        quantity, unit_price, delivery_cost, vat_amount, line_total = _line_amounts(line)
        line_expected = round((quantity * unit_price) + delivery_cost + vat_amount, 2)
        computed_subtotal += round(quantity * unit_price, 2)
        computed_delivery += round(delivery_cost, 2)
        computed_vat += round(vat_amount, 2)
        computed_total += round(line_total, 2)
        if quantity > 0 and unit_price == 0:
            validation_errors.append("zero price")
        if unit_price < 0 or line_total < 0:
            validation_errors.append("negative price")
        if abs(line_total - line_expected) > 0.05:
            quantity_mismatches += 1

    provided_subtotal = _safe_float(
        data.get("subtotal")
        or data.get("net_total")
        or data.get("total_ex_vat")
        or data.get("ex_vat_total")
        or computed_subtotal,
        computed_subtotal,
    )
    provided_vat_total = _safe_float(data.get("vat_total") or data.get("vat_amount") or computed_vat, computed_vat)
    provided_delivery_total = _safe_float(data.get("delivery_total") or data.get("delivery_cost") or computed_delivery, computed_delivery)
    provided_total = _safe_float(
        data.get("grand_total")
        or data.get("total")
        or data.get("total_incl_vat")
        or data.get("quote_total")
        or (provided_subtotal + provided_vat_total + provided_delivery_total),
        provided_subtotal + provided_vat_total + provided_delivery_total,
    )

    if abs(provided_subtotal - computed_subtotal) > 0.05:
        validation_errors.append("subtotal mismatch")
    if abs(provided_vat_total - computed_vat) > 0.05:
        validation_errors.append("VAT mismatch")
    if abs(provided_delivery_total - computed_delivery) > 0.05 and (provided_delivery_total or computed_delivery):
        validation_warnings.append("delivery inconsistency")
    if abs(provided_total - (provided_subtotal + provided_vat_total + provided_delivery_total)) > 0.05:
        validation_errors.append("subtotal/total mismatch")
    if quantity_mismatches:
        validation_warnings.append("quantity mismatch")
    if provided_total <= 0 and lines:
        validation_errors.append("unrealistic total")
    if data.get("vat_registered") is False and provided_vat_total > 0:
        validation_warnings.append("VAT inconsistency")
    if data.get("delivery_assumptions") and not provided_delivery_total:
        validation_warnings.append("delivery inconsistency")

    if validation_errors:
        manual_review_required = True
    elif any(item in validation_warnings for item in ("delivery inconsistency", "quantity mismatch")):
        manual_review_required = True

    return {
        "validation_passed": not validation_errors,
        "validation_warnings": list(dict.fromkeys(validation_warnings)),
        "validation_errors": list(dict.fromkeys(validation_errors)),
        "manual_review_required": manual_review_required,
        "computed_subtotal": round(computed_subtotal, 2),
        "computed_delivery_total": round(computed_delivery, 2),
        "computed_vat_total": round(computed_vat, 2),
        "computed_total": round(computed_total, 2),
        "provided_subtotal": round(provided_subtotal, 2),
        "provided_delivery_total": round(provided_delivery_total, 2),
        "provided_vat_total": round(provided_vat_total, 2),
        "provided_total": round(provided_total, 2),
        "advisory_only": True,
    }
