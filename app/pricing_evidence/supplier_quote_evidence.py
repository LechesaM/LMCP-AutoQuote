from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List


SOURCE_PENALTIES = {
    "estimated/manual": 20.0,
    "estimated": 18.0,
    "manual": 18.0,
    "historical pricing": 10.0,
    "historical": 10.0,
    "phone confirmation": 6.0,
    "website/catalogue": 4.0,
    "website": 4.0,
    "catalogue": 4.0,
    "emailed quote": 0.0,
    "email": 0.0,
    "email quote": 0.0,
}


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        if isinstance(value, str):
            value = value.replace("R", "").replace(",", "").strip()
        return float(value)
    except Exception:
        return float(default)


def _parse_dt(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    text = _safe_str(value)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except Exception:
        return text


def _supplier_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    supplier = payload.get("supplier")
    if not isinstance(supplier, dict):
        supplier = {}
    return supplier


def _line_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("lines") or payload.get("line_items") or payload.get("quoted_items") or []
    return [item for item in items if isinstance(item, dict)]


def _normalize_source_type(value: Any) -> str:
    source = _safe_str(value).lower()
    if "email" in source:
        return "emailed quote"
    if "phone" in source:
        return "phone confirmation"
    if "website" in source or "catalogue" in source:
        return "website/catalogue"
    if "historical" in source:
        return "historical pricing"
    if "estimate" in source or "manual" in source:
        return "estimated/manual"
    return source or "emailed quote"


def build_supplier_quote_evidence(quote_or_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(quote_or_payload or {})
    supplier = _supplier_info(payload)
    supplier_name = _safe_str(payload.get("supplier_name") or supplier.get("supplier_name"))
    supplier_contact = _safe_str(
        payload.get("supplier_contact")
        or payload.get("contact_name")
        or supplier.get("contact_name")
        or supplier.get("contact_email")
        or supplier.get("contact_phone")
    )
    quote_reference = _safe_str(payload.get("quote_reference") or payload.get("supplier_quote_reference"))
    quote_received_date = _parse_dt(payload.get("quote_received_date"))
    quote_valid_until = _parse_dt(payload.get("quote_valid_until"))
    delivery_assumptions = payload.get("delivery_assumptions")
    if not isinstance(delivery_assumptions, list):
        delivery_assumptions = []
    vat_clarity = _safe_str(payload.get("vat_clarity") or ("VAT registered" if payload.get("vat_registered") else ""))
    stock_availability_notes = payload.get("stock_availability_notes")
    if not isinstance(stock_availability_notes, list):
        stock_availability_notes = []
    lead_time_notes = payload.get("lead_time_notes")
    if not isinstance(lead_time_notes, list):
        lead_time_notes = []
    quotation_source_type = _normalize_source_type(
        payload.get("quotation_source_type") or payload.get("source_type") or payload.get("quote_source_type")
    )
    lines = _line_items(payload)
    quoted_items = [str(item.get("description") or item.get("item") or "").strip() for item in lines if str(item.get("description") or item.get("item") or "").strip()]
    quoted_unit_prices = [_safe_float(item.get("unit_price") or item.get("price") or item.get("unit_cost")) for item in lines if item.get("unit_price") is not None or item.get("price") is not None or item.get("unit_cost") is not None]
    quoted_totals = [
        _safe_float(item.get("line_total") or item.get("total") or item.get("amount"))
        for item in lines
        if item.get("line_total") is not None or item.get("total") is not None or item.get("amount") is not None
    ]

    evidence_fields = {
        "supplier_name": bool(supplier_name),
        "supplier_contact": bool(supplier_contact),
        "quote_reference": bool(quote_reference),
        "quote_received_date": bool(quote_received_date),
        "quote_valid_until": bool(quote_valid_until),
        "quoted_items": bool(quoted_items),
        "quoted_unit_prices": bool(quoted_unit_prices),
        "quoted_totals": bool(quoted_totals),
        "delivery_assumptions": bool(delivery_assumptions),
        "vat_clarity": bool(vat_clarity),
        "stock_availability_notes": bool(stock_availability_notes),
        "lead_time_notes": bool(lead_time_notes),
        "quotation_source_type": bool(quotation_source_type),
    }
    present_count = sum(1 for present in evidence_fields.values() if present)
    completeness_score = round((present_count / max(len(evidence_fields), 1)) * 100.0, 2)

    evidence_warnings: List[str] = []
    evidence_gaps: List[str] = [name for name, present in evidence_fields.items() if not present]
    source_penalty = SOURCE_PENALTIES.get(quotation_source_type, 8.0 if quotation_source_type else 15.0)
    if quotation_source_type in {"estimated/manual", "manual"}:
        evidence_warnings.append("estimated or manual pricing lowers confidence")
    if not vat_clarity:
        evidence_warnings.append("missing VAT clarity lowers confidence")
    if not delivery_assumptions:
        evidence_warnings.append("missing delivery assumptions lowers confidence")
    if not quoted_items:
        evidence_warnings.append("missing quoted items lowers confidence")
    if not quote_reference:
        evidence_warnings.append("missing supplier quote reference lowers confidence")
    if not quote_received_date:
        evidence_warnings.append("missing quote received date lowers confidence")

    pricing_defensibility_score = round(
        max(
            0.0,
            completeness_score
            - source_penalty
            - (12.0 if not vat_clarity else 0.0)
            - (8.0 if not delivery_assumptions else 0.0)
            - (5.0 if not quoted_items else 0.0)
            - (5.0 if not quoted_totals else 0.0),
        ),
        2,
    )
    return {
        "supplier_name": supplier_name,
        "supplier_contact": supplier_contact,
        "quote_reference": quote_reference,
        "quote_received_date": quote_received_date,
        "quote_valid_until": quote_valid_until,
        "quoted_items": quoted_items,
        "quoted_unit_prices": quoted_unit_prices,
        "quoted_totals": quoted_totals,
        "delivery_assumptions": delivery_assumptions,
        "vat_clarity": vat_clarity,
        "stock_availability_notes": stock_availability_notes,
        "lead_time_notes": lead_time_notes,
        "quotation_source_type": quotation_source_type,
        "evidence_fields": evidence_fields,
        "evidence_gaps": evidence_gaps,
        "evidence_completeness_score": completeness_score,
        "pricing_defensibility_score": pricing_defensibility_score,
        "evidence_warnings": list(dict.fromkeys(evidence_warnings)),
        "supplier_evidence_score": completeness_score,
        "advisory_only": True,
    }


def build_supplier_quote_evidence_summary(quotes: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    reports = [build_supplier_quote_evidence(quote) for quote in quotes if isinstance(quote, dict)]
    if not reports:
        return {
            "quote_count": 0,
            "average_evidence_completeness": 0.0,
            "average_pricing_defensibility": 0.0,
            "evidence_warning_count": 0,
            "supplier_evidence_gaps": {},
            "advisory_only": True,
        }
    gap_counts: Dict[str, int] = {}
    for report in reports:
        for gap in report.get("evidence_gaps", []):
            gap_counts[gap] = gap_counts.get(gap, 0) + 1
    recommended = max(
        reports,
        key=lambda item: (item.get("pricing_defensibility_score", 0.0), item.get("evidence_completeness_score", 0.0)),
    )
    return {
        "quote_count": len(reports),
        "average_evidence_completeness": round(mean(report["evidence_completeness_score"] for report in reports), 2),
        "average_pricing_defensibility": round(mean(report["pricing_defensibility_score"] for report in reports), 2),
        "recommended_evidence": recommended,
        "evidence_warning_count": sum(len(report.get("evidence_warnings", [])) for report in reports),
        "supplier_evidence_gaps": gap_counts,
        "advisory_only": True,
    }
