from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Dict, List

from app.analytics.tender_success_analytics import get_tender_outcome_history
from app.quality.context import build_quality_context
from ._shared import now_iso, safe_float


def _extract_profit(record: Dict[str, Any]) -> float:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return safe_float(
        record.get("estimated_profit")
        or record.get("gross_profit")
        or payload.get("estimated_profit")
        or payload.get("gross_profit")
        or payload.get("profit")
    )


def _extract_margin(record: Dict[str, Any]) -> float:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return safe_float(record.get("margin") or payload.get("margin") or payload.get("gross_margin"))


def build_profitability_analytics(limit: int = 200) -> Dict[str, Any]:
    records = get_tender_outcome_history(limit=limit)
    quality_context = build_quality_context(limit=limit)
    profit_values = [_extract_profit(record) for record in records]
    margin_values = [_extract_margin(record) for record in records]
    by_source = defaultdict(list)
    by_province = defaultdict(list)
    high_value_rfqs: List[Dict[str, Any]] = []
    low_confidence: List[Dict[str, Any]] = []
    stale_pricing: List[Dict[str, Any]] = []
    supplier_evidence: List[Dict[str, Any]] = []
    for record in records:
        source = str(record.get("source_id") or record.get("source_name") or record.get("payload", {}).get("source") or "unknown")
        province = str(record.get("province") or record.get("payload", {}).get("province") or "unknown")
        by_source[source].append(_extract_profit(record))
        by_province[province].append(_extract_profit(record))
        if _extract_profit(record) >= 30000:
            high_value_rfqs.append(
                {
                    "tender_id": record.get("tender_id") or record.get("rfq_id") or "",
                    "title": record.get("title") or record.get("payload", {}).get("title") or "",
                    "province": province,
                    "estimated_profit": _extract_profit(record),
                    "estimated_margin": _extract_margin(record),
                }
            )
        if float(record.get("pricing_confidence", 0.0) or 0.0) < 0.6:
            low_confidence.append({"tender_id": record.get("tender_id") or "", "title": record.get("title") or "", "pricing_confidence": safe_float(record.get("pricing_confidence"))})
        if bool(record.get("stale_quote_warning")):
            stale_pricing.append({"tender_id": record.get("tender_id") or "", "title": record.get("title") or ""})
        supplier_evidence.append(
            {
                "tender_id": record.get("tender_id") or "",
                "supplier_evidence_score": safe_float(record.get("supplier_evidence_score") or quality_context.get("supplier_evidence_score", 0.0)),
            }
        )
    margin_distribution = {
        "below_25": sum(1 for margin in margin_values if margin < 25),
        "between_25_and_35": sum(1 for margin in margin_values if 25 <= margin < 35),
        "above_35": sum(1 for margin in margin_values if margin >= 35),
    }
    profitability_by_source = [
        {"source": source, "estimated_profit": round(mean(values), 2) if values else 0.0, "count": len(values)}
        for source, values in sorted(by_source.items(), key=lambda item: (sum(item[1]), len(item[1])), reverse=True)
    ]
    profitability_by_province = [
        {"province": province, "estimated_profit": round(mean(values), 2) if values else 0.0, "count": len(values)}
        for province, values in sorted(by_province.items(), key=lambda item: (sum(item[1]), len(item[1])), reverse=True)
    ]
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if records else "fallback",
        "summary": {
            "estimated_total_profit": round(sum(profit_values), 2),
            "average_estimated_profit": round(mean(profit_values), 2) if profit_values else 0.0,
            "average_margin": round(mean(margin_values), 2) if margin_values else 0.0,
            "high_value_rfq_count": len(high_value_rfqs),
            "low_confidence_profitability_count": len(low_confidence),
            "stale_pricing_impact_count": len(stale_pricing),
            "supplier_evidence_impact_average": round(mean([item["supplier_evidence_score"] for item in supplier_evidence]), 2) if supplier_evidence else 0.0,
        },
        "estimated_rfq_profitability": [
            {"tender_id": record.get("tender_id") or "", "title": record.get("title") or "", "estimated_profit": _extract_profit(record), "estimated_margin": _extract_margin(record)}
            for record in records
        ],
        "estimated_margin_distribution": margin_distribution,
        "high_value_rfqs": high_value_rfqs[:10],
        "low_confidence_profitability": low_confidence[:10],
        "stale_pricing_impact": stale_pricing[:10],
        "supplier_evidence_impact": supplier_evidence[:10],
        "profitability_by_source": profitability_by_source[:10],
        "profitability_by_province": profitability_by_province[:10],
    }

