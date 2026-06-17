from typing import Any, Dict, List, Optional

from app.services.procurement_heatmap import get_next_best_portals


def get_default_historical_stats() -> Dict[str, Dict[str, Any]]:
    return {
        "eTenders": {
            "success_rate": 0.95,
            "recent_opportunity_hits": 12,
            "last_crawled_at": None,
        },
        "Tender Bulletin": {
            "success_rate": 0.92,
            "recent_opportunity_hits": 9,
            "last_crawled_at": None,
        },
        "SANRAL": {
            "success_rate": 0.90,
            "recent_opportunity_hits": 6,
            "last_crawled_at": None,
        },
    }


def get_priority_portal_queue(limit: int = 20) -> List[Dict[str, Any]]:
    historical_stats = get_default_historical_stats()
    return get_next_best_portals(limit=limit, historical_stats=historical_stats)


def choose_portals_for_harvest(limit: int = 20) -> List[Dict[str, Any]]:
    ranked = get_priority_portal_queue(limit=limit)

    chosen: List[Dict[str, Any]] = []
    for portal in ranked:
        action = portal.get("recommended_action")
        category = portal.get("category")

        if action in {"crawl_now", "crawl_soon"} and category in {"healthy", "slow"}:
            chosen.append(portal)

    return chosen
