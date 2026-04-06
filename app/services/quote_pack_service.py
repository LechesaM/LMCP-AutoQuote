from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except Exception as exc:
    raise RuntimeError(
        "reportlab is required for PDF quote generation. "
        "Install it with: pip install reportlab"
    ) from exc

try:
    from app.services.compliance_document_service import ComplianceDocumentService
except Exception:
    class ComplianceDocumentService:  # type: ignore
        @classmethod
        def merge_compliance_documents(
            cls,
            existing_docs: Optional[List[Dict[str, Any]]] = None,
            include_defaults: bool = True,
        ) -> List[Dict[str, Any]]:
            return existing_docs or []

        @classmethod
        def build_pack_attachment_paths(
            cls,
            existing_paths: Optional[List[str]] = None,
            include_default_compliance_docs: bool = True,
        ) -> List[str]:
            return existing_paths or []

        @classmethod
        def resolve_csd_report(
            cls,
            explicit_path: Optional[str] = None,
        ) -> Optional[Dict[str, Any]]:
            return None
        
DEFAULT_COMPANY_NAME = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
DEFAULT_COMPANY_ADDRESS = "1787 Dube Street, Batho Location, Bloemfontein, 9323"
DEFAULT_COMPANY_PHONE = "0826338492"
DEFAULT_COMPANY_EMAIL = "lechesam@me.com"
DEFAULT_COMPANY_REG_NO = "2012/159509/07"
DEFAULT_COMPANY_VAT_NO = "4260295953"

DEFAULT_CURRENCY = "ZAR"
DEFAULT_VALIDITY_DAYS = 30
DEFAULT_OUTPUT_ROOT = "monthly_quotes"
DEFAULT_VAT_RATE = Decimal("15.00")
DEFAULT_SUBMISSION_METHOD = "email"
DEFAULT_DELIVERY_PERIOD = "14 days"
DEFAULT_MARGIN_RATE = Decimal("25.00")


@dataclass
class QuoteNumbers:
    buyer_rfq_number: str
    quote_number: str
    document_number: str


def _now() -> datetime:
    return datetime.now()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        return value if value else default
    return str(value).strip() or default


def _is_unknown(value: Any) -> bool:
    text = _safe_str(value).strip().lower()
    return text in {
        "",
        "unknown",
        "unknown-rfq",
        "rfq-unknown",
        "n/a",
        "na",
        "-",
        "none",
        "null",
        "buyer / issuing entity",
        "supply and delivery item",
        "client",
        "lmcp-quote",
        "quotation",
    }


