from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.domain.rfq import RFQRecord
from app.qualification.compliance_matrix import build_compliance_matrix
from app.qualification.opportunity_viability import assess_opportunity_viability
from app.qualification.rfq_language_intelligence import analyze_rfq_language
from app.qualification.rfq_risk_engine import assess_rfq_risk
from app.qualification.rfq_classifier import classify_rfq
from app.qualification.submission_readiness import assess_submission_readiness
from app.qualification.submission_method_detector import detect_submission_method
from app.qualification.supplier_match_intelligence import assess_supplier_match
from app.qualification.supplier_domain_mapper import map_supplier_domain
from app.pricing_evidence import (
    assess_pricing_confidence,
    assess_quote_aging,
    build_pricing_traceability,
    build_supplier_quote_evidence,
    validate_pricing_evidence,
)


def _coerce_record(rfq_record_or_dict: Dict[str, Any] | RFQRecord | None) -> Dict[str, Any]:
    if isinstance(rfq_record_or_dict, RFQRecord):
        return rfq_record_or_dict.to_jsonable_dict()
    return dict(rfq_record_or_dict or {})


def _collect_blockers(classification: Dict[str, Any], compliance_matrix: Dict[str, Any], viability: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if classification.get("excluded_category"):
        blockers.append("excluded category")
    if classification.get("manual_review_required") and classification.get("category") == "technical_fabrication":
        blockers.append("technical fabrication requires manual review")
    for blocker in compliance_matrix.get("blockers", []):
        blockers.append(str(blocker))
    if not viability.get("profit_gate", True):
        blockers.append("minimum profit R30,000 not met")
    if not viability.get("margin_gate", True):
        blockers.append("minimum supply margin 25% not met")
    return list(dict.fromkeys(blockers))


def qualify_rfq(rfq_record_or_dict: Dict[str, Any] | RFQRecord | None) -> Dict[str, Any]:
    payload = _coerce_record(rfq_record_or_dict)
    classification = classify_rfq(payload)
    language_intelligence = analyze_rfq_language(payload)
    compliance_matrix = build_compliance_matrix(payload, language_intelligence=language_intelligence)
    submission_method = detect_submission_method(payload, language_intelligence=language_intelligence)
    supplier_domain = map_supplier_domain(classification, language_intelligence=language_intelligence)
    supplier_match = assess_supplier_match(payload, classification=classification, language_intelligence=language_intelligence, submission_method=submission_method)
    pricing_payload = payload.get("pricing_evidence") or payload.get("supplier_quote") or {}
    if not pricing_payload and isinstance(payload.get("supplier_quotes"), list) and payload.get("supplier_quotes"):
        first_quote = payload.get("supplier_quotes")[0]
        pricing_payload = first_quote if isinstance(first_quote, dict) else {}
    pricing_evidence = build_supplier_quote_evidence(pricing_payload) if pricing_payload else {}
    pricing_validation = validate_pricing_evidence(pricing_payload) if pricing_payload else {}
    quote_aging = assess_quote_aging(pricing_payload) if pricing_payload else {}
    pricing_confidence = (
        assess_pricing_confidence(
            pricing_payload,
            evidence_report=pricing_evidence,
            validation_report=pricing_validation,
            quote_aging_report=quote_aging,
            supplier_match=supplier_match,
        )
        if pricing_payload
        else {}
    )
    pricing_traceability = (
        build_pricing_traceability(
            pricing_payload,
            evidence_report=pricing_evidence,
            validation_report=pricing_validation,
            quote_aging_report=quote_aging,
        )
        if pricing_payload
        else {}
    )
    viability = assess_opportunity_viability(
        payload,
        classification,
        compliance_matrix,
        submission_method,
        language_intelligence=language_intelligence,
        supplier_match=supplier_match,
        pricing_evidence=pricing_evidence,
        pricing_validation=pricing_validation,
        quote_aging=quote_aging,
        pricing_confidence=pricing_confidence,
        pricing_traceability=pricing_traceability,
    )
    risk_engine = assess_rfq_risk(
        payload,
        classification=classification,
        language_intelligence=language_intelligence,
        compliance_matrix=compliance_matrix,
        submission_method=submission_method,
        opportunity_viability=viability,
        supplier_match=supplier_match,
    )
    viability = assess_opportunity_viability(
        payload,
        classification,
        compliance_matrix,
        submission_method,
        language_intelligence=language_intelligence,
        risk_engine=risk_engine,
        supplier_match=supplier_match,
        pricing_evidence=pricing_evidence,
        pricing_validation=pricing_validation,
        quote_aging=quote_aging,
        pricing_confidence=pricing_confidence,
        pricing_traceability=pricing_traceability,
    )
    readiness = assess_submission_readiness(
        compliance_matrix=compliance_matrix,
        submission_method=submission_method,
        quote_pack_ready=bool(payload.get("quote_pack_ready", True)),
        pricing_schedule_ready=bool(payload.get("pricing_schedule_ready", True)),
        risk_engine=risk_engine,
        workflow_stage=str(payload.get("workflow_stage") or ""),
    )
    blockers = _collect_blockers(classification, compliance_matrix, viability)
    if readiness.get("blockers"):
        blockers.extend([str(item) for item in readiness.get("blockers", [])])
    blockers = list(dict.fromkeys(blockers))
    warnings: List[str] = []
    if classification.get("manual_review_required"):
        warnings.append("manual review required")
    if submission_method.get("manual_handling_required"):
        warnings.append("manual handling required")
    if compliance_matrix.get("missing_required_count", 0):
        warnings.append("compliance gaps detected")
    if readiness.get("readiness_state") in {"HIGH_RISK", "MANUAL_ONLY", "MISSING_DOCS"}:
        warnings.append(f"readiness {readiness.get('readiness_state').lower()}")
    if viability.get("final_recommendation") == "REJECT":
        warnings.append("qualification rejected")
    if risk_engine.get("manual_review_triggers"):
        warnings.extend([f"risk trigger: {item}" for item in risk_engine.get("manual_review_triggers", [])[:4]])
    if language_intelligence.get("manual_review_triggers"):
        warnings.extend([f"language trigger: {item}" for item in language_intelligence.get("manual_review_triggers", [])[:4]])
    if pricing_validation.get("validation_errors"):
        warnings.extend([f"pricing validation: {item}" for item in pricing_validation.get("validation_errors", [])[:4]])
    if pricing_evidence.get("evidence_warnings"):
        warnings.extend([f"pricing evidence: {item}" for item in pricing_evidence.get("evidence_warnings", [])[:4]])
    if quote_aging.get("stale_pricing_warnings"):
        warnings.extend([f"quote aging: {item}" for item in quote_aging.get("stale_pricing_warnings", [])[:4]])
    recommendation_reasons = []
    recommendation_reasons.extend([str(item) for item in viability.get("reason_chain", []) if item])
    recommendation_reasons.extend([str(item) for item in readiness.get("reason_chain", []) if item])
    recommendation_reasons.extend([str(item) for item in risk_engine.get("manual_review_triggers", [])[:4]])
    recommendation_reasons.extend([str(item) for item in language_intelligence.get("manual_review_triggers", [])[:4]])
    recommendation_reasons.extend([str(item) for item in pricing_validation.get("validation_errors", [])[:4]])
    recommendation_reasons.extend([str(item) for item in pricing_evidence.get("evidence_warnings", [])[:4]])
    recommendation_reasons.extend([str(item) for item in quote_aging.get("stale_pricing_warnings", [])[:4]])
    recommendation_reasons = list(dict.fromkeys([item for item in recommendation_reasons if item]))
    if risk_engine.get("risk_level") == "blocked" or classification.get("excluded_category"):
        recommendation = "REJECT"
    elif viability.get("final_recommendation") == "REJECT":
        recommendation = "REJECT"
    elif pricing_validation.get("manual_review_required") or quote_aging.get("risk_level") == "HIGH_RISK" or viability.get("manual_pricing_review_required"):
        recommendation = "MANUAL_REVIEW"
    elif readiness.get("readiness_state") == "READY" and risk_engine.get("risk_level") in {"low", "medium"} and supplier_match.get("supplier_match_score", 0.0) >= 55:
        recommendation = "GO"
    else:
        recommendation = "MANUAL_REVIEW"
    next_operator_action = readiness.get("next_operator_action") or (
        "stop and resolve disqualification blockers" if recommendation == "REJECT" else "continue under manual supervision" if recommendation == "MANUAL_REVIEW" else "proceed with governed approval steps"
    )
    result = {
        "tender_id": str(payload.get("tender_id") or ""),
        "category": classification.get("category", "unknown"),
        "classification": classification,
        "recommendation": recommendation,
        "recommendation_reasons": recommendation_reasons,
        "automation_suitability_score": viability.get("automation_suitability_score", 0.0),
        "risk_level": risk_engine.get("risk_level", viability.get("risk_level", "medium")),
        "compliance_matrix": compliance_matrix,
        "submission_method": submission_method,
        "supplier_domain": supplier_domain,
        "supplier_match_intelligence": supplier_match,
        "supplier_match_score": supplier_match.get("supplier_match_score", 0.0),
        "supplier_evidence_score": pricing_evidence.get("evidence_completeness_score", 0.0),
        "pricing_confidence": pricing_confidence,
        "pricing_validation": pricing_validation,
        "quote_aging": quote_aging,
        "pricing_traceability": pricing_traceability,
        "pricing_traceability_summary": pricing_traceability.get("pricing_traceability_summary", {}),
        "stale_quote_warning": bool(quote_aging.get("stale_pricing_warnings")),
        "manual_pricing_review_required": bool(pricing_validation.get("manual_review_required") or quote_aging.get("risk_level") == "HIGH_RISK" or viability.get("manual_pricing_review_required")),
        "language_intelligence": language_intelligence,
        "risk_breakdown": risk_engine,
        "readiness_state": readiness.get("readiness_state", "HIGH_RISK"),
        "submission_readiness": readiness,
        "viability": viability,
        "blockers": blockers,
        "warnings": list(dict.fromkeys(warnings)),
        "manual_review_required": recommendation != "GO",
        "quote_candidate": recommendation != "REJECT",
        "detected_language_patterns": language_intelligence.get("detected_patterns", []),
        "manual_review_triggers": list(dict.fromkeys(risk_engine.get("manual_review_triggers", []) + language_intelligence.get("manual_review_triggers", []) + readiness.get("warnings", []))),
        "disqualification_triggers": list(dict.fromkeys(risk_engine.get("disqualification_triggers", []) + language_intelligence.get("disqualification_triggers", []))),
        "next_operator_action": next_operator_action,
    }
    return result


def qualify_text(text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(metadata or {})
    payload.setdefault("title", payload.get("title") or text[:120])
    payload.setdefault("description", text)
    payload.setdefault("extracted_text", text)
    return qualify_rfq(payload)


def qualify_fixture(path: Path | str) -> Dict[str, Any]:
    fixture_path = Path(path)
    if fixture_path.is_dir():
        json_files = sorted(fixture_path.glob("*.json"))
        if not json_files:
            raise FileNotFoundError(f"No JSON fixture found in {fixture_path}")
        fixture_path = json_files[0]
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("qualification fixture must contain a JSON object")
    return qualify_rfq(payload)


def build_qualification_summary(results: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    items = list(results or [])
    counts = {"GO": 0, "MANUAL_REVIEW": 0, "REJECT": 0}
    risk_breakdown = {"low": 0, "medium": 0, "high": 0}
    readiness_breakdown: Dict[str, int] = {}
    supplier_domain_breakdown: Dict[str, int] = {}
    submission_method_breakdown: Dict[str, int] = {}
    pricing_confidence_scores: List[float] = []
    supplier_evidence_scores: List[float] = []
    manual_pricing_review_count = 0
    automation_scores: List[float] = []
    blockers: List[str] = []
    manual_review_trigger_counts: Dict[str, int] = {}
    language_pattern_counts: Dict[str, int] = {}
    for item in items:
        recommendation = str(item.get("recommendation") or "MANUAL_REVIEW")
        if recommendation in counts:
            counts[recommendation] += 1
        risk = str(item.get("risk_level") or "medium")
        if risk in risk_breakdown:
            risk_breakdown[risk] += 1
        readiness_state = str(item.get("readiness_state") or item.get("submission_readiness", {}).get("readiness_state") or "HIGH_RISK")
        readiness_breakdown[readiness_state] = readiness_breakdown.get(readiness_state, 0) + 1
        supplier_domain = str(item.get("supplier_domain", {}).get("supplier_domain") or "unknown")
        supplier_domain_breakdown[supplier_domain] = supplier_domain_breakdown.get(supplier_domain, 0) + 1
        submission_method = str(item.get("submission_method", {}).get("method") or "unknown")
        submission_method_breakdown[submission_method] = submission_method_breakdown.get(submission_method, 0) + 1
        pricing_confidence_scores.append(float(item.get("pricing_confidence", {}).get("overall_pricing_confidence") or 0.0))
        supplier_evidence_scores.append(float(item.get("supplier_evidence_score") or 0.0))
        if bool(item.get("manual_pricing_review_required")):
            manual_pricing_review_count += 1
        automation_scores.append(float(item.get("automation_suitability_score") or 0.0))
        blockers.extend([str(blocker) for blocker in item.get("blockers", [])])
        for trigger in item.get("manual_review_triggers", []) or []:
            manual_review_trigger_counts[str(trigger)] = manual_review_trigger_counts.get(str(trigger), 0) + 1
        for pattern in item.get("detected_language_patterns", []) or []:
            pattern_name = str(pattern.get("name") or "unknown")
            language_pattern_counts[pattern_name] = language_pattern_counts.get(pattern_name, 0) + 1
    average_score = round(sum(automation_scores) / len(automation_scores), 2) if automation_scores else 0.0
    return {
        "total": len(items),
        "recommendation_counts": counts,
        "risk_breakdown": risk_breakdown,
        "readiness_breakdown": readiness_breakdown,
        "supplier_domain_breakdown": supplier_domain_breakdown,
        "submission_method_breakdown": submission_method_breakdown,
        "pricing_confidence_average": round(sum(pricing_confidence_scores) / len(pricing_confidence_scores), 2) if pricing_confidence_scores else 0.0,
        "supplier_evidence_average": round(sum(supplier_evidence_scores) / len(supplier_evidence_scores), 2) if supplier_evidence_scores else 0.0,
        "manual_pricing_review_count": manual_pricing_review_count,
        "manual_review_trigger_counts": manual_review_trigger_counts,
        "language_pattern_counts": language_pattern_counts,
        "average_automation_suitability_score": average_score,
        "blockers": list(dict.fromkeys(blockers)),
        "advisory_only": True,
    }
