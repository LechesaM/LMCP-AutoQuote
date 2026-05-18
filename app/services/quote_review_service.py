from __future__ import annotations

import json
import logging
import multiprocessing
import shutil
import csv
import os
import re
import signal
import threading
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from queue import Empty
from typing import Any, Callable, Dict, Iterable, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.quote_pack_models import QuotePack, QuotePackEditAudit, QuotePackItem, QuotePackStatusHistory, QuoteStatus
from app.quote_pack_service import add_history, generate_quote_number, money
from app.services.operator_auth_service import OperatorContext, operator_audit_payload
from app.services.pricing_engine import PricingEngine
from app.services.rfq_boq_extraction_engine import extract_rfq_boq
from app.services.rfq_document_intelligence import analyse_rfq_documents


logger = logging.getLogger(__name__)

TWOPLACES = Decimal("0.01")
CHECKLIST_STATUSES = {"present", "missing", "not_required", "needs_review"}
REVIEW_RUNTIME_DIR = settings.runtime_dir / "manual_review"
BACKUP_DIR = settings.runtime_dir / "backups"
PILOT_RUNTIME_DIR = REVIEW_RUNTIME_DIR / "pilot_runs"
FAILURE_CATEGORIES = (
    "pdf_extraction",
    "boq_parsing",
    "classification",
    "pricing_mapping",
    "draft_ingestion",
    "compliance_checklist",
    "validation",
    "approval",
    "submission",
)
ALLOWED_PILOT_FILE_EXTENSIONS = {".pdf", ".csv", ".xls", ".xlsx"}
PILOT_PER_RFQ_TIMEOUT_SECONDS = 90
PILOT_MAX_RUNTIME_SECONDS = 900
PILOT_INGESTION_TIMEOUT_SECONDS = 60
PILOT_MAX_PRICING_ROWS = 100
PILOT_MAX_COMPLIANCE_ITEMS = 25
PILOT_MAX_EXTRACTED_TEXT_LENGTH = 12000
PILOT_MAX_DEBUG_FIELD_LENGTH = 1000
DEFAULT_MARGIN_PERCENT = 25.0
TIME_PERIOD_UNITS = {"day", "days", "week", "weeks", "month", "months", "year", "years"}
STANDARD_COMPANY_DOC_KEYS = {
    "csd": "CSD",
    "tax_compliance": "Tax Compliance",
    "bbbee": "BBBEE",
    "company_registration": "Company Registration",
    "bank_confirmation": "Bank Confirmation",
}
FAST_REJECT_REASONS = {
    "excluded_category",
    "compulsory_briefing",
    "low_profit",
    "incomplete_pricing_schedule",
    "no_buyer_pricing_schedule",
    "not_supply_and_delivery",
    "manual_business_decision",
}

PHASE2_ACTIONS = {
    "quote_review_ingest": ("preparer", "admin"),
    "quote_review_view": ("preparer", "reviewer", "submitter", "admin"),
    "quote_review_edit_pricing": ("preparer", "admin"),
    "quote_review_update_compliance": ("reviewer", "admin"),
    "quote_review_mark_manual": ("preparer", "reviewer", "admin"),
    "quote_review_approve": ("reviewer", "admin"),
    "quote_review_reject": ("reviewer", "admin"),
    "quote_review_submit": ("submitter", "admin"),
    "quote_review_pilot_run": ("preparer", "admin"),
    "quote_review_pilot_view": ("preparer", "reviewer", "submitter", "admin"),
    "quote_review_pilot_export": ("preparer", "reviewer", "submitter", "admin"),
}


def _log_event(event: str, **payload: Any) -> None:
    logger.info(json.dumps({"event": event, **payload}, default=str, sort_keys=True))


def _to_decimal(value: Any, default: str = "0.00") -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    text_value = str(value or default).replace(",", "").strip()
    try:
        return Decimal(text_value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal(default).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_text(value: Any, limit: int = 4000) -> str:
    if value is None:
        return ""
    text_value = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text_value[:limit]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=True)


def _json_loads(value: Any) -> Any:
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return None


def _normalise_blob(*parts: Any) -> str:
    return " ".join(_safe_text(part, 12000) for part in parts if _safe_text(part, 12000)).lower()


def _ensure_runtime_dirs() -> None:
    REVIEW_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    PILOT_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def ensure_quote_pack_schema() -> None:
    _ensure_runtime_dirs()
    Base.metadata.create_all(bind=engine)

    statements = [
        "ALTER TYPE quotestatus ADD VALUE IF NOT EXISTS 'NEEDS_MANUAL_REVIEW'",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS buyer_name VARCHAR(255)",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS province VARCHAR(120)",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS delivery_location TEXT",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS closing_date_text VARCHAR(120)",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS briefing_required BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS approval_required BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS validation_override_reason TEXT",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS extraction_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS classification_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS estimated_profit NUMERIC(18,2) NOT NULL DEFAULT 0.00",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS estimated_margin_percent NUMERIC(8,4) NOT NULL DEFAULT 0.00",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS extraction_payload_json TEXT",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS classification_payload_json TEXT",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS pricing_payload_json TEXT",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS validation_payload_json TEXT",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS compliance_payload_json TEXT",
        "ALTER TABLE quote_packs ADD COLUMN IF NOT EXISTS submission_gate_payload_json TEXT",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS supplier_cost NUMERIC(18,2) NOT NULL DEFAULT 0.00",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS delivery_cost NUMERIC(18,2) NOT NULL DEFAULT 0.00",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS margin_percent NUMERIC(8,4) NOT NULL DEFAULT 25.00",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS final_quoted_price NUMERIC(18,2) NOT NULL DEFAULT 0.00",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS buyer_row_code VARCHAR(120)",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS buyer_row_text TEXT",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS mapping_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0",
        "ALTER TABLE quote_pack_items ADD COLUMN IF NOT EXISTS requires_manual_review BOOLEAN NOT NULL DEFAULT FALSE",
    ]

    with engine.begin() as connection:
        for statement in statements:
            try:
                connection.execute(text(statement))
            except Exception as exc:
                logger.debug("Schema statement skipped: %s (%s)", statement, exc)


def _append_action_permissions() -> None:
    from app.services import operator_auth_service as auth

    auth.OPERATOR_ACTION_ALLOWED_ROLES.update(PHASE2_ACTIONS)
    auth.OPERATOR_ACTION_LABELS.update(
        {
            "quote_review_ingest": "prepare RFQ review drafts",
            "quote_review_view": "view RFQ review data",
            "quote_review_edit_pricing": "edit pricing review data",
            "quote_review_update_compliance": "update compliance checklist evidence",
            "quote_review_mark_manual": "mark RFQs for manual review",
            "quote_review_approve": "approve quote drafts",
            "quote_review_reject": "reject quote drafts",
            "quote_review_submit": "submit approved quote drafts",
            "quote_review_pilot_run": "run the controlled RFQ pilot",
            "quote_review_pilot_view": "view controlled RFQ pilot results",
            "quote_review_pilot_export": "export controlled RFQ pilot results",
        }
    )


_append_action_permissions()


def _detect_province(text: str) -> str:
    provinces = (
        "Eastern Cape",
        "Free State",
        "Gauteng",
        "KwaZulu-Natal",
        "Limpopo",
        "Mpumalanga",
        "Northern Cape",
        "North West",
        "Western Cape",
    )
    lowered = text.lower()
    for province in provinces:
        if province.lower() in lowered:
            return province
    return ""


def _extract_delivery_location(text: str) -> str:
    markers = ("delivery to", "delivery address", "place of delivery", "delivery location", "deliver to")
    lowered = text.lower()
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            snippet = text[index : index + 220]
            return snippet.split(".")[0].strip()
    return ""


def _looks_like_supply_delivery_title(text: str) -> bool:
    blob = _normalise_blob(text)
    return "supply" in blob and "delivery" in blob


def _clean_row_quantity(value: Any) -> float:
    quantity = _safe_float(value, 0.0)
    if quantity <= 0:
        return 0.0
    return round(quantity, 4)


def _clean_row_unit(value: Any) -> str:
    return _safe_text(value, 80).strip()


def _row_is_structurally_complete(row: Dict[str, Any]) -> bool:
    return bool(
        _safe_text(row.get("description"), 4000)
        and _clean_row_quantity(row.get("quantity")) > 0
        and _clean_row_unit(row.get("unit"))
    )


def _extract_advert_subject(text: str) -> str:
    candidates = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in candidates:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if len(cleaned) < 18:
            continue
        upper_ratio = sum(1 for char in cleaned if char.isupper()) / max(1, sum(1 for char in cleaned if char.isalpha()))
        if upper_ratio >= 0.6 and "supply" in cleaned.lower() and "delivery" in cleaned.lower():
            return cleaned.title()
    return ""


def _should_create_advert_fallback_row(rfq_data: Dict[str, Any], classification: Dict[str, Any], text_excerpt: str = "") -> bool:
    if str(classification.get("decision") or "").startswith("excluded_"):
        return False
    title_blob = _normalise_blob(rfq_data.get("title"), rfq_data.get("description"), text_excerpt)
    if not _looks_like_supply_delivery_title(title_blob):
        return False
    return not any(term in title_blob for term in ("briefing", "site inspection", "asbestos removal"))


def _build_advert_fallback_row(rfq_data: Dict[str, Any], text_excerpt: str = "") -> Dict[str, Any]:
    buyer_text = _safe_text(
        _extract_advert_subject(text_excerpt)
        or rfq_data.get("title")
        or rfq_data.get("description")
        or "Manual pricing row required",
        4000,
    )
    return {
        "description": buyer_text,
        "quantity": 1.0,
        "unit": "lot",
        "item_code": "",
        "specification": "",
        "confidence": 0.38,
        "evidence": ["advert_title_fallback"],
        "source": "advert_title_fallback",
    }


def _row_review_reasons(row: Dict[str, Any]) -> List[str]:
    reasons = [str(reason) for reason in row.get("manual_review_reasons") or [] if reason]
    return sorted(dict.fromkeys(reasons))


