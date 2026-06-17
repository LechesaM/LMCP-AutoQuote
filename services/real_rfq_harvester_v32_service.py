from __future__ import annotations

"""
LMCP V32 Real RFQ Harvester Upgrade

Drop-in:
    app/services/real_rfq_harvester_v32_service.py

Purpose:
    Use the existing national harvester, but stop direct auto-quote from noisy source data.
    V32 harvests first, extracts real RFQs, then sends only accepted items to pipeline.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.services.real_rfq_extractor_v32_service import extract_real_rfqs
from app.services.smart_rfq_detection_service import filter_smart_rfqs

SERVICE_VERSION = "V32_REAL_RFQ_HARVESTER_UPGRADE"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOG_DIR = PROJECT_ROOT / "runtime" / "v32_real_rfq_harvester" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_log(prefix: str, payload: Dict[str, Any]) -> str:
    try:
        path = LOG_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _normalize_raw_items(raw_result: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_result, dict):
        return []
    for key in ["items", "results", "opportunities", "rfqs"]:
        value = raw_result.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def run_v32_real_rfq_harvest(
    max_total: int = 10,
    max_per_source: int = 1,
    enable_auto_quote: bool = True,
    persist_to_live_store: bool = True,
    include_review_in_pipeline: bool = False,
) -> Dict[str, Any]:
    from app.services.tender_harvester import run_national_tender_radar

    # Disable old auto-quote until V32 validates the candidates.
    raw_result = run_national_tender_radar(
        max_total=max_total,
        max_per_source=max_per_source,
        enable_auto_quote=False,
        persist_to_live_store=persist_to_live_store,
    )

    raw_items = _normalize_raw_items(raw_result)

    # Stage 1: real RFQ extraction.
    v32 = extract_real_rfqs(raw_items)

    # Stage 2: V31 smart detection as second opinion.
    v31 = filter_smart_rfqs(v32.get("accepted_items", []) + (v32.get("review_items", []) if include_review_in_pipeline else []))

    pipeline_items = v31.get("accepted_items", [])
    if include_review_in_pipeline:
        pipeline_items = pipeline_items + v31.get("review_items", [])

    auto_quote_results: List[Dict[str, Any]] = []
    if enable_auto_quote and pipeline_items:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_batch
            auto_quote_results = run_tender_pipeline_batch(
                pipeline_items,
                source="v32-real-rfq-harvester",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{
                "status": "error",
                "message": str(exc),
                "stage": "v32_pipeline_batch",
            }]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "raw_harvester_status": raw_result.get("status") if isinstance(raw_result, dict) else "unknown",
        "source_count": raw_result.get("source_count") if isinstance(raw_result, dict) else None,
        "harvested_total": len(raw_items),
        "v32_accepted_total": v32.get("accepted_total", 0),
        "v32_review_total": v32.get("review_total", 0),
        "v32_rejected_total": v32.get("rejected_total", 0),
        "v31_accepted_total": v31.get("accepted_total", 0),
        "v31_review_total": v31.get("review_total", 0),
        "v31_rejected_total": v31.get("rejected_total", 0),
        "pipeline_candidate_total": len(pipeline_items),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "persist_to_live_store": persist_to_live_store,
        "v32_real_rfq_extraction": v32,
        "v31_smart_detection": v31,
        "items": v32.get("items", []),
        "pipeline_items": pipeline_items,
    }
    result["log_path"] = _write_log("v32_real_rfq_harvest", result)
    return result
