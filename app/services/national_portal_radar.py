from datetime import datetime
from typing import Any, Dict, List

from app.services.portal_registry import get_active_portals
from app.services.adaptive_crawler import crawl_portal


def run_national_portal_radar() -> Dict[str, Any]:
    """
    Runs the central portal radar across all registered portals.
    This is the clean service entrypoint for future scheduler wiring.
    """
    portals = get_active_portals()
    portal_runs: List[Dict[str, Any]] = []

    for portal in portals:
        portal_result = crawl_portal(portal)
        portal_runs.append(portal_result)

    total_items = sum(run.get("total_items", 0) for run in portal_runs)
    total_portals = len(portal_runs)
    successful_portals = sum(
        1
        for run in portal_runs
        if run.get("successful_fetches", 0) > 0 or run.get("total_fetches", 0) == 0
    )

    return {
        "started_at": datetime.utcnow().isoformat(),
        "total_portals": total_portals,
        "successful_portals": successful_portals,
        "total_items_detected": total_items,
        "portal_runs": portal_runs,
    }
