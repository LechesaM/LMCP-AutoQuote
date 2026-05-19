from __future__ import annotations

from typing import Any, Dict, List


SUPPLIER_DOMAIN_HINTS = {
    "household_products": "FMCG wholesalers",
    "consumables": "FMCG/general wholesalers",
    "equipment_supply": "industrial/equipment suppliers",
    "building_materials": "hardware/building suppliers",
    "technical_fabrication": "fabrication specialists",
    "ppe": "PPE suppliers",
}


def assess_supplier_match(
    rfq_record_or_dict: Dict[str, Any],
    *,
    classification: Dict[str, Any],
    language_intelligence: Dict[str, Any],
    submission_method: Dict[str, Any],
) -> Dict[str, Any]:
    payload = dict(rfq_record_or_dict or {})
    category = str(classification.get("category") or "unknown")
    supplier_domain = SUPPLIER_DOMAIN_HINTS.get(category, "general supplier network")
    base_score = 55.0
    risks: List[str] = []
    recommendations: List[str] = []

    if classification.get("confidence", 0.0) >= 0.85:
        base_score += 15.0
    if category in {"household_products", "consumables"}:
        base_score += 20.0
    elif category == "equipment_supply":
        base_score += 15.0
    elif category == "building_materials":
        base_score += 10.0
    elif category == "technical_fabrication":
        base_score -= 10.0
        risks.append("specialization required")
        recommendations.append("source fabrication-capable suppliers")

    if "sample_requirement" in language_intelligence.get("risk_flags", []):
        base_score -= 15.0
        risks.append("sample evidence required")
    if "oem_accreditation_requirement" in language_intelligence.get("risk_flags", []):
        base_score -= 10.0
        risks.append("OEM accreditation required")
    if "local_content_requirement" in language_intelligence.get("risk_flags", []):
        base_score += 5.0
        recommendations.append("prioritize local suppliers")
    if "physical_submission_requirement" in language_intelligence.get("risk_flags", []):
        base_score -= 5.0
        risks.append("manual submission logistics")

    method = str(submission_method.get("method") or "unknown")
    if method == "email":
        base_score += 5.0
    elif method == "portal":
        base_score += 0.0
        risks.append("portal handling required")
    elif method in {"physical_delivery", "courier_hand_delivery"}:
        base_score -= 10.0
        risks.append("delivery complexity")
    else:
        base_score -= 5.0
        risks.append("submission ambiguity")

    if category == "equipment_supply" and "pump" in str(payload.get("title") or payload.get("description") or "").lower():
        base_score += 5.0
        recommendations.append("validate industrial pump compatibility")
    if category == "technical_fabrication":
        risks.append("specialized fabrication capacity")
    if category == "building_materials":
        recommendations.append("compare hardware and builder supply channels")
    if category == "household_products":
        recommendations.append("compare FMCG wholesale pricing")

    supplier_match_score = round(max(0.0, min(100.0, base_score)), 2)
    if supplier_match_score >= 75:
        recommendation = "supplier domain suitable"
    elif supplier_match_score >= 55:
        recommendation = "supplier domain plausible"
    else:
        recommendation = "supplier domain weak"

    return {
        "supplier_match_score": supplier_match_score,
        "supplier_domain": supplier_domain,
        "supplier_risks": list(dict.fromkeys(risks)),
        "supplier_recommendations": list(dict.fromkeys(recommendations)),
        "supplier_domain_confidence": round(min(0.99, 0.5 + classification.get("confidence", 0.0) * 0.4), 2),
        "stock_availability_risk": "low" if category in {"consumables", "household_products"} else "medium" if category in {"equipment_supply", "building_materials"} else "high",
        "delivery_feasibility": "high" if method == "email" else "medium" if method == "portal" else "low",
        "logistics_complexity": "low" if method == "email" else "medium" if method == "portal" else "high",
        "specialization_requirement": category == "technical_fabrication" or "oem_accreditation_requirement" in language_intelligence.get("risk_flags", []),
        "local_supplier_advantage": bool("local_content_requirement" in language_intelligence.get("risk_flags", [])),
        "supplier_evidence_required": bool(risks),
        "supplier_recommendation": recommendation,
    }
