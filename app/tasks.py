from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from app.celery_app import celery_app

logger = logging.getLogger(__name__)

AUTO_HARVEST_ENABLED = str(os.getenv("AUTO_HARVEST_ENABLED", "true")).strip().lower() == "true"
AUTO_QUOTE_ENABLED = str(os.getenv("AUTO_QUOTE_ENABLED", "true")).strip().lower() == "true"
AUTO_SUBMIT_ENABLED = str(os.getenv("AUTO_SUBMIT_ENABLED", "false")).strip().lower() == "true"

# Backward-compatible alias expected by older modules such as app.tasks_api
celery = celery_app


def _resolve_engine_factory():
    """
    Backward/forward compatible resolver for the autonomous engine.
    Supports:
    - class AutonomousTenderEngine
    - callable autonomous_engine
    - object autonomous_engine with run_once()
    """
    try:
        import app.autonomous_engine as engine_module  # type: ignore

        cls = getattr(engine_module, "AutonomousTenderEngine", None)
        if callable(cls):
            logger.info("[TASKS] Using AutonomousTenderEngine class")
            return lambda: cls()

        obj = getattr(engine_module, "autonomous_engine", None)
        if obj is not None:
            if callable(obj):
                logger.info("[TASKS] Using autonomous_engine callable")
                return obj
            if hasattr(obj, "run_once"):
                logger.info("[TASKS] Using autonomous_engine object")
                return lambda: obj

        logger.warning("[TASKS] No compatible autonomous engine found in app.autonomous_engine")
        return None

    except Exception as exc:
        logger.warning("[TASKS] Could not import app.autonomous_engine: %s", exc)
        return None


def _resolve_pipeline_batch_function():
    """
    Backward/forward compatible resolver for tender pipeline batch execution.
    Supports:
    - run_tender_pipeline_batch_from_harvest
    - run_tender_pipeline_batch
    """
    try:
        from app.services import tender_pipeline as pipeline_module  # type: ignore

        for func_name in [
            "run_tender_pipeline_batch_from_harvest",
            "run_tender_pipeline_batch",
        ]:
            func = getattr(pipeline_module, func_name, None)
            if callable(func):
                logger.info("[TASKS] Using pipeline function: %s", func_name)
                return func

        logger.warning("[TASKS] No compatible batch pipeline function found in app.services.tender_pipeline")
        return None

    except Exception as exc:
        logger.warning("[TASKS] Could not import app.services.tender_pipeline: %s", exc)
        return None


@celery_app.task(name="app.tasks.health_check")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "worker": "celery",
        "policy": "supply-and-delivery-only",
        "auto_harvest_enabled": AUTO_HARVEST_ENABLED,
        "auto_quote_enabled": AUTO_QUOTE_ENABLED,
        "auto_submit_enabled": AUTO_SUBMIT_ENABLED,
    }


@celery_app.task(name="app.tasks.run_supply_intelligence_scan")
def run_supply_intelligence_scan() -> Dict[str, Any]:
    if not AUTO_HARVEST_ENABLED:
        logger.info("[TASKS] AUTO_HARVEST_ENABLED is false. Skipping scan.")
        return {
            "status": "skipped",
            "reason": "AUTO_HARVEST_ENABLED is false",
            "auto_quote_enabled": AUTO_QUOTE_ENABLED,
            "auto_submit_enabled": AUTO_SUBMIT_ENABLED,
        }

    try:
        engine_factory = _resolve_engine_factory()
        if engine_factory is None:
            return {
                "status": "failed",
                "task": "run_supply_intelligence_scan",
                "error": "Autonomous engine not available",
            }

        engine = engine_factory()

        if not hasattr(engine, "run_once"):
            return {
                "status": "failed",
                "task": "run_supply_intelligence_scan",
                "error": "Resolved autonomous engine has no run_once() method",
            }

        result = engine.run_once()

        return {
            "status": "ok",
            "task": "run_supply_intelligence_scan",
            "auto_quote_enabled": AUTO_QUOTE_ENABLED,
            "auto_submit_enabled": AUTO_SUBMIT_ENABLED,
            "result": result,
        }
    except Exception as exc:
        logger.exception("[TASKS] run_supply_intelligence_scan failed")
        return {
            "status": "failed",
            "task": "run_supply_intelligence_scan",
            "error": str(exc),
        }


@celery_app.task(name="app.tasks.run_harvest_only")
def run_harvest_only(
    max_total: int = 20,
    max_per_source: int = 5,
) -> Dict[str, Any]:
    if not AUTO_HARVEST_ENABLED:
        return {
            "status": "skipped",
            "reason": "AUTO_HARVEST_ENABLED is false",
        }

    try:
        engine_factory = _resolve_engine_factory()
        if engine_factory is None:
            return {
                "status": "failed",
                "task": "run_harvest_only",
                "error": "Autonomous engine not available",
            }

        engine = engine_factory()

        if hasattr(engine, "run_once"):
            result = engine.run_once()
        else:
            result = {
                "status": "warning",
                "message": "Resolved autonomous engine has no run_once() method",
            }

        return {
            "status": "ok",
            "task": "run_harvest_only",
            "max_total": max_total,
            "max_per_source": max_per_source,
            "result": result,
        }
    except Exception as exc:
        logger.exception("[TASKS] run_harvest_only failed")
        return {
            "status": "failed",
            "task": "run_harvest_only",
            "error": str(exc),
        }


# Backward-compatible alias expected by older modules such as app.opportunities_api
manual_harvest = run_harvest_only


