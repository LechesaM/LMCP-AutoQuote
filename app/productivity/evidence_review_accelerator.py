from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_evidence_acceleration_summary(limit: int = 200) -> Dict[str, Any]:
    queue = build_review_queue_optimization_summary(limit=limit)
    items = list(queue.get("optimized_queue", []))
    missing_evidence: List[Dict[str, Any]] = []
    stale_evidence: List[Dict[str, Any]] = []
    pricing_mismatches: List[Dict[str, Any]] = []
    supplier_completeness: List[Dict[str, Any]] = []
    warning_groups: Counter[str] = Counter()

    for item in items:
        completeness = float(item.get("pricing_confidence") or 0.0)
        if completeness <= 35:
            missing_evidence.append(item)
            warning_groups["missing_evidence"] += 1
        if item.get("stale_evidence"):
            stale_evidence.append(item)
            warning_groups["stale_evidence"] += 1
        if completeness and completeness < 65:
            pricing_mismatches.append(item)
            warning_groups["pricing_mismatch"] += 1
        supplier_completeness.append(
            {
                "tender_id": item.get("tender_id"),
                "title": item.get("title"),
                "pricing_confidence": completeness,
                "queue_age_minutes": item.get("queue_age_minutes", 0.0),
            }
        )

    return {
        "status": "ok" if items else "degraded",
        "generated_at": _now_iso(),
        "data_source": "runtime" if items else "fallback",
        "missing_evidence": missing_evidence[:25],
        "stale_evidence": stale_evidence[:25],
        "supplier_quote_completeness": supplier_completeness[:50],
        "pricing_mismatch_summary": pricing_mismatches[:25],
        "grouped_warnings": dict(warning_groups),
        "summary": {
            "total": len(items),
            "missingEvidence": len(missing_evidence),
            "staleEvidence": len(stale_evidence),
            "pricingMismatches": len(pricing_mismatches),
        },
    }

