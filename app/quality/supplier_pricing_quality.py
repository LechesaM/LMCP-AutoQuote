from __future__ import annotations

from typing import Any, Dict, List


def assess_supplier_pricing_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    quotes = payload.get("supplier_quotes") or []
    comparison_rows = []
    for quote in quotes:
        total = 0.0
        anomalies = []
        for line in quote.get("lines") or []:
            total += float(line.get("unit_price") or 0) * float(line.get("quantity") or 0) + float(line.get("delivery_cost") or 0) + float(line.get("vat_amount") or 0)
            if float(line.get("unit_price") or 0) <= 0:
                anomalies.append("non_positive_price")
        comparison_rows.append({"supplier_name": quote.get("supplier_name"), "quote_reference": quote.get("quote_reference"), "total": total, "anomalies": anomalies})
    recommended = min(comparison_rows, key=lambda row: row["total"]) if comparison_rows else {}
    return {
        "comparison_rows": comparison_rows,
        "supplier_comparison_summary": {"quote_count": len(comparison_rows), "recommended_supplier": recommended},
    }


def build_supplier_comparison_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"supplier_comparison_summary": {"quote_count": len(rows), "recommended_supplier": min(rows, key=lambda row: row.get("total", 0)) if rows else {}}}
