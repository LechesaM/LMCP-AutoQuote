from __future__ import annotations

from statistics import median
from typing import Any, Dict, Iterable, List

from app.domain.supplier import SupplierQuote


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
        "quote_reference": quote.get("quote_reference", ""),
        "quote_valid_until": quote.get("quote_valid_until"),
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
    for quote in quotes:
        anomalies: List[str] = []
        total = _quote_total(quote)
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
                }
            )
        ).to_jsonable_dict()
        for quote, row in zip(quotes, comparison_rows)
    ]
    return {
        "supplier_quotes": quote_models,
        "comparison_rows": comparison_rows,
        "supplier_comparison_summary": {
            "quote_count": len(comparison_rows),
            "median_total": round(baseline, 2),
            "recommended_supplier": recommended,
            "notes": list(dict.fromkeys(summary_notes)),
        },
        "status": "healthy" if not summary_notes else "degraded",
    }


def build_supplier_comparison_summary(quotes: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    return assess_supplier_pricing_quality({"supplier_quotes": list(quotes)})
