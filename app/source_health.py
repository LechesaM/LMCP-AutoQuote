from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_STATUS_PATH = Path("app/entity_source_status.json")


def _load_status_file(status_path: Path = DEFAULT_STATUS_PATH) -> Dict[str, Any]:
    if not status_path.exists():
        return {"summary": {}, "items": []}

    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return {"summary": {}, "items": []}


def _normalize_status(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def load_all_source_statuses(status_path: Path = DEFAULT_STATUS_PATH) -> List[Dict[str, Any]]:
    payload = _load_status_file(status_path)
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    return items


def get_sources_by_status(
    allowed_statuses: List[str],
    status_path: Path = DEFAULT_STATUS_PATH,
) -> List[Dict[str, Any]]:
    allowed = {_normalize_status(x) for x in allowed_statuses if x}
    items = load_all_source_statuses(status_path)

    return [
        item for item in items
        if _normalize_status(item.get("status")) in allowed
    ]


def get_working_sources(status_path: Path = DEFAULT_STATUS_PATH) -> List[Dict[str, Any]]:
    return get_sources_by_status(["working"], status_path=status_path)


def get_harvestable_sources(
    status_path: Path = DEFAULT_STATUS_PATH,
    include_homepage_only: bool = True,
    include_needs_custom_parser: bool = False,
    min_confidence: int = 0,
) -> List[Dict[str, Any]]:
    allowed = ["working"]
    if include_homepage_only:
        allowed.append("homepage_only")
    if include_needs_custom_parser:
        allowed.append("needs_custom_parser")

    items = get_sources_by_status(allowed, status_path=status_path)

    filtered: List[Dict[str, Any]] = []
    seen = set()

    for item in items:
        confidence = int(item.get("procurement_confidence") or 0)
        if confidence < min_confidence:
            continue

        url = (item.get("final_url") or item.get("tested_url") or "").strip()
        entity_name = (item.get("entity_name") or "").strip()
        entity_type = (item.get("entity_type") or "").strip()

        if not url:
            continue

        key = (entity_name.lower(), url.rstrip("/").lower())
        if key in seen:
            continue
        seen.add(key)

        filtered.append(
            {
                "name": entity_name,
                "entity_type": entity_type,
                "url": url,
                "base_url": (item.get("base_url") or "").strip(),
                "status": (item.get("status") or "").strip(),
                "procurement_confidence": confidence,
                "keywords": item.get("procurement_keywords_found") or [],
                "page_title": (item.get("page_title") or "").strip(),
                "source_registry": (item.get("source_registry") or "").strip(),
                "notes": (item.get("notes") or "").strip(),
            }
        )

    filtered.sort(
        key=lambda x: (
            -int(x.get("procurement_confidence") or 0),
            x.get("entity_type", ""),
            x.get("name", ""),
        )
    )
    return filtered


def summarize_source_health(status_path: Path = DEFAULT_STATUS_PATH) -> Dict[str, Any]:
    payload = _load_status_file(status_path)
    items = payload.get("items", [])
    summary = payload.get("summary", {})

    by_status: Dict[str, int] = {}
    by_type: Dict[str, int] = {}

    for item in items if isinstance(items, list) else []:
        status = _normalize_status(item.get("status")) or "unknown"
        entity_type = (item.get("entity_type") or "unknown").strip()

        by_status[status] = by_status.get(status, 0) + 1
        by_type[entity_type] = by_type.get(entity_type, 0) + 1

    return {
        "total_items": len(items) if isinstance(items, list) else 0,
        "summary": summary,
        "by_status": by_status,
        "by_entity_type": by_type,
        "working_sources": len(get_working_sources(status_path=status_path)),
        "harvestable_sources_default": len(
            get_harvestable_sources(
                status_path=status_path,
                include_homepage_only=True,
                include_needs_custom_parser=False,
                min_confidence=0,
            )
        ),
    }


if __name__ == "__main__":
    result = summarize_source_health()
    print(json.dumps(result, indent=2))
