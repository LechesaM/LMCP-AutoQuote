from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.harvest.source_health import get_source_health, get_source_health_summary
from app.harvest.source_registry import load_source_registry


def build_source_reliability_analytics(limit: int = 100) -> Dict[str, Any]:
    registry = load_source_registry()
    sources = registry.list_sources()
    health = get_source_health_summary(limit=limit)
    detailed = []
    for source in sources[: max(1, int(limit or 100))]:
        source_health = get_source_health(source.id).to_jsonable_dict()
        detailed.append(
            {
                "id": source.id,
                "name": source.name,
                "tier": source.source_tier,
                "status": source_health.get("status", "healthy"),
                "failure_count": source_health.get("failure_count", 0),
                "parser_failure_rate": source_health.get("parser_failure_rate", 0.0),
                "average_response_time_ms": source_health.get("average_response_time_ms", 0),
                "last_success_at": source_health.get("last_success_at", ""),
                "last_failure_at": source_health.get("last_failure_at", ""),
            }
        )
    top_failing = [item for item in detailed if item["failure_count"] > 0][:10]
    top_reliable = sorted(detailed, key=lambda item: (item["failure_count"], item["parser_failure_rate"], -item["average_response_time_ms"]))[:10]
    return {
        "status": "ok",
        "generated_at": health.get("generated_at"),
        "data_source": "runtime" if sources else "fallback",
        "summary": {
            "harvest_success_rate": health.get("healthy_sources", 0) / max(1, health.get("total_sources", 1)),
            "parser_failure_rate": health.get("parser_failure_rate", 0.0),
            "source_response_latency_ms": health.get("average_response_time_ms", 0),
            "dead_source_frequency": health.get("failing_sources", 0),
            "stale_source_frequency": health.get("degraded_sources", 0),
            "source_disablement_frequency": health.get("disabled_sources", 0),
        },
        "top_failing_sources": top_failing,
        "top_reliable_sources": top_reliable,
        "source_status_counts": dict(Counter(item["status"] for item in detailed)),
        "source_health": health,
    }

