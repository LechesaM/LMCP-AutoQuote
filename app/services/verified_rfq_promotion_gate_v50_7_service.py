"""
LMCP V50.7 - Verified RFQ Promotion Gate

Purpose:
- Promote only verified buyer-quantity RFQs into quote generation/submission preparation.
- Keep unsafe or unverified tenders blocked.
- Produce a clear promotion decision object for autonomous radar/scheduler.

Drop-in file:
    app/services/verified_rfq_promotion_gate_v50_7_service.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SERVICE_VERSION = "V50.7_VERIFIED_RFQ_PROMOTION_GATE"

VERIFIED_QUANTITY_STATUSES = {
    "verified_buyer_docx_quantities",
    "verified_buyer_xlsx_quantities",
    "verified_buyer_pdf_quantities",
    "verified_boq_quantities",
    "verified_pricing_schedule_quantities",
}

BLOCKED_PIPELINE_STATUSES = {
    "screened_out",
    "quantity_verification_required",
    "blocked",
    "excluded",
}

EXCLUDED_REASON_HITS = {
    "briefing_required",
    "non_supply_scope",
    "medical_consumables",
    "it_equipment",
    "petrol",
    "diesel",
    "catering",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _has_verified_line_items(item: Dict[str, Any]) -> bool:
    line_items = item.get("line_items") or item.get("items") or []
    if not isinstance(line_items, list) or not line_items:
        return False

    verified_count = 0
    for row in line_items:
        if not isinstance(row, dict):
            continue

        qty = _safe_float(row.get("quantity"), 0.0)
        description = str(row.get("description") or "").strip()
        source = _safe_lower(row.get("source"))
        confidence = _safe_float(row.get("docx_confidence") or row.get("confidence"), 0.0)

        source_verified = any(
            key in source
            for key in ("buyer_docx", "buyer_xlsx", "buyer_pdf", "boq", "pricing_schedule", "buyer_doc")
        )

        if qty > 0 and description and (source_verified or confidence >= 0.85):
            verified_count += 1

    return verified_count > 0


def evaluate_verified_rfq_for_promotion(
    item: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    item = item or {}
    policy = policy or {}

    reasons: List[str] = []
    blockers: List[str] = []

    minimum_profit = _safe_float(policy.get("minimum_profit_required"), 30000.0)
    min_confidence = _safe_float(policy.get("min_confidence"), 0.35)
    allow_email_send = _safe_bool(policy.get("allow_email_send"))
    allow_portal_upload = _safe_bool(policy.get("allow_portal_upload"))
    allow_final_submit = _safe_bool(policy.get("allow_portal_final_submit"))

    eligible = _safe_bool(item.get("eligible"))
    quote_ready = _safe_bool(item.get("quote_ready"))
    estimated_profit = _safe_float(item.get("estimated_profit"), 0.0)
    ai_score = _safe_float(item.get("ai_score"), 0.0)
    confidence = max(
        _safe_float(item.get("confidence"), 0.0),
        _safe_float(item.get("package_match_confidence"), 0.0),
        ai_score / 100.0 if ai_score > 1 else ai_score,
    )

    pipeline_status = _safe_lower(item.get("pipeline_status"))
    exclusion_reason = _safe_lower(item.get("exclusion_reason"))
    quantity_status = _safe_lower(item.get("quantity_safety_status"))
    quantity_source = _safe_lower(item.get("quantity_source"))
    submission_method = _safe_lower(item.get("submission_method"))

    verified_quantity_status = quantity_status in VERIFIED_QUANTITY_STATUSES
    verified_line_items = _has_verified_line_items(item)
    verified_quantities = verified_quantity_status or verified_line_items
    nav_result = item.get("v50_7_navigation_result") if isinstance(item.get("v50_7_navigation_result"), dict) else {}
    nav_status = _safe_lower(item.get("v50_7_navigation_status") or nav_result.get("recommended_action"))
    nav_blockers = item.get("v50_7_navigation_blockers") if isinstance(item.get("v50_7_navigation_blockers"), list) else []
    nav_reasons = item.get("v50_7_navigation_reasons") if isinstance(item.get("v50_7_navigation_reasons"), dict) else {}
    extended_resolution_status = _safe_lower(item.get("v50_8_extended_resolution_status"))
    extended_resolution_summary = item.get("v50_8_extended_resolution_summary") if isinstance(item.get("v50_8_extended_resolution_summary"), dict) else {}

    if eligible:
        reasons.append("eligible_true")
    else:
        blockers.append("not_eligible")

    if quote_ready:
        reasons.append("quote_ready_true")
    else:
        reasons.append("quote_not_yet_generated")

    if estimated_profit >= minimum_profit:
        reasons.append("minimum_profit_met")
    else:
        blockers.append("minimum_profit_not_met")

    if confidence >= min_confidence:
        reasons.append("confidence_met")
    else:
        blockers.append("confidence_below_policy")

    if verified_quantities:
        reasons.append("verified_buyer_quantities")
    else:
        blockers.append("quantity_verification_required")

    if nav_status == "detail_navigation_required":
        blockers.append("detail_navigation_required")
        if extended_resolution_status == "no_verified_resolution":
            blockers.append("no_verified_detail_or_document_link")
    if nav_status == "navigation_failed":
        blockers.append("navigation_failed")
    if nav_status == "safe_detail_link":
        reasons.append("safe_detail_link_verified")
    if nav_status == "safe_document_link":
        reasons.append("safe_document_link_verified")
    if extended_resolution_status == "verified_tenderdetails_document":
        reasons.append("verified_tenderdetails_document")
    elif extended_resolution_status == "verified_document":
        reasons.append("verified_document_resolution")
    elif extended_resolution_status == "verified_detail":
        reasons.append("verified_detail_resolution")
    for blocker in nav_blockers:
        blocker = _safe_lower(blocker)
        if blocker:
            blockers.append(blocker)

    if pipeline_status in BLOCKED_PIPELINE_STATUSES:
        blockers.append(f"blocked_pipeline_status:{pipeline_status}")

    for hit in EXCLUDED_REASON_HITS:
        if hit in exclusion_reason:
            blockers.append(f"excluded_reason:{hit}")

    if item.get("briefing_required") is True:
        blockers.append("briefing_required")

    stalled_stage = "hold"
    if not eligible:
        stalled_stage = "eligibility_gate"
    elif "detail_navigation_required" in blockers or "navigation_failed" in blockers:
        stalled_stage = "detail_navigation"
    elif "quantity_verification_required" in blockers:
        stalled_stage = "quantity_verification"
    elif "minimum_profit_not_met" in blockers or "confidence_below_policy" in blockers:
        stalled_stage = "score_or_profit"
    elif len(blockers) == 0:
        stalled_stage = "quote_pack_ready" if quote_ready else "quote_pack_preparation"
    else:
        stalled_stage = "manual_review"

    # Submission permission decision
    can_prepare_quote = len(blockers) == 0
    can_prepare_submission_pack = can_prepare_quote and quote_ready

    can_send_email = (
        can_prepare_submission_pack
        and submission_method == "email"
        and allow_email_send
    )

    can_upload_portal = (
        can_prepare_submission_pack
        and submission_method in {"portal", "online", "manual_portal"}
        and allow_portal_upload
    )

    # Final submit remains separately guarded.
    can_final_submit = (can_send_email or can_upload_portal) and allow_final_submit

    next_action = "hold"
    if can_prepare_quote and not quote_ready:
        next_action = "generate_quote_pack"
    elif can_prepare_submission_pack and can_send_email:
        next_action = "prepare_and_send_email_submission"
    elif can_prepare_submission_pack and can_upload_portal:
        next_action = "prepare_portal_submission_pack"
    elif can_prepare_submission_pack:
        next_action = "prepare_submission_pack_policy_limited"
    elif blockers:
        next_action = "manual_review_required"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "evaluated_at": _now(),
        "buyer_rfq_number": item.get("buyer_rfq_number") or item.get("rfq_number") or item.get("reference_number") or "",
        "title": item.get("title") or "",
        "eligible": eligible,
        "quote_ready": quote_ready,
        "estimated_profit": estimated_profit,
        "minimum_profit_required": minimum_profit,
        "confidence": round(confidence, 4),
        "min_confidence": min_confidence,
        "quantity_safety_status": quantity_status,
        "quantity_source": quantity_source,
        "verified_quantities": verified_quantities,
        "verified_line_items": verified_line_items,
        "navigation_status": nav_status,
        "navigation_blockers": nav_blockers,
        "navigation_reasons": nav_reasons,
        "extended_resolution_status": extended_resolution_status,
        "extended_resolution_summary": extended_resolution_summary,
        "can_prepare_quote": can_prepare_quote,
        "can_prepare_submission_pack": can_prepare_submission_pack,
        "can_send_email": can_send_email,
        "can_upload_portal": can_upload_portal,
        "can_final_submit": can_final_submit,
        "next_action": next_action,
        "stalled_stage": stalled_stage,
        "blocker_summary": {
            "eligible": eligible,
            "quote_ready": quote_ready,
            "verified_quantities": verified_quantities,
            "navigation_status": nav_status,
            "pipeline_status": pipeline_status,
            "extended_resolution_status": extended_resolution_status,
            "extended_resolution_summary": extended_resolution_summary,
        },
        "promotion_allowed": can_prepare_quote,
        "submission_gate_allowed": can_send_email or can_upload_portal,
        "final_submit_gate_allowed": can_final_submit,
        "reasons": reasons,
        "blockers": sorted(set(blockers)),
    }


def batch_evaluate_verified_rfqs(
    items: Optional[List[Dict[str, Any]]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    items = items or []
    results = [evaluate_verified_rfq_for_promotion(item, policy) for item in items]

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "evaluated_at": _now(),
        "count": len(results),
        "promotion_allowed_count": sum(1 for r in results if r["promotion_allowed"]),
        "submission_gate_allowed_count": sum(1 for r in results if r["submission_gate_allowed"]),
        "final_submit_gate_allowed_count": sum(1 for r in results if r["final_submit_gate_allowed"]),
        "results": results,
    }


def get_v50_7_promotion_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "verified_quantity_statuses": sorted(VERIFIED_QUANTITY_STATUSES),
        "blocked_pipeline_statuses": sorted(BLOCKED_PIPELINE_STATUSES),
        "excluded_reason_hits": sorted(EXCLUDED_REASON_HITS),
    }
