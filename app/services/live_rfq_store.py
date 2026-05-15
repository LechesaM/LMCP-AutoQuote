from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

LIVE_RFQ_STORE_PATH = RUNTIME_DIR / "live_rfqs.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _load_store() -> Dict[str, Any]:
    if not LIVE_RFQ_STORE_PATH.exists():
        return {"status": "ok", "updated_at": _now_iso(), "count": 0, "items": []}
    try:
        data = json.loads(LIVE_RFQ_STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"status": "ok", "updated_at": _now_iso(), "count": 0, "items": []}
        items = data.get("items")
        if not isinstance(items, list):
            data["items"] = []
        data["count"] = len(data.get("items", []))
        return data
    except Exception as exc:
        logger.warning("Failed to load live RFQ store: %s", exc)
        return {"status": "ok", "updated_at": _now_iso(), "count": 0, "items": []}


def _save_store(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {
        "status": "ok",
        "updated_at": _now_iso(),
        "count": len(items),
        "items": items,
    }
    LIVE_RFQ_STORE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _rfq_key(item: Dict[str, Any]) -> str:
    for key in (
        "buyer_rfq_number",
        "rfq_number",
        "reference_number",
        "document_number",
        "quote_number",
        "title",
    ):
        value = _clean(item.get(key))
        if value:
            return value.lower()
    return _clean(item.get("source_url")).lower() + "|" + _clean(item.get("title")).lower()


def _merge_rfq(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(old)
    merged.update({k: v for k, v in new.items() if v not in (None, "")})
    merged["updated_at"] = _now_iso()
    if "created_at" not in merged:
        merged["created_at"] = _now_iso()
    return merged


def get_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def read_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def list_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def save_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = _safe_list(items)
    for item in items:
        item.setdefault("created_at", _now_iso())
        item["updated_at"] = _now_iso()
    return _save_store(items)


def replace_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return save_live_rfqs(items)


def append_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def append_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return promote_live_rfqs(items)


def upsert_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    existing = _load_store()
    items = existing.get("items", [])
    item = dict(item or {})
    item.setdefault("created_at", _now_iso())
    item["updated_at"] = _now_iso()

    target_key = _rfq_key(item)
    replaced = False
    output: List[Dict[str, Any]] = []
    for current in items:
        if _rfq_key(current) == target_key:
            output.append(_merge_rfq(current, item))
            replaced = True
        else:
            output.append(current)

    if not replaced:
        output.append(item)

    saved = _save_store(output)
    saved["action"] = "updated" if replaced else "inserted"
    saved["rfq_key"] = target_key
    return saved


def upsert_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def save_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def persist_live_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def promote_rfq_to_live_store(item: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_live_rfq(item)


def promote_live_rfqs(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = _safe_list(items)
    existing = _load_store()
    current_items = existing.get("items", [])
    indexed = {_rfq_key(item): item for item in current_items}

    for item in items:
        row = dict(item)
        row.setdefault("created_at", _now_iso())
        row["updated_at"] = _now_iso()
        key = _rfq_key(row)
        if key in indexed:
            indexed[key] = _merge_rfq(indexed[key], row)
        else:
            indexed[key] = row

    saved = _save_store(list(indexed.values()))
    saved["action"] = "promoted"
    saved["promoted_count"] = len(items)
    return saved


def delete_live_rfq(rfq_key: str) -> Dict[str, Any]:
    existing = _load_store()
    items = existing.get("items", [])
    rfq_key = _clean(rfq_key).lower()
    kept = [item for item in items if _rfq_key(item) != rfq_key]
    saved = _save_store(kept)
    saved["action"] = "deleted"
    saved["rfq_key"] = rfq_key
    return saved


def clear_live_rfqs() -> Dict[str, Any]:
    return _save_store([])


# =============================================================================
# COMPATIBILITY SHIM FOR API IMPORTS
# =============================================================================

class LiveRFQStore:
    """
    Compatibility wrapper for older API code that imports LiveRFQStore as a class.
    Maps class-style calls to the function-based live RFQ store already in this file.
    """

    @staticmethod
    def _call_first(names, *args, **kwargs):
        for name in names:
            func = globals().get(name)
            if callable(func):
                return func(*args, **kwargs)
        return None

    @staticmethod
    def get_all() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "get_live_rfqs",
                "get_all_live_rfqs",
                "load_live_rfqs",
                "read_live_rfqs",
            ]
        )
        if isinstance(result, dict):
            return result
        if callable(globals().get("_load_store")):
            return _load_store()
        return {"updated_at": _now_iso(), "count": 0, "items": []}

    @staticmethod
    def get_filtered_from_store() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "get_filtered_live_rfqs",
                "get_filtered_rfqs",
                "filter_live_rfqs",
            ]
        )
        if isinstance(result, dict):
            return result

        data = LiveRFQStore.get_all()
        items = data.get("items", [])
        filtered_items = [
            item for item in items
            if not bool(item.get("blocked", False))
        ]

        return {
            "updated_at": data.get("updated_at", _now_iso()),
            "count": len(filtered_items),
            "items": filtered_items,
        }

    @staticmethod
    def get_scored_from_store() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "get_scored_live_rfqs",
                "score_live_rfqs_from_store",
                "get_recommended_live_rfqs",
            ]
        )
        if isinstance(result, dict):
            return result

        data = LiveRFQStore.get_filtered_from_store()
        items = data.get("items", [])

        scored_items = sorted(
            items,
            key=lambda item: float(item.get("score", 0) or 0),
            reverse=True,
        )

        recommended_items = [
            item for item in scored_items
            if bool(item.get("eligible", False)) or bool(item.get("quote_ready", False))
        ]

        return {
            "updated_at": data.get("updated_at", _now_iso()),
            "count": len(scored_items),
            "items": scored_items,
            "recommended_count": len(recommended_items),
            "recommended_items": recommended_items,
        }

    @staticmethod
    def upsert(item: Dict[str, Any]) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "upsert_live_rfq",
                "save_live_rfq",
                "save_live_rfq_item",
                "append_live_rfq",
            ],
            item,
        )
        if isinstance(result, dict):
            return result
        return {"status": "ok"}

    @staticmethod
    def promote(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(
            [
                "promote_live_rfqs",
                "promote_rfqs_to_live_store",
                "save_live_rfqs",
            ],
            items,
        )
        if isinstance(result, dict):
            return result
        return {"status": "ok", "promoted_count": len(items)}

    @staticmethod
    def delete(rfq_key: str) -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["delete_live_rfq"], rfq_key)
        if isinstance(result, dict):
            return result
        return {"status": "ok", "rfq_key": rfq_key}

    @staticmethod
    def clear() -> Dict[str, Any]:
        result = LiveRFQStore._call_first(["clear_live_rfqs"])
        if isinstance(result, dict):
            return result
        return {"status": "ok"}