def _build_row_base(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    description = _safe_text(item.get("description"), 4000)
    quantity = _clean_row_quantity(item.get("quantity"))
    unit = _clean_row_unit(item.get("unit"))
    item_code = _safe_text(item.get("item_code"), 120)
    row_confidence = _safe_float(item.get("confidence"), 0.0)
    source = _safe_text(item.get("source"), 255)
    autofilled_fields: List[str] = []
    review_reasons: List[str] = []

    if quantity <= 0 and description:
        quantity = 1.0
        autofilled_fields.append("quantity")
        review_reasons.append("quantity_inferred_default_1")
        row_confidence = max(row_confidence, 0.42)

    if not unit:
        unit = "lot" if source == "advert_title_fallback" else "each"
        autofilled_fields.append("unit")
        review_reasons.append("unit_inferred_default")
        row_confidence = max(row_confidence, 0.42)

    if unit.lower() in TIME_PERIOD_UNITS and "period of" in description.lower():
        review_reasons.append("contract_period_detected")
        row_confidence = min(row_confidence, 0.35)

    if not description:
        review_reasons.append("description_missing")
    if row_confidence < 0.6:
        review_reasons.append("low_mapping_confidence")

    mapping_confidence = round(
        min(
            0.98,
            max(
                row_confidence,
                0.68 if description and quantity > 0 and unit else row_confidence,
            ),
        ),
        4,
    )

    buyer_row_code = item_code or f"ROW-{index:03d}"
    buyer_row_text = description
    structurally_complete = bool(description and quantity > 0 and unit)
    requires_manual_review = bool(review_reasons) or not structurally_complete

    return {
        "row_number": index,
        "buyer_row_code": buyer_row_code,
        "buyer_row_text": buyer_row_text,
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "supplier_cost": 0.0,
        "delivery_cost": 0.0,
        "margin_percent": DEFAULT_MARGIN_PERCENT,
        "unit_price": 0.0,
        "final_quoted_price": 0.0,
        "mapping_confidence": mapping_confidence,
        "pricing_confidence": 0.0,
        "supplier_cost_estimate": 0.0,
        "delivery_cost_estimate": 0.0,
        "recommended_unit_price": 0.0,
        "recommended_total_price": 0.0,
        "pricing_reason": "",
        "source": source,
        "source_pricing": "",
        "requires_manual_review": requires_manual_review,
        "manual_review_reasons": _row_review_reasons({"manual_review_reasons": review_reasons}),
        "autofilled_fields": autofilled_fields,
        "notes": "",
    }


def _apply_pricing_suggestions(
    rows: List[Dict[str, Any]],
    rfq_data: Dict[str, Any],
) -> Dict[str, Any]:
    if not rows:
        return {
            "rows": [],
            "overall_confidence": 0.0,
            "suggested_total_quote": 0.0,
            "suggested_total_profit": 0.0,
            "suggested_margin_percent": 0.0,
            "minimum_required_quote_total": float(settings.minimum_profit_margin_zar),
            "pricing_autofill_status": "manual_pricing_required",
            "confidence_summary": {"high": 0, "medium": 0, "low": 0},
        }

    pricing_payload = {
        "title": _safe_text(rfq_data.get("title"), 255),
        "description": _safe_text(rfq_data.get("description"), 4000),
        "line_items": [
            {
                "description": row.get("buyer_row_text") or row.get("description"),
                "quantity": row.get("quantity") or 1,
                "unit": row.get("unit") or "each",
                "item_code": row.get("buyer_row_code"),
                "supplier_unit_cost": row.get("supplier_cost") or 0,
            }
            for row in rows
        ],
    }
    priced = PricingEngine.price_rfq(
        rfq_payload=pricing_payload,
        supplier_quotes=[],
        pricing_context={
            "min_margin": settings.minimum_supply_margin_ratio,
            "min_profit_total": settings.minimum_profit_margin_zar,
            "include_vat": False,
        },
    )
    line_results = priced.get("line_items") or []
    summary = priced.get("pricing_summary") or {}
    high = medium = low = 0

    for row, line in zip(rows, line_results):
        supplier_unit_cost = _safe_float(line.get("supplier_unit_cost"), 0.0)
        landed_unit_cost = _safe_float(line.get("landed_unit_cost"), 0.0)
        quantity = _safe_float(line.get("quantity") or row.get("quantity"), 0.0)
        delivery_total = round(max(0.0, landed_unit_cost - supplier_unit_cost) * max(quantity, 0.0), 2)
        source = _safe_text(line.get("source"), 255) or "fallback_estimate"
        recommended_unit_price = round(_safe_float(line.get("selling_unit_price_excl_vat"), 0.0), 2)
        recommended_total_price = round(_safe_float(line.get("line_total_excl_vat"), 0.0), 2)
        margin_percent = round(_safe_float(line.get("margin_percent"), DEFAULT_MARGIN_PERCENT), 2)
        manual_review_reasons = list(row.get("manual_review_reasons") or [])

        if source != "supplier_quote":
            manual_review_reasons.append("estimated_supplier_cost")
            pricing_confidence = round(max(0.35, min(0.68, row["mapping_confidence"] * 0.9)), 4)
            pricing_reason = "Heuristic supplier cost estimate applied; operator review required before approval."
        else:
            pricing_confidence = round(max(0.72, min(0.95, row["mapping_confidence"] + 0.12)), 4)
            pricing_reason = "Mapped against known supplier quote reference."

        if source == "advert_title_fallback":
            pricing_reason = "No buyer pricing table detected; single advert title row priced for manual review."

        if recommended_unit_price <= 0:
            manual_review_reasons.append("recommended_price_missing")

        row.update(
            {
                "supplier_cost_estimate": round(supplier_unit_cost, 2),
                "delivery_cost_estimate": delivery_total,
                "recommended_unit_price": recommended_unit_price,
                "recommended_total_price": recommended_total_price,
                "pricing_confidence": pricing_confidence,
                "pricing_reason": pricing_reason,
                "source_pricing": source,
                "supplier_cost": round(supplier_unit_cost, 2),
                "delivery_cost": delivery_total,
                "margin_percent": margin_percent,
                "unit_price": recommended_unit_price,
                "final_quoted_price": recommended_unit_price,
                "requires_manual_review": bool(manual_review_reasons),
                "manual_review_reasons": _row_review_reasons({"manual_review_reasons": manual_review_reasons}),
                "notes": _safe_text(pricing_reason, 1000),
            }
        )

        if pricing_confidence >= 0.8:
            high += 1
        elif pricing_confidence >= 0.6:
            medium += 1
        else:
            low += 1

    completed_rows = [row["row_number"] for row in rows if _row_is_structurally_complete(row) and row.get("recommended_unit_price", 0) > 0]
    unmapped_rows = [
        row["row_number"]
        for row in rows
        if not _row_is_structurally_complete(row) or _safe_float(row.get("recommended_unit_price"), 0.0) <= 0.0
    ]
    review_rows = [row["row_number"] for row in rows if bool(row.get("requires_manual_review"))]
    autofill_status = "fully_autofilled" if rows and not unmapped_rows else ("partially_autofilled" if completed_rows else "manual_pricing_required")
    overall_confidence = round(sum(_safe_float(row.get("pricing_confidence"), 0.0) for row in rows) / max(len(rows), 1), 4)

    return {
        "rows": rows,
        "unmapped_rows": unmapped_rows,
        "review_rows": review_rows,
        "completed_rows": completed_rows,
        "overall_confidence": overall_confidence,
        "suggested_total_quote": round(_safe_float(summary.get("total_sell_excl_vat"), 0.0), 2),
        "suggested_total_profit": round(_safe_float(summary.get("total_profit"), 0.0), 2),
        "suggested_margin_percent": round(_safe_float(summary.get("achieved_margin_percent"), 0.0), 2),
        "minimum_required_quote_total": round(
            max(
                _safe_float(summary.get("minimum_profit_required"), 0.0),
                _safe_float(summary.get("total_cost_excl_vat"), 0.0) / max(1.0 - settings.minimum_supply_margin_ratio, 0.01),
            ),
            2,
        ),
        "pricing_autofill_status": autofill_status,
        "confidence_summary": {"high": high, "medium": medium, "low": low},
    }


def _extract_compliance_requirements(doc_result: Dict[str, Any]) -> List[str]:
    intelligence = doc_result.get("document_intelligence") if isinstance(doc_result, dict) else {}
    requirements: List[str] = []
    if intelligence.get("csd_mentioned"):
        requirements.append("CSD")
    if intelligence.get("tax_compliance_mentioned"):
        requirements.append("tax compliance")
    if intelligence.get("bbbee_mentioned"):
        requirements.append("BBBEE")
    for form in intelligence.get("sbd_forms_detected") or []:
        requirements.append(str(form))
    return sorted(dict.fromkeys(requirements))


def classify_tender(rfq_data: Dict[str, Any], extraction: Dict[str, Any], boq: Dict[str, Any]) -> Dict[str, Any]:
    text_blob = _normalise_blob(
        rfq_data.get("title"),
        rfq_data.get("description"),
        rfq_data.get("raw_text"),
        extraction.get("document_intelligence"),
        boq.get("boq_context"),
    )

    reasons: List[str] = []
    codes: List[str] = []
    allowed = "supply" in text_blob and "delivery" in text_blob

    exclusion_rules = [
        ("excluded_medical_consumables", ("medical consumables", "pharmaceutical", "clinical", "surgical", "reagents")),
        ("excluded_it_equipment", ("laptop", "desktop", "server", "printer cartridge", "it equipment", "computer", "software licence")),
        ("excluded_petrol_diesel", ("petrol", "diesel", "fuel", "lubricants")),
        ("excluded_catering", ("catering", "refreshments", "meals", "food parcels")),
    ]

    decision = "allowed_supply_and_delivery"
    confidence = 0.55

    for code, terms in exclusion_rules:
        if any(term in text_blob for term in terms):
            decision = code
            codes.append(code)
            reasons.append(code.replace("_", " "))
            confidence = max(confidence, 0.9)

    briefing_required = bool((extraction.get("document_intelligence") or {}).get("compulsory_briefing_required"))
    if briefing_required:
        decision = "excluded_compulsory_briefing"
        codes.append("briefing_required")
        reasons.append("compulsory briefing session detected")
        confidence = max(confidence, 0.95)

    if decision == "allowed_supply_and_delivery" and not allowed:
        decision = "excluded_non_supply_service_construction"
        codes.append("non_supply")
        reasons.append("supply and delivery wording not confirmed")
        confidence = max(confidence, 0.7)

    profit_estimate = _safe_float((rfq_data.get("estimated_profit_signal") or {}).get("estimated_profit"), 0.0)
    if not profit_estimate:
        profit_estimate = max(
            _safe_float(boq.get("line_item_count"), 0.0) * 3500.0,
            settings.minimum_profit_margin_zar if allowed else 0.0,
        )

    eligible = decision == "allowed_supply_and_delivery" and profit_estimate >= settings.minimum_profit_margin_zar
    if not eligible and decision == "allowed_supply_and_delivery":
        decision = "review_profit_threshold"
        codes.append("profit_below_threshold")
        reasons.append("estimated profit below LMCP threshold")

    return {
        "decision": decision,
        "eligible": eligible,
        "reason_codes": codes or (["eligible_supply_delivery"] if eligible else []),
        "reasons": reasons or (["supply and delivery tender accepted"] if eligible else []),
        "confidence": round(confidence, 4),
        "estimated_profit": round(profit_estimate, 2),
        "minimum_profit_required": settings.minimum_profit_margin_zar,
        "minimum_margin_required": settings.minimum_supply_margin_ratio * 100.0,
        "briefing_required": briefing_required,
    }


def build_compliance_checklist(extraction: Dict[str, Any], classification: Dict[str, Any]) -> List[Dict[str, Any]]:
    intelligence = extraction.get("document_intelligence") if isinstance(extraction, dict) else {}
    requirements = {
        "csd": intelligence.get("csd_mentioned", False),
        "tax_compliance": intelligence.get("tax_compliance_mentioned", False),
        "bbbee": intelligence.get("bbbee_mentioned", False),
        "company_registration": True,
        "bank_confirmation": True,
        "municipal_account_or_proof_of_address": "municipal" in _normalise_blob(extraction),
        "sbd_forms": bool(intelligence.get("sbd_forms_detected")),
    }

    labels = {
        "csd": "CSD",
        "tax_compliance": "Tax Compliance",
        "bbbee": "BBBEE",
        "company_registration": "Company Registration",
        "bank_confirmation": "Bank Confirmation",
        "municipal_account_or_proof_of_address": "Municipal Account / Proof of Address",
        "sbd_forms": "SBD Forms",
    }

    checklist: List[Dict[str, Any]] = []
    for key, required in requirements.items():
        status = "needs_review" if required else "not_required"
        checklist.append(
            {
                "key": key,
                "label": labels[key],
                "status": status,
                "reason": "auto-detected requirement" if required else "not referenced in RFQ evidence",
                "source": "document_intelligence",
            }
        )

    if not classification.get("eligible"):
        checklist.append(
            {
                "key": "eligibility_gate",
                "label": "Eligibility Gate",
                "status": "needs_review",
                "reason": ", ".join(classification.get("reasons") or []) or "Eligibility review required",
                "source": "classification",
            }
        )
    return checklist


def map_pricing_schedule_rows(boq: Dict[str, Any], rfq_data: Optional[Dict[str, Any]] = None, classification: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rfq_data = dict(rfq_data or {})
    classification = dict(classification or {})
    source_items = list(boq.get("line_items") or [])
    text_excerpt = str(boq.get("combined_text_excerpt") or "")[:4000]
    manual_pricing_required_reason = _safe_text(boq.get("manual_pricing_required_reason"), 1000)

    if not source_items and _should_create_advert_fallback_row(rfq_data, classification, text_excerpt=text_excerpt):
        source_items = [_build_advert_fallback_row(rfq_data, text_excerpt=text_excerpt)]

    rows = [_build_row_base(item, index) for index, item in enumerate(source_items, start=1)]
    suggestion_summary = _apply_pricing_suggestions(rows, rfq_data)
    rows = suggestion_summary.pop("rows", rows)

    if not rows and not manual_pricing_required_reason:
        manual_pricing_required_reason = "No buyer pricing schedule detected; manual pricing schedule required."

    return {
        "row_count": len(rows),
        "rows": rows,
        "unmapped_rows": suggestion_summary.get("unmapped_rows", []),
        "review_rows": suggestion_summary.get("review_rows", []),
        "completed_rows": suggestion_summary.get("completed_rows", []),
        "manual_pricing_required_reason": manual_pricing_required_reason,
        **suggestion_summary,
    }


def build_extraction_summary(rfq_data: Dict[str, Any]) -> Dict[str, Any]:
    extraction = analyse_rfq_documents(rfq_data)
    enriched_input = dict(rfq_data)
    enriched_input["document_intelligence_result"] = extraction
    boq = extract_rfq_boq(enriched_input)
    classification = classify_tender(rfq_data, extraction, boq)
    pricing = map_pricing_schedule_rows(boq, rfq_data=rfq_data, classification=classification)
    intelligence = extraction.get("document_intelligence") or {}
    date_mentions = intelligence.get("date_mentions") or []
    text_blob = _normalise_blob(rfq_data.get("description"), intelligence)

    structured = {
        "tender_title": _safe_text(rfq_data.get("title") or extraction.get("title") or "Untitled RFQ", 255),
        "buyer_department": _safe_text(rfq_data.get("buyer_name") or rfq_data.get("issuing_entity") or extraction.get("buyer_name"), 255),
        "closing_date": _safe_text(rfq_data.get("closing_date") or (date_mentions[0] if date_mentions else ""), 120),
        "briefing_required": bool(intelligence.get("compulsory_briefing_required")),
        "province": _safe_text(rfq_data.get("province") or _detect_province(text_blob), 120),
        "delivery_location": _safe_text(rfq_data.get("delivery_location") or _extract_delivery_location(text_blob), 500),
        "pricing_schedule_tables": boq.get("boq_context", {}).get("table_count", 0),
        "compliance_requirements": _extract_compliance_requirements(extraction),
        "line_items": boq.get("line_items") or [],
        "pricing_rows": pricing.get("rows") or [],
        "pricing_review_rows": pricing.get("review_rows") or [],
        "confidence_scores": {
            "document_extraction": round(
                max(
                    0.25 if extraction.get("downloads") else 0.0,
                    0.6 if intelligence.get("has_text") else 0.2,
                    0.75 if intelligence.get("pricing_schedule_confidence", 0.0) >= 0.65 else 0.35,
                ),
                4,
            ),
            "boq_extraction": round(_safe_float(boq.get("confidence"), 0.0), 4),
            "classification": round(_safe_float(classification.get("confidence"), 0.0), 4),
            "pricing_mapping": round(_safe_float(pricing.get("overall_confidence"), 0.0), 4),
            "pricing_schedule_confidence": round(_safe_float(intelligence.get("pricing_schedule_confidence"), 0.0), 4),
            "boq_confidence": round(_safe_float(intelligence.get("boq_confidence"), 0.0), 4),
            "commercial_returnables_confidence": round(_safe_float(intelligence.get("commercial_returnables_confidence"), 0.0), 4),
            "technical_document_confidence": round(_safe_float(intelligence.get("technical_document_confidence"), 0.0), 4),
        },
        "source_paths": boq.get("paths") or {},
    }

    return {
        "extraction": extraction,
        "boq": boq,
        "classification": classification,
        "pricing": pricing,
        "structured": structured,
        "compliance_checklist": build_compliance_checklist(extraction, classification),
    }


def recalculate_quote_pack(quote: QuotePack) -> None:
    subtotal = Decimal("0.00")
    total_cost = Decimal("0.00")

    for item in quote.items:
        quantity = money(item.quantity or 0)
        supplier_cost = money(item.supplier_cost or 0)
        delivery_cost = money(item.delivery_cost or 0)
        margin_percent = _to_decimal(item.margin_percent or 0)

        base_cost = money((supplier_cost * quantity) + delivery_cost)
        unit_price = money(item.unit_price or 0)
        final_price = money(item.final_quoted_price or 0)

        if final_price <= Decimal("0.00") and unit_price > Decimal("0.00"):
            final_price = unit_price
        if final_price <= Decimal("0.00") and base_cost > Decimal("0.00") and quantity > Decimal("0.00"):
            final_price = money((base_cost / quantity) * (Decimal("1.00") + (margin_percent / Decimal("100.00"))))

        item.unit_price = final_price
        item.final_quoted_price = final_price
        item.line_total = money(final_price * quantity)

        subtotal += Decimal(item.line_total or 0)
        total_cost += base_cost

        if item.line_total and Decimal(item.line_total or 0) > Decimal("0.00"):
            item.margin_percent = money(((Decimal(item.line_total or 0) - base_cost) / Decimal(item.line_total or 0)) * Decimal("100.00"))

    quote.subtotal = money(subtotal)
    vat_rate = Decimal(quote.vat_rate or Decimal("0.15"))
    quote.vat_amount = money(subtotal * vat_rate)
    quote.total_amount = money(quote.subtotal + quote.vat_amount)
    estimated_profit = money(subtotal - total_cost)
    quote.estimated_profit = estimated_profit
    if subtotal > Decimal("0.00"):
        quote.estimated_margin_percent = money((estimated_profit / subtotal) * Decimal("100.00"))
    else:
        quote.estimated_margin_percent = Decimal("0.00")


def _quote_pack_json_payload(quote: QuotePack) -> Dict[str, Any]:
    return {
        "extraction": _json_loads(quote.extraction_payload_json) or {},
        "classification": _json_loads(quote.classification_payload_json) or {},
        "pricing": _json_loads(quote.pricing_payload_json) or {},
        "validation": _json_loads(quote.validation_payload_json) or {},
        "compliance": _json_loads(quote.compliance_payload_json) or [],
        "submission_gate": _json_loads(quote.submission_gate_payload_json) or {},
    }


def _pricing_payload_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _pricing_row_lookup(payload: Dict[str, Any], row_number: int) -> Dict[str, Any]:
    for row in _pricing_payload_rows(payload):
        if int(row.get("row_number") or 0) == int(row_number):
            return row
    return {}


def _minimum_quote_guidance(quote: QuotePack) -> Dict[str, Any]:
    total_supplier_cost = Decimal("0.00")
    current_quote_total = Decimal(quote.subtotal or 0)
    per_row_guidance: List[Dict[str, Any]] = []

    for item in quote.items:
        quantity = _to_decimal(item.quantity or 0)
        supplier_cost = _to_decimal(item.supplier_cost or 0)
        delivery_cost = _to_decimal(item.delivery_cost or 0)
        line_cost_total = money((supplier_cost * quantity) + delivery_cost)
        total_supplier_cost += line_cost_total

        minimum_margin_unit_price = Decimal("0.00")
        if quantity > Decimal("0.00"):
            minimum_margin_unit_price = money((line_cost_total / quantity) / Decimal(str(1.0 - settings.minimum_supply_margin_ratio)))
        per_row_guidance.append(
            {
                "row_number": item.item_no,
                "buyer_row_code": item.buyer_row_code,
                "buyer_row_text": item.buyer_row_text or item.description,
                "minimum_margin_unit_price": float(minimum_margin_unit_price),
                "current_unit_price": float(_to_decimal(item.final_quoted_price or item.unit_price or 0)),
            }
        )

    minimum_quote_for_margin = money(total_supplier_cost / Decimal(str(1.0 - settings.minimum_supply_margin_ratio))) if total_supplier_cost > 0 else Decimal("0.00")
    minimum_quote_for_profit = money(total_supplier_cost + Decimal(str(settings.minimum_profit_margin_zar)))
    minimum_required_quote_total = money(max(minimum_quote_for_margin, minimum_quote_for_profit))

    shortfall = money(max(Decimal("0.00"), minimum_required_quote_total - current_quote_total))
    total_quantity = sum((_to_decimal(item.quantity or 0) for item in quote.items), Decimal("0.00"))
    additional_per_unit = money(shortfall / total_quantity) if shortfall > 0 and total_quantity > 0 else Decimal("0.00")

    for row in per_row_guidance:
        row["minimum_recommended_unit_price"] = float(money(Decimal(str(row["minimum_margin_unit_price"])) + additional_per_unit))

    return {
        "total_supplier_cost": float(money(total_supplier_cost)),
        "total_quoted_price": float(money(current_quote_total)),
        "gross_profit": float(money(current_quote_total - total_supplier_cost)),
        "gross_margin_percent": float(money(quote.estimated_margin_percent or 0)),
        "minimum_quote_for_margin": float(minimum_quote_for_margin),
        "minimum_quote_for_profit": float(minimum_quote_for_profit),
        "minimum_required_quote_total": float(minimum_required_quote_total),
        "required_quote_shortfall": float(shortfall),
        "required_unit_prices": per_row_guidance,
    }


def _serialise_quote_pricing_payload(quote: QuotePack) -> Dict[str, Any]:
    existing_payload = _json_loads(quote.pricing_payload_json) or {}
    rows = []
    for row in quote.items:
        notes = row.notes or ""
        existing_row = _pricing_row_lookup(existing_payload, row.item_no)
        reasons = [str(reason) for reason in existing_row.get("manual_review_reasons") or [] if reason]
        if "operator review required" in notes.lower() and "estimated_supplier_cost" not in reasons:
            reasons.append("estimated_supplier_cost")
        if row.requires_manual_review and not reasons:
            reasons.append("manual_review_required")
        rows.append(
            {
                "row_number": row.item_no,
                "buyer_row_code": row.buyer_row_code,
                "buyer_row_text": row.buyer_row_text,
                "description": row.description,
                "quantity": float(row.quantity or 0),
                "unit": row.unit,
                "supplier_cost": float(row.supplier_cost or 0),
                "delivery_cost": float(row.delivery_cost or 0),
                "margin_percent": float(row.margin_percent or 0),
                "unit_price": float(row.unit_price or 0),
                "final_quoted_price": float(row.final_quoted_price or 0),
                "recommended_unit_price": float(row.final_quoted_price or row.unit_price or 0),
                "recommended_total_price": float(row.line_total or 0),
                "supplier_cost_estimate": float(row.supplier_cost or 0),
                "delivery_cost_estimate": float(row.delivery_cost or 0),
                "mapping_confidence": float(row.mapping_confidence or 0),
                "pricing_confidence": float(existing_row.get("pricing_confidence", row.mapping_confidence or 0)),
                "requires_manual_review": bool(row.requires_manual_review),
                "manual_review_reasons": sorted(dict.fromkeys(reasons)),
                "pricing_reason": existing_row.get("pricing_reason") or notes,
                "notes": notes,
                "source_pricing": existing_row.get("source_pricing") or "",
            }
        )

    guidance = _minimum_quote_guidance(quote)
    review_rows = [row["row_number"] for row in rows if row["requires_manual_review"]]
    completed_rows = [row["row_number"] for row in rows if _row_is_structurally_complete(row) and row["recommended_unit_price"] > 0]
    unmapped_rows = [row["row_number"] for row in rows if row["recommended_unit_price"] <= 0 or not _row_is_structurally_complete(row)]
    return {
        "row_count": len(rows),
        "rows": rows,
        "unmapped_rows": unmapped_rows,
        "review_rows": review_rows,
        "completed_rows": completed_rows,
        "overall_confidence": round(sum(float(row["mapping_confidence"]) for row in rows) / max(len(rows), 1), 4) if rows else 0.0,
        "suggested_total_quote": guidance["total_quoted_price"],
        "suggested_total_profit": guidance["gross_profit"],
        "suggested_margin_percent": guidance["gross_margin_percent"],
        "minimum_required_quote_total": guidance["minimum_required_quote_total"],
        "pricing_autofill_status": "fully_autofilled" if rows and not unmapped_rows else ("partially_autofilled" if completed_rows else "manual_pricing_required"),
        "manual_pricing_required_reason": existing_payload.get("manual_pricing_required_reason", ""),
        "confidence_summary": {
            "high": sum(1 for row in rows if float(row["mapping_confidence"]) >= 0.8),
            "medium": sum(1 for row in rows if 0.6 <= float(row["mapping_confidence"]) < 0.8),
            "low": sum(1 for row in rows if float(row["mapping_confidence"]) < 0.6),
        },
    }


def validate_quote_pack(quote: QuotePack) -> Dict[str, Any]:
    classification = _json_loads(quote.classification_payload_json) or {}
    compliance = _json_loads(quote.compliance_payload_json) or []
    pricing_payload = _json_loads(quote.pricing_payload_json) or {}

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    margin_pct = _safe_float(quote.estimated_margin_percent, 0.0)
    profit = _safe_float(quote.estimated_profit, 0.0)

    if margin_pct < settings.minimum_supply_margin_ratio * 100.0:
        errors.append({"code": "margin_below_minimum", "message": "Estimated margin is below 25%."})
    if profit < settings.minimum_profit_margin_zar:
        errors.append({"code": "profit_below_minimum", "message": "Estimated profit is below R30,000."})
    if classification.get("decision", "").startswith("excluded_"):
        errors.append({"code": "excluded_tender", "message": ", ".join(classification.get("reasons") or ["Tender is excluded."])})
    if quote.briefing_required:
        errors.append({"code": "compulsory_briefing", "message": "Compulsory briefing session detected."})
    if not quote.items:
        empty_message = pricing_payload.get("manual_pricing_required_reason") or "No pricing schedule rows were extracted."
        errors.append({"code": "pricing_schedule_empty", "message": empty_message})

    incomplete_rows = []
    for item in quote.items:
        if (
            _to_decimal(item.final_quoted_price or 0) <= Decimal("0.00")
            or _to_decimal(item.quantity or 0) <= Decimal("0.00")
            or not _safe_text(item.unit, 50)
            or not _safe_text(item.description, 4000)
        ):
            incomplete_rows.append(item.item_no)
        if bool(item.requires_manual_review):
            warnings.append({"code": "manual_review_required", "message": f"Pricing row {item.item_no} requires manual review."})

    if incomplete_rows:
        errors.append({"code": "pricing_schedule_incomplete", "message": f"Pricing schedule rows incomplete: {incomplete_rows}"})

    missing_documents = [item["label"] for item in compliance if item.get("status") == "missing"]
    if missing_documents:
        errors.append({"code": "required_documents_missing", "message": f"Required documents missing: {', '.join(missing_documents)}"})

    needs_review = [item["label"] for item in compliance if item.get("status") == "needs_review"]
    if needs_review:
        warnings.append({"code": "compliance_needs_review", "message": f"Compliance items need review: {', '.join(needs_review)}"})

    guidance = _minimum_quote_guidance(quote)
    ready_for_approval = not errors
    ready_for_submission = ready_for_approval and quote.status == QuoteStatus.APPROVED
    result = {
        "status": "ok" if not errors else "blocked",
        "ready_for_approval": ready_for_approval,
        "ready_for_submission": ready_for_submission,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "estimated_margin_percent": round(margin_pct, 2),
            "estimated_profit": round(profit, 2),
            "line_item_count": len(quote.items),
            "total_supplier_cost": guidance["total_supplier_cost"],
            "total_quoted_price": guidance["total_quoted_price"],
            "gross_profit": guidance["gross_profit"],
            "gross_margin_percent": guidance["gross_margin_percent"],
            "minimum_quote_for_margin": guidance["minimum_quote_for_margin"],
            "minimum_quote_for_profit": guidance["minimum_quote_for_profit"],
            "minimum_required_quote_total": guidance["minimum_required_quote_total"],
            "required_quote_shortfall": guidance["required_quote_shortfall"],
            "required_unit_prices": guidance["required_unit_prices"],
            "pricing_rows_total": len(quote.items),
            "pricing_rows_completed": len(pricing_payload.get("completed_rows") or [row.item_no for row in quote.items if _to_decimal(row.final_quoted_price or 0) > 0]),
            "pricing_rows_needing_review": len(pricing_payload.get("review_rows") or [row.item_no for row in quote.items if row.requires_manual_review]),
            "pricing_confidence_summary": pricing_payload.get("confidence_summary") or {},
        },
    }
    quote.validation_payload_json = _json_dumps(result)
    return result


def review_queue_priority(record: Dict[str, Any]) -> float:
    blocked = 1 if record.get("validation_status") != "ok" else 0
    excluded = 1 if str(record.get("classification_result") or "").startswith("excluded_") else 0
    missing_pricing = 1 if int(record.get("pricing_rows_total") or 0) == 0 else 0
    pricing_review_rows = int(record.get("pricing_rows_needing_review") or 0)
    missing_compliance = int(record.get("compliance_missing_count") or 0)
    needs_review_compliance = int(record.get("compliance_needs_review_count") or 0)
    profit_shortfall = max(0.0, settings.minimum_profit_margin_zar - _safe_float(record.get("estimated_profit"), 0.0))
    margin_shortfall = max(0.0, settings.minimum_supply_margin_ratio * 100.0 - _safe_float(record.get("margin_percent"), 0.0))
    closing_bonus = 0.0
    closing_text = _safe_text(record.get("closing_date"), 120)
    if closing_text:
        closing_bonus = -0.05
    return round(
        excluded * 1000
        + blocked * 120
        + missing_pricing * 80
        + pricing_review_rows * 3.5
        + missing_compliance * 9
        + needs_review_compliance * 2
        + min(200.0, profit_shortfall / 1000.0)
        + margin_shortfall
        + closing_bonus,
        4,
    )


def review_queue_next_action(record: Dict[str, Any]) -> str:
    if str(record.get("classification_result") or "").startswith("excluded_"):
        return "Reject excluded tender"
    if "pricing_schedule_empty" in (record.get("validation_error_codes") or []):
        return "Build manual pricing schedule"
    if int(record.get("pricing_rows_needing_review") or 0) > 0:
        return "Review and accept pricing suggestions"
    if int(record.get("compliance_missing_count") or 0) > 0:
        return "Upload or confirm required compliance docs"
    if int(record.get("compliance_needs_review_count") or 0) > 0:
        return "Confirm compliance checklist"
    if record.get("approval_ready"):
        return "Ready for approval"
    return "Review validation blockers"


def review_queue_approval_readiness(validation: Dict[str, Any]) -> Dict[str, Any]:
    errors = validation.get("errors") or []
    blocking_reasons = [error.get("message") or error.get("code") for error in errors]
    override_required = [error.get("code") for error in errors if error.get("code") in {"margin_below_minimum", "profit_below_minimum"}]
    return {
        "can_approve": not errors,
        "blocking_reasons": [reason for reason in blocking_reasons if reason],
        "override_required_codes": [code for code in override_required if code],
    }


def build_review_queue_record(quote: QuotePack) -> Dict[str, Any]:
    payload = _quote_pack_json_payload(quote)
    validation = validate_quote_pack(quote)
    pricing = payload.get("pricing") or {}
    compliance = payload.get("compliance") or []
    classification = payload.get("classification") or {}
    readiness = review_queue_approval_readiness(validation)
    record = {
        "quote_pack_id": quote.id,
        "quote_number": quote.quote_number,
        "rfq_filename": _safe_text(quote.project_title, 255),
        "rfq_title": _safe_text(quote.project_title, 255),
        "buyer": _safe_text(quote.buyer_name, 255),
        "province": _safe_text(quote.province, 120),
        "closing_date": _safe_text(quote.closing_date_text, 120),
        "classification_result": _safe_text(classification.get("decision"), 255),
        "pilot_status": "manual-review" if quote.status == QuoteStatus.NEEDS_MANUAL_REVIEW else quote.status.value.lower(),
        "validation_status": validation.get("status"),
        "extraction_confidence": _safe_float(quote.extraction_confidence, 0.0),
        "classification_confidence": _safe_float(quote.classification_confidence, 0.0),
        "pricing_rows_total": int(pricing.get("row_count") or 0),
        "pricing_rows_completed": len(pricing.get("completed_rows") or []),
        "pricing_rows_needing_review": len(pricing.get("review_rows") or pricing.get("unmapped_rows") or []),
        "suggested_total_quote": _safe_float(pricing.get("suggested_total_quote"), _safe_float(quote.subtotal, 0.0)),
        "estimated_profit": _safe_float(quote.estimated_profit, 0.0),
        "margin_percent": _safe_float(quote.estimated_margin_percent, 0.0),
        "compliance_status": _compliance_status(compliance),
        "compliance_missing_count": sum(1 for item in compliance if item.get("status") == "missing"),
        "compliance_needs_review_count": sum(1 for item in compliance if item.get("status") == "needs_review"),
        "approval_ready": readiness["can_approve"],
        "approval_blocking_reasons": readiness["blocking_reasons"],
        "approval_override_required_codes": readiness["override_required_codes"],
        "validation_error_codes": [error.get("code") for error in validation.get("errors") or [] if error.get("code")],
        "profit_qualified": _safe_float(quote.estimated_profit, 0.0) >= settings.minimum_profit_margin_zar,
        "manual_pricing_required_reason": _safe_text(pricing.get("manual_pricing_required_reason"), 255),
        "pricing_autofill_status": _safe_text(pricing.get("pricing_autofill_status"), 120),
        "status": quote.status.value,
    }
    record["easiest_to_approve_score"] = review_queue_priority(record)
    record["next_action"] = review_queue_next_action(record)
    return record


def build_review_detail_payload(quote: QuotePack) -> Dict[str, Any]:
    payload = _quote_pack_json_payload(quote)
    validation = validate_quote_pack(quote)
    queue_record = build_review_queue_record(quote)
    return {
        "queue_summary": queue_record,
        "quote_pack": {
            "quote_pack_id": quote.id,
            "quote_number": quote.quote_number,
            "status": quote.status.value,
            "buyer": quote.buyer_name,
            "province": quote.province,
            "closing_date": quote.closing_date_text,
            "project_title": quote.project_title,
            "rfq_reference": quote.rfq_reference,
        },
        "extraction_summary": payload.get("extraction") or {},
        "classification": {
            **(payload.get("classification") or {}),
            "reasons": (payload.get("classification") or {}).get("reasons") or [],
            "reason_codes": (payload.get("classification") or {}).get("reason_codes") or [],
        },
        "pricing_schedule_rows": payload.get("pricing", {}).get("rows") or [],
        "pricing_suggestions": payload.get("pricing", {}).get("rows") or [],
        "validation": validation,
        "compliance_checklist": payload.get("compliance") or [],
        "approval_readiness": review_queue_approval_readiness(validation),
        "edit_audit_count": len(quote.edit_audits or []),
    }


def _record_edit_audit(
    db: Session,
    quote: QuotePack,
    item: Optional[QuotePackItem],
    action: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    operator: Optional[OperatorContext],
    notes: str = "",
) -> None:
    payload = operator_audit_payload(operator)
    db.add(
        QuotePackEditAudit(
            quote_pack_id=quote.id,
            quote_pack_item_id=item.id if item else None,
            action=action,
            field_name=field_name,
            old_value=_safe_text(old_value, 4000),
            new_value=_safe_text(new_value, 4000),
            operator_id=payload.get("operator_id"),
            operator_name=payload.get("operator_display_name"),
            operator_role=payload.get("operator_role"),
            notes=_safe_text(notes, 4000),
        )
    )


def ingest_rfq_review_draft(
    db: Session,
    rfq_data: Dict[str, Any],
    operator: Optional[OperatorContext],
    precomputed_summary: Optional[Dict[str, Any]] = None,
    ensure_schema: bool = True,
) -> QuotePack:
    start_time = time.monotonic()
    if ensure_schema:
        schema_started = time.monotonic()
        ensure_quote_pack_schema()
        _emit_ingestion_timing("schema_check", time.monotonic() - schema_started)
    summary = precomputed_summary or build_extraction_summary(rfq_data)
    _emit_ingestion_timing("summary_ready", time.monotonic() - start_time, title=_safe_text((summary.get("structured") or {}).get("tender_title"), 255))
    structured = summary["structured"]
    classification = summary["classification"]
    pricing = summary["pricing"]
    compliance_checklist = summary["compliance_checklist"]

    quote_init_started = time.monotonic()
    quote = QuotePack(
        quote_number=generate_quote_number(db),
        client_name=_safe_text(structured.get("buyer_department") or "Unknown Buyer", 255),
        project_title=_safe_text(structured.get("tender_title") or "Untitled RFQ", 255),
        rfq_reference=_safe_text(rfq_data.get("buyer_rfq_number") or rfq_data.get("rfq_reference"), 255) or None,
        company_name=settings.your_company_name,
        company_email=settings.your_contact_email or None,
        company_phone=settings.your_contact_phone or None,
        company_address=settings.your_location or None,
        notes="Manual review draft created from RFQ intelligence.",
        created_by=operator.display_name if operator else _safe_text(rfq_data.get("created_by"), 255) or None,
        buyer_name=_safe_text(structured.get("buyer_department"), 255) or None,
        province=_safe_text(structured.get("province"), 120) or None,
        delivery_location=_safe_text(structured.get("delivery_location"), 1000) or None,
        closing_date_text=_safe_text(structured.get("closing_date"), 120) or None,
        briefing_required=bool(structured.get("briefing_required")),
        approval_required=True,
        extraction_confidence=_safe_float((structured.get("confidence_scores") or {}).get("document_extraction"), 0.0),
        classification_confidence=_safe_float((structured.get("confidence_scores") or {}).get("classification"), 0.0),
        extraction_payload_json=_json_dumps(summary["extraction"]),
        classification_payload_json=_json_dumps(classification),
        pricing_payload_json=_json_dumps(pricing),
        compliance_payload_json=_json_dumps(compliance_checklist),
        submission_gate_payload_json=_json_dumps({"approval_required": True, "manual_only": True}),
        status=QuoteStatus.NEEDS_MANUAL_REVIEW if (not classification.get("eligible") or pricing.get("review_rows") or pricing.get("manual_pricing_required_reason")) else QuoteStatus.DRAFT,
    )
    _emit_ingestion_timing(
        "quote_pack_creation",
        time.monotonic() - quote_init_started,
        pricing_rows=len(pricing.get("rows") or []),
        compliance_items=len(compliance_checklist or []),
        extraction_payload_bytes=len(quote.extraction_payload_json or ""),
    )

    header_flush_started = time.monotonic()
    db.add(quote)
    db.flush()
    _emit_ingestion_timing("header_flush", time.monotonic() - header_flush_started, quote_number=quote.quote_number)

    item_loop_started = time.monotonic()
    for index, row in enumerate(pricing.get("rows") or [], start=1):
        db.add(
            QuotePackItem(
                quote_pack_id=quote.id,
                item_no=index,
                description=_safe_text(row.get("description"), 4000),
                unit=_safe_text(row.get("unit"), 50) or "each",
                quantity=_to_decimal(row.get("quantity") or 0),
                unit_price=_to_decimal(row.get("unit_price") or 0),
                line_total=_to_decimal("0.00"),
                supplier_cost=_to_decimal(row.get("supplier_cost") or 0),
                delivery_cost=_to_decimal(row.get("delivery_cost") or 0),
                margin_percent=_to_decimal(row.get("margin_percent") or settings.minimum_supply_margin_ratio * 100.0),
                final_quoted_price=_to_decimal(row.get("final_quoted_price") or 0),
                buyer_row_code=_safe_text(row.get("buyer_row_code"), 120) or None,
                buyer_row_text=_safe_text(row.get("buyer_row_text"), 4000) or None,
                notes=_safe_text(row.get("notes"), 4000) or None,
                mapping_confidence=_safe_float(row.get("mapping_confidence"), 0.0),
                requires_manual_review=bool(row.get("requires_manual_review")),
            )
        )
    _emit_ingestion_timing("item_insert_loop", time.monotonic() - item_loop_started, item_count=len(pricing.get("rows") or []))

    item_flush_started = time.monotonic()
    db.flush()
    db.refresh(quote)
    _emit_ingestion_timing("item_flush_refresh", time.monotonic() - item_flush_started, quote_id=quote.id)
    _emit_ingestion_timing("compliance_checklist_creation", 0.0, compliance_items=len(compliance_checklist or []))
    validation_started = time.monotonic()
    recalculate_quote_pack(quote)
    validate_quote_pack(quote)
    quote.pricing_payload_json = _json_dumps(_serialise_quote_pricing_payload(quote))
    _emit_ingestion_timing("validation_creation", time.monotonic() - validation_started, quote_id=quote.id, validation_bytes=len(quote.validation_payload_json or ""))
    add_history(
        db=db,
        quote=quote,
        from_status=None,
        to_status=quote.status.value,
        action_by=operator.display_name if operator else None,
        comment="RFQ review draft created",
    )
    commit_started = time.monotonic()
    db.commit()
    db.refresh(quote)
    _emit_ingestion_timing("db_commit_refresh", time.monotonic() - commit_started, quote_id=quote.id)
    _emit_ingestion_timing("draft_ingestion_total", time.monotonic() - start_time, quote_id=quote.id)
    _log_event("rfq_upload", quote_pack_id=quote.id, operator=operator_audit_payload(operator), rfq_reference=quote.rfq_reference)
    _log_event("rfq_extraction", quote_pack_id=quote.id, extraction_confidence=quote.extraction_confidence)
    _log_event("pricing_mapping", quote_pack_id=quote.id, row_count=len(quote.items), overall_confidence=pricing.get("overall_confidence"))
    _log_event("quote_generation", quote_pack_id=quote.id, estimated_profit=str(quote.estimated_profit), estimated_margin_percent=str(quote.estimated_margin_percent))
    return quote


def _build_skip_ingestion_validation(summary: Dict[str, Any]) -> Dict[str, Any]:
    structured = summary.get("structured") or {}
    classification = summary.get("classification") or {}
    pricing = summary.get("pricing") or {}
    compliance = summary.get("compliance_checklist") or []

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if str(classification.get("decision") or "").startswith("excluded_"):
        errors.append({"code": "excluded_tender", "message": ", ".join(classification.get("reasons") or ["Tender is excluded."])})
    if structured.get("briefing_required"):
        errors.append({"code": "compulsory_briefing", "message": "Compulsory briefing session detected."})
    if not pricing.get("row_count"):
        errors.append({"code": "pricing_schedule_empty", "message": pricing.get("manual_pricing_required_reason") or "No pricing schedule rows were extracted."})

    missing_documents = [item.get("label") for item in compliance if item.get("status") == "missing" and item.get("label")]
    if missing_documents:
        errors.append({"code": "required_documents_missing", "message": f"Required documents missing: {', '.join(missing_documents)}"})

    needs_review = [item.get("label") for item in compliance if item.get("status") == "needs_review" and item.get("label")]
    if needs_review:
        warnings.append({"code": "compliance_needs_review", "message": f"Compliance items need review: {', '.join(needs_review)}"})
    for row_no in pricing.get("review_rows") or []:
        warnings.append({"code": "manual_review_required", "message": f"Pricing row {row_no} requires manual review."})

    return {
        "status": "ok" if not errors else "blocked",
        "ready_for_approval": not errors,
        "ready_for_submission": False,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "estimated_margin_percent": _safe_float(pricing.get("suggested_margin_percent"), 0.0),
            "estimated_profit": _safe_float(pricing.get("suggested_total_profit"), 0.0),
            "line_item_count": int(pricing.get("row_count") or 0),
            "pricing_rows_total": int(pricing.get("row_count") or 0),
            "pricing_rows_completed": len(pricing.get("completed_rows") or []),
            "pricing_rows_needing_review": len(pricing.get("review_rows") or []),
            "suggested_total_quote": _safe_float(pricing.get("suggested_total_quote"), 0.0),
            "suggested_total_profit": _safe_float(pricing.get("suggested_total_profit"), 0.0),
            "suggested_margin_percent": _safe_float(pricing.get("suggested_margin_percent"), 0.0),
            "minimum_required_quote_total": _safe_float(pricing.get("minimum_required_quote_total"), 0.0),
            "pricing_confidence_summary": pricing.get("confidence_summary") or {},
        },
    }


