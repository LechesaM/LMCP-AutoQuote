from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.supply_target_config import (
    SUPPLY_DEFAULT_TAX_RATE,
    SUPPLY_MIN_PROFIT_PER_WIN,
    SUPPLY_REJECT_IF_BELOW_MIN_PROFIT,
)
from app.services.supplier_engine import choose_best_supplier, find_supplier_options


EXCLUDED_PRICING_CATEGORIES = {
    "medical_consumables",
    "it_equipment",
    "petrol_diesel_supply",
}


PROVINCE_DELIVERY_BASE = {
    "free state": 3500.0,
    "gauteng": 4500.0,
    "northern cape": 12000.0,
    "eastern cape": 9000.0,
    "western cape": 11000.0,
    "kwazulu-natal": 8500.0,
    "limpopo": 8000.0,
    "mpumalanga": 7000.0,
    "north west": 6500.0,
}


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _extract_quantity_hint(quantities: List[Dict[str, Any]]) -> int:
    if not quantities:
        return 1

    normalized_values = []

    for item in quantities:
        if isinstance(item, dict):
            try:
                normalized_values.append(int(item.get("quantity", 1)))
            except Exception:
                normalized_values.append(1)
        elif isinstance(item, (int, float)):
            normalized_values.append(int(item))
        else:
            normalized_values.append(1)

    return max(normalized_values) if normalized_values else 1


def estimate_delivery_cost(
    delivery_location: Optional[str],
    category: str,
    quantity_hint: int = 1,
) -> float:
    location = _normalize(delivery_location)

    base = 6000.0
    for province, price in PROVINCE_DELIVERY_BASE.items():
        if province in location:
            base = price
            break

    category_multiplier = {
        "ppe": 0.7,
        "stationery_office": 0.8,
        "cleaning_hygiene": 0.9,
        "electrical": 1.1,
        "plumbing_water": 1.2,
        "building_materials": 1.3,
        "fleet_spares_tyres_lubricants": 1.15,
        "furniture": 1.2,
        "agriculture_inputs": 1.1,
        "safety_security_general": 1.0,
        "water_treatment_chemicals": 1.1,
        "general_supply": 1.0,
    }.get(category, 1.0)

    quantity_factor = 1.0
    if quantity_hint > 10000:
        quantity_factor = 1.6
    elif quantity_hint > 5000:
        quantity_factor = 1.45
    elif quantity_hint > 1000:
        quantity_factor = 1.3
    elif quantity_hint > 500:
        quantity_factor = 1.2
    elif quantity_hint > 100:
        quantity_factor = 1.1

    return round(base * category_multiplier * quantity_factor, 2)


def determine_margin_percent(estimated_value: float) -> float:
    if estimated_value < 50_000:
        return 65.0
    if estimated_value < 100_000:
        return 48.0
    if estimated_value < 250_000:
        return 35.0
    if estimated_value < 500_000:
        return 28.0
    if estimated_value < 1_000_000:
        return 24.0
    if estimated_value < 2_000_000:
        return 20.0
    if estimated_value < 10_000_000:
        return 16.0
    return 12.0


def _reject_quote(
    classification: Dict[str, Any],
    reason: str,
) -> Dict[str, Any]:
    return {
        "rfq_id": classification.get("rfq_id"),
        "can_quote": False,
        "recommended_submit": False,
        "profit_floor_passed": False,
        "profit_floor_minimum": SUPPLY_MIN_PROFIT_PER_WIN,
        "rejection_reason": reason,
        "category": classification.get("category", "general_supply"),
        "delivery_location": classification.get("delivery_location"),
        "quantity_hint": 0,
        "selected_supplier": None,
        "alternative_suppliers": alternative_suppliers,        
        "line_items": line_items,        
        "cost_breakdown": {
            "material_cost": 0.0,
            "delivery_cost": 0.0,
            "estimated_cost_excl_vat": 0.0,
            "margin_percent": 0.0,
            "gross_profit": 0.0,
            "quote_total_excl_vat": 0.0,
            "vat_amount": 0.0,
            "quote_total_incl_vat": 0.0,
        },
    }


