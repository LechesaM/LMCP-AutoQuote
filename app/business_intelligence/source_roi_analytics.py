from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from ._shared import base_report, utc_now_iso


def _load_live_rfqs() -> List[Dict[str, Any]]:
    path = Path("runtime/live_rfqs.json")
    if not path.exists():
        return []
    try:
        data = __import__("json").loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = data.get("items") if isinstance(data, dict) else []
    return [item for item in items if isinstance(item, dict)]


def build_source_roi_analytics(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    source_totals: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"source": "", "total_profit": 0.0, "count": 0})
    for item in _load_live_rfqs():
        source = str(item.get("source_name") or item.get("source_url") or item.get("portal_slug") or "unknown").strip() or "unknown"
        bucket = source_totals[source]
        bucket["source"] = source
        bucket["total_profit"] += float(item.get("estimated_profit") or 0.0)
        bucket["count"] += 1
    ordered = sorted(source_totals.values(), key=lambda item: (-float(item["total_profit"] or 0), item["source"]))
    top_value_sources = ordered[:limit]
    low_value_sources = list(reversed(ordered[-limit:])) if ordered else []

    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "summary": {
            "awardees_count": report["award_intelligence"]["unique_awardees"],
            "province_count": len(report["award_intelligence"]["awardees_by_province"]),
            "supplier_response_rate": report["supplier_funnel"]["supplier_response_rate"],
        },
        "top_value_sources": top_value_sources,
        "low_value_sources": low_value_sources,
        "data_source": report["data_source"],
    }
