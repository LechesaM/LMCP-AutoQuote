from __future__ import annotations

import importlib
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.celery_app import celery
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


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _extract_harvest_items(harvest_result: Any) -> List[Dict[str, Any]]:
    if isinstance(harvest_result, list):
        return [item for item in harvest_result if isinstance(item, dict)]

    if not isinstance(harvest_result, dict):
        return []

    candidates = [
        harvest_result.get("items"),
        harvest_result.get("opportunities"),
        harvest_result.get("results"),
        harvest_result.get("data"),
        harvest_result.get("candidates"),
        harvest_result.get("rfqs"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]

    return []


def _build_task_summary(
    task_name: str,
    status: str,
    message: str,
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "task": task_name,
        "status": status,
        "message": message,
        "updated_at": _now_iso(),
    }
    payload.update(extra)
    return payload


def _run_harvester() -> Any:
    """
    Stable autonomous harvester order based on real callable signatures.

    Order:
    1. app.services.tender_harvester.run_national_tender_radar(db=None)
    2. app.tender_harvester.harvest_etenders()
    3. app.harvester.harvest_opportunities(...) fallback
    """
    try:
        service_module = importlib.import_module("app.services.tender_harvester")
        radar_fn = getattr(service_module, "run_national_tender_radar", None)
        if callable(radar_fn):
            logger.info("Using app.services.tender_harvester.run_national_tender_radar(db=None)")
            result = radar_fn(db=None)
            if result is not None:
                return result
    except Exception as exc:
        logger.exception("run_national_tender_radar failed: %s", exc)

    try:
        et_module = importlib.import_module("app.tender_harvester")
        et_fn = getattr(et_module, "harvest_etenders", None)
        if callable(et_fn):
            logger.info("Using app.tender_harvester.harvest_etenders()")
            result = et_fn()
            if result is not None:
                return result
    except Exception as exc:
        logger.exception("harvest_etenders failed: %s", exc)

    harvester_module = importlib.import_module("app.harvester")

    full_fn = getattr(harvester_module, "harvest_opportunities", None)
    if callable(full_fn):
        logger.info("Using app.harvester.harvest_opportunities() fallback")
        return full_fn(
            include_parser_router=True,
            include_department_scraper=False,
            include_homepage_only=False,
            include_needs_custom_parser=True,
            min_confidence=5,
            entity_type_filter=None,
            limit_sources=10,
        )

    quick_fn = getattr(harvester_module, "harvest_opportunities_quick", None)
    if callable(quick_fn):
        logger.info("Fallback to app.harvester.harvest_opportunities_quick()")
        return quick_fn()

    available = [name for name in dir(harvester_module) if not name.startswith("_")]
    raise AttributeError(
        "No supported harvester entry point found. "
        f"Available names in app.harvester: {available}"
    )


def _run_with_timeout(fn, timeout_seconds: int) -> Any:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)

    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    except Exception:
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    finally:
        if future.done():
            executor.shutdown(wait=True, cancel_futures=True)


