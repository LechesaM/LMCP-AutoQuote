from __future__ import annotations

from typing import Any, Dict


DOMAIN_MAP = {
    "household_products": "FMCG wholesalers",
    "consumables": "FMCG/general wholesalers",
    "equipment_supply": "industrial/equipment suppliers",
    "building_materials": "hardware/building suppliers",
    "technical_fabrication": "fabrication specialists",
    "ppe": "PPE suppliers",
    "fuel_diesel": "excluded supplier domain",
    "catering": "excluded supplier domain",
    "it_equipment": "excluded supplier domain",
}


def map_supplier_domain(category: str | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(category, dict):
        key = str(category.get("category") or category.get("classification", {}).get("category") or "").strip()
    else:
        key = str(category or "").strip()
    domain = DOMAIN_MAP.get(key, "general supplier network")
    excluded = domain == "excluded supplier domain"
    return {
        "category": key or "unknown",
        "supplier_domain": domain,
        "excluded_domain": excluded,
        "notes": "advisory mapping only",
    }