def build_supply_quote(classification: Dict[str, Any]) -> Dict[str, Any]:
    category = classification.get("category", "general_supply")
    delivery_location = classification.get("delivery_location")
    quantities: List[Dict[str, Any]] = classification.get("quantities", []) or []
    quantity_hint = _extract_quantity_hint(quantities)


    line_items = []

    for i, item in enumerate(quantities, start=1):
        if isinstance(item, dict):
            description = item.get("description") or f"Supply Item {i}"
            try:
                qty = int(item.get("quantity", 1))
            except Exception:
                qty = 1
        elif isinstance(item, (int, float)):
            description = f"Supply Item {i}"
            qty = int(item)
        else:
            description = f"Supply Item {i}"
            qty = 1

        line_items.append({
            "line_number": i,
            "description": description,
            "quantity": qty,
            "unit_price": 0.0,
            "total": 0.0,
        })


    if classification.get("excluded_category") in EXCLUDED_PRICING_CATEGORIES:
        return _reject_quote(
            classification,
            f"RFQ category '{classification.get('excluded_category')}' is excluded from quoting.",
        )

    if classification.get("is_construction"):
        return _reject_quote(
            classification,
            "RFQ includes construction / works / installation / maintenance scope and is excluded from quoting.",
        )

    if not classification.get("supply_only"):
        return _reject_quote(
            classification,
            "RFQ is not classified as pure supply-and-delivery.",
        )

    if classification.get("has_compulsory_briefing"):
        return _reject_quote(
            classification,
            "RFQ includes a compulsory or mandatory briefing/site meeting.",
        )

    if category in EXCLUDED_PRICING_CATEGORIES:
        return _reject_quote(
            classification,
            f"Detected category '{category}' is excluded from quoting.",
        )

    best_supplier = choose_best_supplier(
        category=category,
        delivery_location=delivery_location,
        min_stock=1,
    )

    alternative_suppliers = find_supplier_options(
        category=category,
        delivery_location=delivery_location,
        min_stock=1,
    )[:5]

    if not best_supplier:
        return _reject_quote(
            classification,
            f"No suitable supplier found for detected category '{category}'.",
        )

    unit_price = float(best_supplier["unit_price"])
    material_cost = unit_price * max(quantity_hint, 1)
    
    for line in line_items:
        line["unit_price"] = round(unit_price, 2)
        line["total"] = round(line["quantity"] * unit_price, 2)

    delivery_cost = estimate_delivery_cost(
        delivery_location=delivery_location,
        category=category,
        quantity_hint=quantity_hint,
    )

    estimated_cost_excl_vat = material_cost + delivery_cost
    margin_percent = determine_margin_percent(estimated_cost_excl_vat)
    gross_profit = estimated_cost_excl_vat * (margin_percent / 100.0)
    quote_total_excl_vat = estimated_cost_excl_vat + gross_profit

    vat_amount = quote_total_excl_vat * SUPPLY_DEFAULT_TAX_RATE
    quote_total_incl_vat = quote_total_excl_vat + vat_amount

    profit_floor_passed = gross_profit >= SUPPLY_MIN_PROFIT_PER_WIN
    recommended_submit = True
    rejection_reason = ""

    if SUPPLY_REJECT_IF_BELOW_MIN_PROFIT and not profit_floor_passed:
        recommended_submit = False
        rejection_reason = (
            f"Estimated gross profit of R{gross_profit:,.2f} is below minimum floor "
            f"of R{SUPPLY_MIN_PROFIT_PER_WIN:,.2f}."
        )

    return {
        "rfq_id": classification.get("rfq_id"),
        "can_quote": True,
        "recommended_submit": recommended_submit,
        "profit_floor_passed": profit_floor_passed,
        "profit_floor_minimum": SUPPLY_MIN_PROFIT_PER_WIN,
        "rejection_reason": rejection_reason,
        "category": category,
        "delivery_location": delivery_location,
        "quantity_hint": quantity_hint,
        "selected_supplier": best_supplier,
        "alternative_suppliers": alternative_suppliers,
        "line_items": line_items,        
        "cost_breakdown": {
            "material_cost": round(material_cost, 2),
            "delivery_cost": round(delivery_cost, 2),
            "estimated_cost_excl_vat": round(estimated_cost_excl_vat, 2),
            "margin_percent": round(margin_percent, 2),
            "gross_profit": round(gross_profit, 2),
            "quote_total_excl_vat": round(quote_total_excl_vat, 2),
            "vat_amount": round(vat_amount, 2),
            "quote_total_incl_vat": round(quote_total_incl_vat, 2),
        },
    }