def _safe_decimal(value: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    if value is None:
        return default.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    text = _safe_str(value)
    if not text:
        return default.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    text = text.replace("R", "").replace(",", "").replace("%", "").strip()
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return default.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money(value: Any, currency: str = DEFAULT_CURRENCY) -> str:
    amount = _safe_decimal(value)
    if currency.upper() == "ZAR":
        return f"R {amount:,.2f}"
    return f"{currency.upper()} {amount:,.2f}"


def _clean_filename(value: str, fallback: str = "document") -> str:
    text = _safe_str(value, fallback)
    text = re.sub(r"[^\w\-. ]+", "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text or fallback


def _extract_first(payload: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload.get(key) not in (None, "", [], {}):
            return payload.get(key)
    return default


def _deep_extract_first(payload: Dict[str, Any], key_groups: List[List[str]], default: Any = None) -> Any:
    for keys in key_groups:
        current: Any = payload
        found = True
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current.get(key)
        if found and current not in (None, "", [], {}):
            return current
    return default


def _pick_first_meaningful(*values: Any, default: str = "") -> str:
    for value in values:
        text = _safe_str(value)
        if text and not _is_unknown(text):
            return text
    return default


def _get_original_input_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    original = payload.get("_original_input_payload")
    if isinstance(original, dict) and original:
        return deepcopy(original)
    return deepcopy(payload if isinstance(payload, dict) else {})


def _get_locked_rfq(payload: Dict[str, Any], default: str = "") -> str:
    original = _get_original_input_payload(payload)
    locked = _pick_first_meaningful(
        payload.get("_locked_buyer_rfq_number"),
        payload.get("buyer_rfq_number"),
        payload.get("rfq_number"),
        payload.get("reference_number"),
        payload.get("document_number"),
        original.get("_locked_buyer_rfq_number"),
        original.get("buyer_rfq_number"),
        original.get("rfq_number"),
        original.get("reference_number"),
        original.get("document_number"),
        default=default,
    )
    return locked


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    safe_text = _safe_str(text, "").replace("\n", "<br/>")
    return Paragraph(safe_text, style)


def _today_compact() -> str:
    return _now().strftime("%Y%m%d")


def _normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_seller(payload: Dict[str, Any]) -> Dict[str, Any]:
    seller = deepcopy(payload.get("seller") or {})
    company = deepcopy(payload.get("company") or {})

    return {
        "name": _safe_str(
            seller.get("name") or company.get("name"),
            DEFAULT_COMPANY_NAME,
        ),
        "address": _safe_str(
            seller.get("address") or company.get("address"),
            DEFAULT_COMPANY_ADDRESS,
        ),
        "phone": _safe_str(
            seller.get("phone") or company.get("phone"),
            DEFAULT_COMPANY_PHONE,
        ),
        "email": _safe_str(
            seller.get("email") or company.get("email"),
            DEFAULT_COMPANY_EMAIL,
        ),
        "registration_number": _safe_str(
            seller.get("registration_number")
            or seller.get("reg_no")
            or company.get("registration_number")
            or company.get("reg_no"),
            DEFAULT_COMPANY_REG_NO,
        ),
        "vat_number": _safe_str(
            seller.get("vat_number")
            or seller.get("vat_no")
            or company.get("vat_number")
            or company.get("vat_no"),
            DEFAULT_COMPANY_VAT_NO,
        ),
    }


def _normalize_buyer(payload: Dict[str, Any]) -> Dict[str, Any]:
    original = _get_original_input_payload(payload)

    buyer = deepcopy(payload.get("buyer") or {})
    issuing = payload.get("issuing_entity") or {}
    if not isinstance(issuing, dict):
        issuing = {"name": _safe_str(issuing)}

    rfq = deepcopy(payload.get("rfq") or {})
    opportunity = deepcopy(payload.get("opportunity") or {})
    original_buyer = deepcopy(original.get("buyer") or {})

    address_parts: List[str] = []

    raw_address = _pick_first_meaningful(
        buyer.get("address"),
        rfq.get("buyer_address"),
        payload.get("buyer_address"),
        opportunity.get("buyer_address"),
        original_buyer.get("address"),
        original.get("buyer_address"),
    )
    if raw_address:
        address_parts.append(raw_address)

    country = _pick_first_meaningful(
        buyer.get("country"),
        rfq.get("country"),
        payload.get("country"),
        opportunity.get("country"),
        original_buyer.get("country"),
        original.get("country"),
        default="South Africa",
    )
    if country and country not in address_parts:
        address_parts.append(country)

    buyer_name = _pick_first_meaningful(
        buyer.get("name"),
        issuing.get("name"),
        rfq.get("buyer_name"),
        rfq.get("entity_name"),
        opportunity.get("buyer_name"),
        opportunity.get("entity_name"),
        payload.get("buyer_name"),
        payload.get("entity_name"),
        payload.get("issuing_entity_name"),
        original_buyer.get("name"),
        original_buyer.get("company_name"),
        original.get("buyer_name"),
        default="Buyer / Issuing Entity",
    )

    return {
        "name": buyer_name,
        "department": _pick_first_meaningful(
            buyer.get("department"),
            rfq.get("department"),
            opportunity.get("department"),
            payload.get("department_name"),
            original_buyer.get("department"),
            original.get("department_name"),
            default="Procurement Office",
        ),
        "contact_person": _pick_first_meaningful(
            buyer.get("contact_person"),
            buyer.get("contact_name"),
            rfq.get("contact_person"),
            opportunity.get("contact_person"),
            payload.get("contact_person"),
            original_buyer.get("contact_person"),
            original.get("contact_person"),
            default="-",
        ),
        "email": _pick_first_meaningful(
            buyer.get("email"),
            rfq.get("buyer_email"),
            opportunity.get("buyer_email"),
            payload.get("buyer_email"),
            payload.get("recipient_email"),
            payload.get("submission_email"),
            original_buyer.get("email"),
            original.get("buyer_email"),
            original.get("recipient_email"),
            original.get("submission_email"),
            default="-",
        ),
        "phone": _pick_first_meaningful(
            buyer.get("phone"),
            rfq.get("buyer_phone"),
            opportunity.get("buyer_phone"),
            payload.get("buyer_phone"),
            original_buyer.get("phone"),
            original.get("buyer_phone"),
            default="-",
        ),
        "address_lines": address_parts or ["South Africa"],
    }


def _generate_quote_number(output_root: Optional[str] = None) -> str:
    root = Path(output_root or os.getenv("QUOTE_PACK_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT))
    month_folder = _now().strftime("%Y-%m")
    month_dir = root / month_folder
    month_dir.mkdir(parents=True, exist_ok=True)

    today = _today_compact()
    pattern = re.compile(rf"LMCP-{today}-(\d{{4}})$")

    max_seq = 0
    for entry in month_dir.iterdir():
        if not entry.is_dir():
            continue
        folder_name = entry.name.split("__")[-1]
        match = pattern.search(folder_name)
        if match:
            try:
                max_seq = max(max_seq, int(match.group(1)))
            except Exception:
                pass

    return f"LMCP-{today}-{max_seq + 1:04d}"


def _extract_rfq_from_text(*texts: Any) -> str:
    patterns = [
        r"\b(?:RFQ|RFP|BID|TENDER|TNDR|QUOTATION|QUOTE)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/\-_.]{2,})\b",
        r"\b([A-Z]{2,}[-/][A-Z0-9][A-Z0-9/\-_.]{2,})\b",
        r"\b([A-Z0-9]{2,}[-/][A-Z0-9][A-Z0-9/\-_.]{2,})\b",
    ]

    for text in texts:
        blob = _safe_str(text)
        if not blob:
            continue
        for pattern in patterns:
            match = re.search(pattern, blob, flags=re.IGNORECASE)
            if match:
                candidate = _safe_str(match.group(1))
                if candidate and not _is_unknown(candidate):
                    return candidate
    return ""


def _resolve_quote_numbers(payload: Dict[str, Any]) -> QuoteNumbers:
    original = _get_original_input_payload(payload)
    rfq = deepcopy(payload.get("rfq") or {})
    opportunity = deepcopy(payload.get("opportunity") or {})
    submission_pack = deepcopy(payload.get("submission_pack") or {})
    buyer_schedule = deepcopy(payload.get("buyer_pricing_schedule") or {})
    mapped_schedule = deepcopy(payload.get("pricing_schedule_mapped") or {})

    locked_rfq = _get_locked_rfq(payload)

    buyer_rfq_number = _pick_first_meaningful(
        locked_rfq,
        payload.get("_locked_buyer_rfq_number"),
        payload.get("buyer_rfq_number"),
        payload.get("rfq_number"),
        payload.get("document_number"),
        payload.get("tender_number"),
        payload.get("reference_number"),
        payload.get("bid_number"),
        payload.get("notice_number"),
        payload.get("opportunity_number"),
        payload.get("buyer_reference_number"),
        submission_pack.get("buyer_rfq_number"),
        submission_pack.get("document_number"),
        rfq.get("buyer_rfq_number"),
        rfq.get("rfq_number"),
        rfq.get("document_number"),
        rfq.get("tender_number"),
        rfq.get("reference_number"),
        rfq.get("bid_number"),
        rfq.get("notice_number"),
        opportunity.get("buyer_rfq_number"),
        opportunity.get("rfq_number"),
        opportunity.get("reference_number"),
        opportunity.get("notice_number"),
        buyer_schedule.get("rfq_number") if isinstance(buyer_schedule, dict) else "",
        buyer_schedule.get("reference_number") if isinstance(buyer_schedule, dict) else "",
        mapped_schedule.get("rfq_number") if isinstance(mapped_schedule, dict) else "",
        mapped_schedule.get("reference_number") if isinstance(mapped_schedule, dict) else "",
        original.get("_locked_buyer_rfq_number"),
        original.get("buyer_rfq_number"),
        original.get("rfq_number"),
        original.get("document_number"),
        original.get("tender_number"),
        original.get("reference_number"),
        original.get("bid_number"),
        original.get("notice_number"),
        original.get("opportunity_number"),
    )

    if not buyer_rfq_number:
        buyer_rfq_number = _pick_first_meaningful(
            _deep_extract_first(
                payload,
                [
                    ["rfq", "buyer_rfq_number"],
                    ["rfq", "rfq_number"],
                    ["rfq", "document_number"],
                    ["rfq", "tender_number"],
                    ["rfq", "reference_number"],
                    ["rfq", "bid_number"],
                    ["rfq", "notice_number"],
                    ["opportunity", "buyer_rfq_number"],
                    ["opportunity", "rfq_number"],
                    ["opportunity", "reference_number"],
                    ["submission_pack", "buyer_rfq_number"],
                    ["submission_pack", "document_number"],
                    ["buyer_pricing_schedule", "rfq_number"],
                    ["buyer_pricing_schedule", "reference_number"],
                    ["pricing_schedule_mapped", "rfq_number"],
                    ["pricing_schedule_mapped", "reference_number"],
                ],
                "",
            ),
            _deep_extract_first(
                original,
                [
                    ["rfq", "buyer_rfq_number"],
                    ["rfq", "rfq_number"],
                    ["rfq", "document_number"],
                    ["rfq", "tender_number"],
                    ["rfq", "reference_number"],
                    ["rfq", "bid_number"],
                    ["rfq", "notice_number"],
                    ["opportunity", "buyer_rfq_number"],
                    ["opportunity", "rfq_number"],
                    ["opportunity", "reference_number"],
                    ["submission_pack", "buyer_rfq_number"],
                    ["submission_pack", "document_number"],
                ],
                "",
            ),
        )

    if not buyer_rfq_number:
        buyer_rfq_number = _extract_rfq_from_text(
            payload.get("subject"),
            payload.get("title"),
            payload.get("description"),
            payload.get("email_subject"),
            rfq.get("title"),
            rfq.get("description"),
            opportunity.get("title"),
            opportunity.get("description"),
            original.get("subject"),
            original.get("title"),
            original.get("description"),
            original.get("email_subject"),
        )

    quote_number = _pick_first_meaningful(
        payload.get("quote_number"),
        payload.get("lmcp_quote_number"),
        payload.get("quotation_number"),
        submission_pack.get("quote_number"),
        original.get("quote_number"),
        original.get("lmcp_quote_number"),
        original.get("quotation_number"),
    )

    if not quote_number:
        quote_number = _generate_quote_number(_safe_str(payload.get("output_root"), "") or None)

    if not buyer_rfq_number or _is_unknown(buyer_rfq_number):
        buyer_rfq_number = f"NO-RFQ-{_today_compact()}"

    document_number = _pick_first_meaningful(
        locked_rfq,
        payload.get("_locked_buyer_rfq_number"),
        payload.get("document_number"),
        submission_pack.get("document_number"),
        original.get("_locked_buyer_rfq_number"),
        original.get("document_number"),
        buyer_rfq_number,
        default=buyer_rfq_number,
    )

    return QuoteNumbers(
        buyer_rfq_number=buyer_rfq_number,
        quote_number=quote_number,
        document_number=document_number,
    )


def _extract_subject(payload: Dict[str, Any]) -> str:
    original = _get_original_input_payload(payload)

    raw_subject = _pick_first_meaningful(
        payload.get("subject"),
        payload.get("quote_subject"),
        payload.get("title"),
        payload.get("description"),
        payload.get("email_subject"),
        _deep_extract_first(payload, [["rfq", "title"], ["rfq", "description"]], ""),
        _deep_extract_first(payload, [["opportunity", "title"], ["opportunity", "description"]], ""),
        original.get("subject"),
        original.get("quote_subject"),
        original.get("title"),
        original.get("description"),
        original.get("email_subject"),
        _deep_extract_first(original, [["rfq", "title"], ["rfq", "description"]], ""),
    )

    numbers = _resolve_quote_numbers(payload)

    locked_rfq = _safe_str(
        payload.get("_locked_buyer_rfq_number")
        or numbers.buyer_rfq_number
    )

    if locked_rfq and not _is_unknown(locked_rfq):
        return f"Quotation for RFQ: {locked_rfq}"

    return raw_subject or "Quotation"


def _apply_margin_to_price(unit_price: Decimal, payload: Dict[str, Any]) -> Decimal:
    if unit_price <= Decimal("0.00"):
        return unit_price

    margin_rate = _safe_decimal(
        payload.get("margin_rate")
        or payload.get("default_margin_rate")
        or payload.get("minimum_margin_rate")
        or DEFAULT_MARGIN_RATE,
        DEFAULT_MARGIN_RATE,
    )

    if margin_rate <= Decimal("0.00"):
        margin_rate = DEFAULT_MARGIN_RATE

    multiplier = (Decimal("100.00") + margin_rate) / Decimal("100.00")
    return (unit_price * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_line_item(item: Dict[str, Any], idx: int, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    description = _safe_str(
        item.get("description")
        or item.get("item_description")
        or item.get("name")
        or item.get("title")
        or item.get("specification"),
        f"Item {idx}",
    )

    brand = _safe_str(item.get("brand"))
    model = _safe_str(item.get("model"))
    if brand or model:
        meta = " / ".join(x for x in [brand, model] if x)
        if meta:
            description = f"{description} ({meta})"

    qty = _safe_decimal(item.get("quantity") or item.get("qty") or 1, Decimal("1.00"))
    if qty <= Decimal("0.00"):
        qty = Decimal("1.00")

    unit = _safe_str(item.get("unit") or item.get("uom"), "Each")

    raw_supplier_unit_price = _safe_decimal(
        item.get("supplier_unit_price")
        or item.get("supplier_price")
        or item.get("supplier_rate"),
        Decimal("0.00"),
    )
    raw_unit_price = _safe_decimal(
        item.get("unit_price")
        or item.get("rate")
        or item.get("price")
        or item.get("estimated_unit_price")
        or item.get("amount"),
        Decimal("0.00"),
    )

    selected_unit_price = raw_supplier_unit_price if raw_supplier_unit_price > Decimal("0.00") else raw_unit_price
    pricing_source = "supplier_quote" if raw_supplier_unit_price > Decimal("0.00") else "payload"

    apply_margin = _normalize_bool(
        item.get("apply_margin", payload.get("apply_margin_to_supplier_price", True)),
        True,
    )
    final_unit_price = _apply_margin_to_price(selected_unit_price, payload) if apply_margin else selected_unit_price

    line_total = _safe_decimal(
        item.get("total")
        or item.get("line_total")
        or item.get("total_price"),
        Decimal("0.00"),
    )

    if line_total <= Decimal("0.00"):
        line_total = (qty * final_unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    supplier_name = _safe_str(item.get("supplier_name") or item.get("vendor_name"))
    return {
        "item_no": idx,
        "description": description,
        "unit": unit,
        "quantity": qty,
        "unit_price": final_unit_price,
        "line_total": line_total,
        "pricing_source": pricing_source,
        "raw_supplier_unit_price": raw_supplier_unit_price,
        "raw_unit_price": raw_unit_price,
        "supplier_name": supplier_name,
    }


def _extract_schedule_rows_from_value(value: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(value, list):
        rows = [row for row in value if isinstance(row, dict)]
        return rows if rows else None

    if isinstance(value, dict):
        for key in ["items", "rows", "line_items", "pricing_items", "schedule_items"]:
            nested = value.get(key)
            if isinstance(nested, list):
                rows = [row for row in nested if isinstance(row, dict)]
                if rows:
                    return rows
    return None


def _extract_items(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str, bool, str]:
    original = _get_original_input_payload(payload)

    candidate_sources: List[Tuple[Any, str]] = [
        (payload.get("items"), "items"),
        (payload.get("line_items"), "line_items"),
        (payload.get("pricing_items"), "pricing_items"),
        (payload.get("supplier_quote_items"), "supplier_quote_items"),
        (payload.get("pricing_schedule"), "pricing_schedule"),
        (payload.get("pricing_schedule_mapped"), "pricing_schedule_mapped"),
        (payload.get("buyer_pricing_schedule"), "buyer_pricing_schedule"),
        (original.get("items"), "original_items"),
        (original.get("line_items"), "original_line_items"),
        (original.get("pricing_items"), "original_pricing_items"),
        (original.get("supplier_quote_items"), "original_supplier_quote_items"),
        (original.get("pricing_schedule"), "original_pricing_schedule"),
        (original.get("pricing_schedule_mapped"), "original_pricing_schedule_mapped"),
        (original.get("buyer_pricing_schedule"), "original_buyer_pricing_schedule"),
    ]

    selected_source_name = "fallback"
    selected_supplier_name = ""
    supplier_pricing_used = False

    for raw_items, source_name in candidate_sources:
        rows = _extract_schedule_rows_from_value(raw_items)
        if rows is None:
            if isinstance(raw_items, dict):
                rows = [raw_items]
            elif isinstance(raw_items, list):
                rows = raw_items

        normalized: List[Dict[str, Any]] = []
        if isinstance(rows, list):
            for idx, item in enumerate(rows, start=1):
                if not isinstance(item, dict):
                    normalized.append(
                        {
                            "item_no": idx,
                            "description": _safe_str(item, f"Item {idx}"),
                            "unit": "Each",
                            "quantity": Decimal("1.00"),
                            "unit_price": Decimal("0.00"),
                            "line_total": Decimal("0.00"),
                            "pricing_source": source_name,
                            "raw_supplier_unit_price": Decimal("0.00"),
                            "raw_unit_price": Decimal("0.00"),
                            "supplier_name": "",
                        }
                    )
                else:
                    normalized_item = _normalize_line_item(item, idx, payload)
                    normalized_item["pricing_source"] = normalized_item.get("pricing_source") or source_name
                    normalized.append(normalized_item)

        has_meaningful = any(
            (
                _safe_str(item.get("description"))
                and item.get("description") != "Supply and delivery item"
            )
            or _safe_decimal(item.get("unit_price")) > Decimal("0.00")
            or _safe_decimal(item.get("line_total")) > Decimal("0.00")
            for item in normalized
        )

        if normalized and has_meaningful:
            selected_source_name = source_name
            selected_supplier_name = _pick_first_meaningful(
                *[item.get("supplier_name") for item in normalized],
                payload.get("selected_supplier_name"),
                payload.get("supplier_name"),
                original.get("selected_supplier_name"),
                original.get("supplier_name"),
            )
            supplier_pricing_used = any(
                _safe_decimal(item.get("raw_supplier_unit_price")) > Decimal("0.00")
                for item in normalized
            )
            return normalized, selected_source_name, supplier_pricing_used, selected_supplier_name

    fallback_total = _safe_decimal(
        payload.get("grand_total")
        or payload.get("total")
        or payload.get("quote_total")
        or payload.get("final_total")
        or payload.get("amount")
        or payload.get("estimated_total"),
        Decimal("0.00"),
    )

    fallback_description = _safe_str(
        _extract_subject(payload) or "Supply and delivery as per RFQ specification",
        "Supply and delivery as per RFQ specification",
    )

    return (
        [
            {
                "item_no": 1,
                "description": fallback_description,
                "unit": "Lot",
                "quantity": Decimal("1.00"),
                "unit_price": fallback_total,
                "line_total": fallback_total,
                "pricing_source": "fallback",
                "raw_supplier_unit_price": Decimal("0.00"),
                "raw_unit_price": fallback_total,
                "supplier_name": "",
            }
        ],
        "fallback",
        False,
        "",
    )


def _extract_buyer_schedule(payload: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    for value in [
        payload.get("buyer_pricing_schedule"),
        payload.get("pricing_schedule_mapped"),
        payload.get("pricing_schedule"),
    ]:
        rows = _extract_schedule_rows_from_value(value)
        if rows:
            return rows
    return None


def _compute_totals(payload: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Decimal]:
    original = _get_original_input_payload(payload)

    subtotal = sum((_safe_decimal(item.get("line_total")) for item in items), Decimal("0.00"))

    explicit_subtotal = _safe_decimal(
        payload.get("subtotal") or original.get("subtotal"),
        Decimal("0.00"),
    )
    if explicit_subtotal > Decimal("0.00"):
        subtotal = explicit_subtotal

    vat_amount = _safe_decimal(
        payload.get("vat_amount") or payload.get("vat") or original.get("vat_amount") or original.get("vat"),
        Decimal("0.00"),
    )
    vat_rate = _safe_decimal(payload.get("vat_rate") or original.get("vat_rate"), DEFAULT_VAT_RATE)
    grand_total = _safe_decimal(
        payload.get("grand_total")
        or payload.get("total")
        or payload.get("quote_total")
        or payload.get("quotation_total")
        or payload.get("final_total")
        or original.get("grand_total")
        or original.get("total")
        or original.get("quote_total")
        or original.get("quotation_total"),
        Decimal("0.00"),
    )

    vat_inclusive = str(payload.get("vat_inclusive", "false")).strip().lower() in {"1", "true", "yes", "on"}

    if grand_total <= Decimal("0.00"):
        if vat_inclusive and subtotal > Decimal("0.00"):
            divisor = Decimal("1.00") + (vat_rate / Decimal("100.00"))
            subtotal_excl = (
                (subtotal / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if divisor > 0
                else subtotal
            )
            vat_amount = (subtotal - subtotal_excl).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            grand_total = subtotal
            subtotal = subtotal_excl
        else:
            if vat_amount <= Decimal("0.00") and subtotal > Decimal("0.00") and vat_rate > Decimal("0.00"):
                vat_amount = (subtotal * vat_rate / Decimal("100.00")).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
            grand_total = (subtotal + vat_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        if vat_amount <= Decimal("0.00") and grand_total > subtotal:
            vat_amount = (grand_total - subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "subtotal_excl_vat": subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "vat_amount": vat_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "total_incl_vat": grand_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "vat_rate": vat_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }


def _build_output_folder(
    buyer_rfq_number: str,
    quote_number: str,
    output_root: Optional[str] = None,
) -> Path:
    root = Path(output_root or os.getenv("QUOTE_PACK_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT))
    month_folder = _now().strftime("%Y-%m")

    rfq_segment = _clean_filename(buyer_rfq_number or "NO-RFQ")
    quote_segment = _clean_filename(quote_number or "NO-QUOTE")

    folder = root / month_folder / f"{rfq_segment}__{quote_segment}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _extract_submission_method(payload: Dict[str, Any]) -> str:
    original = _get_original_input_payload(payload)
    return _pick_first_meaningful(
        payload.get("submission_method"),
        payload.get("submission"),
        payload.get("submission_channel"),
        payload.get("delivery_method"),
        original.get("submission_method"),
        original.get("submission"),
        original.get("submission_channel"),
        original.get("delivery_method"),
        default=DEFAULT_SUBMISSION_METHOD,
    )


def _extract_validity_days(payload: Dict[str, Any]) -> int:
    original = _get_original_input_payload(payload)
    try:
        return int(
            _safe_decimal(
                payload.get("validity_days")
                or original.get("validity_days")
                or DEFAULT_VALIDITY_DAYS
            )
        )
    except Exception:
        return DEFAULT_VALIDITY_DAYS


def _extract_delivery_text(payload: Dict[str, Any]) -> str:
    original = _get_original_input_payload(payload)
    return _pick_first_meaningful(
        payload.get("delivery_period"),
        payload.get("delivery"),
        payload.get("delivery_time"),
        payload.get("delivery_days"),
        original.get("delivery_period"),
        original.get("delivery"),
        original.get("delivery_time"),
        original.get("delivery_days"),
        default=DEFAULT_DELIVERY_PERIOD,
    )


def _extract_payment_terms(payload: Dict[str, Any]) -> str:
    original = _get_original_input_payload(payload)
    return _pick_first_meaningful(
        payload.get("payment_terms"),
        original.get("payment_terms"),
        default="Payment due within 30 days from statement unless otherwise agreed in writing.",
    )


def _extract_notes(payload: Dict[str, Any]) -> List[str]:
    validity_days = _extract_validity_days(payload)
    delivery = _extract_delivery_text(payload)

    notes: List[str] = [
        f"Quotation validity: {validity_days} days from date of issue.",
        f"Estimated delivery period: {delivery} from official order or appointment.",
        "Pricing is subject to final confirmation against the buyer's full RFQ documents and specifications.",
        "This quote is valid for 30 days from the date issued, for any queries pertaining the quote please contact us at 0826338492 or lechesam@me.com.",
    ]

    original = _get_original_input_payload(payload)
    extra_notes = (
        payload.get("special_terms")
        or payload.get("terms")
        or payload.get("notes")
        or payload.get("quote_notes")
        or original.get("special_terms")
        or original.get("terms")
        or original.get("notes")
        or original.get("quote_notes")
    )

    if isinstance(extra_notes, list):
        for note in extra_notes:
            note_text = _safe_str(note)
            if note_text:
                notes.append(note_text)
    elif isinstance(extra_notes, str):
        note_text = _safe_str(extra_notes)
        if note_text:
            notes.append(note_text)

    return notes


def _path_exists(value: Any) -> bool:
    try:
        text = _safe_str(value)
        return bool(text) and Path(text).expanduser().exists()
    except Exception:
        return False


def _normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    seen = set()
    for item in value:
        text = _safe_str(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _normalize_document_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    result: List[Dict[str, Any]] = []
    seen = set()

    for item in value:
        if not isinstance(item, dict):
            path = _safe_str(item)
            if not path:
                continue
            doc = {
                "label": Path(path).name,
                "path": path,
                "filename": Path(path).name,
                "category": "supporting_document",
                "source": "payload",
                "required": False,
                "exists": _path_exists(path),
                "metadata": {},
            }
        else:
            path = _safe_str(item.get("path"))
            doc = {
                "label": _safe_str(item.get("label"), Path(path).name if path else "Document"),
                "path": path,
                "filename": _safe_str(item.get("filename"), Path(path).name if path else ""),
                "category": _safe_str(item.get("category"), "supporting_document"),
                "source": _safe_str(item.get("source"), "payload"),
                "required": bool(item.get("required", False)),
                "exists": bool(item.get("exists")) if "exists" in item else _path_exists(path),
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            }

        key = _safe_str(doc.get("path")).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(doc)

    return result


def _serialize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for item in items:
        serialized.append(
            {
                "item_no": item.get("item_no"),
                "description": _safe_str(item.get("description")),
                "unit": _safe_str(item.get("unit"), "Each"),
                "quantity": float(_safe_decimal(item.get("quantity"), Decimal("0.00"))),
                "unit_price": float(_safe_decimal(item.get("unit_price"), Decimal("0.00"))),
                "line_total": float(_safe_decimal(item.get("line_total"), Decimal("0.00"))),
                "pricing_source": _safe_str(item.get("pricing_source")),
                "supplier_name": _safe_str(item.get("supplier_name")),
            }
        )
    return serialized


def _build_pdf(
    *,
    pdf_path: Path,
    seller: Dict[str, Any],
    buyer: Dict[str, Any],
    numbers: QuoteNumbers,
    subject: str,
    items: List[Dict[str, Any]],
    totals: Dict[str, Decimal],
    payload: Dict[str, Any],
    buyer_schedule: Optional[List[Dict[str, Any]]] = None,
) -> None:
    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "LMCPNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        spaceAfter=2,
    )

    small = ParagraphStyle(
        "LMCPSmall",
        parent=normal,
        fontSize=8,
        leading=10,
        spaceAfter=1,
    )

    header_left = ParagraphStyle(
        "LMCPHeaderLeft",
        parent=normal,
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        alignment=0,
    )

    header_right = ParagraphStyle(
        "LMCPHeaderRight",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=18,
        alignment=2,
    )

    section_title = ParagraphStyle(
        "LMCPSectionTitle",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        spaceAfter=4,
        spaceBefore=4,
    )

    quote_date = _safe_str(payload.get("quote_date"), _now().strftime("%Y-%m-%d"))
    currency = _safe_str(payload.get("currency"), DEFAULT_CURRENCY).upper()
    validity_days = _extract_validity_days(payload)
    delivery_text = _extract_delivery_text(payload)
    payment_terms = _extract_payment_terms(payload)
    submission_method = _extract_submission_method(payload)
    notes = _extract_notes(payload)

    pricing_source = _safe_str(payload.get("pricing_source"), "unknown")
    selected_supplier_name = _safe_str(payload.get("selected_supplier_name"))
    supplier_pricing_used = _normalize_bool(payload.get("supplier_pricing_used"), False)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    story: List[Any] = []

    header_data = [
        [
            _paragraph(
                "<b>%s</b><br/>%s<br/>Tel: %s<br/>Email: %s<br/>Reg No: %s<br/>VAT No: %s"
                % (
                    seller["name"],
                    seller["address"],
                    seller["phone"],
                    seller["email"],
                    seller["registration_number"],
                    seller["vat_number"],
                ),
                header_left,
            ),
            _paragraph("QUOTATION", header_right),
        ]
    ]
    header_table = Table(header_data, colWidths=[125 * mm, 50 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 4))

    story.append(_paragraph(f"Quote No: {numbers.quote_number}", normal))
    story.append(_paragraph(f"Issue Date: {quote_date}", normal))
    story.append(_paragraph(f"Subject: {subject}", normal))
    story.append(_paragraph(f"Buyer: {buyer['name']}", normal))
    story.append(
        _paragraph(
            f"Validity: {validity_days} days&nbsp;&nbsp;&nbsp;Delivery: {delivery_text}&nbsp;&nbsp;&nbsp;Currency: {currency}",
            normal,
        )
    )
    story.append(Spacer(1, 6))

    buyer_supplier_data = [
        [
            _paragraph("<b>Buyer / Client Details</b>", section_title),
            _paragraph("<b>Supplier Details</b>", section_title),
        ],
        [
            _paragraph(
                "<br/>".join(
                    [
                        buyer["name"],
                        buyer["department"],
                        buyer["contact_person"],
                        buyer["email"],
                        buyer["phone"],
                        *buyer["address_lines"],
                    ]
                ),
                normal,
            ),
            _paragraph(
                "<br/>".join(
                    [
                        seller["name"],
                        seller["email"],
                        seller["phone"],
                        seller["address"],
                        f"Reg No: {seller['registration_number']}",
                    ]
                ),
                normal,
            ),
        ],
    ]

    buyer_supplier_table = Table(buyer_supplier_data, colWidths=[87.5 * mm, 87.5 * mm])
    buyer_supplier_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(buyer_supplier_table)
    story.append(Spacer(1, 6))

    story.append(_paragraph(f"Reference: {numbers.quote_number}", normal))
    if numbers.buyer_rfq_number:
        story.append(_paragraph(f"RFQ ID: {numbers.buyer_rfq_number}", normal))
    story.append(_paragraph(f"Document Number: {numbers.document_number}", normal))
    story.append(_paragraph(f"Submission: {submission_method}", normal))
    story.append(_paragraph(f"Validity: {validity_days} days", normal))
    story.append(_paragraph(f"Delivery: {delivery_text}", normal))
    story.append(_paragraph(f"Payment: {payment_terms}", normal))
    if pricing_source:
        story.append(_paragraph(f"Pricing Source: {pricing_source}", normal))
    if supplier_pricing_used:
        supplier_line = selected_supplier_name or "Supplier quotation"
        story.append(_paragraph(f"Supplier Pricing Used: Yes - {supplier_line}", normal))
    story.append(Spacer(1, 6))

    table_rows: List[List[Any]] = [
        [
            _paragraph("<b>No.</b>", small),
            _paragraph("<b>Description</b>", small),
            _paragraph("<b>Unit</b>", small),
            _paragraph("<b>Qty</b>", small),
            _paragraph("<b>Unit Price</b>", small),
            _paragraph("<b>Line Total</b>", small),
        ]
    ]

    for item in items:
        table_rows.append(
            [
                _paragraph(str(item["item_no"]), small),
                _paragraph(_safe_str(item["description"]), small),
                _paragraph(_safe_str(item["unit"], "Each"), small),
                _paragraph(f"{_safe_decimal(item['quantity']):,.2f}", small),
                _paragraph(_money(item["unit_price"], currency), small),
                _paragraph(_money(item["line_total"], currency), small),
            ]
        )

    pricing_table = Table(
        table_rows,
        colWidths=[12 * mm, 86 * mm, 18 * mm, 16 * mm, 28 * mm, 30 * mm],
        repeatRows=1,
    )
    pricing_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(pricing_table)
    story.append(Spacer(1, 5))

    totals_rows = [
        ["Subtotal Excl. VAT", _money(totals["subtotal_excl_vat"], currency)],
        [f"VAT ({totals['vat_rate']}%)", _money(totals["vat_amount"], currency)],
        ["Total Incl. VAT", _money(totals["total_incl_vat"], currency)],
    ]
    totals_table = Table(totals_rows, colWidths=[120 * mm, 42 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 6))

    if buyer_schedule:
        story.append(_paragraph("<b>Buyer Pricing Schedule</b>", section_title))
        schedule_rows: List[List[Any]] = [
            [
                _paragraph("<b>No.</b>", small),
                _paragraph("<b>Description</b>", small),
                _paragraph("<b>Qty</b>", small),
                _paragraph("<b>Amount</b>", small),
            ]
        ]

        for idx, row in enumerate(buyer_schedule, start=1):
            desc = _safe_str(
                row.get("description")
                or row.get("item_description")
                or row.get("name")
                or f"Item {idx}"
            )
            qty = _safe_decimal(row.get("quantity") or 1)
            amount = _safe_decimal(
                row.get("amount")
                or row.get("total")
                or row.get("total_price")
                or row.get("price")
                or row.get("unit_price")
            )

            schedule_rows.append(
                [
                    _paragraph(str(idx), small),
                    _paragraph(desc, small),
                    _paragraph(f"{qty:,.2f}", small),
                    _paragraph(_money(amount, currency), small),
                ]
            )

        schedule_table = Table(
            schedule_rows,
            colWidths=[12 * mm, 110 * mm, 18 * mm, 35 * mm],
            repeatRows=1,
        )
        schedule_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(schedule_table)
        story.append(Spacer(1, 6))

    story.append(_paragraph("<b>Notes and Conditions</b>", section_title))
    for note in notes:
        story.append(_paragraph(f"- {note}", normal))
    story.append(Spacer(1, 4))

    story.append(_paragraph("<b>Payment Terms</b>", section_title))
    story.append(_paragraph(payment_terms, normal))
    story.append(Spacer(1, 8))

    story.append(
        _paragraph(
            f"Prepared by {seller['name']}<br/>{seller['address']}<br/>{seller['phone']} | {seller['email']}",
            small,
        )
    )

    doc.build(story)


class QuotePackService:
    @classmethod
    def generate_quote_pack(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        safe_payload = deepcopy(payload if isinstance(payload, dict) else {})
        original_payload = _get_original_input_payload(safe_payload)

        result: Dict[str, Any] = deepcopy(safe_payload)
        result.setdefault("quote_generated", False)
        result.setdefault("pdf_generated", False)

        try:
            seller = _normalize_seller(safe_payload)
            buyer = _normalize_buyer(safe_payload)

            locked_rfq = _get_locked_rfq(safe_payload)

            if locked_rfq:
                numbers = _resolve_quote_numbers({
                    **safe_payload,
                    "_locked_buyer_rfq_number": locked_rfq,
                    "buyer_rfq_number": locked_rfq,
                    "rfq_number": locked_rfq,
                    "reference_number": locked_rfq,
                    "document_number": locked_rfq,
                })
            else:
                numbers = _resolve_quote_numbers(safe_payload)

            locked_rfq = _safe_str(
                safe_payload.get("_locked_buyer_rfq_number")
                or numbers.buyer_rfq_number
            )

            subject = _extract_subject({
                **safe_payload,
                "_locked_buyer_rfq_number": locked_rfq,
                "buyer_rfq_number": locked_rfq or safe_payload.get("buyer_rfq_number"),
                "rfq_number": locked_rfq or safe_payload.get("rfq_number"),
                "reference_number": locked_rfq or safe_payload.get("reference_number"),
                "document_number": locked_rfq or safe_payload.get("document_number"),
            })

            items, pricing_source, supplier_pricing_used, selected_supplier_name = _extract_items(safe_payload)
            buyer_schedule = _extract_buyer_schedule(safe_payload)
            totals = _compute_totals(safe_payload, items)

            output_folder = _build_output_folder(
                buyer_rfq_number=locked_rfq or numbers.buyer_rfq_number,
                quote_number=numbers.quote_number,
                output_root=_safe_str(safe_payload.get("output_root"), "") or None,
            )

            quote_pack_dir = output_folder
            monthly_quote_folder = output_folder

            pdf_filename = f"{_clean_filename(locked_rfq)}__{_clean_filename(numbers.quote_number)}.pdf"
            pdf_path = quote_pack_dir / pdf_filename

            pdf_payload = deepcopy(safe_payload)
            pdf_payload["_locked_buyer_rfq_number"] = locked_rfq
            pdf_payload["buyer_rfq_number"] = locked_rfq
            pdf_payload["rfq_number"] = locked_rfq
            pdf_payload["reference_number"] = locked_rfq
            pdf_payload["document_number"] = locked_rfq
            pdf_payload["pricing_source"] = pricing_source
            pdf_payload["supplier_pricing_used"] = supplier_pricing_used
            pdf_payload["selected_supplier_name"] = selected_supplier_name

            # ================================
            # 📄 GENERATE PDF (LOCKED)
            # ================================
            _build_pdf(
                pdf_path=pdf_path,
                seller=seller,
                buyer=buyer,
                numbers=QuoteNumbers(
                    buyer_rfq_number=locked_rfq or numbers.buyer_rfq_number,
                    quote_number=numbers.quote_number,
                    document_number=locked_rfq or numbers.document_number,
                ),
                subject=subject,
                items=items,
                totals=totals,
                payload=pdf_payload,
                buyer_schedule=buyer_schedule,
            )
            
            # ================================
            # 🔒 PDF VALIDATION (MANDATORY)
            # ================================
            if not pdf_path.exists():
                raise RuntimeError("PDF generation failed - file not created")

            if pdf_path.stat().st_size == 0:
                raise RuntimeError("PDF generation failed - empty file")

            existing_supporting_docs = _normalize_document_list(
                safe_payload.get("supporting_documents") or result.get("supporting_documents") or []
            )
            merged_supporting_docs = ComplianceDocumentService.merge_compliance_documents(
                existing_docs=existing_supporting_docs,
                include_defaults=True,
            )
            merged_supporting_docs = _normalize_document_list(merged_supporting_docs)

            existing_attachment_paths = _normalize_string_list(
                safe_payload.get("submission_attachments") or result.get("submission_attachments") or []
            )

            existing_attachment_paths = [p for p in existing_attachment_paths if p != str(pdf_path)]
            existing_attachment_paths.insert(0, str(pdf_path))

            submission_attachments = ComplianceDocumentService.build_pack_attachment_paths(
                existing_paths=existing_attachment_paths,
                include_default_compliance_docs=True,
            )
            submission_attachments = _normalize_string_list(submission_attachments)

            if str(pdf_path) not in submission_attachments:
                submission_attachments.insert(0, str(pdf_path))
            else:
                submission_attachments = [str(pdf_path)] + [
                    p for p in submission_attachments if p != str(pdf_path)
                ]

            explicit_csd_path = _pick_first_meaningful(
                safe_payload.get("latest_csd_report"),
                safe_payload.get("csd_report_path"),
                original_payload.get("latest_csd_report"),
                original_payload.get("csd_report_path"),
            ) or None

            latest_csd_doc = ComplianceDocumentService.resolve_csd_report(explicit_path=explicit_csd_path)
            if latest_csd_doc and isinstance(latest_csd_doc, dict):
                normalized_csd_docs = _normalize_document_list([latest_csd_doc])
                latest_csd_doc = normalized_csd_docs[0] if normalized_csd_docs else None

            serializable_items = _serialize_items(items)

            pricing_schedule_source = "buyer_pricing_schedule" if buyer_schedule else ""
            used_buyer_format = bool(buyer_schedule)

            metadata = {
                "buyer_rfq_number": _safe_str(
                    safe_payload.get("_locked_buyer_rfq_number")
                    or numbers.buyer_rfq_number
                ),
                "quote_number": numbers.quote_number,
                "document_number": _safe_str(
                    safe_payload.get("_locked_buyer_rfq_number")
                    or numbers.document_number
                ),
                "pdf_path": str(pdf_path),
                "quote_folder": str(output_folder),
                "quote_pack_dir": str(quote_pack_dir),
                "monthly_quote_folder": str(monthly_quote_folder),
                "generated_at": _now().isoformat(),
                "currency": _safe_str(safe_payload.get("currency"), DEFAULT_CURRENCY).upper(),
                "seller": seller,
                "buyer": buyer,
                "subject": subject,
                "pricing_source": pricing_source,
                "pricing_schedule_source": pricing_schedule_source,
                "supplier_pricing_used": supplier_pricing_used,
                "selected_supplier_name": selected_supplier_name,
                "used_buyer_format": used_buyer_format,
                "totals": {
                    "subtotal_excl_vat": str(totals["subtotal_excl_vat"]),
                    "vat_amount": str(totals["vat_amount"]),
                    "total_incl_vat": str(totals["total_incl_vat"]),
                    "vat_rate": str(totals["vat_rate"]),
                },
                "items_count": len(items),
                "items": serializable_items,
                "buyer_pricing_schedule": buyer_schedule or [],
                "supporting_documents": merged_supporting_docs,
                "submission_attachments": submission_attachments,
                "latest_csd_report": latest_csd_doc,
                "csd_report_attached": bool(latest_csd_doc and latest_csd_doc.get("exists")),
            }

            metadata_path = quote_pack_dir / "quote_pack_metadata.json"
            with metadata_path.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            recipient_email = buyer["email"] if buyer["email"] != "-" else _pick_first_meaningful(
                safe_payload.get("recipient_email"),
                safe_payload.get("buyer_email"),
                safe_payload.get("submission_email"),
                original_payload.get("recipient_email"),
                original_payload.get("buyer_email"),
                original_payload.get("submission_email"),
            )

            result.update(
                {
                    "quote_generated": True,
                    "pdf_generated": True,
                    "quote_number": numbers.quote_number,
                    "lmcp_quote_number": numbers.quote_number,
                    "buyer_rfq_number": locked_rfq,
                    "_locked_buyer_rfq_number": locked_rfq,
                    "document_number": locked_rfq,
                    "rfq_number": locked_rfq,
                    "reference_number": locked_rfq,
                    "pdf_path": str(pdf_path),
                    "final_pdf_path": str(pdf_path),
                    "quote_folder": str(output_folder),
                    "quote_pack_dir": str(quote_pack_dir),
                    "monthly_quote_folder": str(monthly_quote_folder),
                    "quote_pack_metadata_path": str(metadata_path),
                    "seller": seller,
                    "buyer": buyer,
                    "buyer_name": buyer["name"],
                    "recipient_email": recipient_email,
                    "buyer_email": recipient_email,
                    "items": serializable_items,
                    "line_items": serializable_items,
                    "subtotal": float(totals["subtotal_excl_vat"]),
                    "vat_amount": float(totals["vat_amount"]),
                    "grand_total": float(totals["total_incl_vat"]),
                    "quotation_total": float(totals["total_incl_vat"]),
                    "total": float(totals["total_incl_vat"]),
                    "quote_subject": subject,
                    "subject": subject,
                    "pricing_source": pricing_source,
                    "pricing_schedule_source": pricing_schedule_source,
                    "used_buyer_format": used_buyer_format,
                    "supplier_pricing_used": supplier_pricing_used,
                    "selected_supplier_name": selected_supplier_name,
                    "submission_method": _extract_submission_method(safe_payload),
                    "supporting_documents": merged_supporting_docs,
                    "submission_attachments": submission_attachments,
                    "latest_csd_report": latest_csd_doc,
                    "csd_report_attached": bool(latest_csd_doc and latest_csd_doc.get("exists")),
                    "_original_input_payload": original_payload,
                }
            )

            submission_pack = deepcopy(result.get("submission_pack") or {})
            submission_pack.update(
                {
                    "buyer_rfq_number": locked_rfq,
                    "quote_number": numbers.quote_number,
                    "document_number": locked_rfq,
                    "submission_method": _extract_submission_method(safe_payload),
                    "recipient_email": result.get("recipient_email"),
                    "buyer_email": result.get("recipient_email"),
                    "monthly_quote_folder": str(monthly_quote_folder),
                    "quote_folder": str(output_folder),
                    "quote_pack_dir": str(quote_pack_dir),
                    "quote_pack_metadata_path": str(metadata_path),
                    "pdf_path": str(pdf_path),
                    "final_pdf_path": str(pdf_path),
                    "submission_attachments": submission_attachments,
                    "supporting_documents": merged_supporting_docs,
                    "supplier_quotes_folder": _safe_str(
                        safe_payload.get("supplier_quotes_folder") or output_folder
                    ),
                    "pricing_source": pricing_source,
                    "pricing_schedule_source": pricing_schedule_source,
                    "used_buyer_format": used_buyer_format,
                    "supplier_pricing_used": supplier_pricing_used,
                    "selected_supplier_name": selected_supplier_name,
                }
            )
            result["submission_pack"] = submission_pack
            result["monthly_quote_folder"] = str(monthly_quote_folder)
            result["quote_folder"] = str(output_folder)
            result["quote_pack_dir"] = str(quote_pack_dir)

            if buyer_schedule:
                result["pricing_schedule"] = buyer_schedule
                result["buyer_pricing_schedule"] = buyer_schedule

            submission_method = safe_payload.get("submission_method", "email")

            recipient_email = (
                safe_payload.get("recipient_email")
                or safe_payload.get("buyer_email")
                or safe_payload.get("buyer", {}).get("email")
            )

            if submission_method == "physical":
                submission_channel = "physical_via_email"
                recipient_email = "lmcpaqsystem@gmail.com"
            elif submission_method == "portal":
                submission_channel = "portal"
            else:
                submission_channel = "email"
                if not recipient_email:
                    recipient_email = "lmcpaqsystem@gmail.com"

            submission_pack = {
                "buyer_rfq_number": locked_rfq or numbers.buyer_rfq_number,
                "document_number": locked_rfq or numbers.document_number,
                "monthly_quote_folder": str(monthly_quote_folder),
                "quote_folder": str(output_folder),
                "supplier_quotes_folder": _safe_str(
                    safe_payload.get("supplier_quotes_folder") or output_folder
            ),
            "quote_number": numbers.quote_number,
            "submission_method": submission_method,
            "submission_channel": submission_channel,
            "recipient_email": recipient_email,
            "buyer_email": _safe_str(safe_payload.get("buyer_email") or ""),
            "quote_pack_dir": str(quote_pack_dir),
            "quote_pack_metadata_path": str(metadata_path),
            "pdf_path": str(pdf_path),
            "final_pdf_path": str(pdf_path),
            "submission_attachments": submission_attachments,
            "supporting_documents": merged_supporting_docs,
            "pricing_source": pricing_source,
            "pricing_schedule_source": pricing_schedule_source,
            "used_buyer_format": used_buyer_format,
            "supplier_pricing_used": supplier_pricing_used,
            "selected_supplier_name": selected_supplier_name,
        }
            
            return result

        except Exception as exc:
            result.update(
                {
                    "quote_generated": False,
                    "pdf_generated": False,
                    "pdf_path": "",
                    "final_pdf_path": "",
                    "quote_pack_error": str(exc),
                    "_original_input_payload": original_payload,
                }
            )
            return result


def generate_quote_pack(payload: Dict[str, Any]) -> Dict[str, Any]:
    return QuotePackService.generate_quote_pack(payload)
