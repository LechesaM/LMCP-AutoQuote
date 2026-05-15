from typing import Any, Dict, List

from app.services.portal_crawl_priority import choose_portals_for_harvest


def get_priority_harvest_targets(limit: int = 50) -> List[Dict[str, Any]]:
    return choose_portals_for_harvest(limit=limit)


def print_priority_harvest_targets(limit: int = 20) -> None:
    targets = get_priority_harvest_targets(limit=limit)

    print("\n" + "=" * 100)
    print("LIVE PRIORITY HARVEST QUEUE")
    print("=" * 100)

    for item in targets:
        print(
            f"[{item.get('priority_band', '').upper():8}] "
            f"score={str(item.get('priority_score')).rjust(6)}  "
            f"every={str(item.get('recommended_crawl_every_minutes')).rjust(3)}m  "
            f"{item.get('name')} -> {item.get('url')}"
        )

    print("=" * 100 + "\n")
