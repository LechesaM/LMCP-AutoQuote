from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.domain.rfq import RFQRecord
from app.qualification.compliance_matrix import build_compliance_matrix
from app.qualification.opportunity_viability import assess_opportunity_viability
from app.qualification.rfq_classifier import classify_rfq
from app.qualification.submission_method_detector import detect_submission_method
from app.qualification.supplier_domain_mapper import map_supplier_domain


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
    compliance_matrix = build_compliance_matrix(payload)
    submission_method = detect_submission_method(payload)
    supplier_domain = map_supplier_domain(classification)
    viability = assess_opportunity_viability(payload, classification, compliance_matrix, submission_method)
    blockers = _collect_blockers(classification, compliance_matrix, viability)
    warnings: List[str] = []
    if classification.get("manual_review_required"):
        warnings.append("manual review required")
    if submission_method.get("manual_handling_required"):
        warnings.append("manual handling required")
    if compliance_matrix.get("missing_required_count", 0):
        warnings.append("compliance gaps detected")
    if viability.get("final_recommendation") == "REJECT":
        warnings.append("qualification rejected")
    result = {
        "tender_id": str(payload.get("tender_id") or ""),
        "category": classification.get("category", "unknown"),
        "classification": classification,
        "recommendation": viability.get("final_recommendation", "MANUAL_REVIEW"),
        "automation_suitability_score": viability.get("automation_suitability_score", 0.0),
        "risk_level": viability.get("risk_level", "medium"),
        "compliance_matrix": compliance_matrix,
        "submission_method": submission_method,
        "supplier_domain": supplier_domain,
        "viability": viability,
        "blockers": blockers,
        "warnings": list(dict.fromkeys(warnings)),
        "manual_review_required": viability.get("final_recommendation") != "GO",
        "quote_candidate": viability.get("final_recommendation") != "REJECT",
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
    supplier_domain_breakdown: Dict[str, int] = {}
    submission_method_breakdown: Dict[str, int] = {}
    automation_scores: List[float] = []
    blockers: List[str] = []
    for item in items:
        recommendation = str(item.get("recommendation") or "MANUAL_REVIEW")
        if recommendation in counts:
            counts[recommendation] += 1
        risk = str(item.get("risk_level") or "medium")
        if risk in risk_breakdown:
            risk_breakdown[risk] += 1
        supplier_domain = str(item.get("supplier_domain", {}).get("supplier_domain") or "unknown")
        supplier_domain_breakdown[supplier_domain] = supplier_domain_breakdown.get(supplier_domain, 0) + 1
        submission_method = str(item.get("submission_method", {}).get("method") or "unknown")
        submission_method_breakdown[submission_method] = submission_method_breakdown.get(submission_method, 0) + 1
        automation_scores.append(float(item.get("automation_suitability_score") or 0.0))
        blockers.extend([str(blocker) for blocker in item.get("blockers", [])])
    average_score = round(sum(automation_scores) / len(automation_scores), 2) if automation_scores else 0.0
    return {
        "total": len(items),
        "recommendation_counts": counts,
        "risk_breakdown": risk_breakdown,
        "supplier_domain_breakdown": supplier_domain_breakdown,
        "submission_method_breakdown": submission_method_breakdown,
        "average_automation_suitability_score": average_score,
        "blockers": list(dict.fromkeys(blockers)),
        "advisory_only": True,
    }
