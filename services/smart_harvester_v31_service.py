from __future__ import annotations

"""
LMCP V31 Smart Harvester Wrapper

Drop-in:
    app/services/smart_harvester_v31_service.py

Purpose:
    Wrap existing tender_harvester.run_national_tender_radar without breaking it.
    Applies V31 Smart RFQ Detection to harvested items and only auto-quotes accepted RFQs.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.services.smart_rfq_detection_service import filter_smart_rfqs

SERVICE_VERSION = "V31_SMART_HARVESTER_REAL_RFQ_DETECTION"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "smart_harvester_v31"
V31_DIR = RUNTIME_DIR / "v31_smart_harvester"
LOG_DIR = V31_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_log(name: str, payload: Dict[str, Any]) -> str:
    try:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = LOG_DIR / f"{name}_{stamp}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def run_smart_national_tender_radar(
    max_total: int = 10,
    max_per_source: int = 1,
    enable_auto_quote: bool = True,
    persist_to_live_store: bool = True,
) -> Dict[str, Any]:
    from app.services.tender_harvester import run_national_tender_radar

    # First harvest WITHOUT auto-quote. We classify first, then submit only clean accepted RFQs.
    raw_result = run_national_tender_radar(
        max_total=max_total,
        max_per_source=max_per_source,
        enable_auto_quote=False,
        persist_to_live_store=persist_to_live_store,
    )

    raw_items: List[Dict[str, Any]] = []
    if isinstance(raw_result, dict):
        if isinstance(raw_result.get("items"), list):
            raw_items = [x for x in raw_result.get("items", []) if isinstance(x, dict)]
        elif isinstance(raw_result.get("results"), list):
            raw_items = [x for x in raw_result.get("results", []) if isinstance(x, dict)]

    detection = filter_smart_rfqs(raw_items)
    accepted_items = detection.get("accepted_items", [])

    auto_quote_results: List[Dict[str, Any]] = []
    if enable_auto_quote and accepted_items:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_batch

            auto_quote_results = run_tender_pipeline_batch(
                accepted_items,
                source="v31-smart-harvester",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{
                "status": "error",
                "message": str(exc),
                "stage": "v31_auto_quote_batch",
            }]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "raw_harvester_status": raw_result.get("status") if isinstance(raw_result, dict) else "unknown",
        "source_count": raw_result.get("source_count") if isinstance(raw_result, dict) else None,
        "harvested_total": len(raw_items),
        "accepted_total": detection.get("accepted_total", 0),
        "review_total": detection.get("review_total", 0),
        "rejected_total": detection.get("rejected_total", 0),
        "smart_detection": detection,
        "items": detection.get("items", []),
        "accepted_items": accepted_items,
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "persist_to_live_store": persist_to_live_store,
        "raw_result_summary": {
            "status": raw_result.get("status") if isinstance(raw_result, dict) else "unknown",
            "harvested_total": raw_result.get("harvested_total") if isinstance(raw_result, dict) else None,
            "eligible_total": raw_result.get("eligible_total") if isinstance(raw_result, dict) else None,
            "quote_ready_total": raw_result.get("quote_ready_total") if isinstance(raw_result, dict) else None,
        },
    }

    result["log_path"] = _write_log("smart_radar", result)
    return result
