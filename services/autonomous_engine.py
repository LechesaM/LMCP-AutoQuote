from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.system_state_service import (
    get_block_reason,
    get_system_state,
)
from app.services.tender_harvester import run_national_tender_radar
from app.services.tender_pipeline import run_tender_pipeline_batch_from_harvest

logger = logging.getLogger(__name__)


RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
LOW_DISK_PAUSE_FILE = RUNTIME_DIR / "harvester.paused"
MIN_FREE_DISK_GB = float(str(os.getenv("MIN_FREE_DISK_GB", "10")).strip() or "10")

# --- Channel 3 Portal/Source Isolation ---
ISOLATED_SOURCES: Dict[str, Dict[str, Any]] = {}
ISOLATION_FAILURE_THRESHOLD = 3

# --- Channel 3 Auto-Recovery / Isolation Release ---
ISOLATION_COOLDOWN_SECONDS = 900

# --- Channel 3 Persistent Isolation Memory ---
ISOLATION_DIR = RUNTIME_DIR / "source_isolation"
ISOLATION_FILE = ISOLATION_DIR / "source_isolation.json"


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


def _disk_free_gb(path: str = ".") -> float:
    usage = shutil.disk_usage(path)
    return round(usage.free / (1024 ** 3), 2)


def _set_low_disk_pause_marker() -> str:
    LOW_DISK_PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOW_DISK_PAUSE_FILE.exists():
        LOW_DISK_PAUSE_FILE.write_text(
            f"paused_at={_now_iso()}\nreason=low_disk_space\n",
            encoding="utf-8",
        )
    return str(LOW_DISK_PAUSE_FILE)


def _clear_low_disk_pause_marker() -> None:
    try:
        if LOW_DISK_PAUSE_FILE.exists():
            LOW_DISK_PAUSE_FILE.unlink()
    except Exception:
        logger.warning("Failed clearing low disk pause marker: %s", LOW_DISK_PAUSE_FILE)


def _check_disk_guard() -> Optional[Dict[str, Any]]:
    free_gb = _disk_free_gb(".")
    if free_gb < MIN_FREE_DISK_GB:
        pause_file = _set_low_disk_pause_marker()
        logger.warning(
            "Autonomous cycle skipped due to low disk space. free_gb=%s threshold_gb=%s",
            free_gb,
            MIN_FREE_DISK_GB,
        )
        return {
            "status": "skipped",
            "reason": "low_disk_space",
            "message": "Autonomous cycle skipped due to low disk space.",
            "free_disk_gb": free_gb,
            "min_free_disk_gb": MIN_FREE_DISK_GB,
            "pause_file": pause_file,
        }

    _clear_low_disk_pause_marker()
    return None


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

        row["pipeline_test_mode"] = _safe_bool(
            row.get("pipeline_test_mode"),
            default=False,
        )
        row["force_quote_ready"] = _safe_bool(
            row.get("force_quote_ready"),
            default=False,
        )

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


def _source_key(item: Dict[str, Any]) -> str:
    return _safe_str(
        item.get("source")
        or item.get("source_name")
        or item.get("portal_name")
        or "unknown_source"
    )


