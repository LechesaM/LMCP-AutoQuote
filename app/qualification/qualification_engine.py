from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


SUPPLIER_DOMAIN_MAP = {
    "household_products": "FMCG wholesalers",
    "equipment_supply": "industrial/equipment suppliers",
    "technical_fabrication": "fabrication specialists",
    "building_materials": "hardware/building suppliers",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _infer_submission_method(text: str) -> str:
    lower = _clean(text).lower()
    if "portal" in lower or "online submission" in lower or "e-tender" in lower:
        return "portal"
    if "hand delivery" in lower or "tender box" in lower:
        return "physical_delivery"
    if "courier" in lower:
        return "courier_hand_delivery"
    if "email" in lower or "e-mail" in lower:
        return "email"
    return "unknown"


def _normalize_category(category: str) -> str:
    text = _clean(category).lower().replace("&", " and ")
    mapping = {
        "catering": "catering",
        "it equipment": "it_equipment",
        "ict equipment": "it_equipment",
        "fuel": "fuel_diesel",
        "diesel": "fuel_diesel",
        "medical consumables": "medical_consumables",
        "medical supplies": "medical_consumables",
        "household products": "household_products",
        "household_product": "household_products",
        "building materials": "building_materials",
        "technical fabrication": "technical_fabrication",
        "equipment supply": "equipment_supply",
        "supply and delivery": "supply_and_delivery",
        "consumables": "consumables",
    }
    return mapping.get(text, text.replace(" ", "_"))


def _supplier_domain(category: str) -> str:
    return SUPPLIER_DOMAIN_MAP.get(category, "general suppliers")


def _compliance_matrix(text: str) -> Dict[str, Any]:
    lower = _clean(text).lower()
    items = []
    checks = [
        ("SBD4", ["sbd4", "sbd 4"]),
        ("SBD6.1", ["sbd6.1", "sbd 6.1", "sbd6 1"]),
        ("CSD", ["csd"]),
        ("BBBEE", ["bbbee", "bee"]),
        ("Pricing schedule", ["pricing schedule", "price schedule"]),
        ("Quotation on company letterhead", ["quotation on company letterhead", "company letterhead"]),
    ]
    for name, markers in checks:
        detected = any(marker in lower for marker in markers)
        items.append({"item": name, "detected": detected})
    return {"items": items}


def _recommendation(result: Dict[str, Any]) -> str:
    if result.get("rejected") or result.get("qualification_status") == "rejected":
        return "REJECT"
    if result.get("review_required"):
        return "MANUAL_REVIEW"
    if result.get("briefing_compulsory"):
        return "MANUAL_REVIEW"
    return "GO"


def _build_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    text = " ".join(
        [
            _clean(payload.get("title")),
            _clean(payload.get("description") or payload.get("extracted_text")),
            _clean(payload.get("category")),
            _clean(payload.get("submission_instructions")),
        ]
    )
    if not payload.get("submission_method"):
        payload["submission_method"] = _infer_submission_method(text)
    if not payload.get("estimated_contract_value") and payload.get("estimated_profit") is not None:
        payload["estimated_contract_value"] = round(_safe_float(payload.get("estimated_profit")) / 0.25, 2)

    category = _normalize_category(payload.get("category") or "")
    lower = text.lower()
    briefing_compulsory = "briefing" in lower and any(marker in lower for marker in ["compulsory", "mandatory", "required"])
    excluded_catering = "catering" in lower or category == "catering"
    excluded_medical = any(marker in lower for marker in ["medical consumables", "medical supplies", "pharmaceutical", "medicine", "clinical", "surgical"])
    excluded_it = any(marker in lower for marker in ["it equipment", "ict equipment", "laptop", "printer", "server", "network equipment", "software", "software license"])
    excluded_fuel = any(marker in lower for marker in ["fuel", "diesel", "petrol", "lubricant", "lubricants"])
    excluded_other = any(marker in lower for marker in ["construction", "civil works", "road works", "building works", "professional services", "consulting services"])
    excluded_by_business_rules = any([excluded_medical, excluded_it, excluded_fuel, excluded_other, excluded_catering])
    submission_method = _clean(payload.get("submission_method")).lower().replace(" ", "_") or _infer_submission_method(text)
    has_valid_submission_method = submission_method in {"email", "portal", "physical_delivery", "courier_hand_delivery"}
    is_supply_delivery = any(marker in lower for marker in ["supply", "delivery", "goods", "materials", "consumables", "stationery", "ppe"]) or category in {
        "household_products",
        "equipment_supply",
        "technical_fabrication",
        "building_materials",
        "consumables",
        "supply_and_delivery",
    }
    profit_value = _safe_float(payload.get("estimated_profit"), 0.0)
    margin_value = _safe_float(payload.get("gross_margin_ratio"), 0.0)
    profit_gate = profit_value >= 30000.0
    margin_gate = margin_value >= 0.25
    requires_review = category in {"equipment_supply", "technical_fabrication", "building_materials"}
    rejected = any(
        [
            briefing_compulsory,
            excluded_by_business_rules,
            not is_supply_delivery,
            not has_valid_submission_method,
            not profit_gate,
            not margin_gate,
        ]
    )
    if rejected:
        recommendation = "REJECT"
        qualification_status = "rejected"
    elif requires_review:
        recommendation = "MANUAL_REVIEW"
        qualification_status = "review_required"
    else:
        recommendation = "GO"
        qualification_status = "qualified"

    reasons: List[str] = []
    rejection_reasons: List[str] = []
    review_reasons: List[str] = []
    risk_flags: List[str] = []
    if is_supply_delivery:
        reasons.append("Supply and delivery opportunity detected")
    if has_valid_submission_method:
        reasons.append(f"Submission method: {submission_method}")
    if profit_gate:
        reasons.append("Profit threshold passed")
    else:
        rejection_reasons.append("Estimated profit below threshold")
    if margin_gate:
        reasons.append("Margin threshold passed")
    else:
        rejection_reasons.append("Margin threshold below threshold")
    if excluded_medical:
        rejection_reasons.append("Medical consumables tender excluded")
    if excluded_it:
        rejection_reasons.append("IT equipment tender excluded")
    if excluded_fuel:
        rejection_reasons.append("Petrol, diesel, or fuel tender excluded")
    if excluded_catering:
        rejection_reasons.append("Catering tender excluded")
    if excluded_other:
        rejection_reasons.append("Non-supply or execution-based scope excluded")
    if briefing_compulsory:
        rejection_reasons.append("Compulsory briefing or site meeting detected")
    if requires_review:
        review_reasons.append("Manual review recommended for supplier qualification")
    if not has_valid_submission_method:
        rejection_reasons.append("No valid submission route identified")
    if not is_supply_delivery:
        rejection_reasons.append("Tender is not clearly supply and delivery")
    return {
        "qualification_status": qualification_status,
        "qualified": recommendation == "GO",
        "review_required": recommendation == "MANUAL_REVIEW",
        "rejected": recommendation == "REJECT",
        "is_supply_delivery": is_supply_delivery,
        "province_ok": bool(_clean(payload.get("province"))),
        "has_valid_submission_method": has_valid_submission_method,
        "has_briefing_session": "briefing" in lower,
        "briefing_compulsory": briefing_compulsory,
        "excluded_medical": excluded_medical,
        "excluded_it": excluded_it,
        "excluded_fuel": excluded_fuel,
        "excluded_catering": excluded_catering,
        "excluded_other": excluded_other,
        "excluded_by_business_rules": excluded_by_business_rules,
        "estimated_contract_value": _safe_float(payload.get("estimated_contract_value"), 0.0) or None,
        "assumed_margin_percent": 25.0,
        "estimated_profit_value": profit_value or None,
        "meets_profit_threshold": profit_gate,
        "score_total": 90.0 if recommendation == "GO" else 65.0 if recommendation == "MANUAL_REVIEW" else 25.0,
        "auto_quote_recommended": recommendation == "GO",
        "category": category,
        "recommendation": recommendation,
        "quote_candidate": recommendation == "GO",
        "manual_review_required": recommendation == "MANUAL_REVIEW",
        "supplier_domain": {"supplier_domain": _supplier_domain(category)},
        "classification": {
            "manual_review_required": recommendation == "MANUAL_REVIEW",
            "excluded_category": excluded_by_business_rules,
        },
        "viability": {
            "profit_gate": profit_gate,
            "margin_gate": margin_gate,
        },
        "submission_method": {
            "method": _infer_submission_method(text) if payload.get("submission_method") in {None, "", "unknown"} else _clean(payload.get("submission_method")).lower().replace(" ", "_"),
            "automation_candidate": _clean(payload.get("submission_method")).lower() == "email" or _infer_submission_method(text) == "email",
        },
        "compliance_matrix": _compliance_matrix(text),
        "warnings": list(payload.get("warnings") or []),
        "reasons": reasons,
        "rejection_reasons": rejection_reasons,
        "review_reasons": review_reasons,
        "risk_flags": risk_flags,
        "exclusion_reason": "excluded_category" if excluded_by_business_rules else "",
        "commodity_class": category or "unknown",
        "province": _clean(payload.get("province")),
        "days_to_deadline": None,
    }


def qualify_rfq(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _build_result(payload)


def qualify_text(text: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(overrides or {})
    payload.setdefault("title", text)
    payload.setdefault("description", text)
    payload.setdefault("extracted_text", text)
    if "submission_method" not in payload:
        payload["submission_method"] = _infer_submission_method(text)
    return _build_result(payload)


def qualify_fixture(path: Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return _build_result(payload)


def build_qualification_summary(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    recommendation_counts: Dict[str, int] = {}
    risk_level_counts: Dict[str, int] = {}
    for record in records:
        recommendation = _clean(record.get("recommendation") or record.get("qualification_status") or "UNKNOWN").upper()
        recommendation_counts[recommendation] = recommendation_counts.get(recommendation, 0) + 1
        risk_level = _clean(record.get("risk_level") or "unknown").lower()
        risk_level_counts[risk_level] = risk_level_counts.get(risk_level, 0) + 1
    return {
        "recommendation_counts": recommendation_counts,
        "risk_level_counts": risk_level_counts,
        "total": sum(recommendation_counts.values()),
    }