def _process_single_pilot_rfq(
    db: Optional[Session],
    rfq_entry: Dict[str, Any],
    operator: Optional[OperatorContext],
    *,
    run_id: str,
    rfq_index: int,
    skip_ingestion: bool,
    ingestion_timeout_seconds: int,
    max_pilot_pricing_rows: int,
    continue_on_timeout: bool,
    progress_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    rfq_data = dict(rfq_entry.get("rfq_data") or {})
    human_notes = _safe_text(rfq_entry.get("human_notes"), 4000)
    rfq_filename = _safe_text(rfq_entry.get("rfq_filename") or Path(_safe_text(rfq_entry.get("rfq_path")) or "rfq").name, 255)

    _write_rfq_progress_artifact(
        run_id,
        rfq_index,
        {
            "run_id": run_id,
            "rfq_index": rfq_index,
            "rfq_filename": rfq_filename,
            "rfq_path": _safe_text(rfq_entry.get("rfq_path"), 2000),
            "status": "in_progress",
            "current_stage": "rfq_start",
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    _emit_pilot_progress(progress_callback, "rfq_start", "start", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)

    processing_error = ""
    quote: Optional[QuotePack] = None

    _emit_pilot_progress(progress_callback, "extraction", "start", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)
    extracted_summary = build_extraction_summary(rfq_data)
    _write_rfq_progress_artifact(
        run_id,
        rfq_index,
        {
            "run_id": run_id,
            "rfq_index": rfq_index,
            "rfq_filename": rfq_filename,
            "status": "in_progress",
            "current_stage": "extraction_complete",
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    _emit_pilot_progress(progress_callback, "extraction", "end", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)

    summary: Dict[str, Any] = {
        "structured": extracted_summary.get("structured") or {},
        "classification": extracted_summary.get("classification") or {},
        "pricing": extracted_summary.get("pricing") or {},
        "compliance_checklist": extracted_summary.get("compliance_checklist") or [],
        "extraction": extracted_summary.get("extraction") or {},
        "boq": extracted_summary.get("boq") or {},
    }
    prepared_summary = _prepare_summary_for_pilot_ingestion(summary, max_pricing_rows=max_pilot_pricing_rows)
    classification_decision = _safe_text((summary.get("classification") or {}).get("decision"), 255)

    if skip_ingestion or classification_decision.startswith("excluded_"):
        if classification_decision.startswith("excluded_") and not skip_ingestion:
            _emit_pilot_progress(progress_callback, "draft_ingestion", "skipped", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename, reason="excluded_tender")
        validation = _build_skip_ingestion_validation(summary)
    else:
        if db is None:
            raise ValueError("Database session is required when ingestion is enabled.")
        _emit_pilot_progress(progress_callback, "draft_ingestion", "start", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)
        _write_rfq_progress_artifact(
            run_id,
            rfq_index,
            {
                "run_id": run_id,
                "rfq_index": rfq_index,
                "rfq_filename": rfq_filename,
                "status": "in_progress",
                "current_stage": "draft_ingestion_start",
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        try:
            quote = _run_draft_ingestion_with_timeout(
                db,
                rfq_data,
                operator,
                prepared_summary,
                ingestion_timeout_seconds,
            )
        except DraftIngestionTimeoutError as exc:
            processing_error = _safe_text(exc, 1000)
            _write_rfq_progress_artifact(
                run_id,
                rfq_index,
                {
                    "run_id": run_id,
                    "rfq_index": rfq_index,
                    "rfq_filename": rfq_filename,
                    "status": "failed",
                    "current_stage": "draft_ingestion_timeout",
                    "error": processing_error,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            _emit_pilot_progress(progress_callback, "draft_ingestion", "timeout", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename, error=processing_error)
            validation = {
                "status": "blocked",
                "errors": [{"code": "draft_ingestion_timeout", "message": processing_error}],
                "warnings": [],
                "metrics": {},
            }
            if not continue_on_timeout:
                raise
            record = build_pilot_result_record(
                rfq_entry,
                summary,
                validation,
                quote=None,
                human_notes=human_notes,
                processing_error=processing_error,
                processing_stage="draft_ingestion_timeout",
            )
            record["rfq_index"] = rfq_index
            _emit_pilot_progress(progress_callback, "rfq_start", "end", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename, pilot_status=record.get("pilot_status"))
            return record
        _emit_pilot_progress(progress_callback, "draft_ingestion", "end", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename, quote_pack_id=quote.id)

        summary = {
            "structured": extracted_summary.get("structured") or summary["structured"],
            "classification": _json_loads(quote.classification_payload_json) or extracted_summary.get("classification") or {},
            "pricing": _json_loads(quote.pricing_payload_json) or extracted_summary.get("pricing") or {},
            "compliance_checklist": _json_loads(quote.compliance_payload_json) or extracted_summary.get("compliance_checklist") or [],
            "extraction": _json_loads(quote.extraction_payload_json) or extracted_summary.get("extraction") or {},
            "boq": extracted_summary.get("boq") or {},
        }

        _emit_pilot_progress(progress_callback, "classification", "start", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)
        _emit_pilot_progress(
            progress_callback,
            "classification",
            "end",
            run_id=run_id,
            rfq_index=rfq_index,
            rfq_filename=rfq_filename,
            decision=_safe_text(summary.get("classification", {}).get("decision"), 255),
        )

        _emit_pilot_progress(progress_callback, "validation", "start", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)
        validation = validate_quote_pack(quote)
        _emit_pilot_progress(progress_callback, "validation", "end", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename, status_text=validation.get("status"))

    if skip_ingestion:
        _emit_pilot_progress(progress_callback, "classification", "start", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)
        _emit_pilot_progress(
            progress_callback,
            "classification",
            "end",
            run_id=run_id,
            rfq_index=rfq_index,
            rfq_filename=rfq_filename,
            decision=_safe_text(summary.get("classification", {}).get("decision"), 255),
        )
        _emit_pilot_progress(progress_callback, "validation", "start", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename)
        _emit_pilot_progress(progress_callback, "validation", "end", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename, status_text=validation.get("status"))

    record = build_pilot_result_record(
        rfq_entry,
        summary,
        validation,
        quote=quote,
        human_notes=human_notes,
        processing_error=processing_error,
    )
    record["rfq_index"] = rfq_index
    _write_rfq_progress_artifact(
        run_id,
        rfq_index,
        {
            "run_id": run_id,
            "rfq_index": rfq_index,
            "rfq_filename": rfq_filename,
            "status": "completed",
            "pilot_status": record.get("pilot_status"),
            "quote_pack_id": record.get("quote_pack_id"),
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    _emit_pilot_progress(progress_callback, "rfq_start", "end", run_id=run_id, rfq_index=rfq_index, rfq_filename=rfq_filename, pilot_status=record.get("pilot_status"))
    return record


def list_review_queue(db: Session) -> List[QuotePack]:
    active_statuses = [
        QuoteStatus.DRAFT,
        QuoteStatus.NEEDS_MANUAL_REVIEW,
        QuoteStatus.PENDING_APPROVAL,
        QuoteStatus.APPROVED,
        QuoteStatus.REJECTED,
    ]
    recent = (
        db.query(QuotePack)
        .options(joinedload(QuotePack.items), joinedload(QuotePack.edit_audits), joinedload(QuotePack.history))
        .order_by(QuotePack.id.desc())
        .limit(500)
        .all()
    )
    filtered = [quote for quote in recent if quote.status in active_statuses]
    filtered.sort(key=lambda quote: ((quote.updated_at or quote.created_at), quote.id), reverse=True)
    return filtered[:200]


def list_review_queue_summary(db: Session) -> List[Dict[str, Any]]:
    records = [build_review_queue_record(quote) for quote in list_review_queue(db)]
    ranked = sorted(records, key=lambda record: (record["easiest_to_approve_score"], record["quote_pack_id"]))
    for index, record in enumerate(ranked, start=1):
        record["easiest_to_approve_rank"] = index
    return ranked


def get_review_details(db: Session, quote_id: int) -> QuotePack:
    quote = (
        db.query(QuotePack)
        .options(joinedload(QuotePack.items), joinedload(QuotePack.edit_audits), joinedload(QuotePack.history))
        .filter(QuotePack.id == quote_id)
        .first()
    )
    if not quote:
        raise ValueError("Quotation not found")
    return quote


def get_review_detail_payload(db: Session, quote_id: int) -> Dict[str, Any]:
    return build_review_detail_payload(get_review_details(db, quote_id))


def update_pricing_item(
    db: Session,
    quote: QuotePack,
    item_id: int,
    updates: Dict[str, Any],
    operator: Optional[OperatorContext],
) -> QuotePack:
    item = next((row for row in quote.items if row.id == item_id), None)
    if not item:
        raise ValueError("Quote pack item not found")

    for field_name in ("unit_price", "margin_percent", "supplier_cost", "delivery_cost", "final_quoted_price", "notes", "requires_manual_review"):
        if field_name not in updates or updates[field_name] is None:
            continue
        old_value = getattr(item, field_name)
        new_value = updates[field_name]
        if field_name in {"unit_price", "margin_percent", "supplier_cost", "delivery_cost", "final_quoted_price"}:
            new_value = _to_decimal(new_value)
        if field_name == "requires_manual_review":
            new_value = bool(new_value)
        setattr(item, field_name, new_value)
        _record_edit_audit(db, quote, item, "pricing_edit", field_name, old_value, new_value, operator)

    recalculate_quote_pack(quote)
    validate_quote_pack(quote)
    quote.pricing_payload_json = _json_dumps(_serialise_quote_pricing_payload(quote))
    quote.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(quote)
    _log_event("manual_edit", quote_pack_id=quote.id, item_id=item.id, operator=operator_audit_payload(operator))
    return quote


def accept_suggested_pricing(db: Session, quote: QuotePack, item_id: int, operator: Optional[OperatorContext]) -> QuotePack:
    pricing_payload = _json_loads(quote.pricing_payload_json) or {}
    item = next((row for row in quote.items if row.id == item_id), None)
    if not item:
        raise ValueError("Quote pack item not found")
    suggested = _pricing_row_lookup(pricing_payload, item.item_no)
    if not suggested:
        raise ValueError("No suggested pricing found for this row.")
    suggested_price = _to_decimal(suggested.get("recommended_unit_price") or suggested.get("final_quoted_price") or 0)
    if suggested_price <= Decimal("0.00"):
        raise ValueError("Suggested price is missing for this row.")
    return update_pricing_item(
        db,
        quote,
        item_id,
        {
            "supplier_cost": _to_decimal(suggested.get("supplier_cost_estimate") or suggested.get("supplier_cost") or 0),
            "delivery_cost": _to_decimal(suggested.get("delivery_cost_estimate") or suggested.get("delivery_cost") or 0),
            "margin_percent": _to_decimal(suggested.get("margin_percent") or DEFAULT_MARGIN_PERCENT),
            "final_quoted_price": suggested_price,
            "unit_price": suggested_price,
            "requires_manual_review": False,
            "notes": _safe_text(
                f"Suggested pricing accepted by operator. {suggested.get('pricing_reason') or ''}",
                4000,
            ),
        },
        operator,
    )


def accept_all_suggested_pricing(db: Session, quote: QuotePack, operator: Optional[OperatorContext]) -> QuotePack:
    pricing_payload = _json_loads(quote.pricing_payload_json) or {}
    suggestions = {int(row.get("row_number") or 0): row for row in _pricing_payload_rows(pricing_payload)}
    for item in list(quote.items or []):
        suggested = suggestions.get(int(item.item_no or 0))
        if not suggested:
            continue
        quote = update_pricing_item(
            db,
            quote,
            int(item.id),
            {
                "supplier_cost": _to_decimal(suggested.get("supplier_cost_estimate") or suggested.get("supplier_cost") or 0),
                "delivery_cost": _to_decimal(suggested.get("delivery_cost_estimate") or suggested.get("delivery_cost") or 0),
                "margin_percent": _to_decimal(suggested.get("margin_percent") or DEFAULT_MARGIN_PERCENT),
                "final_quoted_price": _to_decimal(suggested.get("recommended_unit_price") or suggested.get("final_quoted_price") or 0),
                "unit_price": _to_decimal(suggested.get("recommended_unit_price") or suggested.get("final_quoted_price") or 0),
                "requires_manual_review": False,
                "notes": _safe_text(
                    f"Suggested pricing accepted by operator. {suggested.get('pricing_reason') or ''}",
                    4000,
                ),
            },
            operator,
        )
    return quote


def update_compliance_checklist(db: Session, quote: QuotePack, items: List[Dict[str, Any]], operator: Optional[OperatorContext]) -> QuotePack:
    normalised: List[Dict[str, Any]] = []
    for item in items:
        status = _safe_text(item.get("status"), 40).lower()
        if status not in CHECKLIST_STATUSES:
            raise ValueError(f"Unsupported compliance status '{status}'.")
        normalised.append(
            {
                "key": _safe_text(item.get("key"), 120),
                "label": _safe_text(item.get("label"), 255),
                "status": status,
                "reason": _safe_text(item.get("reason"), 1000),
                "source": _safe_text(item.get("source"), 255),
            }
        )

    previous = quote.compliance_payload_json
    quote.compliance_payload_json = _json_dumps(normalised)
    _record_edit_audit(db, quote, None, "compliance_update", "compliance_payload_json", previous, quote.compliance_payload_json, operator)
    validate_quote_pack(quote)
    db.commit()
    db.refresh(quote)
    return quote


def update_single_compliance_item(
    db: Session,
    quote: QuotePack,
    key: str,
    status: str,
    operator: Optional[OperatorContext],
    reason: str = "",
) -> QuotePack:
    items = _json_loads(quote.compliance_payload_json) or []
    updated = False
    for item in items:
        if _safe_text(item.get("key"), 120) == _safe_text(key, 120):
            item["status"] = _safe_text(status, 40).lower()
            if reason:
                item["reason"] = _safe_text(reason, 1000)
            updated = True
            break
    if not updated:
        raise ValueError("Compliance checklist item not found")
    return update_compliance_checklist(db, quote, items, operator)


def bulk_mark_standard_company_docs(
    db: Session,
    quote: QuotePack,
    operator: Optional[OperatorContext],
    status: str = "present",
) -> QuotePack:
    status = _safe_text(status, 40).lower()
    items = _json_loads(quote.compliance_payload_json) or []
    target_labels = set(STANDARD_COMPANY_DOC_KEYS.values())
    changed = False
    for item in items:
        if _safe_text(item.get("label"), 255) in target_labels:
            item["status"] = status
            item["reason"] = f"Bulk updated to {status} during manual review"
            changed = True
    if not changed:
        raise ValueError("No standard company compliance items were found")
    return update_compliance_checklist(db, quote, items, operator)


def mark_needs_manual_review(db: Session, quote: QuotePack, operator: Optional[OperatorContext], comment: str = "") -> QuotePack:
    old_status = quote.status.value if quote.status else None
    quote.status = QuoteStatus.NEEDS_MANUAL_REVIEW
    add_history(db, quote, old_status, quote.status.value, operator.display_name if operator else None, comment or "Marked for manual review")
    db.commit()
    db.refresh(quote)
    _log_event("manual_review_marked", quote_pack_id=quote.id, operator=operator_audit_payload(operator))
    return quote


def approve_quote(db: Session, quote: QuotePack, operator: Optional[OperatorContext], override_validation: bool = False, override_reason: str = "", comment: str = "") -> QuotePack:
    validation = validate_quote_pack(quote)
    blocking = [error for error in validation["errors"] if error["code"] not in {"margin_below_minimum", "profit_below_minimum"}]
    overridable = [error for error in validation["errors"] if error["code"] in {"margin_below_minimum", "profit_below_minimum"}]
    if blocking:
        raise ValueError("; ".join(error["message"] for error in blocking))
    if overridable and not override_validation:
        raise ValueError("Validation override required for margin/profit exceptions.")
    if overridable and operator and _safe_text(operator.role, 40).lower() != "admin":
        raise ValueError("Admin override required for margin/profit exceptions.")
    if overridable and not override_reason:
        raise ValueError("override_reason is required when overriding validation.")

    if override_validation:
        quote.validation_override_reason = override_reason

    old_status = quote.status.value if quote.status else None
    quote.status = QuoteStatus.APPROVED
    quote.approved_by = operator.display_name if operator else None
    add_history(db, quote, old_status, quote.status.value, operator.display_name if operator else None, comment or "Quote approved")
    db.commit()
    db.refresh(quote)
    _log_event("approval", quote_pack_id=quote.id, operator=operator_audit_payload(operator), override=override_validation)
    return quote


def fast_reject_quote(
    db: Session,
    quote: QuotePack,
    operator: Optional[OperatorContext],
    reject_reason_code: str,
    comment: str = "",
) -> QuotePack:
    reject_reason_code = _safe_text(reject_reason_code, 120).lower()
    if reject_reason_code not in FAST_REJECT_REASONS:
        raise ValueError("Unsupported fast reject reason.")
    reason_map = {
        "excluded_category": "Rejected: excluded category",
        "compulsory_briefing": "Rejected: compulsory briefing",
        "low_profit": "Rejected: low profit",
        "incomplete_pricing_schedule": "Rejected: incomplete pricing schedule",
        "no_buyer_pricing_schedule": "Rejected: no buyer pricing schedule",
        "not_supply_and_delivery": "Rejected: not supply and delivery",
        "manual_business_decision": "Rejected: manual business decision",
    }
    return reject_quote(
        db,
        quote,
        operator,
        rejection_reason=reason_map[reject_reason_code],
        comment=comment or reason_map[reject_reason_code],
    )


def reject_quote(db: Session, quote: QuotePack, operator: Optional[OperatorContext], rejection_reason: str, comment: str = "") -> QuotePack:
    old_status = quote.status.value if quote.status else None
    quote.status = QuoteStatus.REJECTED
    quote.rejected_by = operator.display_name if operator else None
    quote.rejection_reason = rejection_reason
    add_history(db, quote, old_status, quote.status.value, operator.display_name if operator else None, comment or rejection_reason)
    db.commit()
    db.refresh(quote)
    _log_event("rejection", quote_pack_id=quote.id, operator=operator_audit_payload(operator), reason=rejection_reason)
    return quote


def submit_quote(db: Session, quote: QuotePack, operator: Optional[OperatorContext], comment: str = "") -> QuotePack:
    validation = validate_quote_pack(quote)
    if quote.status != QuoteStatus.APPROVED:
        raise ValueError("Quote must be approved before submission.")
    if not validation.get("ready_for_submission"):
        raise ValueError("Quote is not ready for submission.")

    old_status = quote.status.value if quote.status else None
    quote.status = QuoteStatus.SENT
    add_history(db, quote, old_status, quote.status.value, operator.display_name if operator else None, comment or "Manual submission released after approval")
    db.commit()
    db.refresh(quote)
    _log_event("submission_attempt", quote_pack_id=quote.id, operator=operator_audit_payload(operator), approved=True)
    return quote


def backup_manual_review_assets() -> Dict[str, Any]:
    ensure_quote_pack_schema()
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    destination = BACKUP_DIR / f"manual_review_backup_{timestamp}"
    destination.mkdir(parents=True, exist_ok=True)

    runtime_snapshot = destination / "runtime_snapshot"
    quote_snapshot = destination / "monthly_quotes_snapshot"
    if settings.runtime_dir.exists():
        shutil.copytree(settings.runtime_dir, runtime_snapshot, dirs_exist_ok=True)
    if settings.monthly_quotes_dir.exists():
        shutil.copytree(settings.monthly_quotes_dir, quote_snapshot, dirs_exist_ok=True)

    db_info = {
        "database_url": settings.database_url,
        "backup_note": "Use pg_dump with the configured DATABASE_URL for a full PostgreSQL backup.",
    }
    db_info_path = destination / "database_backup_instructions.json"
    db_info_path.write_text(_json_dumps(db_info))

    return {
        "status": "ok",
        "backup_dir": str(destination),
        "database_instructions": str(db_info_path),
    }


def _now_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _pilot_run_dir(run_id: str) -> Path:
    _ensure_runtime_dirs()
    return PILOT_RUNTIME_DIR / run_id


def _pilot_json_path(run_id: str) -> Path:
    return _pilot_run_dir(run_id) / "pilot_results.json"


def _pilot_csv_path(run_id: str) -> Path:
    return _pilot_run_dir(run_id) / "pilot_results.csv"


def _pilot_summary_path(run_id: str) -> Path:
    return _pilot_run_dir(run_id) / "pilot_summary.json"


def _pilot_manifest_path(run_id: str) -> Path:
    return _pilot_run_dir(run_id) / "pilot_manifest.json"


def _pilot_failure_path(run_id: str) -> Path:
    return _pilot_run_dir(run_id) / "pilot_failure.json"


def _failure_bucket(category: str, reasons: List[str]) -> Dict[str, Any]:
    return {"category": category, "reasons": [reason for reason in reasons if reason]}


def _looks_like_placeholder_rfq_path(path_text: str) -> bool:
    normalised = _safe_text(path_text, 2000).replace("\\", "/").lower()
    if not normalised:
        return False
    if normalised.startswith("/absolute/path/") or normalised.startswith("/real/absolute/path/"):
        return True
    if "/pilot_rfqs/" in normalised and re.search(r"/rfq_\d{2}\.(pdf|csv|xls|xlsx)$", normalised):
        return True
    return False


def validate_pilot_rfq_entries(rfq_entries: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    selected_entries = list(rfq_entries or [])[: max(1, min(int(limit or 10), 10))]
    if not selected_entries:
        raise ValueError("At least one RFQ entry is required for the pilot.")

    issues: List[Dict[str, Any]] = []
    for index, entry in enumerate(selected_entries, start=1):
        rfq_entry = dict(entry or {})
        rfq_path_raw = _safe_text(rfq_entry.get("rfq_path"), 2000)
        reasons: List[str] = []

        if not rfq_path_raw:
            reasons.append("rfq_path is required")
        elif _looks_like_placeholder_rfq_path(rfq_path_raw):
            reasons.append("placeholder rfq_path detected")

        try:
            resolved_path = Path(rfq_path_raw).expanduser().resolve() if rfq_path_raw else None
        except Exception:
            resolved_path = None
            reasons.append("rfq_path could not be resolved")

        if resolved_path is not None:
            if not resolved_path.exists():
                reasons.append("rfq_path does not exist")
            elif not resolved_path.is_file():
                reasons.append("rfq_path is not a file")
            elif resolved_path.suffix.lower() not in ALLOWED_PILOT_FILE_EXTENSIONS:
                reasons.append(
                    "unsupported rfq file type "
                    f"'{resolved_path.suffix.lower() or 'missing'}'. Allowed: {', '.join(sorted(ALLOWED_PILOT_FILE_EXTENSIONS))}"
                )

        if reasons:
            issues.append(
                {
                    "rfq_index": index,
                    "rfq_path": rfq_path_raw,
                    "reasons": reasons,
                }
            )
    return issues


def _raise_pilot_manifest_validation_error(issues: List[Dict[str, Any]]) -> None:
    if not issues:
        return
    lines = ["Pilot manifest RFQ path validation failed:"]
    for issue in issues:
        lines.append(
            f"- RFQ {issue.get('rfq_index')}: {issue.get('rfq_path') or '<missing path>'} "
            f"({' ; '.join(issue.get('reasons') or [])})"
        )
    raise ValueError("\n".join(lines))


def _run_with_timeout(callback, timeout_seconds: int, timeout_label: str) -> Any:
    timeout_seconds = max(1, int(timeout_seconds or 0))
    if timeout_seconds <= 0:
        return callback()
    if threading.current_thread() is threading.main_thread() and os.name != "nt":
        def _timeout_handler(signum, frame):  # type: ignore[unused-argument]
            raise TimeoutError(f"{timeout_label} timed out after {timeout_seconds} seconds.")

        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_seconds)
        try:
            return callback()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)
    return callback()


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(payload), encoding="utf-8")


def _emit_pilot_progress(
    progress_callback: Optional[Callable[[str, str, Dict[str, Any]], None]],
    stage: str,
    status: str,
    **payload: Any,
) -> None:
    safe_payload = {key: value for key, value in payload.items() if value is not None}
    _log_event("pilot_progress", stage=stage, status=status, **safe_payload)
    if progress_callback:
        progress_callback(stage, status, safe_payload)


def _pilot_progress_path(run_id: str) -> Path:
    return _pilot_run_dir(run_id) / "pilot_progress.json"


def _pilot_rfq_progress_path(run_id: str, rfq_index: int) -> Path:
    return _pilot_run_dir(run_id) / f"rfq_{rfq_index:02d}_progress.json"


def _write_pilot_progress_artifact(run_id: str, payload: Dict[str, Any]) -> None:
    _write_json_file(_pilot_progress_path(run_id), payload)


def _write_rfq_progress_artifact(run_id: str, rfq_index: int, payload: Dict[str, Any]) -> None:
    _write_json_file(_pilot_rfq_progress_path(run_id, rfq_index), payload)


def _emit_ingestion_timing(stage: str, elapsed_seconds: float, **payload: Any) -> None:
    safe_payload = {key: value for key, value in payload.items() if value is not None}
    _log_event("draft_ingestion_timing", stage=stage, elapsed_seconds=round(elapsed_seconds, 4), **safe_payload)
    detail = " ".join(f"{key}={value}" for key, value in sorted(safe_payload.items()))
    suffix = f" {detail}" if detail else ""
    print(f"[pilot] draft_ingestion_timing stage={stage} elapsed_seconds={round(elapsed_seconds, 4)}{suffix}", flush=True)


class DraftIngestionTimeoutError(TimeoutError):
    pass


def _operator_payload_to_context(payload: Dict[str, Any]) -> Optional[OperatorContext]:
    if not payload:
        return None
    return OperatorContext(
        operator_id=_safe_text(payload.get("operator_id"), 255),
        display_name=_safe_text(payload.get("operator_display_name") or payload.get("operator_name"), 255),
        role=_safe_text(payload.get("operator_role"), 50) or "admin",
        authenticated=bool(payload.get("authenticated")),
        auth_source=_safe_text(payload.get("auth_source"), 255) or "pilot_script",
    )


def _ingest_rfq_review_draft_worker(
    queue: "multiprocessing.queues.Queue",
    rfq_data: Dict[str, Any],
    operator_payload: Dict[str, Any],
    precomputed_summary: Dict[str, Any],
) -> None:
    db = SessionLocal()
    try:
        operator = _operator_payload_to_context(operator_payload)
        quote = ingest_rfq_review_draft(db, rfq_data, operator, precomputed_summary=precomputed_summary, ensure_schema=False)
        queue.put({"status": "ok", "quote_id": int(quote.id)})
    except Exception as exc:
        queue.put({"status": "error", "error": _safe_text(exc, 2000)})
    finally:
        db.close()


def _run_draft_ingestion_with_timeout(
    db: Session,
    rfq_data: Dict[str, Any],
    operator: Optional[OperatorContext],
    precomputed_summary: Dict[str, Any],
    timeout_seconds: int,
) -> QuotePack:
    timeout_seconds = max(1, int(timeout_seconds or PILOT_INGESTION_TIMEOUT_SECONDS))
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_ingest_rfq_review_draft_worker,
        args=(queue, rfq_data, operator_audit_payload(operator), precomputed_summary),
    )
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        raise DraftIngestionTimeoutError(f"draft_ingestion timed out after {timeout_seconds} seconds")

    try:
        payload = queue.get_nowait()
    except Empty:
        payload = {"status": "error", "error": "draft_ingestion exited without returning a result"}
    finally:
        queue.close()
        queue.join_thread()

    if payload.get("status") != "ok":
        raise RuntimeError(_safe_text(payload.get("error"), 2000) or "draft_ingestion failed")

    quote_id = int(payload.get("quote_id") or 0)
    db.expire_all()
    quote = db.query(QuotePack).filter(QuotePack.id == quote_id).first()
    if not quote:
        raise RuntimeError(f"draft_ingestion completed but quote pack {quote_id} could not be reloaded")
    return quote


def _normalise_pilot_entries(rfq_entries: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    selected_entries = list(rfq_entries or [])[: max(1, min(int(limit or 10), 10))]
    if not selected_entries:
        raise ValueError("At least one RFQ entry is required for the pilot.")
    validation_issues = validate_pilot_rfq_entries(selected_entries, limit=len(selected_entries))
    _raise_pilot_manifest_validation_error(validation_issues)

    normalised_entries: List[Dict[str, Any]] = []
    for entry in selected_entries:
        rfq_entry = dict(entry or {})
        rfq_data = dict(rfq_entry.get("rfq_data") or {})
        rfq_path = _safe_text(rfq_entry.get("rfq_path"), 2000)
        if rfq_path:
            resolved_rfq_path = str(Path(rfq_path).expanduser().resolve())
            rfq_data.setdefault("local_document_paths", [resolved_rfq_path])
            rfq_entry["rfq_path"] = resolved_rfq_path
            rfq_entry.setdefault("rfq_filename", Path(resolved_rfq_path).name)
        rfq_entry["rfq_data"] = rfq_data
        normalised_entries.append(rfq_entry)
    return normalised_entries


def _truncate_nested_strings(value: Any, max_length: int = PILOT_MAX_EXTRACTED_TEXT_LENGTH) -> Any:
    if isinstance(value, str):
        if len(value) <= max_length:
            return value
        suffix = " ...[truncated]"
        return value[: max(0, max_length - len(suffix))] + suffix
    if isinstance(value, list):
        return [_truncate_nested_strings(item, max_length=max_length) for item in value]
    if isinstance(value, dict):
        return {key: _truncate_nested_strings(item, max_length=max_length) for key, item in value.items()}
    return value


def _summarise_extraction_payload_for_storage(extraction: Dict[str, Any], max_text_length: int = PILOT_MAX_EXTRACTED_TEXT_LENGTH) -> Dict[str, Any]:
    extraction = dict(extraction or {})
    intelligence = _truncate_nested_strings(dict(extraction.get("document_intelligence") or {}), max_text_length)
    downloads_summary = []
    for item in (extraction.get("downloads") or []):
        if isinstance(item, dict):
            downloads_summary.append(
                {
                    "url": _safe_text(item.get("url"), 1000),
                    "file_path": _safe_text(item.get("file_path"), 1000),
                    "content_type": _safe_text(item.get("content_type"), 255),
                }
            )
        else:
            downloads_summary.append({"value": _safe_text(item, 1000)})
    return {
        "status": _safe_text(extraction.get("status"), 120),
        "engine_version": _safe_text(extraction.get("engine_version"), 120),
        "analysed_at": _safe_text(extraction.get("analysed_at"), 120),
        "title": _safe_text(extraction.get("title"), 255),
        "buyer_name": _safe_text(extraction.get("buyer_name"), 255),
        "buyer_rfq_number": _safe_text(extraction.get("buyer_rfq_number"), 255),
        "quote_safe": bool(extraction.get("quote_safe", True)),
        "quote_block_reason": _safe_text(extraction.get("quote_block_reason"), 255),
        "report_path": _safe_text(extraction.get("report_path"), 1000),
        "downloads": downloads_summary,
        "document_intelligence": intelligence,
        "download_count": len(extraction.get("downloads") or []),
        "text_extraction_count": len(extraction.get("text_extraction") or []),
    }


def _prepare_summary_for_pilot_ingestion(
    summary: Dict[str, Any],
    *,
    max_pricing_rows: int = PILOT_MAX_PRICING_ROWS,
    max_compliance_items: int = PILOT_MAX_COMPLIANCE_ITEMS,
    max_text_length: int = PILOT_MAX_EXTRACTED_TEXT_LENGTH,
) -> Dict[str, Any]:
    prepared = json.loads(json.dumps(summary or {}, default=str))
    pricing = dict(prepared.get("pricing") or {})
    boq = dict(prepared.get("boq") or {})
    structured = dict(prepared.get("structured") or {})
    compliance = list(prepared.get("compliance_checklist") or [])

    max_pricing_rows = max(1, int(max_pricing_rows or PILOT_MAX_PRICING_ROWS))
    original_row_count = len(pricing.get("rows") or [])
    original_line_item_count = len(boq.get("line_items") or [])
    if original_row_count > max_pricing_rows:
        pricing["rows"] = list(pricing.get("rows") or [])[:max_pricing_rows]
        pricing["row_count"] = len(pricing["rows"])
        pricing["unmapped_rows"] = [row for row in (pricing.get("unmapped_rows") or []) if int(row) <= max_pricing_rows]
        pricing["pilot_row_cap_applied"] = True
        pricing["original_row_count"] = original_row_count
    if original_line_item_count > max_pricing_rows:
        boq["line_items"] = list(boq.get("line_items") or [])[:max_pricing_rows]
        boq["pilot_row_cap_applied"] = True
        boq["original_line_item_count"] = original_line_item_count
    if len(compliance) > max_compliance_items:
        compliance = compliance[:max_compliance_items]
        prepared["pilot_compliance_cap_applied"] = True

    structured["pricing_rows"] = list(structured.get("pricing_rows") or [])[:max_pricing_rows]
    structured["line_items"] = list(structured.get("line_items") or [])[:max_pricing_rows]
    structured["source_paths"] = _truncate_nested_strings(structured.get("source_paths") or {}, PILOT_MAX_DEBUG_FIELD_LENGTH)

    prepared["pricing"] = _truncate_nested_strings(pricing, max_text_length)
    prepared["boq"] = _truncate_nested_strings(boq, max_text_length)
    prepared["structured"] = _truncate_nested_strings(structured, max_text_length)
    prepared["classification"] = _truncate_nested_strings(prepared.get("classification") or {}, max_text_length)
    prepared["compliance_checklist"] = _truncate_nested_strings(compliance, max_text_length)
    prepared["extraction"] = _summarise_extraction_payload_for_storage(prepared.get("extraction") or {}, max_text_length=max_text_length)
    return prepared


def _write_pilot_run_payload(
    run_id: str,
    manifest: Dict[str, Any],
    records: List[Dict[str, Any]],
    summary: Dict[str, Any],
    *,
    status: str = "ok",
    error: str = "",
) -> Dict[str, Any]:
    payload = {
        "status": status,
        "run_id": run_id,
        "manifest": manifest,
        "records": records,
        "summary": summary,
    }
    _pilot_json_path(run_id).write_text(_json_dumps(payload))
    _pilot_summary_path(run_id).write_text(_json_dumps(summary))
    _pilot_manifest_path(run_id).write_text(_json_dumps(manifest))
    csv_path = _export_pilot_results_csv(records, _pilot_csv_path(run_id))
    if error:
        _pilot_failure_path(run_id).write_text(_json_dumps({"run_id": run_id, "status": status, "error": error}))
    payload["exports"] = {
        "json": str(_pilot_json_path(run_id)),
        "csv": csv_path,
        "summary": str(_pilot_summary_path(run_id)),
    }
    return payload


def _pricing_status(pricing: Dict[str, Any]) -> str:
    if not pricing.get("row_count"):
        return "missing"
    if pricing.get("unmapped_rows"):
        return "needs_manual_review"
    if pricing.get("review_rows") or pricing.get("manual_pricing_required_reason"):
        return "needs_review"
    return "complete"


def _compliance_status(compliance: List[Dict[str, Any]]) -> str:
    if any(item.get("status") == "missing" for item in compliance):
        return "missing"
    if any(item.get("status") == "needs_review" for item in compliance):
        return "needs_review"
    return "complete"


def _flatten_failure_reasons(failures: List[Dict[str, Any]]) -> List[str]:
    reasons: List[str] = []
    for failure in failures:
        for reason in failure.get("reasons") or []:
            if reason:
                reasons.append(str(reason))
    return reasons


def _derive_final_decision(classification: Dict[str, Any], validation: Dict[str, Any], compliance: List[Dict[str, Any]], pricing: Dict[str, Any]) -> Dict[str, str]:
    reasons = [error.get("code") for error in validation.get("errors") or []]
    if str(classification.get("decision") or "").startswith("excluded_") or "excluded_tender" in reasons or "compulsory_briefing" in reasons:
        return {
            "pilot_status": "rejected",
            "approval_status": "blocked",
            "recommendation": "reject",
            "final_decision": "rejected",
        }
    if validation.get("errors"):
        return {
            "pilot_status": "manual-review",
            "approval_status": "blocked",
            "recommendation": "manual_review",
            "final_decision": "manual_review",
        }
    if pricing.get("unmapped_rows") or pricing.get("review_rows") or pricing.get("manual_pricing_required_reason") or any(item.get("status") == "needs_review" for item in compliance):
        return {
            "pilot_status": "manual-review",
            "approval_status": "pending_manual_review",
            "recommendation": "manual_review",
            "final_decision": "manual_review",
        }
    return {
        "pilot_status": "accepted",
        "approval_status": "ready_for_human_approval",
        "recommendation": "approve_for_manual_submission",
        "final_decision": "accepted",
    }


def build_pilot_result_record(
    rfq_entry: Dict[str, Any],
    summary: Dict[str, Any],
    validation: Dict[str, Any],
    quote: Optional[QuotePack] = None,
    human_notes: str = "",
    processing_error: str = "",
    processing_stage: str = "",
) -> Dict[str, Any]:
    structured = summary.get("structured") or {}
    classification = summary.get("classification") or {}
    pricing = summary.get("pricing") or {}
    compliance = summary.get("compliance_checklist") or []
    extraction = summary.get("extraction") or {}
    boq = summary.get("boq") or {}

    extraction_failures: List[str] = []
    if extraction.get("status") not in {"ok", "partial"}:
        extraction_failures.append(_safe_text(extraction.get("status") or "document_extraction_failed"))
    if not (extraction.get("downloads") or []):
        extraction_failures.append("no_documents_available")

    boq_failures: List[str] = []
    if boq.get("status") not in {"ok"}:
        boq_failures.append(_safe_text(boq.get("status") or "boq_extraction_failed"))
    if not pricing.get("row_count"):
        boq_failures.append("no_pricing_rows_extracted")

    classification_failures: List[str] = []
    if not classification.get("decision"):
        classification_failures.append("classification_missing")
    elif str(classification.get("decision")).startswith("excluded_"):
        classification_failures.extend(classification.get("reason_codes") or [classification.get("decision")])

    pricing_failures: List[str] = []
    if pricing.get("unmapped_rows"):
        pricing_failures.append(f"unmapped_rows:{','.join(str(row) for row in pricing.get('unmapped_rows') or [])}")
    if not pricing.get("row_count"):
        pricing_failures.append("pricing_schedule_empty")
    elif pricing.get("manual_pricing_required_reason"):
        pricing_failures.append(_safe_text(pricing.get("manual_pricing_required_reason"), 255))

    missing_compliance_items = [
        _safe_text(item.get("label"), 255)
        for item in compliance
        if item.get("status") in {"missing", "needs_review"}
    ]
    compliance_failures = []
    if missing_compliance_items:
        compliance_failures.extend(missing_compliance_items)

    draft_ingestion_failures: List[str] = []
    if processing_stage.startswith("draft_ingestion"):
        draft_ingestion_failures.append(processing_stage)
        if processing_error:
            draft_ingestion_failures.append(processing_error)

    validation_failures = [error.get("code") or error.get("message") for error in validation.get("errors") or []]
    approval_failures: List[str] = []
    submission_failures: List[str] = []
    if processing_error:
        validation_failures.append(processing_error)

    failure_log = [
        _failure_bucket("pdf_extraction", extraction_failures),
        _failure_bucket("boq_parsing", boq_failures),
        _failure_bucket("classification", classification_failures),
        _failure_bucket("pricing_mapping", pricing_failures),
        _failure_bucket("draft_ingestion", draft_ingestion_failures),
        _failure_bucket("compliance_checklist", compliance_failures),
        _failure_bucket("validation", validation_failures),
        _failure_bucket("approval", approval_failures),
        _failure_bucket("submission", submission_failures),
    ]
    failure_log = [entry for entry in failure_log if entry["reasons"]]

    decision = _derive_final_decision(classification, validation, compliance, pricing)
    rejection_reason = "; ".join(_flatten_failure_reasons(failure_log)) if decision["pilot_status"] != "accepted" else ""
    validation_metrics = validation.get("metrics") or {}

    return {
        "rfq_filename": _safe_text(rfq_entry.get("rfq_filename") or Path(_safe_text(rfq_entry.get("rfq_path")) or "rfq").name, 255),
        "rfq_path": _safe_text(rfq_entry.get("rfq_path"), 2000),
        "buyer": _safe_text(structured.get("buyer_department") or rfq_entry.get("buyer_name"), 255),
        "closing_date": _safe_text(structured.get("closing_date") or rfq_entry.get("closing_date"), 120),
        "province": _safe_text(structured.get("province") or rfq_entry.get("province"), 120),
        "classification_result": _safe_text(classification.get("decision"), 255),
        "classification_reason_codes": classification.get("reason_codes") or [],
        "classification_reasons": classification.get("reasons") or [],
        "extraction_confidence": _safe_float((structured.get("confidence_scores") or {}).get("document_extraction"), 0.0),
        "pricing_mapping_confidence": _safe_float((structured.get("confidence_scores") or {}).get("pricing_mapping"), 0.0),
        "pricing_schedule_status": _pricing_status(pricing),
        "compliance_status": _compliance_status(compliance),
        "approval_status": decision["approval_status"],
        "final_recommendation": decision["recommendation"],
        "pilot_status": decision["pilot_status"],
        "rejection_reason": rejection_reason,
        "extraction_failures": extraction_failures,
        "pricing_mapping_failures": pricing_failures,
        "validation_failures": validation_failures,
        "missing_compliance_items": missing_compliance_items,
        "estimated_profit": _safe_float((quote.estimated_profit if quote else validation.get("metrics", {}).get("estimated_profit")), 0.0),
        "margin_percent": _safe_float((quote.estimated_margin_percent if quote else validation.get("metrics", {}).get("estimated_margin_percent")), 0.0),
        "pricing_rows_total": int(pricing.get("row_count") or 0),
        "pricing_rows_completed": len(pricing.get("completed_rows") or []),
        "pricing_rows_needing_review": len(pricing.get("review_rows") or pricing.get("unmapped_rows") or []),
        "suggested_total_quote": _safe_float(pricing.get("suggested_total_quote"), _safe_float(validation_metrics.get("suggested_total_quote"), 0.0)),
        "suggested_total_profit": _safe_float(pricing.get("suggested_total_profit"), _safe_float(validation_metrics.get("suggested_total_profit"), 0.0)),
        "suggested_margin_percent": _safe_float(pricing.get("suggested_margin_percent"), _safe_float(validation_metrics.get("suggested_margin_percent"), 0.0)),
        "minimum_required_quote_total": _safe_float(validation_metrics.get("minimum_required_quote_total"), _safe_float(pricing.get("minimum_required_quote_total"), 0.0)),
        "pricing_autofill_status": _safe_text(pricing.get("pricing_autofill_status"), 120),
        "pricing_confidence_summary": pricing.get("confidence_summary") or {},
        "human_notes": _safe_text(human_notes or rfq_entry.get("human_notes"), 4000),
        "final_decision": decision["final_decision"],
        "quote_pack_id": quote.id if quote else None,
        "validation": validation,
        "failure_log": failure_log,
    }


def summarise_pilot_results(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(records)
    passed = sum(1 for record in records if record.get("pilot_status") == "accepted")
    rejected = sum(1 for record in records if record.get("pilot_status") == "rejected")
    manual_review = sum(1 for record in records if record.get("pilot_status") == "manual-review")
    extraction_confidences = [_safe_float(record.get("extraction_confidence"), 0.0) for record in records]
    pricing_confidences = [_safe_float(record.get("pricing_mapping_confidence"), 0.0) for record in records]
    profit_qualified = sum(
        1
        for record in records
        if _safe_float(record.get("estimated_profit"), 0.0) >= settings.minimum_profit_margin_zar
    )
    blocked_by_rules = sum(
        1
        for record in records
        if str(record.get("classification_result") or "").startswith("excluded_")
    )

    category_counts: Dict[str, int] = {category: 0 for category in FAILURE_CATEGORIES}
    reason_counts: Dict[str, int] = {}
    for record in records:
        for failure in record.get("failure_log") or []:
            category = _safe_text(failure.get("category"), 120)
            if category:
                category_counts[category] = category_counts.get(category, 0) + len(failure.get("reasons") or [])
            for reason in failure.get("reasons") or []:
                reason_text = _safe_text(reason, 255)
                if reason_text:
                    reason_counts[reason_text] = reason_counts.get(reason_text, 0) + 1

    most_common_failure_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]

    return {
        "total_rfqs_tested": total,
        "passed": passed,
        "rejected": rejected,
        "needs_manual_review": manual_review,
        "average_extraction_confidence": round(sum(extraction_confidences) / max(total, 1), 4) if records else 0.0,
        "average_pricing_mapping_confidence": round(sum(pricing_confidences) / max(total, 1), 4) if records else 0.0,
        "most_common_failure_reasons": most_common_failure_reasons,
        "profit_qualified_opportunities": profit_qualified,
        "rfqs_blocked_by_business_rules": blocked_by_rules,
        "failure_category_totals": category_counts,
    }


def _export_pilot_results_csv(records: List[Dict[str, Any]], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rfq_filename",
        "rfq_path",
        "buyer",
        "closing_date",
        "province",
        "classification_result",
        "extraction_confidence",
        "pricing_mapping_confidence",
        "pricing_schedule_status",
        "compliance_status",
        "approval_status",
        "final_recommendation",
        "pilot_status",
        "rejection_reason",
        "estimated_profit",
        "margin_percent",
        "pricing_rows_total",
        "pricing_rows_completed",
        "pricing_rows_needing_review",
        "suggested_total_quote",
        "suggested_total_profit",
        "suggested_margin_percent",
        "minimum_required_quote_total",
        "pricing_autofill_status",
        "human_notes",
        "final_decision",
        "quote_pack_id",
        "missing_compliance_items",
        "extraction_failures",
        "pricing_mapping_failures",
        "validation_failures",
    ]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    **{key: record.get(key, "") for key in fieldnames},
                    "missing_compliance_items": "; ".join(record.get("missing_compliance_items") or []),
                    "extraction_failures": "; ".join(record.get("extraction_failures") or []),
                    "pricing_mapping_failures": "; ".join(record.get("pricing_mapping_failures") or []),
                    "validation_failures": "; ".join(record.get("validation_failures") or []),
                }
            )
    return str(destination)


def run_manual_review_pilot(
    db: Optional[Session],
    rfq_entries: List[Dict[str, Any]],
    operator: Optional[OperatorContext],
    pilot_name: str = "",
    limit: int = 10,
    *,
    skip_ingestion: bool = False,
    per_rfq_timeout_seconds: int = PILOT_PER_RFQ_TIMEOUT_SECONDS,
    ingestion_timeout_seconds: int = PILOT_INGESTION_TIMEOUT_SECONDS,
    max_pilot_pricing_rows: int = PILOT_MAX_PRICING_ROWS,
    max_runtime_seconds: int = PILOT_MAX_RUNTIME_SECONDS,
    continue_on_timeout: bool = True,
    progress_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    _emit_pilot_progress(progress_callback, "manifest_validation", "start", limit=limit)
    selected_entries = _normalise_pilot_entries(rfq_entries, limit=limit)
    _emit_pilot_progress(progress_callback, "manifest_validation", "end", rfq_count=len(selected_entries))

    if not skip_ingestion:
        _emit_pilot_progress(progress_callback, "db_schema_check", "start")
        ensure_quote_pack_schema()
        _emit_pilot_progress(progress_callback, "db_schema_check", "end")

    run_id = f"pilot_{_now_timestamp()}"
    run_dir = _pilot_run_dir(run_id)
    _emit_pilot_progress(progress_callback, "run_directory_creation", "start", run_id=run_id, run_dir=str(run_dir))
    run_dir.mkdir(parents=True, exist_ok=True)
    _emit_pilot_progress(progress_callback, "run_directory_creation", "end", run_id=run_id, run_dir=str(run_dir))

    records: List[Dict[str, Any]] = []
    manifest = {
        "run_id": run_id,
        "pilot_name": _safe_text(pilot_name or "Controlled Phase 5 Pilot", 255),
        "created_at": datetime.utcnow().isoformat(),
        "operator": operator_audit_payload(operator),
        "rfq_count": len(selected_entries),
        "skip_ingestion": bool(skip_ingestion),
        "per_rfq_timeout_seconds": int(per_rfq_timeout_seconds or PILOT_PER_RFQ_TIMEOUT_SECONDS),
        "ingestion_timeout_seconds": int(ingestion_timeout_seconds or PILOT_INGESTION_TIMEOUT_SECONDS),
        "max_pilot_pricing_rows": int(max_pilot_pricing_rows or PILOT_MAX_PRICING_ROWS),
        "max_runtime_seconds": int(max_runtime_seconds or PILOT_MAX_RUNTIME_SECONDS),
        "continue_on_timeout": bool(continue_on_timeout),
        "status": "in_progress",
    }
    _write_json_file(_pilot_manifest_path(run_id), manifest)
    _write_pilot_progress_artifact(
        run_id,
        {
            "run_id": run_id,
            "status": "in_progress",
            "current_stage": "run_directory_creation",
            "created_at": manifest["created_at"],
            "updated_at": datetime.utcnow().isoformat(),
            "rfq_count": len(selected_entries),
        },
    )

    run_started_at = time.monotonic()
    try:
        for index, rfq_entry in enumerate(selected_entries, start=1):
            elapsed = time.monotonic() - run_started_at
            if max_runtime_seconds and elapsed >= max_runtime_seconds:
                manifest["stopped_reason"] = "pilot_max_runtime_exceeded"
                break

            _write_pilot_progress_artifact(
                run_id,
                {
                    "run_id": run_id,
                    "status": "in_progress",
                    "current_stage": "rfq_start",
                    "updated_at": datetime.utcnow().isoformat(),
                    "current_rfq_index": index,
                    "current_rfq_filename": _safe_text(rfq_entry.get("rfq_filename"), 255),
                    "completed_rfqs": len(records),
                },
            )
            try:
                record = _run_with_timeout(
                    lambda: _process_single_pilot_rfq(
                        db,
                        rfq_entry,
                        operator,
                        run_id=run_id,
                        rfq_index=index,
                        skip_ingestion=skip_ingestion,
                        ingestion_timeout_seconds=ingestion_timeout_seconds,
                        max_pilot_pricing_rows=max_pilot_pricing_rows,
                        continue_on_timeout=continue_on_timeout,
                        progress_callback=progress_callback,
                    ),
                    per_rfq_timeout_seconds,
                    f"RFQ {index} total processing",
                )
            except Exception as exc:
                if isinstance(exc, DraftIngestionTimeoutError) and not continue_on_timeout:
                    raise
                processing_error = _safe_text(exc, 1000)
                if db is not None and hasattr(db, "rollback"):
                    try:
                        db.rollback()
                    except Exception:
                        pass
                rfq_data = dict(rfq_entry.get("rfq_data") or {})
                summary = {
                    "structured": {
                        "buyer_department": rfq_data.get("buyer_name") or "",
                        "closing_date": rfq_data.get("closing_date") or "",
                        "province": rfq_data.get("province") or "",
                        "confidence_scores": {"document_extraction": 0.0, "pricing_mapping": 0.0},
                    },
                    "classification": {"decision": "", "eligible": False, "reason_codes": [], "reasons": []},
                    "pricing": {"row_count": 0, "rows": [], "unmapped_rows": [], "overall_confidence": 0.0},
                    "compliance_checklist": [],
                    "extraction": {"status": "failed", "downloads": [], "error": processing_error},
                    "boq": {"status": "failed", "line_item_count": 0, "confidence": 0.0},
                }
                validation = {
                    "status": "blocked",
                    "errors": [{"code": "pilot_processing_error", "message": processing_error}],
                    "warnings": [],
                    "metrics": {},
                }
                record = build_pilot_result_record(
                    rfq_entry,
                    summary,
                    validation,
                    quote=None,
                    human_notes=_safe_text(rfq_entry.get("human_notes"), 4000),
                    processing_error=processing_error,
                )
                record["rfq_index"] = index
                _log_event("pilot_rfq_failure", run_id=run_id, rfq_index=index, error=processing_error, operator=operator_audit_payload(operator))
                _write_rfq_progress_artifact(
                    run_id,
                    index,
                    {
                        "run_id": run_id,
                        "rfq_index": index,
                        "rfq_filename": _safe_text(rfq_entry.get("rfq_filename"), 255),
                        "status": "failed",
                        "error": processing_error,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                )
            records.append(record)
            for failure in record.get("failure_log") or []:
                _log_event(
                    "pilot_failure",
                    run_id=run_id,
                    rfq_index=index,
                    rfq_filename=record.get("rfq_filename"),
                    category=failure.get("category"),
                    reasons=failure.get("reasons") or [],
                    operator=operator_audit_payload(operator),
                )

        summary = summarise_pilot_results(records)
        manifest["completed_at"] = datetime.utcnow().isoformat()
        status = "ok"
        if manifest.get("stopped_reason"):
            status = "partial"
            summary["status"] = "partial"
            summary["error"] = str(manifest.get("stopped_reason"))
        manifest["status"] = status
        _emit_pilot_progress(progress_callback, "artifact_write", "start", run_id=run_id, status_text=status)
        result = _write_pilot_run_payload(run_id, manifest, records, summary, status=status)
        _write_pilot_progress_artifact(
            run_id,
            {
                "run_id": run_id,
                "status": status,
                "current_stage": "artifact_write_complete",
                "updated_at": datetime.utcnow().isoformat(),
                "completed_rfqs": len(records),
            },
        )
        _emit_pilot_progress(progress_callback, "artifact_write", "end", run_id=run_id, status_text=status)
        _log_event("pilot_run_completed", run_id=run_id, summary=summary, operator=operator_audit_payload(operator))
        return result
    except Exception as exc:
        error_text = _safe_text(exc, 2000)
        summary = {
            "total_rfqs_tested": len(records),
            "passed": 0,
            "rejected": 0,
            "needs_manual_review": len(records),
            "average_extraction_confidence": 0.0,
            "average_pricing_mapping_confidence": 0.0,
            "most_common_failure_reasons": [{"reason": error_text, "count": 1}] if error_text else [],
            "profit_qualified_opportunities": 0,
            "rfqs_blocked_by_business_rules": 0,
            "failure_category_totals": {category: 0 for category in FAILURE_CATEGORIES},
            "status": "failed",
            "error": error_text,
        }
        failed_manifest = {**manifest, "status": "failed", "error": error_text}
        _emit_pilot_progress(progress_callback, "artifact_write", "start", run_id=run_id, status_text="failed")
        _write_pilot_run_payload(run_id, failed_manifest, records, summary, status="failed", error=error_text)
        _write_pilot_progress_artifact(
            run_id,
            {
                "run_id": run_id,
                "status": "failed",
                "current_stage": "artifact_write_failed",
                "updated_at": datetime.utcnow().isoformat(),
                "error": error_text,
                "completed_rfqs": len(records),
            },
        )
        _emit_pilot_progress(progress_callback, "artifact_write", "end", run_id=run_id, status_text="failed")
        _log_event("pilot_run_failed", run_id=run_id, error=error_text, operator=operator_audit_payload(operator))
        raise


def load_pilot_run(run_id: str) -> Dict[str, Any]:
    path = _pilot_json_path(run_id)
    if not path.exists():
        raise ValueError("Pilot run not found.")
    data = _json_loads(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("Pilot run payload is invalid.")
    return data


def list_pilot_runs() -> List[Dict[str, Any]]:
    _ensure_runtime_dirs()
    runs: List[Dict[str, Any]] = []
    for run_dir in sorted(PILOT_RUNTIME_DIR.glob("pilot_*"), reverse=True):
        manifest_path = run_dir / "pilot_manifest.json"
        summary_path = run_dir / "pilot_summary.json"
        manifest = _json_loads(manifest_path.read_text()) if manifest_path.exists() else {}
        summary = _json_loads(summary_path.read_text()) if summary_path.exists() else {}
        runs.append(
            {
                "run_id": run_dir.name,
                "manifest": manifest or {},
                "summary": summary or {},
                "exports": {
                    "json": str(run_dir / "pilot_results.json"),
                    "csv": str(run_dir / "pilot_results.csv"),
                },
            }
        )
    return runs


def latest_pilot_run_id() -> str:
    runs = list_pilot_runs()
    if not runs:
        raise ValueError("No pilot runs found.")
    return _safe_text(runs[0].get("run_id"), 255)


def build_pilot_to_review_bridge(run_id: Optional[str] = None) -> Dict[str, Any]:
    if not run_id:
        run_id = latest_pilot_run_id()
    payload = load_pilot_run(run_id)
    records = list(payload.get("records") or [])
    ranked: List[Dict[str, Any]] = []
    for record in records:
        queue_like = {
            "validation_status": (record.get("validation") or {}).get("status"),
            "classification_result": record.get("classification_result"),
            "pricing_rows_total": record.get("pricing_rows_total"),
            "pricing_rows_needing_review": record.get("pricing_rows_needing_review"),
            "compliance_missing_count": 0,
            "compliance_needs_review_count": len(record.get("missing_compliance_items") or []),
            "estimated_profit": record.get("estimated_profit"),
            "margin_percent": record.get("margin_percent"),
            "closing_date": record.get("closing_date"),
        }
        record = dict(record)
        record["easiest_to_approve_score"] = review_queue_priority(queue_like)
        ranked.append(record)
    ranked.sort(key=lambda row: (row["easiest_to_approve_score"], row.get("rfq_index", 0)))

    pricing_only = []
    compliance_only = []
    both = []
    recommended_reject = []
    for record in ranked:
        pricing_needed = int(record.get("pricing_rows_needing_review") or 0) > 0 or "pricing_schedule_empty" in (record.get("validation_failures") or [])
        compliance_needed = bool(record.get("missing_compliance_items"))
        if pricing_needed and compliance_needed:
            both.append(record)
        elif pricing_needed:
            pricing_only.append(record)
        elif compliance_needed:
            compliance_only.append(record)
        if str(record.get("classification_result") or "").startswith("excluded_") or "pricing_schedule_empty" in (record.get("validation_failures") or []):
            recommended_reject.append(record)

    return {
        "run_id": run_id,
        "top_3_easiest_rfqs": [
            {
                "quote_pack_id": row.get("quote_pack_id"),
                "rfq_index": row.get("rfq_index"),
                "rfq_filename": row.get("rfq_filename"),
                "estimated_profit": row.get("estimated_profit"),
                "margin_percent": row.get("margin_percent"),
                "pricing_rows_needing_review": row.get("pricing_rows_needing_review"),
                "missing_compliance_items": row.get("missing_compliance_items"),
            }
            for row in ranked[:3]
        ],
        "rfqs_requiring_pricing_only": [row.get("quote_pack_id") for row in pricing_only],
        "rfqs_requiring_compliance_only": [row.get("quote_pack_id") for row in compliance_only],
        "rfqs_requiring_both_pricing_and_compliance": [row.get("quote_pack_id") for row in both],
        "rfqs_recommended_for_rejection": [row.get("quote_pack_id") for row in recommended_reject],
    }


def export_review_queue(db: Session, export_format: str = "json") -> Dict[str, Any]:
    export_format = _safe_text(export_format, 20).lower() or "json"
    if export_format not in {"json", "csv"}:
        raise ValueError("Unsupported export format. Use json or csv.")
    export_dir = REVIEW_RUNTIME_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _now_timestamp()
    records = list_review_queue_summary(db)
    if export_format == "json":
        path = export_dir / f"review_queue_{timestamp}.json"
        path.write_text(_json_dumps({"generated_at": datetime.utcnow().isoformat(), "records": records}), encoding="utf-8")
    else:
        path = export_dir / f"review_queue_{timestamp}.csv"
        fieldnames = [
            "quote_pack_id",
            "quote_number",
            "rfq_title",
            "buyer",
            "province",
            "closing_date",
            "classification_result",
            "pilot_status",
            "validation_status",
            "pricing_rows_total",
            "pricing_rows_completed",
            "pricing_rows_needing_review",
            "suggested_total_quote",
            "estimated_profit",
            "margin_percent",
            "compliance_status",
            "easiest_to_approve_rank",
            "easiest_to_approve_score",
            "next_action",
            "approval_ready",
            "approval_blocking_reasons",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in records:
                writer.writerow(
                    {
                        **{name: row.get(name, "") for name in fieldnames},
                        "approval_blocking_reasons": "; ".join(row.get("approval_blocking_reasons") or []),
                    }
                )
    return {"format": export_format, "path": str(path)}


def export_pilot_run(run_id: str, export_format: str = "json") -> Dict[str, Any]:
    export_format = _safe_text(export_format, 20).lower() or "json"
    if export_format not in {"json", "csv", "summary"}:
        raise ValueError("Unsupported export format. Use json, csv, or summary.")
    if export_format == "json":
        path = _pilot_json_path(run_id)
    elif export_format == "csv":
        path = _pilot_csv_path(run_id)
    else:
        path = _pilot_summary_path(run_id)
    if not path.exists():
        raise ValueError("Pilot export not found.")
    return {"run_id": run_id, "format": export_format, "path": str(path)}
