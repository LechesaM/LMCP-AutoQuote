from __future__ import annotations

from statistics import median
from typing import Any, Dict, Iterable, List

from app.domain.supplier import SupplierQuote
from app.pricing_evidence import (
    assess_pricing_confidence,
    assess_quote_aging,
    build_pricing_traceability,
    build_supplier_quote_evidence,
    build_supplier_quote_evidence_summary,
    validate_pricing_evidence,
)


def _quotes(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("supplier_quotes") or payload.get("quotes") or []
    return [item for item in items if isinstance(item, dict)]


def _quote_total(quote: Dict[str, Any]) -> float:
    total = 0.0
    for line in quote.get("lines") or []:
        if not isinstance(line, dict):
            continue
        quantity = float(line.get("quantity") or 0.0)
        unit_price = float(line.get("unit_price") or 0.0)
        delivery_cost = float(line.get("delivery_cost") or 0.0)
        vat_amount = float(line.get("vat_amount") or 0.0)
        total += (quantity * unit_price) + delivery_cost + vat_amount
    return round(total, 2)


def _supplier_payload(quote: Dict[str, Any]) -> Dict[str, Any]:
    supplier = quote.get("supplier")
    if not isinstance(supplier, dict):
        supplier = {
            "supplier_name": quote.get("supplier_name") or "",
            "contact_name": quote.get("contact_name") or "",
            "contact_email": quote.get("contact_email") or "",
            "contact_phone": quote.get("contact_phone") or "",
            "vat_registered": bool(quote.get("vat_registered", False)) if quote.get("vat_registered") is not None else False,
            "notes": quote.get("notes") if isinstance(quote.get("notes"), list) else [],
        }
    return {
        "supplier": supplier,
        "supplier_contact": quote.get("supplier_contact", ""),
        "quote_reference": quote.get("quote_reference", ""),
        "quote_received_date": quote.get("quote_received_date"),
        "quote_valid_until": quote.get("quote_valid_until"),
        "quotation_source_type": quote.get("quotation_source_type", ""),
        "delivery_assumptions": quote.get("delivery_assumptions") if isinstance(quote.get("delivery_assumptions"), list) else [],
        "quoted_items": quote.get("quoted_items") if isinstance(quote.get("quoted_items"), list) else [],
        "quoted_unit_prices": quote.get("quoted_unit_prices") if isinstance(quote.get("quoted_unit_prices"), list) else [],
        "quoted_totals": quote.get("quoted_totals") if isinstance(quote.get("quoted_totals"), list) else [],
        "vat_clarity": quote.get("vat_clarity", ""),
        "stock_availability_notes": quote.get("stock_availability_notes") if isinstance(quote.get("stock_availability_notes"), list) else [],
        "lead_time_notes": quote.get("lead_time_notes") if isinstance(quote.get("lead_time_notes"), list) else [],
        "confidence_notes": quote.get("confidence_notes") if isinstance(quote.get("confidence_notes"), list) else [],
        "lines": quote.get("lines") if isinstance(quote.get("lines"), list) else [],
        "confidence_score": float(quote.get("confidence_score") or 0.0),
        "price_anomaly_notes": quote.get("price_anomaly_notes") if isinstance(quote.get("price_anomaly_notes"), list) else [],
        "comparison_summary": quote.get("comparison_summary") if isinstance(quote.get("comparison_summary"), dict) else {},
    }


def assess_supplier_pricing_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    quotes = _quotes(payload)
    totals = [_quote_total(quote) for quote in quotes if quote.get("lines")]
    baseline = median(totals) if totals else 0.0
    comparison_rows: List[Dict[str, Any]] = []
    summary_notes: List[str] = []
    pricing_evidence_rows: List[Dict[str, Any]] = []
    pricing_validation_rows: List[Dict[str, Any]] = []
    pricing_confidence_rows: List[Dict[str, Any]] = []
    traceability_rows: List[Dict[str, Any]] = []
    aging_rows: List[Dict[str, Any]] = []
    for quote in quotes:
        anomalies: List[str] = []
        total = _quote_total(quote)
        evidence_report = build_supplier_quote_evidence(quote)
        validation_report = validate_pricing_evidence(quote)
        aging_report = assess_quote_aging(quote)
        confidence_report = assess_pricing_confidence(
            quote,
            evidence_report=evidence_report,
            validation_report=validation_report,
            quote_aging_report=aging_report,
        )
        traceability_report = build_pricing_traceability(
            quote,
            evidence_report=evidence_report,
            validation_report=validation_report,
            quote_aging_report=aging_report,
        )
        if total <= 0:
            anomalies.append("zero price")
        if any(float((line or {}).get("unit_price") or 0.0) < 0 for line in quote.get("lines") or [] if isinstance(line, dict)):
            anomalies.append("negative price")
        if totals and baseline and total < baseline * 0.7:
            anomalies.append("unusually low price")
        if totals and baseline and total > baseline * 1.3:
            anomalies.append("unusually high price")
        if any(float((line or {}).get("delivery_cost") or 0.0) == 0 for line in quote.get("lines") or [] if isinstance(line, dict)):
            anomalies.append("missing delivery cost")
        if quote.get("vat_registered") is None:
            anomalies.append("missing VAT clarity")
        confidence = max(0.0, 1.0 - (0.2 * len(anomalies)))
        comparison_rows.append(
            {
                "supplier_name": quote.get("supplier_name") or (quote.get("supplier") or {}).get("supplier_name", ""),
                "quote_reference": quote.get("quote_reference", ""),
                "total": total,
                "confidence_score": round(confidence, 4),
                "anomalies": anomalies,
            }
        )
        summary_notes.extend(anomalies)
        pricing_evidence_rows.append(evidence_report)
        pricing_validation_rows.append(validation_report)
        pricing_confidence_rows.append(confidence_report)
        traceability_rows.append(traceability_report)
        aging_rows.append(aging_report)

    ranked = sorted(comparison_rows, key=lambda row: (row["confidence_score"], -row["total"]), reverse=True)
    recommended = ranked[0] if ranked else {}
    quote_models = [
        SupplierQuote.validate_payload(
            _supplier_payload(
                {
                    **quote,
                    "confidence_score": row["confidence_score"],
                    "price_anomaly_notes": row["anomalies"],
                    "comparison_summary": {},
                    "supplier_contact": quote.get("supplier_contact", ""),
                    "quote_received_date": quote.get("quote_received_date"),
                    "quotation_source_type": quote.get("quotation_source_type", ""),
                    "delivery_assumptions": quote.get("delivery_assumptions") if isinstance(quote.get("delivery_assumptions"), list) else [],
                    "quoted_items": quote.get("quoted_items") if isinstance(quote.get("quoted_items"), list) else [],
                    "quoted_unit_prices": quote.get("quoted_unit_prices") if isinstance(quote.get("quoted_unit_prices"), list) else [],
                    "quoted_totals": quote.get("quoted_totals") if isinstance(quote.get("quoted_totals"), list) else [],
                    "vat_clarity": quote.get("vat_clarity", ""),
                    "stock_availability_notes": quote.get("stock_availability_notes") if isinstance(quote.get("stock_availability_notes"), list) else [],
                    "lead_time_notes": quote.get("lead_time_notes") if isinstance(quote.get("lead_time_notes"), list) else [],
                }
            )
        ).to_jsonable_dict()
        for quote, row in zip(quotes, comparison_rows)
    ]
    evidence_summary = build_supplier_quote_evidence_summary(quotes)
    pricing_confidence_summary = {
        "quote_count": len(pricing_confidence_rows),
        "average_overall_pricing_confidence": round(sum(row.get("overall_pricing_confidence", 0.0) for row in pricing_confidence_rows) / max(len(pricing_confidence_rows), 1), 2),
        "average_supplier_confidence_score": round(sum(row.get("supplier_confidence_score", 0.0) for row in pricing_confidence_rows) / max(len(pricing_confidence_rows), 1), 2),
        "average_pricing_confidence_score": round(sum(row.get("pricing_confidence_score", 0.0) for row in pricing_confidence_rows) / max(len(pricing_confidence_rows), 1), 2),
        "average_logistics_confidence_score": round(sum(row.get("logistics_confidence_score", 0.0) for row in pricing_confidence_rows) / max(len(pricing_confidence_rows), 1), 2),
        "average_delivery_confidence_score": round(sum(row.get("delivery_confidence_score", 0.0) for row in pricing_confidence_rows) / max(len(pricing_confidence_rows), 1), 2),
        "advisory_only": True,
    }
    return {
        "supplier_quotes": quote_models,
        "comparison_rows": comparison_rows,
        "supplier_comparison_summary": {
            "quote_count": len(comparison_rows),
            "median_total": round(baseline, 2),
            "recommended_supplier": recommended,
            "notes": list(dict.fromkeys(summary_notes)),
        },
        "pricing_evidence_summary": evidence_summary,
        "pricing_validation_summary": {
            "quote_count": len(pricing_validation_rows),
            "validation_passed_count": sum(1 for row in pricing_validation_rows if row.get("validation_passed")),
            "validation_error_count": sum(len(row.get("validation_errors", [])) for row in pricing_validation_rows),
            "validation_warning_count": sum(len(row.get("validation_warnings", [])) for row in pricing_validation_rows),
            "advisory_only": True,
        },
        "pricing_traceability_summary": {
            "quote_count": len(traceability_rows),
            "traceability_chain_lengths": [row.get("traceability_chain_length", 0) for row in traceability_rows],
            "recommended_traceability": (traceability_rows[0]["pricing_traceability_summary"] if traceability_rows else {}),
            "advisory_only": True,
        },
        "quote_aging_summary": {
            "quote_count": len(aging_rows),
            "high_risk_count": sum(1 for row in aging_rows if row.get("risk_level") == "HIGH_RISK"),
            "expired_count": sum(1 for row in aging_rows if row.get("quote_expiry_risk") == "expired"),
            "stale_warning_count": sum(len(row.get("stale_pricing_warnings", [])) for row in aging_rows),
            "advisory_only": True,
        },
        "pricing_confidence_summary": pricing_confidence_summary,
        "status": "healthy" if not summary_notes else "degraded",
    }


def build_supplier_comparison_summary(quotes: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    return assess_supplier_pricing_quality({"supplier_quotes": list(quotes)})
