from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.core.runtime_paths import get_runtime_paths
from app.services.live_rfq_store import LiveRFQStore, save_live_rfqs, summarize_rfq_document_intelligence
from app.services.rfq_document_acquisition_engine import acquire_rfq_documents


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_PROMOTION_REPORT_NAME = "acquirable_live_rfq_promotion_report.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return _clean(value).lower() in {"1", "true", "yes", "y", "on", "ok", "completed", "complete", "downloaded", "verified"}


def _load_live_items(live_items: Optional[Sequence[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if live_items is not None:
        return [dict(item) for item in live_items if isinstance(item, dict)]
    data = LiveRFQStore.get_all()
    return [dict(item) for item in (data.get("items") or []) if isinstance(item, dict)]


def _is_acquirable(item: Dict[str, Any]) -> bool:
    summary = summarize_rfq_document_intelligence(item)
    if bool(summary.get("buyer_pack_downloaded")):
        return False
    return any(
        _clean(item.get(key))
        for key in (
            "buyer_pack_path",
            "live_buyer_pack_path",
            "buyer_pack_source",
            "document_url",
            "detail_url",
            "source_url",
            "document_acquisition_report_path",
        )
    ) or any(
        _clean((item.get("document_acquisition_result") or {}).get(key))
        for key in ("buyer_pack_path", "live_buyer_pack_path", "main_document_path", "document_acquisition_report_path")
        if isinstance(item.get("document_acquisition_result"), dict)
    )


def promote_acquirable_live_rfqs(
    *,
    limit: int = 10,
    live_items: Optional[Sequence[Dict[str, Any]]] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    items = _load_live_items(live_items)
    acquirable = [dict(item) for item in items if _is_acquirable(item)]
    acquirable.sort(key=lambda row: _clean(row.get("updated_at") or row.get("created_at")), reverse=True)
    selected = acquirable[: max(1, int(limit))]

    persisted_items: List[Dict[str, Any]] = []
    processed_items: List[Dict[str, Any]] = []
    success_count = 0
    failure_count = 0

    for item in selected:
        rfq_id = _clean(item.get("rfq_id") or item.get("buyer_rfq_number") or item.get("title"))
        acquisition = acquire_rfq_documents(item, timeout_seconds=timeout_seconds)
        enriched = dict(item)
        enriched["document_acquisition_result"] = acquisition
        enriched["document_acquisition_status"] = _clean(acquisition.get("status") or "failed")
        enriched["document_acquisition_timestamp"] = _clean(acquisition.get("acquired_at") or _now_iso())
        enriched["document_acquisition_report_path"] = _clean(acquisition.get("report_path"))
        downloaded_count = int(acquisition.get("downloaded_count") or 0)
        enriched["buyer_pack_downloaded"] = downloaded_count > 0 or _truthy(acquisition.get("live_buyer_pack_path"))
        enriched["buyer_pack_verified"] = enriched["buyer_pack_downloaded"]
        enriched["buyer_pack_path"] = _clean(acquisition.get("live_buyer_pack_path") or acquisition.get("buyer_pack_path"))
        enriched.update(summarize_rfq_document_intelligence(enriched))
        processed_items.append(
            {
                "rfq_id": rfq_id,
                "title": _clean(enriched.get("title")),
                "status": enriched["document_acquisition_status"],
                "downloaded_count": downloaded_count,
                "buyer_pack_downloaded": bool(enriched.get("buyer_pack_downloaded")),
                "document_intelligence_pass": bool(enriched.get("boq_detected") and enriched.get("pricing_schedule_detected") and enriched.get("returnables_detected")),
                "quote_pack_readiness_score": int(enriched.get("quote_pack_readiness_score") or 0),
                "report_path": enriched["document_acquisition_report_path"],
            }
        )
        if enriched["document_acquisition_status"] == "ok":
            success_count += 1
        else:
            failure_count += 1
        persisted_items.append(enriched)

    if persisted_items:
        selected_ids = {_clean(item.get("rfq_id") or item.get("buyer_rfq_number") or item.get("title")) for item in selected}
        remaining = [item for item in items if _clean(item.get("rfq_id") or item.get("buyer_rfq_number") or item.get("title")) not in selected_ids]
        save_live_rfqs(remaining + persisted_items)

    report = {
        "status": "ok" if success_count > 0 else "failed",
        "selected_count": len(selected),
        "success_count": success_count,
        "failure_count": failure_count,
        "processed_items": processed_items,
        "generated_at": _now_iso(),
    }
    destination = Path(output_path).expanduser().resolve() if output_path else get_runtime_paths().manual_production_dir / DEFAULT_PROMOTION_REPORT_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    report["output_path"] = str(destination)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report