def _is_item_supply(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False

    if _safe_bool(item.get("is_supply"), False):
        return True

    category = str(item.get("category") or "").lower()
    title = str(item.get("title") or "").lower()
    description = str(item.get("description") or "").lower()
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


def _prepare_items_for_pipeline(
    items: List[Dict[str, Any]],
    *,
    include_non_quote_ready: bool = False,
    max_items: Optional[int] = None,
) -> List[Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []

    supply_items = [item for item in items if isinstance(item, dict) and _is_item_supply(item)]

    if include_non_quote_ready:
        filtered_items = supply_items
    else:
        filtered_items = [item for item in supply_items if _is_item_quote_ready(item)]

    if isinstance(max_items, int) and max_items > 0:
        filtered_items = filtered_items[:max_items]

    for item in filtered_items:
        row = dict(item)

        # Preserve upstream flags instead of forcing test mode.
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


def _execute_harvest_pipeline(
    *,
    include_non_quote_ready: bool = False,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Plain Python execution path used by Celery tasks.
    This avoids calling one Celery task directly from another.
    """
    harvest_result = _run_with_timeout(_run_harvester, timeout_seconds=90)
    harvested_items = _extract_harvest_items(harvest_result)

    prepared_items = _prepare_items_for_pipeline(
        harvested_items,
        include_non_quote_ready=include_non_quote_ready,
        max_items=max_items,
    )

    pipeline_result = run_tender_pipeline_batch_from_harvest(prepared_items or [])

    return {
        "status": "ok",
        "message": "Harvest + pipeline completed",
        "harvest_count": len(harvested_items),
        "pipeline_input_count": len(prepared_items),
        "harvest_result": harvest_result,
        "pipeline_result": pipeline_result,
    }


@celery.task(name="app.tasks.health_check")
def health_check() -> Dict[str, Any]:
    return _build_task_summary(
        task_name="health_check",
        status="ok",
        message="Celery worker is healthy",
    )


@celery.task(name="app.tasks.run_harvest_only")
def run_harvest_only() -> Dict[str, Any]:
    try:
        harvest_result = _run_with_timeout(_run_harvester, timeout_seconds=90)
        items = _extract_harvest_items(harvest_result)

        return _build_task_summary(
            task_name="run_harvest_only",
            status="ok",
            message="Harvest completed",
            harvested_count=len(items),
            harvest_result=harvest_result,
        )

    except FuturesTimeoutError:
        logger.exception("run_harvest_only timed out")
        return _build_task_summary(
            task_name="run_harvest_only",
            status="failed",
            message="Harvest task timed out after 90 seconds",
        )
    except Exception as exc:
        logger.exception("run_harvest_only failed")
        return _build_task_summary(
            task_name="run_harvest_only",
            status="failed",
            message=f"Harvest task failed: {exc}",
        )


@celery.task(name="app.tasks.run_pipeline_from_items")
def run_pipeline_from_items(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        pipeline_result = run_tender_pipeline_batch_from_harvest(items or [])

        return _build_task_summary(
            task_name="run_pipeline_from_items",
            status="ok",
            message="Pipeline run completed",
            input_count=_safe_len(items),
            pipeline_result=pipeline_result,
        )

    except Exception as exc:
        logger.exception("run_pipeline_from_items failed")
        return _build_task_summary(
            task_name="run_pipeline_from_items",
            status="failed",
            message=f"Pipeline task failed: {exc}",
            input_count=_safe_len(items),
        )


@celery.task(name="app.tasks.run_harvest_pipeline")
def run_harvest_pipeline(
    include_non_quote_ready: bool = False,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        result = _execute_harvest_pipeline(
            include_non_quote_ready=_safe_bool(include_non_quote_ready, False),
            max_items=_safe_int(max_items, None),
        )
        return _build_task_summary(
            task_name="run_harvest_pipeline",
            status=result.get("status", "ok"),
            message=result.get("message", "Harvest + pipeline completed"),
            harvest_count=result.get("harvest_count", 0),
            pipeline_input_count=result.get("pipeline_input_count", 0),
            harvest_result=result.get("harvest_result"),
            pipeline_result=result.get("pipeline_result"),
        )

    except FuturesTimeoutError:
        logger.exception("run_harvest_pipeline timed out")
        return _build_task_summary(
            task_name="run_harvest_pipeline",
            status="failed",
            message="Harvest + pipeline task timed out after 90 seconds",
        )
    except Exception as exc:
        logger.exception("run_harvest_pipeline failed")
        return _build_task_summary(
            task_name="run_harvest_pipeline",
            status="failed",
            message=f"Harvest + pipeline task failed: {exc}",
        )


@celery.task(name="app.tasks.run_autonomous_cycle")
def run_autonomous_cycle(
    include_non_quote_ready: bool = False,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Celery autonomous entry point.

    Compatible with:
    - /autonomous/run-once
    - /autonomous/run-sync fallback behavior in API layer
    """
    try:
        try:
            from app.services.autonomous_engine import run_autonomous_cycle as engine_run_autonomous_cycle

            result = engine_run_autonomous_cycle(
                db=None,
                include_non_quote_ready=_safe_bool(include_non_quote_ready, False),
                max_items=_safe_int(max_items, None),
            )

            return _build_task_summary(
                task_name="run_autonomous_cycle",
                status=result.get("status", "ok") if isinstance(result, dict) else "ok",
                message=result.get("message", "Autonomous cycle completed")
                if isinstance(result, dict)
                else "Autonomous cycle completed",
                include_non_quote_ready=_safe_bool(include_non_quote_ready, False),
                max_items=_safe_int(max_items, None),
                result=result,
            )

        except Exception as engine_exc:
            logger.exception("Autonomous engine invocation failed, falling back to local harvest pipeline: %s", engine_exc)

            fallback_result = _execute_harvest_pipeline(
                include_non_quote_ready=_safe_bool(include_non_quote_ready, False),
                max_items=_safe_int(max_items, None),
            )

            return _build_task_summary(
                task_name="run_autonomous_cycle",
                status=fallback_result.get("status", "ok"),
                message=fallback_result.get(
                    "message",
                    "Autonomous cycle completed via fallback harvest + pipeline",
                ),
                include_non_quote_ready=_safe_bool(include_non_quote_ready, False),
                max_items=_safe_int(max_items, None),
                harvest_count=fallback_result.get("harvest_count", 0),
                pipeline_input_count=fallback_result.get("pipeline_input_count", 0),
                harvest_result=fallback_result.get("harvest_result"),
                pipeline_result=fallback_result.get("pipeline_result"),
                fallback_used=True,
                fallback_reason=str(engine_exc),
            )

    except FuturesTimeoutError:
        logger.exception("run_autonomous_cycle timed out")
        return _build_task_summary(
            task_name="run_autonomous_cycle",
            status="failed",
            message="Autonomous cycle timed out after 90 seconds",
            include_non_quote_ready=_safe_bool(include_non_quote_ready, False),
            max_items=_safe_int(max_items, None),
        )
    except Exception as exc:
        logger.exception("run_autonomous_cycle failed")
        return _build_task_summary(
            task_name="run_autonomous_cycle",
            status="failed",
            message=f"Autonomous cycle failed: {exc}",
            include_non_quote_ready=_safe_bool(include_non_quote_ready, False),
            max_items=_safe_int(max_items, None),
        )


def manual_harvest() -> dict:
    from app.services.tender_harvester import run_national_tender_radar

    result = run_national_tender_radar()

    if not isinstance(result, dict):
        return {
            "status": "ok",
            "source": "manual_harvest",
            "opportunities_found": 0,
            "opportunities": [],
        }

    opportunities = (
        result.get("results")
        or result.get("opportunities")
        or result.get("items")
        or []
    )

    return {
        "status": "ok",
        "source": "manual_harvest",
        "opportunities_found": len(opportunities) if isinstance(opportunities, list) else 0,
        "opportunities": opportunities if isinstance(opportunities, list) else [],
        **result,
    }
