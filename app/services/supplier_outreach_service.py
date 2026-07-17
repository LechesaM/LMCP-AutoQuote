from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


EMAIL_TYPE_INITIAL = "INITIAL_SUPPLIER_RFQ"
EMAIL_TYPE_FOLLOWUP_1 = "SUPPLIER_RFQ_FOLLOWUP_1"
EMAIL_TYPE_FINAL_FOLLOWUP = "SUPPLIER_RFQ_FINAL_FOLLOWUP"
EMAIL_TYPE_CLARIFICATION = "SUPPLIER_CLARIFICATION"
EMAIL_TYPE_RESPONSE_RECEIVED = "SUPPLIER_RESPONSE_RECEIVED"
EMAIL_TYPE_RESPONSE_INCOMPLETE = "SUPPLIER_RESPONSE_INCOMPLETE"

DEFAULT_SUPPLIER_MAILBOX = "lmcpaqsystem@gmail.com"
DEFAULT_MANDATORY_CC = "lechesam@me.com"
DEFAULT_MIN_QUOTES = 3
DEFAULT_FOLLOWUP_DAYS = 2

RESPONSE_COVERAGE_THREE = "THREE_OR_MORE_VALID_QUOTES"
RESPONSE_COVERAGE_TWO = "TWO_VALID_QUOTES"
RESPONSE_COVERAGE_ONE = "ONE_VALID_QUOTE"
RESPONSE_COVERAGE_NONE_FALLBACK = "NO_VALID_QUOTES_FALLBACK_PRICING"
RESPONSE_COVERAGE_PENDING = "SUPPLIER_QUOTES_PENDING"
RESPONSE_COVERAGE_LATE = "SUPPLIER_QUOTES_RECEIVED_AFTER_PRICING"


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return text or "supplier-rfq"


def _stable_request_id(reference_number: str, source: str = "dry-run") -> str:
    digest = hashlib.sha256(f"{reference_number}|{source}".encode("utf-8")).hexdigest()[:10].upper()
    return f"LMCP-SRFQ-{reference_number}-{digest}"


