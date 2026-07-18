from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.rfq_archive_service import RfqArchiveService
from app.services.rfq_operational_classification_service import (
    RfqOperationalClassification,
    RfqOperationalClassificationService,
    canonical_rfq_id,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"

LIVE_RFQ_STORE_PATH = RUNTIME_DIR / "live_rfqs.json"
ARCHIVE_SERVICE_FACTORY = RfqArchiveService


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


def _active_filter(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    classifier = RfqOperationalClassificationService()
    active: List[Dict[str, Any]] = []
    historical: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []
    for item in items:
        result = classifier.classify(item)
        row = dict(item)
        row["operational_classification"] = result.classification.value
        row["operational_classification_reason"] = result.reason
        row["normalized_closing_at"] = result.normalized_closing_at.isoformat() if result.normalized_closing_at else None
        row["classification_confidence"] = result.confidence
        if result.classification == RfqOperationalClassification.ACTIVE:
            active.append(row)
        elif result.classification == RfqOperationalClassification.HISTORICAL:
            historical.append(row)
        else:
            review.append(row)
    return {"active": active, "historical": historical, "review": review}


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
    LIVE_RFQ_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
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
    data = _load_store()
    split = _active_filter(_safe_list(data.get("items", [])))
    return {
        **data,
        "count": len(split["active"]),
        "items": split["active"],
        "active_total": len(split["active"]),
        "archived_total": len(split["historical"]),
        "classification_review_required": len(split["review"]),
    }


def read_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def list_live_rfqs() -> Dict[str, Any]:
    return _load_store()


def list_active_rfqs() -> Dict[str, Any]:
    return get_live_rfqs()


def list_historical_rfqs() -> Dict[str, Any]:
    data = _load_store()
    split = _active_filter(_safe_list(data.get("items", [])))
    archived = ARCHIVE_SERVICE_FACTORY().list_archived_rfqs().get("items", [])
    indexed = {canonical_rfq_id(item): item for item in archived if isinstance(item, dict)}
    for item in split["historical"]:
        indexed[canonical_rfq_id(item)] = item
    items = list(indexed.values())
    return {"status": "ok", "count": len(items), "items": items}


def list_review_required_rfqs() -> Dict[str, Any]:
    data = _load_store()
    split = _active_filter(_safe_list(data.get("items", [])))
    review = ARCHIVE_SERVICE_FACTORY().list_review_required_rfqs().get("items", [])
    indexed = {canonical_rfq_id(item): item for item in review if isinstance(item, dict)}
    for item in split["review"]:
        indexed[canonical_rfq_id(item)] = item
    items = list(indexed.values())
    return {"status": "ok", "count": len(items), "items": items}


def _summary_counts(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    tomorrow = today.fromordinal(today.toordinal() + 1)
    quote_ready = 0
    submission_ready = 0
    closing_today = 0
    closing_tomorrow = 0
    pipeline_value = 0.0
    projected_profit = 0.0
    for item in items:
        if bool(item.get("quote_ready")) or str(item.get("quote_pack_status") or "").lower() in {"ready", "generated", "approved"}:
            quote_ready += 1
        if str(item.get("submission_status") or item.get("submission_pack_status") or "").lower() in {"ready", "submission_ready"}:
            submission_ready += 1
        closing = item.get("normalized_closing_at")
        try:
            closing_date = datetime.fromisoformat(str(closing).replace("Z", "+00:00")).astimezone(timezone.utc).date()
            if closing_date == today:
                closing_today += 1
            if closing_date == tomorrow:
                closing_tomorrow += 1
        except Exception:
            pass
        for key in ("estimated_value", "contract_value", "value", "total_excl_vat"):
            try:
                pipeline_value += float(item.get(key) or 0)
                break
            except Exception:
                continue
        for key in ("estimated_profit", "gross_profit", "projected_profit", "total_profit"):
            try:
                projected_profit += float(item.get(key) or 0)
                break
            except Exception:
                continue
    return {
        "quote_ready": quote_ready,
        "submission_ready": submission_ready,
        "closing_today": closing_today,
        "closing_tomorrow": closing_tomorrow,
        "active_pipeline_value": round(pipeline_value, 2),
        "projected_active_gross_profit": round(projected_profit, 2),
    }


def get_active_counts() -> Dict[str, Any]:
    active = list_active_rfqs().get("items", [])
    counts = _summary_counts(active)
    return {"status": "ok", "active_total": len(active), **counts}


def get_archive_counts() -> Dict[str, Any]:
    archived = list_historical_rfqs().get("items", [])
    reasons: Dict[str, int] = {}
    for item in archived:
        reason = str(item.get("operational_classification_reason") or (item.get("archive_metadata") or {}).get("archive_reason") or "UNKNOWN")
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "status": "ok",
        "archived_total": len(archived),
        "expired": reasons.get("EXPIRED", 0),
        "closed": reasons.get("CLOSED", 0),
        "awarded": reasons.get("AWARDED", 0),
        "cancelled": reasons.get("CANCELLED", 0),
        "withdrawn": reasons.get("WITHDRAWN", 0),
        "superseded": reasons.get("SUPERSEDED", 0),
        "historical_notices": reasons.get("HISTORICAL_NOTICE", 0),
        "test_rfqs": reasons.get("TEST_RFQ", 0),
        "reasons": reasons,
    }


def get_classification_review_counts() -> Dict[str, Any]:
    review = list_review_required_rfqs().get("items", [])
    reasons: Dict[str, int] = {}
    for item in review:
        reason = str(item.get("operational_classification_reason") or "UNKNOWN")
        reasons[reason] = reasons.get(reason, 0) + 1
    return {"status": "ok", "classification_review_required": len(review), "reasons": reasons}


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
    classification = RfqOperationalClassificationService().classify(item)
    if classification.classification == RfqOperationalClassification.HISTORICAL:
        return {
            **ARCHIVE_SERVICE_FACTORY().archive_rfq(item, classification.reason, {"original_store": str(LIVE_RFQ_STORE_PATH.relative_to(PROJECT_ROOT))}),
            "action": "archived",
            "operational_classification": classification.classification.value,
        }
    if classification.classification == RfqOperationalClassification.REVIEW_REQUIRED:
        return {
            **ARCHIVE_SERVICE_FACTORY().store_review_required([item], original_store=str(LIVE_RFQ_STORE_PATH.relative_to(PROJECT_ROOT))),
            "action": "classification_review",
            "operational_classification": classification.classification.value,
            "reason": classification.reason,
        }
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
    classifier = RfqOperationalClassificationService()
    active_items: List[Dict[str, Any]] = []
    historical_items: List[Dict[str, Any]] = []
    review_items: List[Dict[str, Any]] = []
    for item in items:
        result = classifier.classify(item)
        row = dict(item)
        row["operational_classification"] = result.classification.value
        row["operational_classification_reason"] = result.reason
        row["normalized_closing_at"] = result.normalized_closing_at.isoformat() if result.normalized_closing_at else None
        row["classification_confidence"] = result.confidence
        if result.classification == RfqOperationalClassification.ACTIVE:
            active_items.append(row)
        elif result.classification == RfqOperationalClassification.HISTORICAL:
            historical_items.append(row)
        else:
            review_items.append(row)

    archive_result = ARCHIVE_SERVICE_FACTORY().archive_many(historical_items, original_store=str(LIVE_RFQ_STORE_PATH.relative_to(PROJECT_ROOT))) if historical_items else {"count": 0, "added": 0}
    review_result = ARCHIVE_SERVICE_FACTORY().store_review_required(review_items, original_store=str(LIVE_RFQ_STORE_PATH.relative_to(PROJECT_ROOT))) if review_items else {"count": 0, "added": 0}
    existing = _load_store()
    current_items = existing.get("items", [])
    indexed = {_rfq_key(item): item for item in current_items}

    for item in active_items:
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
    saved["promoted_count"] = len(active_items)
    saved["archived_count"] = len(historical_items)
    saved["review_required_count"] = len(review_items)
    saved["archive_result"] = archive_result
    saved["review_result"] = review_result
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
    def upsert_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
        return LiveRFQStore.upsert(item)

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
