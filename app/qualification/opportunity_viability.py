from __future__ import annotations

from typing import Any, Dict


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def assess_opportunity_viability(
    rfq_record_or_dict: Dict[str, Any],
    classification: Dict[str, Any],
    compliance_matrix: Dict[str, Any],
    submission_method: Dict[str, Any],
    *,
    language_intelligence: Dict[str, Any] | None = None,
    risk_engine: Dict[str, Any] | None = None,
    supplier_match: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(rfq_record_or_dict or {})
    category = str(classification.get("category") or "unknown")
    excluded_category = bool(classification.get("excluded_category"))
    manual_review_required = bool(classification.get("manual_review_required"))
    language_intelligence = language_intelligence or {}
    risk_engine = risk_engine or {}
    supplier_match = supplier_match or {}
    estimated_profit = payload.get("estimated_profit")
    gross_margin_ratio = payload.get("gross_margin_ratio")
    estimated_contract_value = payload.get("estimated_contract_value")

    if estimated_profit in (None, "", 0, 0.0):
        estimated_profit = _to_float(payload.get("profit_amount") or payload.get("profit"), 0.0)
    if gross_margin_ratio in (None, "", 0, 0.0):
        gross_margin_ratio = _to_float(payload.get("gross_margin") or payload.get("margin_ratio"), 0.0)
    if estimated_contract_value in (None, "", 0, 0.0):
        estimated_contract_value = _to_float(payload.get("contract_value") or payload.get("estimated_value"), 0.0)

    profit_gate = _to_float(estimated_profit) >= 30000.0
    margin_gate = _to_float(gross_margin_ratio) >= 0.25
    critical_missing = not payload.get("tender_id") or not payload.get("title") or not payload.get("buyer_name")
    compliance_complexity_score = int(compliance_matrix.get("compliance_complexity_score", 0))
    technical_complexity_score = 85 if category == "technical_fabrication" else 70 if manual_review_required else 35
    if bool(payload.get("technical_validation_required")):
        technical_complexity_score = max(technical_complexity_score, 80)
    if "sample_requirement" in set(language_intelligence.get("risk_flags", [])):
        technical_complexity_score = max(technical_complexity_score, 75)
    if "oem_accreditation_requirement" in set(language_intelligence.get("risk_flags", [])):
        technical_complexity_score = max(technical_complexity_score, 78)
    submission_method_name = str(submission_method.get("method") or "unknown")
    submission_complexity_score = {
        "email": 15,
        "portal": 45,
        "physical_delivery": 85,
        "courier_hand_delivery": 75,
        "unknown": 60,
    }.get(submission_method_name, 60)
    automation_suitability_score = max(
        0.0,
        round(
            100.0
            - float(compliance_complexity_score) * 0.35
            - float(technical_complexity_score) * 0.35
            - float(submission_complexity_score) * 0.2
            - (20.0 if critical_missing else 0.0)
            - (10.0 if risk_engine.get("risk_level") == "high" else 0.0)
            + (5.0 if supplier_match.get("supplier_match_score", 0.0) >= 75 else 0.0),
            2,
        ),
    )

    if excluded_category:
        recommendation = "REJECT"
        risk_level = "high"
    elif not margin_gate or not profit_gate:
        recommendation = "REJECT"
        risk_level = "high"
    elif category == "technical_fabrication" or bool(payload.get("technical_validation_required")):
        recommendation = "MANUAL_REVIEW"
        risk_level = "medium"
    elif critical_missing:
        recommendation = "MANUAL_REVIEW"
        risk_level = "medium"
    elif submission_method_name in {"portal", "physical_delivery", "courier_hand_delivery", "unknown"}:
        recommendation = "MANUAL_REVIEW"
        risk_level = "medium"
    else:
        recommendation = "GO"
        risk_level = "low"

    if compliance_matrix.get("blockers"):
        recommendation = "MANUAL_REVIEW" if recommendation == "GO" else recommendation
        risk_level = "medium" if recommendation != "REJECT" else risk_level

    return {
        "estimated_profit": round(_to_float(estimated_profit), 2),
        "estimated_contract_value": round(_to_float(estimated_contract_value), 2),
        "gross_margin_ratio": round(_to_float(gross_margin_ratio), 4),
        "margin_gate": margin_gate,
        "profit_gate": profit_gate,
        "compliance_complexity_score": compliance_complexity_score,
        "technical_complexity_score": technical_complexity_score,
        "submission_complexity_score": submission_complexity_score,
        "automation_suitability_score": automation_suitability_score,
        "risk_level": risk_level,
        "final_recommendation": recommendation,
        "critical_missing_fields": critical_missing,
        "reason_chain": [
            "excluded category" if excluded_category else "",
            "technical validation required" if bool(payload.get("technical_validation_required")) else "",
            "missing critical fields" if critical_missing else "",
            "pricing gate failed" if (not profit_gate or not margin_gate) else "",
            "supplier match strong" if supplier_match.get("supplier_match_score", 0.0) >= 75 else "",
        ],
    }