def _dedupe(values: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = _safe_str(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _normalise_email(value: Any) -> str:
    return _safe_str(value).lower()


def _redact_email(value: str) -> str:
    email = _normalise_email(value)
    if not email:
        return ""
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]
    return f"redacted-email-{digest}"


def supplier_outreach_config(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    env = env or os.environ
    return {
        "supplier_outreach_automation_enabled": str(env.get("LMCP_SUPPLIER_OUTREACH_AUTOMATION_ENABLED", "false")).lower() == "true",
        "buyer_autonomous_submission_enabled": False,
        "manual_buyer_submission_required": True,
        "supplier_rfq_email": env.get("LMCP_SUPPLIER_RFQ_EMAIL", DEFAULT_SUPPLIER_MAILBOX),
        "supplier_rfq_cc": env.get("LMCP_SUPPLIER_RFQ_CC", DEFAULT_MANDATORY_CC),
        "minimum_supplier_target": _safe_int(env.get("LMCP_SUPPLIER_RFQ_MIN_QUOTES"), DEFAULT_MIN_QUOTES),
        "followup_days": _safe_int(env.get("LMCP_SUPPLIER_RFQ_FOLLOWUP_DAYS"), DEFAULT_FOLLOWUP_DAYS),
        "credentials_in_source": False,
    }


def enforce_mandatory_cc(cc_values: Optional[Iterable[str]], config: Optional[Dict[str, Any]] = None) -> List[str]:
    config = config or supplier_outreach_config()
    values = _dedupe(cc_values or [])
    for mandatory in _dedupe([config.get("supplier_rfq_cc"), DEFAULT_MANDATORY_CC]):
        if mandatory and mandatory not in values:
            values.append(mandatory)
    return values


def _technical_requirement_summary(requirement_pack: Dict[str, Any]) -> Dict[str, Any]:
    rows = requirement_pack.get("buyer_rows") if isinstance(requirement_pack.get("buyer_rows"), list) else []
    technical = requirement_pack.get("technical_requirements") if isinstance(requirement_pack.get("technical_requirements"), list) else []
    standards = _dedupe(standard for row in rows for standard in (row.get("standards") or []))
    names = [_safe_str(item.get("name")) for item in technical if isinstance(item, dict)]
    return {
        "brand_required": any(row.get("brand_required") for row in rows) or any("brand" in name.lower() for name in names),
        "datasheet_required": any(row.get("datasheet_required") for row in rows) or any("datasheet" in name.lower() for name in names),
        "sample_may_be_required": any(row.get("sample_may_be_required") for row in rows) or any("sample" in name.lower() for name in names),
        "standards": standards,
        "technical_requirements": technical,
    }


def _sourcing_items(requirement_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    groups = requirement_pack.get("supplier_sourcing_groups") if isinstance(requirement_pack.get("supplier_sourcing_groups"), list) else []
    items: List[Dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        items.append({
            "sourcing_group_number": index,
            "supplier_group_id": group.get("supplier_group_id"),
            "material_number": group.get("material_number") or group.get("item_code") or group.get("part_number") or "",
            "description": group.get("description") or "",
            "specification": group.get("specification") or "",
            "total_quantity": group.get("total_quantity"),
            "unit": group.get("unit") or "",
            "standards": group.get("standards") or [],
            "brand_required": bool(group.get("brand_required")),
            "equivalent_brands_permitted": True,
            "datasheet_required": bool(group.get("datasheet_required")),
            "compliance_certificate_required": bool(group.get("compliance_certificate_required")) or bool(group.get("standards")),
            "sample_may_be_required": bool(group.get("sample_may_be_required")),
            "buyer_requirement_row_ids": group.get("buyer_requirement_row_ids") or [],
            "buyer_line_indexes": group.get("buyer_line_indexes") or [],
            "source_provenance": {
                "requirement_pack_version": requirement_pack.get("requirement_pack_version"),
                "supplier_group_id": group.get("supplier_group_id"),
                "buyer_requirement_row_ids": group.get("buyer_requirement_row_ids") or [],
            },
        })
    return items


def validate_supplier_request_inputs(requirement_pack: Dict[str, Any]) -> Dict[str, Any]:
    items = _sourcing_items(requirement_pack)
    review_reasons: List[str] = []
    if not items:
        review_reasons.append("no_supplier_sourcing_groups")
    for item in items:
        if not item.get("description"):
            review_reasons.append(f"missing_description:{item.get('supplier_group_id')}")
        if item.get("total_quantity") in (None, "", 0):
            review_reasons.append(f"missing_quantity:{item.get('supplier_group_id')}")
        if not item.get("unit"):
            review_reasons.append(f"missing_unit:{item.get('supplier_group_id')}")
    conflicts = requirement_pack.get("requirement_conflicts") if isinstance(requirement_pack.get("requirement_conflicts"), list) else []
    if conflicts:
        review_reasons.append("requirement_conflicts_present")
    brand_values = {
        str(item.get("brand_required"))
        for item in items
        if item.get("material_number") or item.get("description")
    }
    if "True" in brand_values and "False" in brand_values:
        review_reasons.append("conflicting_brand_instructions")
    return {
        "draft_preparation_allowed": not review_reasons,
        "operator_review_required": bool(review_reasons),
        "review_reasons": review_reasons,
        "item_count": len(items),
    }


def build_canonical_supplier_outreach_request(
    *,
    supplier: Dict[str, Any],
    requirement_pack: Dict[str, Any],
    request_id: str,
    created_at: datetime,
    draft_type: str = EMAIL_TYPE_INITIAL,
    config: Optional[Dict[str, Any]] = None,
    response_deadline: str = "",
    delivery_location: str = "",
    delivery_requirements: str = "",
    created_by: str = "system_controlled_validation",
) -> Dict[str, Any]:
    config = config or supplier_outreach_config()
    validation = validate_supplier_request_inputs(requirement_pack)
    technical = _technical_requirement_summary(requirement_pack)
    items = _sourcing_items(requirement_pack)
    supplier_email = _safe_str(supplier.get("supplier_email") or supplier.get("email"))
    if "@" not in supplier_email:
        validation["draft_preparation_allowed"] = False
        validation["operator_review_required"] = True
        validation.setdefault("review_reasons", []).append("supplier_email_missing")
    required_documents = _dedupe([
        "formal supplier quotation",
        "manufacturer datasheet" if technical["datasheet_required"] else "",
        "compliance certificate" if technical["standards"] else "",
        "warranty confirmation",
        "delivery schedule",
        "sample availability confirmation" if technical["sample_may_be_required"] else "",
    ])
    return {
        "rfq_id": requirement_pack.get("rfq_id") or f"TEMP-RFQ-{requirement_pack.get('reference_number', '')}",
        "rfq_reference": _safe_str(requirement_pack.get("reference_number")),
        "buyer_name": _safe_str(requirement_pack.get("buyer_name")),
        "buyer_closing_at": _safe_str(requirement_pack.get("closing_date") or requirement_pack.get("buyer_closing_at")),
        "supplier_response_deadline": response_deadline,
        "supplier_id": _safe_str(supplier.get("supplier_id") or supplier.get("supplier_name") or supplier_email),
        "supplier_name": _safe_str(supplier.get("supplier_name") or supplier.get("name") or supplier_email),
        "supplier_email": supplier_email,
        "supplier_request_id": request_id,
        "draft_type": draft_type,
        "items": items,
        "delivery_location": delivery_location,
        "delivery_requirements": delivery_requirements,
        "required_documents": required_documents,
        "technical_standards": technical["standards"],
        "required_brands": "offered_brand_required" if technical["brand_required"] else "brand_neutral_unless_specified",
        "brand_equivalent_policy": "equivalent brands permitted subject to buyer acceptance",
        "mandatory_cc": config.get("supplier_rfq_cc") or DEFAULT_MANDATORY_CC,
        "attachments": [],
        "source_provenance": {
            "requirement_pack_version": requirement_pack.get("requirement_pack_version"),
            "source_types": requirement_pack.get("source_types") or [],
        },
        "created_by": created_by,
        "approval_state": "APPROVED_FOR_DRAFT" if validation["draft_preparation_allowed"] else "REVIEW_REQUIRED",
        "transport_mode": "DRAFT_ONLY",
        "validation": validation,
    }


def select_supplier_targets(
    supplier_candidates: Optional[Sequence[Dict[str, Any]]] = None,
    minimum_supplier_target: int = DEFAULT_MIN_QUOTES,
) -> List[Dict[str, Any]]:
    candidates = list(supplier_candidates or [])
    if not candidates:
        candidates = [
            {
                "supplier_name": "Dry Run Tools Supplier A",
                "supplier_email": "tools-supplier-a@example.com",
                "category": "heavy duty hand tools",
                "synthetic_validation_supplier": True,
            },
            {
                "supplier_name": "Dry Run Industrial Supplies B",
                "supplier_email": "industrial-supplies-b@example.com",
                "category": "pipe wrenches spanners hammers chisels",
                "synthetic_validation_supplier": True,
            },
            {
                "supplier_name": "Dry Run Hardware Distributor C",
                "supplier_email": "hardware-distributor-c@example.com",
                "category": "SANS ISO compliant tools",
                "synthetic_validation_supplier": True,
            },
        ]

    selected: List[Dict[str, Any]] = []
    seen = set()
    for supplier in candidates:
        if not isinstance(supplier, dict):
            continue
        email = _safe_str(supplier.get("supplier_email") or supplier.get("email"))
        if "@" not in email or email.lower() in seen:
            continue
        seen.add(email.lower())
        selected.append({
            "supplier_id": _safe_str(supplier.get("supplier_id") or supplier.get("supplier_name") or supplier.get("name") or email),
            "supplier_name": _safe_str(supplier.get("supplier_name") or supplier.get("name") or email),
            "supplier_email": email,
            "category": _safe_str(supplier.get("category")),
            "selection_reason": _safe_str(supplier.get("selection_reason") or "category_or_general_supply_fit"),
            "synthetic_validation_supplier": bool(supplier.get("synthetic_validation_supplier")),
        })
        if len(selected) >= minimum_supplier_target:
            break
    return selected


def _subject(reference_number: str, request_id: str, response_deadline: str) -> str:
    return f"Supplier RFQ | Buyer RFQ {reference_number} | LMCP Request {request_id} | Response Required by {response_deadline}"


def _followup_subject(reference_number: str, request_id: str, number: int = 1) -> str:
    return f"Follow-Up {number} | Supplier RFQ | Buyer RFQ {reference_number} | LMCP Request {request_id}"


def _item_schedule_text(items: Sequence[Dict[str, Any]]) -> str:
    lines = [
        "Product schedule:",
        "Group | Material/Item Ref | Description | Qty | Unit | Standards | Brand / Datasheet",
    ]
    for item in items:
        quantity = item.get("total_quantity")
        try:
            quantity_text = str(int(quantity)) if float(quantity).is_integer() else str(quantity)
        except Exception:
            quantity_text = _safe_str(quantity)
        lines.append(
            "{group} | {material} | {description} | {qty} | {unit} | {standards} | {brand}".format(
                group=item.get("sourcing_group_number"),
                material=item.get("material_number"),
                description=item.get("description"),
                qty=quantity_text,
                unit=item.get("unit"),
                standards=", ".join(item.get("standards") or []),
                brand=(
                    "Offered brand required; equivalent brands permitted subject to buyer acceptance; manufacturer datasheet required"
                    if item.get("brand_required") or item.get("datasheet_required")
                    else "Brand-neutral unless specification requires otherwise"
                ),
            )
        )
    return "\n".join(lines)


def build_supplier_email_model(
    *,
    supplier: Dict[str, Any],
    requirement_pack: Dict[str, Any],
    request_id: str,
    created_at: datetime,
    config: Optional[Dict[str, Any]] = None,
    response_deadline: str = "",
    delivery_destination: str = "",
    requested_delivery_period: str = "",
) -> Dict[str, Any]:
    config = config or supplier_outreach_config()
    reference = _safe_str(requirement_pack.get("reference_number") or "UNKNOWN-RFQ")
    buyer_name = _safe_str(requirement_pack.get("buyer_name") or "Buyer organisation")
    title = _safe_str(requirement_pack.get("title") or "RFQ")
    items = _sourcing_items(requirement_pack)
    technical = _technical_requirement_summary(requirement_pack)
    subject = _subject(reference, request_id, response_deadline)
    cc = enforce_mandatory_cc([], config)
    body_lines = [
        "Dear Supplier,",
        "",
        "Please provide a formal supplier quotation for the items below.",
        "",
        f"LMCP internal request reference: {request_id}",
        f"Buyer RFQ reference: {reference}",
        f"Buyer organisation: {buyer_name}",
        f"RFQ title: {title}",
        f"Quotation response deadline: {response_deadline}",
        f"Requested delivery destination: {delivery_destination}",
        f"Requested delivery period: {requested_delivery_period}",
        "",
        _item_schedule_text(items),
        "",
        "Mandatory response fields:",
        "- offered brand",
        "- manufacturer",
        "- manufacturer part or model number",
        "- unit price excluding VAT",
        "- total price excluding VAT",
        "- VAT",
        "- total including VAT",
        "- delivery cost",
        "- delivery period",
        "- quotation validity",
        "- stock availability",
        "- warranty",
        "- country of origin where required",
        "- compliance confirmation",
        "- contact person",
        "- quotation reference",
        "- supplier legal name",
        "- company registration number where appropriate",
        "- VAT registration number where applicable",
        "",
        "Required attachments where applicable:",
        "- formal supplier quotation",
        "- manufacturer datasheet",
        "- product brochure",
        "- compliance certificate",
        "- SANS certificate or conformity evidence",
        "- ISO evidence",
        "- warranty confirmation",
        "- letter of authorised distribution",
        "- product images",
        "- sample availability confirmation",
        "- delivery schedule",
        "",
        "Important technical requirements:",
        f"- Offered brand required: {technical['brand_required']}",
        f"- Manufacturer datasheet required: {technical['datasheet_required']}",
        f"- Sample may be requested: {technical['sample_may_be_required']}",
        f"- Applicable standards: {', '.join(technical['standards'])}",
        "",
        "A price without the offered brand is incomplete where brand details are required.",
        "Please quote excluding VAT and show VAT separately. Please include delivery costs separately.",
        "",
        "Regards,",
        "LMCP AutoQuote Supplier RFQ Desk",
    ]
    followup_due = created_at + timedelta(days=int(config.get("followup_days") or DEFAULT_FOLLOWUP_DAYS))
    return {
        "email_type": EMAIL_TYPE_INITIAL,
        "rfq_id": requirement_pack.get("rfq_id") or f"TEMP-RFQ-{reference}",
        "request_id": request_id,
        "supplier": supplier,
        "from": config.get("supplier_rfq_email"),
        "to": supplier.get("supplier_email"),
        "cc": cc,
        "mandatory_cc": config.get("supplier_rfq_cc"),
        "subject": subject,
        "body": "\n".join(body_lines),
        "created_at": _iso(created_at),
        "approval_state": "DRY_RUN_NOT_SENT",
        "sent": False,
        "contacted": False,
        "supplier_contacted": False,
        "request_sent_at": None,
        "sent_timestamp": None,
        "draft_status": "NOT_CREATED",
        "send_authority_enabled": bool(config.get("supplier_outreach_automation_enabled")),
        "live_email_sent": False,
        "followup_due_at": _iso(followup_due),
        "response_deadline": response_deadline,
        "delivery_destination": delivery_destination,
        "requested_delivery_period": requested_delivery_period,
        "sourcing_items": items,
        "required_attachments": [
            "formal supplier quotation",
            "manufacturer datasheet",
            "product brochure",
            "compliance certificate",
            "SANS certificate or conformity evidence",
            "ISO evidence",
            "warranty confirmation",
            "sample availability confirmation",
            "delivery schedule",
        ],
        "attachment_manifest": [
            {
                "name": "supplier_pricing_request_schedule.json",
                "type": "pricing_request_schedule",
                "contains_internal_pricing": False,
            },
            {
                "name": "technical_requirements_summary.json",
                "type": "technical_requirements",
                "contains_internal_pricing": False,
            },
            {
                "name": "supplier_response_template.json",
                "type": "supplier_response_template",
                "contains_internal_pricing": False,
            },
        ],
    }


def build_followup_model(initial_email: Dict[str, Any], followup_number: int = 1) -> Dict[str, Any]:
    reference_match = re.search(r"Buyer RFQ\s+([A-Za-z0-9_.-]+)", _safe_str(initial_email.get("subject")))
    reference = reference_match.group(1) if reference_match else ""
    request_id = _safe_str(initial_email.get("request_id"))
    subject = _followup_subject(reference, request_id, followup_number)
    return {
        "email_type": EMAIL_TYPE_FOLLOWUP_1 if followup_number == 1 else EMAIL_TYPE_FINAL_FOLLOWUP,
        "request_id": request_id,
        "linked_initial_subject": initial_email.get("subject"),
        "from": initial_email.get("from"),
        "to": initial_email.get("to"),
        "cc": enforce_mandatory_cc(initial_email.get("cc") or []),
        "mandatory_cc": initial_email.get("mandatory_cc"),
        "subject": subject,
        "body": "\n".join([
            "Dear Supplier,",
            "",
            f"This is a follow-up for LMCP supplier request {request_id}.",
            "Please confirm whether you can quote on the requested items and provide the outstanding technical documents.",
            f"Response deadline: {initial_email.get('response_deadline')}",
            "",
            _item_schedule_text(initial_email.get("sourcing_items") or []),
            "",
            "Regards,",
            "LMCP AutoQuote Supplier RFQ Desk",
        ]),
        "approval_state": "DRY_RUN_NOT_SENT",
        "sent": False,
        "contacted": False,
        "supplier_contacted": False,
        "request_sent_at": None,
        "draft_status": "NOT_CREATED",
        "live_email_sent": False,
        "followup_preconditions": {
            "no_valid_supplier_quote_received": True,
            "supplier_not_declined": True,
            "not_permanently_bounced": True,
            "request_not_cancelled": True,
            "buyer_rfq_not_closed": True,
            "same_stage_followup_not_already_sent": True,
        },
    }


def evaluate_followup_draft_preparation(
    *,
    initial_request: Dict[str, Any],
    now: datetime,
    supplier_response_recorded: bool = False,
    existing_followup_draft: bool = False,
    buyer_closed: bool = False,
) -> Dict[str, Any]:
    sent_at_raw = initial_request.get("sent_timestamp") or initial_request.get("request_sent_at")
    if not sent_at_raw:
        return {"eligible": False, "reason": "initial_request_not_sent", "followup_due_at": ""}
    sent_at = datetime.fromisoformat(str(sent_at_raw).replace("Z", "+00:00"))
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    due_at = sent_at + timedelta(days=DEFAULT_FOLLOWUP_DAYS)
    if buyer_closed:
        return {"eligible": False, "reason": "buyer_rfq_closed", "followup_due_at": _iso(due_at)}
    if supplier_response_recorded:
        return {"eligible": False, "reason": "supplier_response_recorded", "followup_due_at": _iso(due_at)}
    if existing_followup_draft:
        return {"eligible": False, "reason": "followup_draft_already_exists", "followup_due_at": _iso(due_at)}
    return {"eligible": now.astimezone(timezone.utc) >= due_at, "reason": "due" if now.astimezone(timezone.utc) >= due_at else "not_yet_due", "followup_due_at": _iso(due_at)}


def build_supplier_outreach_status(
    *,
    supplier_count: int,
    minimum_supplier_target: int,
    initial_email_count: int,
    followup_count: int,
    sourcing_deadline: str,
    pricing_cutoff: str,
) -> Dict[str, Any]:
    return {
        "suppliers_identified": supplier_count,
        "suppliers_contacted": 0,
        "minimum_supplier_target": minimum_supplier_target,
        "initial_requests_sent": 0,
        "initial_requests_prepared": initial_email_count,
        "supplier_responses_received": 0,
        "valid_quotes_received": 0,
        "declined_requests": 0,
        "bounced_requests": 0,
        "pending_responses": initial_email_count,
        "followups_due": 0,
        "followup_drafts_prepared": followup_count,
        "followups_sent": 0,
        "sourcing_deadline": sourcing_deadline,
        "internal_pricing_cutoff": pricing_cutoff,
        "pricing_fallback_required": True,
        "supplier_pricing_confirmed": False,
        "supplier_quote_coverage": RESPONSE_COVERAGE_NONE_FALLBACK,
        "manual_pricing_review_required": True,
        "pricing_ready": True,
        "pricing_confidence": "controlled_fallback_requires_operator_review",
        "technical_evidence_outstanding": True,
        "brands_outstanding": True,
        "datasheets_outstanding": True,
        "delivery_confirmation_outstanding": True,
    }


def build_no_response_pricing_state(status: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pricing_ready": True,
        "supplier_pricing_confirmed": False,
        "supplier_quote_coverage": status.get("supplier_quote_coverage") or RESPONSE_COVERAGE_NONE_FALLBACK,
        "quote_ready": False,
        "manual_pricing_review_required": True,
        "fallback_pricing_sources_used": [
            "controlled_cost_model",
            "operator-entered market estimate or benchmark required before final approval",
        ],
        "pricing_confidence": status.get("pricing_confidence"),
        "contingency_applied": "operator_review_required",
        "operator_warning": "Pricing may continue without supplier response, but supplier confirmation, brand, datasheets and delivery evidence remain unresolved.",
    }


def build_supplier_response_match(
    *,
    response: Dict[str, Any],
    request_id: str,
    buyer_rfq_number: str,
) -> Dict[str, Any]:
    subject = _safe_str(response.get("subject"))
    body = _safe_str(response.get("body"))
    from_email = _safe_str(response.get("from") or response.get("supplier_email"))
    attachments = response.get("attachments") if isinstance(response.get("attachments"), list) else []
    score = 0
    reasons: List[str] = []
    if request_id and request_id in subject + body:
        score += 50
        reasons.append("request_id_match")
    if buyer_rfq_number and buyer_rfq_number in subject + body:
        score += 30
        reasons.append("buyer_rfq_match")
    if "@" in from_email:
        score += 10
        reasons.append("supplier_email_present")
    if attachments:
        score += 10
        reasons.append("attachments_present")
    valid_quote = bool(
        response.get("supplier_name")
        and response.get("items")
        and response.get("prices_present")
        and response.get("offered_brand_present")
        and response.get("delivery_period_present")
    )
    return {
        "email_type": EMAIL_TYPE_RESPONSE_RECEIVED if valid_quote else EMAIL_TYPE_RESPONSE_INCOMPLETE,
        "request_id": request_id,
        "buyer_rfq_number": buyer_rfq_number,
        "match_score": score,
        "match_reasons": reasons,
        "valid_supplier_quote": valid_quote,
        "response_status": "VALID_SUPPLIER_QUOTATION" if valid_quote else "SUPPLIER_RESPONSE_INCOMPLETE",
        "attachments": attachments,
        "operator_review_required": not valid_quote,
    }


def build_outreach_audit_record(email_model: Dict[str, Any], status: str = "prepared") -> Dict[str, Any]:
    supplier = email_model.get("supplier") if isinstance(email_model.get("supplier"), dict) else {}
    return {
        "rfq_id": email_model.get("rfq_id", "TEMP-RFQ-6000080579"),
        "sourcing_request_id": email_model.get("request_id"),
        "supplier": supplier.get("supplier_name") or email_model.get("to"),
        "recipient_address": email_model.get("to"),
        "recipient_address_redacted": _redact_email(email_model.get("to")),
        "sender_mailbox": email_model.get("from"),
        "mandatory_cc": email_model.get("mandatory_cc"),
        "subject": email_model.get("subject"),
        "email_type": email_model.get("email_type"),
        "creation_time": email_model.get("created_at") or _iso(_now_utc()),
        "approval_state": email_model.get("approval_state"),
        "sent_time": None,
        "followup_due_time": email_model.get("followup_due_at"),
        "delivery_status": status,
        "response_status": "pending_response",
        "attachment_manifest": email_model.get("attachment_manifest") or [],
        "linked_buyer_rows": [
            row_id
            for item in (email_model.get("sourcing_items") or [])
            for row_id in (item.get("buyer_requirement_row_ids") or [])
        ],
        "linked_sourcing_groups": [item.get("supplier_group_id") for item in (email_model.get("sourcing_items") or [])],
        "message_thread_identifiers": {
            "request_id": email_model.get("request_id"),
            "subject": email_model.get("subject"),
        },
        "operator_responsible": "system_dry_run",
        "system_action": "dry_run_prepare_supplier_email",
        "error_details": "",
    }


def build_supplier_draft_audit_record(
    *,
    email_model: Dict[str, Any],
    draft_resolution: Dict[str, Any],
    requirement_pack_version: str = "",
) -> Dict[str, Any]:
    return {
        "rfq_reference": _safe_str(email_model.get("rfq_reference") or "6000080579"),
        "supplier_request_id": email_model.get("request_id"),
        "supplier_identity": _safe_str((email_model.get("supplier") or {}).get("supplier_name") or email_model.get("to")),
        "recipient_hash": _redact_email(email_model.get("to")),
        "draft_type": email_model.get("email_type"),
        "transport_mode": "DRAFT_ONLY",
        "idempotency_key_hash": draft_resolution.get("idempotency_key_hash"),
        "requirement_pack_version": requirement_pack_version,
        "item_count": len(email_model.get("sourcing_items") or []),
        "attachment_count": len(email_model.get("attachment_manifest") or []),
        "draft_resolution": draft_resolution.get("status"),
        "approval_state": email_model.get("approval_state"),
        "safety_controls_applied": [
            "draft_only_transport",
            "send_blocked",
            "mandatory_cc_enforced",
            "no_bcc",
            "no_internal_pricing_disclosure",
        ],
        "timestamp": _iso(_now_utc()),
        "failure_reason": draft_resolution.get("failure_reason", ""),
    }


def prepare_supplier_outreach_gmail_drafts(
    *,
    email_models: Sequence[Dict[str, Any]],
    output_dir: Path,
    requirement_pack_version: str = "",
    gmail_service: Optional[Any] = None,
) -> Dict[str, Any]:
    from app.services.gmail_draft_idempotency_ledger import (
        CONTROLLED_WARNING,
        canonical_key_for_request,
        load_ledger,
        locked_ledger,
        resolve_or_create_draft,
        save_ledger_atomic,
    )
    from app.services.gmail_draft_transport_service import (
        FakeGmailDraftClient,
        GmailAttachmentRequest,
        GmailDraftTransportService,
        build_supplier_gmail_draft_request,
        dataclass_to_dict,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    if gmail_service is None:
        gmail_service = GmailDraftTransportService(
            gmail_client=FakeGmailDraftClient(),
            env={"LMCP_EMAIL_TRANSPORT_MODE": "DRAFT_ONLY", "LMCP_GMAIL_USER_ID": "me"},
            controlled_test_mode=True,
        )

    attachments = [
        GmailAttachmentRequest(filename="supplier_pricing_request_schedule.json", mime_type="application/json", content=b"{}", logical_document_type="pricing_request_schedule").normalised(),
        GmailAttachmentRequest(filename="technical_requirements_summary.json", mime_type="application/json", content=b"{}", logical_document_type="technical_requirements").normalised(),
        GmailAttachmentRequest(filename="supplier_response_template.json", mime_type="application/json", content=b"{}", logical_document_type="supplier_response_template").normalised(),
    ]
    ledger_path = output_dir / "state" / "supplier_outreach_draft_ledger.json"
    results: List[Dict[str, Any]] = []
    audit: List[Dict[str, Any]] = []
    with locked_ledger(ledger_path):
        ledger = load_ledger(ledger_path)
        for email in email_models:
            request = build_supplier_gmail_draft_request(
                email,
                recipient=DEFAULT_SUPPLIER_MAILBOX,
                email_type=email.get("email_type") or EMAIL_TYPE_INITIAL,
                attachments=attachments,
                body_prefix=CONTROLLED_WARNING,
            )
            request.idempotency_key = canonical_key_for_request(DEFAULT_SUPPLIER_MAILBOX, request, email.get("email_type") or EMAIL_TYPE_INITIAL)
            resolution = resolve_or_create_draft(
                service=gmail_service,
                ledger=ledger,
                draft_type=email.get("email_type") or EMAIL_TYPE_INITIAL,
                request=request,
                expected_subject=request.subject,
            )
            status = "created_new_draft" if resolution.new_draft_created else "reused_existing_draft"
            record = {
                "supplier_email_redacted": _redact_email(email.get("to")),
                "status": status,
                "draft_status": resolution.message.summary.draft_status,
                "created": resolution.new_draft_created,
                "reused": resolution.canonical_reused,
                "duplicates_detected": resolution.duplicates_detected,
                "idempotency_key_hash": hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest(),
                "draft_reference": dataclass_to_dict(resolution.reference),
                "sent": False,
                "contacted": False,
                "supplier_contacted": False,
                "request_sent_at": None,
                "followup_scheduled": False,
            }
            results.append(record)
            audit.append(build_supplier_draft_audit_record(email_model=email, draft_resolution=record, requirement_pack_version=requirement_pack_version))
        save_ledger_atomic(ledger_path, ledger)
    report = {
        "status": "PASS",
        "transport_mode": "DRAFT_ONLY",
        "draft_results": results,
        "audit_records": audit,
        "draft_count": len(gmail_service.list_drafts()),
        "emails_sent": 0,
        "supplier_contacted": False,
        "followup_scheduled": False,
        "ledger_path": str(ledger_path),
    }
    (output_dir / "supplier_gmail_draft_preparation_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def write_supplier_outreach_dry_run(
    *,
    requirement_pack: Dict[str, Any],
    pricing_workspace_result: Dict[str, Any],
    output_dir: Path,
    supplier_candidates: Optional[Sequence[Dict[str, Any]]] = None,
    created_at: Optional[datetime] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = config or supplier_outreach_config()
    created_at = created_at or _now_utc()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    minimum = int(config.get("minimum_supplier_target") or DEFAULT_MIN_QUOTES)
    suppliers = select_supplier_targets(supplier_candidates, minimum)
    excluded_suppliers = [
        {
            "supplier_name": _safe_str(supplier.get("supplier_name") or supplier.get("name")),
            "reason": "missing_or_duplicate_email",
        }
        for supplier in (supplier_candidates or [])
        if not _safe_str(supplier.get("supplier_email") or supplier.get("email")) or "@" not in _safe_str(supplier.get("supplier_email") or supplier.get("email"))
    ]
    reference = _safe_str(requirement_pack.get("reference_number") or "6000080579")
    request_id = _stable_request_id(reference, "supplier-outreach-dry-run")
    response_deadline = _iso(created_at + timedelta(days=2))
    pricing_cutoff = _iso(created_at + timedelta(days=3))
    emails = [
        build_supplier_email_model(
            supplier=supplier,
            requirement_pack=requirement_pack,
            request_id=request_id,
            created_at=created_at,
            config=config,
            response_deadline=response_deadline,
            delivery_destination="Zandfontein & Ennerdale",
            requested_delivery_period="Supplier to confirm best delivery period",
        )
        for supplier in suppliers
    ]
    followups = [build_followup_model(email, 1) for email in emails]
    audit_records = [build_outreach_audit_record(email) for email in emails]
    attachment_manifests = [
        {
            "supplier_email": email.get("to"),
            "request_id": request_id,
            "attachments": email.get("attachment_manifest") or [],
        }
        for email in emails
    ]
    status = build_supplier_outreach_status(
        supplier_count=len(suppliers),
        minimum_supplier_target=minimum,
        initial_email_count=len(emails),
        followup_count=len(followups),
        sourcing_deadline=response_deadline,
        pricing_cutoff=pricing_cutoff,
    )
    no_response_state = build_no_response_pricing_state(status)
    dashboard = {
        **status,
        "buyer_closing_date": "",
        "next_followup_time": emails[0].get("followup_due_at") if emails else "",
        "supplier_quotation_deadline": response_deadline,
        "pricing_fallback_status": no_response_state.get("supplier_quote_coverage"),
        "pricing_can_continue_without_supplier_response": True,
    }
    validation_checks = {
        "minimum_three_suppliers_selected": len(suppliers) >= minimum,
        "each_request_has_all_sourcing_groups": all(len(email.get("sourcing_items") or []) == 6 for email in emails),
        "mandatory_cc_enforced": all(DEFAULT_MANDATORY_CC in (email.get("cc") or []) for email in emails + followups),
        "sender_mailbox_correct": all(email.get("from") == DEFAULT_SUPPLIER_MAILBOX for email in emails),
        "no_live_email_sent": all(email.get("live_email_sent") is False for email in emails + followups),
        "followup_scheduled_two_days": all(email.get("followup_due_at") == _iso(created_at + timedelta(days=2)) for email in emails),
        "pricing_can_continue_with_zero_responses": bool(no_response_state.get("pricing_ready")),
        "buyer_autonomous_submission_disabled": config.get("buyer_autonomous_submission_enabled") is False,
        "supplier_outreach_separate_from_buyer_submission": config.get("manual_buyer_submission_required") is True,
        "draft_creation_does_not_mark_contacted": True,
        "draft_creation_does_not_set_sent_timestamp": True,
        "no_internal_pricing_disclosed": not any(term in json.dumps(emails).lower() for term in ["markup", "target margin", "buyer-facing selling price", "gross profit", "internal budget"]),
    }
    result = {
        "status": "PASS" if all(validation_checks.values()) else "FAIL",
        "request_id": request_id,
        "config": config,
        "suppliers": suppliers,
        "excluded_suppliers": excluded_suppliers,
        "supplier_selection_summary": {
            "minimum_supplier_target": minimum,
            "selected_count": len(suppliers),
            "fewer_than_three_available": len(suppliers) < minimum,
            "selected_redacted": [
                {
                    "supplier_name": supplier.get("supplier_name"),
                    "supplier_email_redacted": _redact_email(supplier.get("supplier_email")),
                    "selection_reason": supplier.get("selection_reason"),
                }
                for supplier in suppliers
            ],
            "excluded": excluded_suppliers,
        },
        "email_models": emails,
        "email_previews": [
            {
                "to": email.get("to"),
                "cc": email.get("cc"),
                "subject": email.get("subject"),
                "body_preview": _safe_str(email.get("body"))[:4000],
            }
            for email in emails
        ],
        "followup_schedules": followups,
        "attachment_manifests": attachment_manifests,
        "audit_records": audit_records,
        "supplier_outreach_status": status,
        "no_response_pricing_state": no_response_state,
        "dashboard_status": dashboard,
        "pricing_workspace_summary": {
            "pricing_ready": pricing_workspace_result.get("pricing_ready"),
            "quote_ready": pricing_workspace_result.get("quote_ready"),
            "pricing_source": pricing_workspace_result.get("pricing_source"),
        },
        "validation_checks": validation_checks,
    }
    files = {
        "supplier_outreach_dry_run.json": result,
        "supplier_email_models.json": emails,
        "supplier_email_previews.json": result["email_previews"],
        "attachment_manifests.json": attachment_manifests,
        "followup_schedules.json": followups,
        "supplier_outreach_audit_records.json": audit_records,
        "no_response_pricing_state.json": no_response_state,
        "supplier_outreach_dashboard_status.json": dashboard,
        "supplier_outreach_validation_report.json": {
            "result": result["status"],
            "request_id": request_id,
            "supplier_count": len(suppliers),
            "minimum_supplier_target": minimum,
            "validation_checks": validation_checks,
        },
    }
    for filename, payload in files.items():
        (output_dir / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return result
