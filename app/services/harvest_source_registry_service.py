from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.portal_registry import get_active_procurement_portals

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "app" / "data" / "harvest_sources.json"
CURATED_LIVE_SOURCE_FILE = "curated/live/default"
INVALID_SOURCE_URL_SNIPPETS = ("google.com/search", "www.google.com/search")

DEFAULT_CATEGORY_TYPE_MAP = {
    "aggregator": "tenders_api",
    "soe": "portal",
    "public_entity": "portal",
    "national_department": "portal",
    "provincial": "portal",
    "municipality": "portal",
}

DEFAULT_CATEGORY_PRIORITY_MAP = {
    "aggregator": 10,
    "soe": 20,
    "public_entity": 30,
    "national_department": 40,
    "provincial": 50,
    "municipality": 60,
}

DEFAULT_CATEGORY_INTELLIGENCE_MAP = {
    "aggregator": 95,
    "soe": 90,
    "public_entity": 84,
    "national_department": 82,
    "provincial": 80,
    "municipality": 78,
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value

    text = _clean(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _normalize_source(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(row, dict):
        return None

    name = _clean(row.get("name") or row.get("source_name"))
    if not name:
        return None

    url = _clean(row.get("url") or row.get("list_url"))
    list_url = _clean(row.get("list_url") or row.get("url"))
    if any(snippet in url.lower() or snippet in list_url.lower() for snippet in INVALID_SOURCE_URL_SNIPPETS):
        return None

    source_type = _clean(row.get("type") or row.get("source_type") or "generic_portal")
    source_group = _clean(row.get("source_group") or row.get("category_group") or source_type)
    source_name = _clean(row.get("source_name") or name)
    submission_method = _clean(row.get("submission_method") or "portal")
    intelligence_score = _safe_int(row.get("intelligence_score"), 70)
    enabled = _safe_bool(row.get("enabled"), True)
    verify_ssl = _safe_bool(row.get("verify_ssl"), True)

    normalized = {
        "name": name,
        "source_name": source_name,
        "url": url,
        "list_url": list_url,
        "type": source_type,
        "source_group": source_group,
        "category_group": _clean(row.get("category_group") or source_group),
        "submission_method": submission_method,
        "intelligence_score": intelligence_score,
        "enabled": enabled,
        "verify_ssl": verify_ssl,
    }

    # Keep any extra fields from the JSON registry
    for key, value in row.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def _dedupe_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()

    for source in sources:
        key = (
            _clean(source.get("name")).lower(),
            _clean(source.get("source_name")).lower(),
            _clean(source.get("url") or source.get("list_url")).lower(),
            _clean(source.get("type")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)

    return deduped


def _priority_sort_key(source: Dict[str, Any]) -> tuple[int, int, str]:
    return (
        _safe_int(source.get("priority"), 9999),
        -_safe_int(source.get("intelligence_score"), 0),
        _clean(source.get("name") or source.get("source_name")).lower(),
    )


def _portal_to_harvest_source(portal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(portal, dict):
        return None

    name = _clean(portal.get("name") or portal.get("portal_name"))
    url = _clean(portal.get("url") or portal.get("portal_url"))
    category = _clean(portal.get("category")).lower() or "portal"
    province = _clean(portal.get("province")) or "National"
    scope = _clean(portal.get("scope")) or "supply_delivery"

    if not name or not url:
        return None

    if any(snippet in url.lower() for snippet in INVALID_SOURCE_URL_SNIPPETS):
        return None

    source_type = DEFAULT_CATEGORY_TYPE_MAP.get(category, "portal")
    return {
        "name": name,
        "source_name": name,
        "url": url,
        "list_url": url,
        "type": source_type,
        "source_group": category,
        "category_group": category,
        "category": category,
        "province": province,
        "scope": scope,
        "submission_method": "portal",
        "enabled": True,
        "verify_ssl": True,
        "priority": DEFAULT_CATEGORY_PRIORITY_MAP.get(category, 9999),
        "intelligence_score": DEFAULT_CATEGORY_INTELLIGENCE_MAP.get(category, 70),
        "registry_source": "portal_registry",
    }


def build_default_harvest_sources() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for portal in get_active_procurement_portals():
        normalized = _portal_to_harvest_source(portal)
        if normalized:
            rows.append(normalized)
    rows = _dedupe_sources(rows)
    rows.sort(key=_priority_sort_key)
    return rows


def load_default_live_harvest_sources() -> List[Dict[str, Any]]:
    return build_default_harvest_sources()


def get_curated_live_source_file() -> str:
    return CURATED_LIVE_SOURCE_FILE


def build_default_harvest_sources_payload() -> Dict[str, Any]:
    sources = build_default_harvest_sources()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_source": "portal_registry",
        "source_count": len(sources),
        "sources": sources,
    }


def sync_default_registry_file(path: Optional[str | Path] = None) -> Dict[str, Any]:
    registry_path = Path(path) if path else get_registry_path()
    payload = build_default_harvest_sources_payload()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote curated harvest source registry with %s sources to %s", payload["source_count"], registry_path)
    return payload


def get_registry_path() -> Path:
    return DEFAULT_REGISTRY_PATH


def load_harvest_sources(registry_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    if registry_path is None or str(registry_path).strip() == CURATED_LIVE_SOURCE_FILE:
        sources = load_default_live_harvest_sources()
        if sources:
            logger.info("Loaded %s default live harvest sources", len(sources))
            return sources
    path = Path(registry_path) if registry_path else get_registry_path()

    if not path.exists():
        logger.warning("Harvest source registry file not found: %s", path)
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read harvest source registry %s: %s", path, exc)
        return []

    rows: List[Dict[str, Any]] = []

    if isinstance(raw, list):
        iterable = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("sources"), list):
            iterable = raw["sources"]
        else:
            iterable = []
            for value in raw.values():
                if isinstance(value, list):
                    iterable.extend(value)
    else:
        iterable = []

    for item in iterable:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_source(item)
        if normalized:
            rows.append(normalized)

    rows = _dedupe_sources(rows)
    rows.sort(key=_priority_sort_key)
    logger.info("Loaded %s harvest sources from %s", len(rows), path)
    return rows


def get_enabled_harvest_sources(registry_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    sources = load_harvest_sources(registry_path=registry_path)
    enabled = [source for source in sources if _safe_bool(source.get("enabled"), True)]
    logger.info("Enabled harvest sources: %s", len(enabled))
    return enabled


def get_disabled_harvest_sources(registry_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    sources = load_harvest_sources(registry_path=registry_path)
    disabled = [source for source in sources if not _safe_bool(source.get("enabled"), True)]
    logger.info("Disabled harvest sources: %s", len(disabled))
    return disabled


def count_harvest_sources(registry_path: Optional[str | Path] = None) -> Dict[str, int]:
    sources = load_harvest_sources(registry_path=registry_path)
    enabled = sum(1 for source in sources if _safe_bool(source.get("enabled"), True))
    disabled = len(sources) - enabled

    return {
        "total": len(sources),
        "enabled": enabled,
        "disabled": disabled,
    }


def find_harvest_source_by_name(
    name: str,
    registry_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    target = _clean(name).lower()
    if not target:
        return None

    for source in load_harvest_sources(registry_path=registry_path):
        candidates = {
            _clean(source.get("name")).lower(),
            _clean(source.get("source_name")).lower(),
        }
        if target in candidates:
            return source

    return None


def get_sources_by_type(
    source_type: str,
    registry_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    target = _clean(source_type).lower()
    if not target:
        return []

    return [
        source
        for source in load_harvest_sources(registry_path=registry_path)
        if _clean(source.get("type")).lower() == target
    ]


def get_sources_by_group(
    source_group: str,
    registry_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    target = _clean(source_group).lower()
    if not target:
        return []

    return [
        source
        for source in load_harvest_sources(registry_path=registry_path)
        if _clean(source.get("source_group") or source.get("category_group")).lower() == target
    ]


if __name__ == "__main__":
    print(json.dumps(sync_default_registry_file(), indent=2))