@celery_app.task(name="app.tasks.run_harvest_pipeline")
def run_harvest_pipeline(
    harvested_rfqs: List[Dict[str, Any]],
    source: str = "celery_harvest",
    persist_to_live_store: bool = True,
) -> Dict[str, Any]:
    try:
        if not isinstance(harvested_rfqs, list):
            return {
                "status": "failed",
                "task": "run_harvest_pipeline",
                "error": "harvested_rfqs must be a list",
            }

        try:
            from app.services.rfq_lifecycle_service import RfqLifecycleService

            lifecycle_ingestion = RfqLifecycleService().ingest_discovered_items(
                harvested_rfqs,
                source=f"celery:{source}",
            )
        except Exception as exc:
            lifecycle_ingestion = {"status": "warning", "error": str(exc)}

        batch_func = _resolve_pipeline_batch_function()
        if batch_func is None:
            return {
                "status": "failed",
                "task": "run_harvest_pipeline",
                "error": "No compatible tender pipeline batch function found",
            }

        try:
            results = batch_func(
                harvested_rfqs=harvested_rfqs,
                source=source,
                persist_to_live_store=persist_to_live_store,
            )
        except TypeError:
            results = batch_func(
                payloads=harvested_rfqs,
                source=source,
                persist_to_live_store=persist_to_live_store,
            )

        return {
            "status": "ok",
            "task": "run_harvest_pipeline",
            "source": source,
            "count": len(harvested_rfqs),
            "lifecycle_ingestion": lifecycle_ingestion,
            "results": results,
        }

    except Exception as exc:
        logger.exception("[TASKS] run_harvest_pipeline failed")
        return {
            "status": "failed",
            "task": "run_harvest_pipeline",
            "error": str(exc),
        }


@celery_app.task(name="app.tasks.run_manual_pipeline_test")
def run_manual_pipeline_test(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from app.services.tender_pipeline import run_tender_pipeline_from_payload  # type: ignore

        result = run_tender_pipeline_from_payload(
            payload=payload,
            source="celery_manual_test",
            persist_to_live_store=True,
        )

        return {
            "status": "ok",
            "task": "run_manual_pipeline_test",
            "result": result,
        }
    except Exception as exc:
        logger.exception("[TASKS] run_manual_pipeline_test failed")
        return {
            "status": "failed",
            "task": "run_manual_pipeline_test",
            "error": str(exc),
        }


@celery_app.task(name="app.tasks.run_rfq_lifecycle_golden_cycle")
def run_rfq_lifecycle_golden_cycle(limit: int = 25, dry_run: bool = True) -> Dict[str, Any]:
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService

        result = RfqLifecycleService().run_golden_cycle(limit=limit, dry_run=dry_run)
        return {
            "status": "ok",
            "task": "run_rfq_lifecycle_golden_cycle",
            "result": result,
        }
    except Exception as exc:
        logger.exception("[TASKS] run_rfq_lifecycle_golden_cycle failed")
        return {
            "status": "failed",
            "task": "run_rfq_lifecycle_golden_cycle",
            "error": str(exc),
        }


@celery_app.task(name="app.tasks.rfq_lifecycle_acquisition_task", queue="acquisition_queue")
def rfq_lifecycle_acquisition_task(limit: int = 25, timeout_seconds: int = 8, max_concurrent_downloads: int = 4) -> Dict[str, Any]:
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService

        return RfqLifecycleService().advance_discovered(
            limit=limit,
            timeout_seconds=timeout_seconds,
            max_concurrent_downloads=max_concurrent_downloads,
        )
    except Exception as exc:
        logger.exception("[TASKS] rfq_lifecycle_acquisition_task failed")
        return {"status": "failed", "task": "rfq_lifecycle_acquisition_task", "error": str(exc)}


@celery_app.task(name="app.tasks.rfq_lifecycle_parsing_task", queue="parsing_queue")
def rfq_lifecycle_parsing_task(limit: int = 25) -> Dict[str, Any]:
    return {
        "status": "ok",
        "task": "rfq_lifecycle_parsing_task",
        "message": "Parsing is executed inside advance_discovered after acquisition in the current lifecycle architecture.",
        "limit": limit,
        "safety": {"no_email": True, "no_portal_upload": True, "no_final_submit": True, "captcha_bypass": False},
    }


@celery_app.task(name="app.tasks.rfq_lifecycle_pricing_task", queue="pricing_queue")
def rfq_lifecycle_pricing_task(limit: int = 25) -> Dict[str, Any]:
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService

        return RfqLifecycleService().advance_parsed(limit=limit)
    except Exception as exc:
        logger.exception("[TASKS] rfq_lifecycle_pricing_task failed")
        return {"status": "failed", "task": "rfq_lifecycle_pricing_task", "error": str(exc)}


@celery_app.task(name="app.tasks.rfq_lifecycle_proof_task", queue="proof_queue")
def rfq_lifecycle_proof_task(limit: int = 25) -> Dict[str, Any]:
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService

        return RfqLifecycleService().run_controlled_submission(limit=limit)
    except Exception as exc:
        logger.exception("[TASKS] rfq_lifecycle_proof_task failed")
        return {"status": "failed", "task": "rfq_lifecycle_proof_task", "error": str(exc)}


@celery_app.task(name="app.tasks.rfq_lifecycle_retry_task", queue="retry_queue")
def rfq_lifecycle_retry_task(limit: int = 50, timeout_seconds: int = 8) -> Dict[str, Any]:
    try:
        from app.services.rfq_lifecycle_service import RfqLifecycleService

        return RfqLifecycleService().review_recovery(limit=limit, timeout_seconds=timeout_seconds)
    except Exception as exc:
        logger.exception("[TASKS] rfq_lifecycle_retry_task failed")
        return {"status": "failed", "task": "rfq_lifecycle_retry_task", "error": str(exc)}
