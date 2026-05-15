"""
Optional integration helper for existing opportunity endpoints.

Use this inside any route/service that currently returns raw opportunities:

    from app.services.backend_intelligence_integration import enrich_opportunity_response

    return enrich_opportunity_response(raw_result, limit=50)

It accepts:
- list of opportunities
- {"opportunities": [...]}
- {"items": [...]}
- {"records": [...]}
"""

from __future__ import annotations

from typing import Any, Dict

from app.services.backend_intelligence_layer import intelligent_filter_opportunities


def enrich_opportunity_response(raw_result: Any, *, limit: int = 50) -> Dict[str, Any]:
    if isinstance(raw_result, list):
        return intelligent_filter_opportunities(raw_result, limit=limit)

    if isinstance(raw_result, dict):
        records = (
            raw_result.get("opportunities")
            or raw_result.get("items")
            or raw_result.get("records")
            or raw_result.get("data")
            or []
        )

        enriched = intelligent_filter_opportunities(records, limit=limit)
        enriched["source_status"] = raw_result.get("status", "ok")
        enriched["source_message"] = raw_result.get("message")
        return enriched

    return intelligent_filter_opportunities([], limit=limit)
