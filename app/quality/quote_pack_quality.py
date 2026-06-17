from __future__ import annotations

from typing import Any, Dict


def assess_quote_pack_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    warnings = []
    field_warning_map = [
        ("company_details_present", "missing_company_details"),
        ("buyer_details_present", "missing_buyer_details"),
        ("tender_reference_present", "missing_tender_reference"),
        ("pricing_schedule_present", "missing_pricing_schedule"),
        ("vat_treatment_shown", "missing_vat_treatment"),
        ("validity_period_present", "missing_validity_period"),
        ("delivery_terms_present", "missing_delivery_terms"),
        ("signature_placeholder_present", "missing_signature_placeholder"),
    ]
    for key, warning in field_warning_map:
        if not payload.get(key):
            warnings.append(warning)
    artifacts = payload.get("artifacts") or []
    if not artifacts:
        warnings.append("missing_artifacts")
    quality_score = max(0.0, 1.0 - (0.1 * len(warnings)))
    return {
        "quality_score": quality_score,
        "warnings": warnings,
        "missing_artifacts": [] if artifacts else ["artifacts"],
        "quote_pack": {"quote_pack_ready": quality_score >= 0.8},
    }
