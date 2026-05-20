from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_queue_heatmap_summary(limit: int = 200) -> Dict[str, Any]:
    queue = build_review_queue_optimization_summary(limit=limit)
    items = list(queue.get("optimized_queue", []))
    operator_distribution: Counter[str] = Counter()
    source_distribution: Counter[str] = Counter()
    escalation_density: Counter[str] = Counter()
    age_buckets: Dict[str, int] = {"0-60": 0, "60-240": 0, "240+": 0}
    province_density: Counter[str] = Counter()
    for item in items:
        operator_distribution[str(item.get("operator_id") or "unassigned")] += 1
        source_distribution[str(item.get("source_tier") or "Tier 4")] += 1
        escalation_density[str(item.get("priority_group") or "low")] += 1
        province_density[str(item.get("province") or "Unknown")] += 1
        age = float(item.get("queue_age_minutes") or 0.0)
        if age < 60:
            age_buckets["0-60"] += 1
        elif age < 240:
            age_buckets["60-240"] += 1
        else:
            age_buckets["240+"] += 1
    heatmap = [
        {"axis": "queue_age", "label": label, "value": value}
        for label, value in age_buckets.items()
    ] + [
        {"axis": "operator_distribution", "label": label, "value": value}
        for label, value in operator_distribution.most_common(10)
    ] + [
        {"axis": "source_concentration", "label": label, "value": value}
        for label, value in source_distribution.most_common(10)
    ]
    return {
        "status": "ok" if items else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if items else "fallback",
        "heatmap": heatmap,
        "operator_distribution": dict(operator_distribution),
        "source_distribution": dict(source_distribution),
        "escalation_density": dict(escalation_density),
        "province_density": dict(province_density),
    }

