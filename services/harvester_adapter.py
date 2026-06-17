from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple


def _pick_first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        if isinstance(value, dict) and len(value) == 0:
            continue
        return value
    return None


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return deepcopy(value)

    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="python")
            if isinstance(dumped, dict):
                return deepcopy(dumped)
        except Exception:
            pass

    if hasattr(value, "dict"):
        try:
            dumped = value.dict()
            if isinstance(dumped, dict):
                return deepcopy(dumped)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return deepcopy(
                {k: v for k, v in vars(value).items() if not k.startswith("_")}
            )
        except Exception:
            pass

    return {}


def _looks_like_payload(data: Dict[str, Any]) -> bool:
    if not data:
        return False

    signal_keys = {
        "title",
        "tender_title",
        "issuing_entity",
        "buyer_name",
        "reference_number",
        "description",
        "scope_summary",
        "category",
        "province",
        "municipality",
        "closing_at",
        "closing_date",
        "deadline",
        "submission_method",
        "documents",
        "contacts",
        "raw_text",
        "raw_data",
    }
    return any(key in data for key in signal_keys)


def _extract_payload_and_meta(
    item: Any,
    inherited_source: Optional[str] = None,
    inherited_source_type: Optional[str] = None,
    inherited_source_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    obj = _as_dict(item)
    if not obj:
        return []

    source = _pick_first_non_empty(
        obj.get("source"),
        obj.get("source_name"),
        obj.get("portal_slug"),
        inherited_source,
    )
    source_type = _pick_first_non_empty(
        obj.get("source_type"),
        obj.get("portal_type"),
        inherited_source_type,
    )
    source_url = _pick_first_non_empty(
        obj.get("source_url"),
        obj.get("portal_url"),
        obj.get("notice_url"),
        obj.get("url"),
        inherited_source_url,
    )

    nested_candidates = [
        obj.get("payload"),
        obj.get("rfq"),
        obj.get("tender"),
        obj.get("item"),
        obj.get("raw"),
        obj.get("raw_data"),
    ]

    extracted: List[Dict[str, Any]] = []

    for candidate in nested_candidates:
        candidate_dict = _as_dict(candidate)
        if _looks_like_payload(candidate_dict):
            extracted.append(
                {
                    "source": source,
                    "source_type": source_type,
                    "source_url": source_url,
                    "payload": candidate_dict,
                }
            )

    if extracted:
        return extracted

    if _looks_like_payload(obj):
        return [
            {
                "source": source,
                "source_type": source_type,
                "source_url": source_url,
                "payload": obj,
            }
        ]

    return []


def _collect_from_container(
    container: Any,
    inherited_source: Optional[str] = None,
    inherited_source_type: Optional[str] = None,
    inherited_source_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    obj = _as_dict(container)
    if not obj:
        return []

    source = _pick_first_non_empty(
        obj.get("source"),
        obj.get("source_name"),
        obj.get("portal_slug"),
        inherited_source,
    )
    source_type = _pick_first_non_empty(
        obj.get("source_type"),
        obj.get("portal_type"),
        inherited_source_type,
    )
    source_url = _pick_first_non_empty(
        obj.get("source_url"),
        obj.get("portal_url"),
        obj.get("notice_url"),
        obj.get("url"),
        inherited_source_url,
    )

    harvested: List[Dict[str, Any]] = []

    direct_keys = [
        "items",
        "rfqs",
        "tenders",
        "opportunities",
        "accepted_items",
    ]

    for key in direct_keys:
        values = obj.get(key)
        if isinstance(values, list):
            for value in values:
                harvested.extend(
                    _extract_payload_and_meta(
                        value,
                        inherited_source=source,
                        inherited_source_type=source_type,
                        inherited_source_url=source_url,
                    )
                )

    results = obj.get("results")
    if isinstance(results, list):
        for result in results:
            harvested.extend(
                _collect_from_container(
                    result,
                    inherited_source=source,
                    inherited_source_type=source_type,
                    inherited_source_url=source_url,
                )
            )

    if not harvested:
        harvested.extend(
            _extract_payload_and_meta(
                obj,
                inherited_source=source,
                inherited_source_type=source_type,
                inherited_source_url=source_url,
            )
        )

    unique: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for row in harvested:
        payload = row.get("payload") or {}
        dedupe_key = str(
            (
                row.get("source"),
                payload.get("reference_number"),
                payload.get("title"),
                payload.get("issuing_entity"),
                payload.get("notice_url") or payload.get("url"),
            )
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique.append(row)

    return unique


def run_live_harvest(source: str = "all", limit: int = 50) -> Dict[str, Any]:
    """
    Robust adapter around the current harvester stack.

    Tries the canonical harvest entrypoint first.
    Falls back to self-healing harvester.
    Falls back to tender_harvester directly.

    Returns:
    {
        "ok": bool,
        "source": str,
        "raw_result": dict,
        "items": [
            {
                "source": "...",
                "source_type": "...",
                "source_url": "...",
                "payload": {...}
            }
        ]
    }
    """
    raw_result: Dict[str, Any] = {}
    last_error: Optional[str] = None

    try:
        from app.services.harvest_entrypoint import canonical_harvest  # type: ignore

        raw_result = _as_dict(canonical_harvest())
    except Exception as exc_1:
        last_error = f"canonical_harvest failed: {exc_1}"

        try:
            from app.services.self_healing_harvester import run_harvester  # type: ignore

            if source == "all":
                raw_result = _as_dict(run_harvester())
            else:
                raw_result = _as_dict(
                    run_harvester(
                        portals=[
                            {
                                "portal_slug": source,
                                "portal_name": source,
                            }
                        ]
                    )
                )
        except Exception as exc_2:
            last_error = f"{last_error} | run_harvester failed: {exc_2}"

            try:
                from app.services.tender_harvester import harvest_tenders  # type: ignore

                raw_result = _as_dict(harvest_tenders())
            except Exception as exc_3:
                last_error = f"{last_error} | harvest_tenders failed: {exc_3}"
                return {
                    "ok": False,
                    "source": source,
                    "raw_result": {},
                    "items": [],
                    "error": last_error,
                }

    items = _collect_from_container(raw_result)
    if limit and limit > 0:
        items = items[:limit]

    return {
        "ok": True,
        "source": source,
        "raw_result": raw_result,
        "items": items,
        "error": last_error,
    }