def _save_isolation_state() -> None:
    try:
        ISOLATION_DIR.mkdir(parents=True, exist_ok=True)
        ISOLATION_FILE.write_text(
            json.dumps(ISOLATED_SOURCES, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed saving isolation state")


def _load_isolation_state() -> None:
    try:
        if ISOLATION_FILE.exists():
            data = json.loads(ISOLATION_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                ISOLATED_SOURCES.update(data)
    except Exception:
        logger.exception("Failed loading isolation state")


def _source_maybe_release(item: Dict[str, Any]) -> bool:
    key = _source_key(item)
    rec = ISOLATED_SOURCES.get(key) or {}
    if not rec.get("isolated"):
        return False

    last_iso = rec.get("isolated_at")
    if not last_iso:
        return False

    try:
        then = datetime.fromisoformat(str(last_iso))
        now = datetime.now(timezone.utc)
        if (now - then).total_seconds() >= ISOLATION_COOLDOWN_SECONDS:
            rec["isolated"] = False
            rec["failures"] = 0
            rec["released_at"] = now.isoformat()
            ISOLATED_SOURCES[key] = rec
            _save_isolation_state()
            return True
    except Exception:
        return False

    return False


def _is_source_isolated(item: Dict[str, Any]) -> bool:
    key = _source_key(item)
    rec = ISOLATED_SOURCES.get(key) or {}
    if bool(rec.get("isolated", False)):
        _source_maybe_release(item)
        rec = ISOLATED_SOURCES.get(key) or rec
    return bool(rec.get("isolated", False))


def _record_source_failures_from_pipeline(pipeline_result: Dict[str, Any]) -> None:
    rows = pipeline_result.get("results", []) if isinstance(pipeline_result, dict) else []
    if not isinstance(rows, list):
        return

    for row in rows:
        if not isinstance(row, dict):
            continue

        fc = _safe_str(row.get("failure_classification")).lower()
        retry_decision = _safe_str(row.get("retry_decision")).lower()
        if fc in {"selector_failure", "authentication_failure", "portal_unavailable"} or retry_decision == "retry_ceiling_reached":
            key = _source_key(row)
            rec = ISOLATED_SOURCES.get(key, {"failures": 0, "isolated": False})
            rec["failures"] += 1
            if rec["failures"] >= ISOLATION_FAILURE_THRESHOLD:
                rec["isolated"] = True
                rec["isolated_at"] = _now_iso()
            ISOLATED_SOURCES[key] = rec
            _save_isolation_state()


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

    state_snapshot = get_system_state()
    system_block_reason = get_block_reason("system")
    if system_block_reason:
        logger.warning("Autonomous cycle skipped due to system control block: %s", system_block_reason)
        return {
            "status": "skipped",
            "message": "Autonomous cycle skipped by system control",
            "reason": system_block_reason,
            "started_at": started_at,
            "updated_at": _now_iso(),
            "system_state": state_snapshot,
            "isolated_sources": ISOLATED_SOURCES,
            "harvest_count": 0,
            "supply_count": 0,
            "eligible_count": 0,
            "pipeline_input_count": 0,
            "pipeline_result": {
                "status": "skipped",
                "reason": system_block_reason,
                "results": [],
            },
            "radar_output": {},
        }

    disk_guard = _check_disk_guard()
    if disk_guard:
        return {
            "status": "skipped",
            "message": disk_guard["message"],
            "reason": disk_guard["reason"],
            "started_at": started_at,
            "updated_at": _now_iso(),
            "system_state": state_snapshot,
            "isolated_sources": ISOLATED_SOURCES,
            "harvest_count": 0,
            "supply_count": 0,
            "eligible_count": 0,
            "pipeline_input_count": 0,
            "pipeline_result": {
                "status": "skipped",
                "reason": disk_guard["reason"],
                "results": [],
            },
            "radar_output": {},
            "free_disk_gb": disk_guard["free_disk_gb"],
            "min_free_disk_gb": disk_guard["min_free_disk_gb"],
            "pause_file": disk_guard["pause_file"],
        }

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

        eligible_items = [i for i in eligible_items if not _is_source_isolated(i)]
        try:
            from app.services.rfq_lifecycle_service import RfqLifecycleService

            lifecycle_ingestion = RfqLifecycleService().ingest_discovered_items(
                eligible_items,
                source="autonomous_cycle:eligible_items",
            )
        except Exception as exc:
            lifecycle_ingestion = {"status": "warning", "error": str(exc)}
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
                "system_state": state_snapshot,
                "isolated_sources": ISOLATED_SOURCES,
                "free_disk_gb": _disk_free_gb("."),
                "min_free_disk_gb": MIN_FREE_DISK_GB,
                "harvest_count": harvested_count,
                "supply_count": supply_count,
                "eligible_count": eligible_count,
                "pipeline_input_count": 0,
                "lifecycle_ingestion": lifecycle_ingestion,
                "pipeline_result": {
                    "status": "skipped",
                    "reason": "no_eligible_items",
                    "results": [],
                },
                "radar_output": radar_output,
            }

        pipeline_result = run_tender_pipeline_batch_from_harvest(prepared_items)
        _record_source_failures_from_pipeline(pipeline_result)
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
            "system_state": state_snapshot,
            "isolated_sources": ISOLATED_SOURCES,
            "free_disk_gb": _disk_free_gb("."),
            "min_free_disk_gb": MIN_FREE_DISK_GB,
            "harvest_count": harvested_count,
            "supply_count": supply_count,
            "eligible_count": eligible_count,
            "pipeline_input_count": pipeline_input_count,
            "lifecycle_ingestion": lifecycle_ingestion,
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
            "system_state": state_snapshot,
            "isolated_sources": ISOLATED_SOURCES,
            "free_disk_gb": _disk_free_gb("."),
            "min_free_disk_gb": MIN_FREE_DISK_GB,
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
    disk_guard = _check_disk_guard()
    return {
        "status": "ready" if not disk_guard else "guarded",
        "engine": "lmcp_autonomous_engine",
        "mode": "supply-and-delivery-only",
        "autonomous_cycle_available": True,
        "pipeline_batch_available": True,
        "filters": {
            "supply_only": True,
            "exclude_non_supply": True,
            "prefer_quote_ready": True,
        },
        "free_disk_gb": _disk_free_gb("."),
        "min_free_disk_gb": MIN_FREE_DISK_GB,
        "pause_file": str(LOW_DISK_PAUSE_FILE) if LOW_DISK_PAUSE_FILE.exists() else "",
        "isolated_sources": ISOLATED_SOURCES,
        "updated_at": _now_iso(),
    }


_load_isolation_state()
