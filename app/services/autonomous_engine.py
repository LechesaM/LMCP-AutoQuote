from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.tender_harvester import run_national_tender_radar
from app.services.tender_pipeline import run_tender_pipeline_batch_from_harvest

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        cleaned = str(value).replace(",", "").replace("R", "").strip()
        return float(cleaned)
    except Exception:
        return default


def _extract_radar_results(radar_output: Any) -> List[Dict[str, Any]]:
    if not isinstance(radar_output, dict):
        return []

    candidates = [
        radar_output.get("results"),
        radar_output.get("items"),
        radar_output.get("opportunities"),
        radar_output.get("rfqs"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]

    return []


def _is_item_quote_ready(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False

    if _safe_bool(item.get("eligible_for_autonomous"), False):
        return True

    if _safe_bool(item.get("quote_ready"), False):
        return True

    if _safe_bool(item.get("eligible"), False) and _safe_bool(item.get("is_supply"), False):
        return True

    return False


def _is_item_supply(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False

    if _safe_bool(item.get("is_supply"), False):
        return True

    category = _safe_str(item.get("category")).lower()
    title = _safe_str(item.get("title")).lower()
    description = _safe_str(item.get("description")).lower()
    combined = " | ".join([category, title, description])

    supply_markers = [
        "supply",
        "delivery",
        "goods",
        "procurement",
        "materials",
        "consumables",
        "equipment",
    ]
    works_markers = [
        "construction",
        "civil works",
        "maintenance",
        "repair",
        "installation",
        "refurbishment",
        "renovation",
        "building",
    ]

    has_supply = any(marker in combined for marker in supply_markers)
    has_works = any(marker in combined for marker in works_markers)

    if has_works and not has_supply:
        return False

    return has_supply


def _estimated_profit(item: Dict[str, Any]) -> float:
    if not isinstance(item, dict):
        return 0.0

    explicit_profit = _safe_float(item.get("estimated_profit"), 0.0)
    if explicit_profit > 0:
        return explicit_profit

    revenue = _safe_float(
        item.get("estimated_revenue")
        or item.get("quote_total")
        or item.get("total_quote_amount")
        or item.get("estimated_value"),
        0.0,
    )
    cost = _safe_float(
        item.get("estimated_cost")
        or item.get("cost_estimate")
        or item.get("supplier_cost_total")
        or item.get("selected_quote_total"),
        0.0,
    )

    if revenue > 0 and cost > 0:
        return max(0.0, revenue - cost)

    return 0.0


def _sort_items_for_priority(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(item: Dict[str, Any]) -> Any:
        return (
            _estimated_profit(item),
            _safe_float(item.get("intelligence_score"), 0.0),
            _safe_str(item.get("closing_date")),
        )

    return sorted(items, key=sort_key, reverse=True)


def _prepare_items_for_pipeline(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        row = dict(item)

        # Preserve explicit flags from upstream.
        row["pipeline_test_mode"] = _safe_bool(
            row.get("pipeline_test_mode"),
            default=False,
        )
        row["force_quote_ready"] = _safe_bool(
            row.get("force_quote_ready"),
            default=False,
        )

        # Ensure source snapshot exists for traceability.
        if not isinstance(row.get("source_rfq"), dict):
            row["source_rfq"] = dict(item)

        prepared.append(row)

    return prepared


def _summarize_pipeline_results(pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
    results = pipeline_result.get("results", []) if isinstance(pipeline_result, dict) else []
    if not isinstance(results, list):
        results = []

    submitted_count = 0
    quote_generated_count = 0
    pdf_generated_count = 0
    quote_built_count = 0
    failed_count = 0
    flagged_count = 0
    not_quote_ready_count = 0

    for row in results:
        if not isinstance(row, dict):
            continue

        if row.get("submission_status") == "submitted":
            submitted_count += 1
        if row.get("quote_generated") is True:
            quote_generated_count += 1
        if row.get("pdf_generated") is True:
            pdf_generated_count += 1
        if row.get("pipeline_status") in {"quote_built", "quote_generation_complete", "submitted"}:
            quote_built_count += 1
        if row.get("pipeline_status") in {"failed", "quote_build_failed"}:
            failed_count += 1
        if row.get("submission_status") == "flagged":
            flagged_count += 1
        if row.get("pipeline_status") == "not_quote_ready":
            not_quote_ready_count += 1

    return {
        "processed_items": len(results),
        "submitted_count": submitted_count,
        "quote_generated_count": quote_generated_count,
        "pdf_generated_count": pdf_generated_count,
        "quote_built_count": quote_built_count,
        "failed_count": failed_count,
        "flagged_count": flagged_count,
        "not_quote_ready_count": not_quote_ready_count,
    }


def run_autonomous_cycle(
    db: Any = None,
    *,
    include_non_quote_ready: bool = False,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    LMCP autonomous cycle

    Flow:
    1. Harvest RFQs
    2. Extract harvested items
    3. Keep supply-only opportunities
    4. Prefer quote-ready / eligible-for-autonomous opportunities
    5. Prioritize stronger opportunities
    6. Run full tender pipeline batch
    """

    started_at = _now_iso()

    try:
        logger.info("Starting LMCP autonomous cycle.")
        radar_output = run_national_tender_radar(db=db)
        harvested_results = _extract_radar_results(radar_output)

        harvested_count = _safe_len(harvested_results)

        supply_items = [item for item in harvested_results if _is_item_supply(item)]
        supply_count = _safe_len(supply_items)

        if include_non_quote_ready:
            eligible_items = supply_items
        else:
            eligible_items = [item for item in supply_items if _is_item_quote_ready(item)]

        eligible_count = _safe_len(eligible_items)

        prioritized_items = _sort_items_for_priority(eligible_items)

        if isinstance(max_items, int) and max_items > 0:
            prioritized_items = prioritized_items[:max_items]

        prepared_items = _prepare_items_for_pipeline(prioritized_items)
        pipeline_input_count = _safe_len(prepared_items)

        if not prepared_items:
            logger.info(
                "Autonomous cycle completed with no eligible items. harvested=%s supply=%s eligible=%s",
                harvested_count,
                supply_count,
                eligible_count,
            )
            return {
                "status": "ok",
                "message": "Harvest completed but no eligible quote-ready RFQs were found",
                "started_at": started_at,
                "updated_at": _now_iso(),
                "harvest_count": harvested_count,
                "supply_count": supply_count,
                "eligible_count": eligible_count,
                "pipeline_input_count": 0,
                "pipeline_result": {
                    "status": "skipped",
                    "reason": "no_eligible_items",
                    "results": [],
                },
                "radar_output": radar_output,
            }

        pipeline_result = run_tender_pipeline_batch_from_harvest(prepared_items)
        pipeline_summary = _summarize_pipeline_results(
            pipeline_result if isinstance(pipeline_result, dict) else {}
        )

        logger.info(
            "Autonomous cycle completed. harvested=%s supply=%s eligible=%s pipeline_input=%s submitted=%s",
            harvested_count,
            supply_count,
            eligible_count,
            pipeline_input_count,
            pipeline_summary.get("submitted_count", 0),
        )

        return {
            "status": "ok",
            "message": "Harvest + pipeline completed",
            "started_at": started_at,
            "updated_at": _now_iso(),
            "harvest_count": harvested_count,
            "supply_count": supply_count,
            "eligible_count": eligible_count,
            "pipeline_input_count": pipeline_input_count,
            "submitted_count": pipeline_summary.get("submitted_count", 0),
            "quote_generated_count": pipeline_summary.get("quote_generated_count", 0),
            "pdf_generated_count": pipeline_summary.get("pdf_generated_count", 0),
            "quote_built_count": pipeline_summary.get("quote_built_count", 0),
            "flagged_count": pipeline_summary.get("flagged_count", 0),
            "failed_count": pipeline_summary.get("failed_count", 0),
            "not_quote_ready_count": pipeline_summary.get("not_quote_ready_count", 0),
            "pipeline_result": pipeline_result,
            "radar_output": radar_output,
        }

    except Exception as exc:
        logger.exception("Autonomous cycle failed.")
        return {
            "status": "failed",
            "message": f"Autonomous cycle failed: {exc}",
            "started_at": started_at,
            "updated_at": _now_iso(),
            "harvest_count": 0,
            "supply_count": 0,
            "eligible_count": 0,
            "pipeline_input_count": 0,
            "pipeline_result": {
                "status": "failed",
                "error": str(exc),
                "results": [],
            },
            "radar_output": {},
        }


def get_autonomous_status() -> Dict[str, Any]:
    return {
        "status": "ready",
        "engine": "lmcp_autonomous_engine",
        "mode": "supply-and-delivery-only",
        "autonomous_cycle_available": True,
        "pipeline_batch_available": True,
        "filters": {
            "supply_only": True,
            "exclude_non_supply": True,
            "prefer_quote_ready": True,
        },
        "updated_at": _now_iso(),
    }
