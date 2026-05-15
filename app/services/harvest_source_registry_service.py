from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "app" / "data" / "harvest_sources.json"


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


def get_registry_path() -> Path:
    return DEFAULT_REGISTRY_PATH


def load_harvest_sources(registry_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
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
    print(count_harvest_sources())
