from __future__ import annotations

from typing import Any, Dict, List


def _score_from_flags(count: int, base: int = 0, step: int = 10, cap: int = 100) -> int:
    return min(cap, base + count * step)


def assess_rfq_risk(
    rfq_record_or_dict: Dict[str, Any],
    *,
    classification: Dict[str, Any],
    language_intelligence: Dict[str, Any],
    compliance_matrix: Dict[str, Any],
    submission_method: Dict[str, Any],
    opportunity_viability: Dict[str, Any],
    supplier_match: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(rfq_record_or_dict or {})
    language_flags = list(language_intelligence.get("risk_flags", []))
    manual_review_triggers = list(dict.fromkeys(language_intelligence.get("manual_review_triggers", [])))
    disqualification_triggers = list(dict.fromkeys(language_intelligence.get("disqualification_triggers", [])))
    supplier_match = supplier_match or {}

    technical_risk = 15 if classification.get("category") in {"consumables", "household_products"} else 35
    if classification.get("category") == "technical_fabrication":
        technical_risk = 80
        manual_review_triggers.append("technical fabrication")
    if "functionality_scoring" in language_flags or "minimum_functionality_threshold" in language_flags:
        technical_risk = max(technical_risk, 75)
        manual_review_triggers.append("functionality threshold")
    if "oem_accreditation_requirement" in language_flags:
        technical_risk = max(technical_risk, 70)
        manual_review_triggers.append("OEM or accreditation requirement")
    if "sample_requirement" in language_flags:
        technical_risk = max(technical_risk, 65)
        manual_review_triggers.append("sample requirement")

    operational_risk = 20
    if "mandatory_site_inspection" in {item.get("name") for item in language_intelligence.get("detected_patterns", [])}:
        operational_risk = max(operational_risk, 65)
        manual_review_triggers.append("mandatory site inspection")
    if "contract_duration" in {item.get("name") for item in language_intelligence.get("detected_patterns", [])}:
        operational_risk = max(operational_risk, 45)
    if submission_method.get("method") in {"physical_delivery", "courier_hand_delivery"}:
        operational_risk = max(operational_risk, 70)
        manual_review_triggers.append("physical submission")

    pricing_risk = 25
    if not opportunity_viability.get("margin_gate", True):
        pricing_risk = 90
    elif not opportunity_viability.get("profit_gate", True):
        pricing_risk = 85
    elif compliance_matrix.get("missing_required_count", 0):
        pricing_risk = max(pricing_risk, 60)
    if not payload.get("closing_date"):
        pricing_risk = max(pricing_risk, 70)
        manual_review_triggers.append("missing closing date")
    if not payload.get("pricing_schedule_ready", True):
        pricing_risk = max(pricing_risk, 65)
        manual_review_triggers.append("unclear pricing schedule")

    compliance_risk = 20 + int(compliance_matrix.get("missing_required_count", 0)) * 12
    if "cidb_requirement" in language_flags:
        compliance_risk = max(compliance_risk, 45)
        manual_review_triggers.append("CIDB requirement")
    if "local_content_requirement" in language_flags:
        compliance_risk = max(compliance_risk, 40)
        manual_review_triggers.append("local content requirement")
    if "disqualification_clause" in language_flags or "late_submission_clause" in language_flags:
        compliance_risk = max(compliance_risk, 60)

    delivery_risk = 20
    if submission_method.get("method") in {"physical_delivery", "courier_hand_delivery"}:
        delivery_risk = 80
    elif submission_method.get("method") == "portal":
        delivery_risk = 45
    if "delivery_deadline" in language_flags:
        delivery_risk = max(delivery_risk, 60)

    adjudication_risk = 15
    if "functionality_scoring" in language_flags or "minimum_functionality_threshold" in language_flags:
        adjudication_risk = max(adjudication_risk, 75)
        manual_review_triggers.append("functionality threshold")
    if "sample_requirement" in language_flags:
        adjudication_risk = max(adjudication_risk, 55)
    if "disqualification_clause" in language_flags:
        adjudication_risk = max(adjudication_risk, 70)
        disqualification_triggers.append("disqualification clause")

    submission_risk = 20
    if submission_method.get("method") == "email":
        submission_risk = 15
    elif submission_method.get("method") == "portal":
        submission_risk = 40
    elif submission_method.get("method") in {"physical_delivery", "courier_hand_delivery"}:
        submission_risk = 80
        manual_review_triggers.append("physical submission")
    elif submission_method.get("method") == "unknown":
        submission_risk = 65
        manual_review_triggers.append("ambiguous submission method")
    if not submission_method.get("confidence", 0.0) or submission_method.get("method") == "unknown":
        manual_review_triggers.append("ambiguous submission method")

    overall_score = round(
        min(
            100.0,
            (technical_risk * 0.18)
            + (operational_risk * 0.12)
            + (pricing_risk * 0.2)
            + (compliance_risk * 0.2)
            + (delivery_risk * 0.12)
            + (adjudication_risk * 0.1)
            + (submission_risk * 0.08),
        ),
        2,
    )
    if supplier_match:
        overall_score = round(min(100.0, overall_score + max(0.0, 50.0 - float(supplier_match.get("supplier_match_score", 50.0))) * 0.05), 2)

    blocked = bool(classification.get("excluded_category")) or bool(disqualification_triggers)
    if blocked:
        level = "blocked"
    elif overall_score < 30:
        level = "low"
    elif overall_score < 60:
        level = "medium"
    else:
        level = "high"

    if not payload.get("closing_date"):
        manual_review_triggers.append("missing closing date")
    if submission_method.get("method") == "unknown":
        manual_review_triggers.append("ambiguous submission method")

    return {
        "technical_risk": min(100, technical_risk),
        "operational_risk": min(100, operational_risk),
        "pricing_risk": min(100, pricing_risk),
        "compliance_risk": min(100, compliance_risk),
        "delivery_risk": min(100, delivery_risk),
        "adjudication_risk": min(100, adjudication_risk),
        "submission_risk": min(100, submission_risk),
        "overall_risk": overall_score,
        "risk_level": level,
        "manual_review_triggers": list(dict.fromkeys(manual_review_triggers)),
        "disqualification_triggers": list(dict.fromkeys(disqualification_triggers)),
        "risk_flags": list(dict.fromkeys(language_flags)),
    }
