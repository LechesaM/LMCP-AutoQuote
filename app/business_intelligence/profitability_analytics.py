from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ._shared import base_report, utc_now_iso


def _load_live_rfqs() -> List[Dict[str, Any]]:
    path = Path("runtime/live_rfqs.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = data.get("items") if isinstance(data, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _top_values(items: List[Dict[str, Any]], key: str, limit: int = 10) -> List[Dict[str, Any]]:
    ordered = sorted(items, key=lambda row: float(row.get(key, 0) or 0), reverse=True)
    return ordered[:limit]


def build_profitability_analytics(limit: int = 25) -> Dict[str, Any]:
    report = base_report(limit=limit)
    live = report["procurement_funnel"]
    top_rfqs = sorted(
        (
            {
                "rfq_id": item.get("rfq_id") or item.get("buyer_rfq_number") or item.get("quote_number") or "unknown",
                "title": item.get("title") or item.get("description") or "unknown",
                "estimated_profit": float(item.get("estimated_profit") or 0.0),
                "estimated_contract_value": float(item.get("estimated_contract_value") or 0.0),
            }
            for item in _load_live_rfqs()
        ),
        key=lambda row: float(row["estimated_profit"] or 0.0),
        reverse=True,
    )
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "summary": {
            "rfqs_harvested": live["rfqs_harvested"],
            "rfqs_quoted": live["rfqs_quoted"],
            "average_margin": live["average_margin"],
            "expected_gross_profit": live["expected_gross_profit"],
            "profit_per_rfq": report["financial_funnel"]["profit_per_rfq"],
        },
        "high_value_rfqs": top_rfqs[:limit] or _top_values(
            [
                {"rfq_id": "aggregated", "estimated_profit": live["expected_gross_profit"]},
                {"rfq_id": "awarded", "estimated_profit": report["financial_funnel"]["awarded_value"]},
                {"rfq_id": "submitted", "estimated_profit": report["financial_funnel"]["submitted_value"]},
            ],
            "estimated_profit",
            limit=limit,
        ),
        "data_source": report["data_source"],
    }
