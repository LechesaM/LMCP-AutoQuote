from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.analytics.source_reliability_analytics import build_source_reliability_analytics
from app.harvest.source_registry import load_source_registry
from ._shared import now_iso, safe_float, safe_int


def build_source_roi_analytics(limit: int = 100) -> Dict[str, Any]:
    source_reliability = build_source_reliability_analytics(limit=limit)
    registry = load_source_registry()
    sources = registry.list_sources()[: max(1, int(limit or 100))]
    reliability_rows = source_reliability.get("top_reliable_sources", [])
    failing_rows = source_reliability.get("top_failing_sources", [])
    top_value_sources: List[Dict[str, Any]] = []
    low_value_sources: List[Dict[str, Any]] = []
    noisy_sources: List[Dict[str, Any]] = []
    for source in sources:
        summary = source_reliability.get("source_health", {})
        score = safe_float(summary.get("harvest_success_rate", 0.0)) * 100.0 - safe_float(summary.get("parser_failure_rate", 0.0)) * 100.0
        row = {
            "source_id": source.id,
            "name": source.name,
            "tier": source.source_tier,
            "roi_score": round(score, 2),
            "quality_signal": safe_float(100.0 - summary.get("parser_failure_rate", 0.0) * 100.0),
            "reliability_signal": safe_float(summary.get("harvest_success_rate", 0.0) * 100.0),
        }
        if score >= 70:
            top_value_sources.append(row)
        elif score < 30:
            low_value_sources.append(row)
        if safe_float(summary.get("parser_failure_rate", 0.0)) >= 0.2:
            noisy_sources.append(row)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if sources else "fallback",
        "summary": {
            "rfqs_per_source": len(sources),
            "qualification_success_rate": safe_float(source_reliability.get("summary", {}).get("harvest_success_rate", 0.0)),
            "dead_source_cost": safe_int(source_reliability.get("source_health", {}).get("failing_sources", 0)),
            "parser_failure_impact": safe_float(source_reliability.get("source_health", {}).get("parser_failure_rate", 0.0)),
        },
        "top_value_sources": top_value_sources[:10],
        "low_value_sources": low_value_sources[:10],
        "noisy_sources": noisy_sources[:10],
        "reliability_rows": reliability_rows[:10],
        "failing_rows": failing_rows[:10],
    }

