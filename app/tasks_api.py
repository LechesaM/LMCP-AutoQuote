from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from celery.result import AsyncResult

from app.tasks import celery
from app.tasks import run_harvest_only as run_harvest_only_task
from app.tasks import run_harvest_pipeline as run_harvest_pipeline_task
from app.tasks import run_scheduled_tender_harvest_task
from app.scripts.run_source_by_source_live_smoke import run_source_by_source_live_smoke as run_source_by_source_live_smoke_helper

router = APIRouter(prefix="/tasks", tags=["Tasks"])
SMOKE_SOURCE_FILE = Path(__file__).resolve().parent / "data" / "smoke_harvest_sources.json"


@router.post("/run-harvest-only")
def trigger_run_harvest_only():
    task = run_harvest_only_task.delay()
    return {
        "status": "queued",
        "task_name": "run_harvest_only",
        "task_id": task.id,
    }


@router.post("/run-harvest-pipeline")
def trigger_run_harvest_pipeline():
    task = run_harvest_pipeline_task.delay()
    return {
        "status": "queued",
        "task_name": "run_harvest_pipeline",
        "task_id": task.id,
    }


@router.post("/run-scheduled-harvest")
def trigger_run_scheduled_harvest(
    duration_minutes: int = 60,
    sleep_seconds: int = 600,
    max_total: int = 20,
    max_per_source: int = 3,
    max_sources_per_cycle: int = 10,
    source_file: Optional[str] = None,
    include_bad_sources: bool = False,
    headless: bool = True,
    auto_quote: bool = False,
    true_autonomous: bool = False,
    persist_to_live_store: bool = True,
    minimum_margin_pct: float = 25.0,
    minimum_profit: float = 30000.0,
    controlled_mode: bool = False,
    runtime_dir: Optional[str] = None,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
):
    if controlled_mode and source_file is None:
        source_file = str(SMOKE_SOURCE_FILE)
    if controlled_mode:
        persist_to_live_store = False
    task = run_scheduled_tender_harvest_task.delay(
        duration_minutes=duration_minutes,
        sleep_seconds=sleep_seconds,
        max_total=max_total,
        max_per_source=max_per_source,
        max_sources_per_cycle=max_sources_per_cycle,
        source_file=source_file,
        include_bad_sources=include_bad_sources,
        headless=headless,
        auto_quote=auto_quote,
        true_autonomous=true_autonomous,
        persist_to_live_store=persist_to_live_store,
        minimum_margin_pct=minimum_margin_pct,
        minimum_profit=minimum_profit,
        controlled_mode=controlled_mode,
        runtime_dir=runtime_dir,
        source_timeout_seconds=source_timeout_seconds,
        playwright_timeout_ms=playwright_timeout_ms,
    )
    return {
        "status": "queued",
        "task_name": "run_scheduled_tender_harvest_task",
        "task_id": task.id,
        "duration_minutes": duration_minutes,
        "sleep_seconds": sleep_seconds,
        "persist_to_live_store": persist_to_live_store,
        "controlled_mode": controlled_mode,
        "runtime_dir": runtime_dir,
        "source_timeout_seconds": source_timeout_seconds,
        "playwright_timeout_ms": playwright_timeout_ms,
    }


@router.post("/run-scheduled-harvest-now")
def run_scheduled_harvest_now(
    duration_minutes: int = 60,
    sleep_seconds: int = 600,
    max_total: int = 20,
    max_per_source: int = 3,
    max_sources_per_cycle: int = 10,
    source_file: Optional[str] = None,
    include_bad_sources: bool = False,
    headless: bool = True,
    auto_quote: bool = False,
    true_autonomous: bool = False,
    persist_to_live_store: bool = True,
    minimum_margin_pct: float = 25.0,
    minimum_profit: float = 30000.0,
    controlled_mode: bool = False,
    runtime_dir: Optional[str] = None,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
):
    try:
        from app.services.harvest_scheduler_service import run_scheduled_tender_harvest

        if controlled_mode and source_file is None:
            source_file = str(SMOKE_SOURCE_FILE)
        if controlled_mode:
            persist_to_live_store = False
        return {
            "status": "ok",
            "task_name": "run_scheduled_tender_harvest",
            "result": run_scheduled_tender_harvest(
                duration_minutes=duration_minutes,
                sleep_seconds=sleep_seconds,
                max_total=max_total,
                max_per_source=max_per_source,
                max_sources_per_cycle=max_sources_per_cycle,
                source_file=source_file,
                include_bad_sources=include_bad_sources,
                headless=headless,
                enable_auto_quote=auto_quote,
                true_autonomous=true_autonomous,
                persist_to_live_store=persist_to_live_store,
                minimum_margin_pct=minimum_margin_pct,
                minimum_profit=minimum_profit,
                controlled_mode=controlled_mode,
                runtime_dir=runtime_dir,
                source_timeout_seconds=source_timeout_seconds,
                playwright_timeout_ms=playwright_timeout_ms,
            ),
        }
    except Exception as e:
        return {
            "status": "failed",
            "task_name": "run_scheduled_tender_harvest",
            "error": str(e),
        }


@router.post("/run-scheduled-harvest-smoke-now")
def run_scheduled_harvest_smoke_now(
    duration_minutes: int = 1,
    sleep_seconds: int = 5,
    max_total: int = 10,
    max_per_source: int = 2,
    max_sources_per_cycle: int = 1,
    include_bad_sources: bool = False,
    headless: bool = True,
    auto_quote: bool = False,
    true_autonomous: bool = False,
    minimum_margin_pct: float = 25.0,
    minimum_profit: float = 30000.0,
    runtime_dir: Optional[str] = None,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
):
    try:
        from app.services.harvest_scheduler_service import run_scheduled_tender_harvest

        return {
            "status": "ok",
            "task_name": "run_scheduled_tender_harvest_smoke",
            "result": run_scheduled_tender_harvest(
                duration_minutes=duration_minutes,
                sleep_seconds=sleep_seconds,
                max_total=max_total,
                max_per_source=max_per_source,
                max_sources_per_cycle=max_sources_per_cycle,
                source_file=str(SMOKE_SOURCE_FILE),
                include_bad_sources=include_bad_sources,
                headless=headless,
                enable_auto_quote=auto_quote,
                true_autonomous=true_autonomous,
                persist_to_live_store=False,
                minimum_margin_pct=minimum_margin_pct,
                minimum_profit=minimum_profit,
                controlled_mode=True,
                runtime_dir=runtime_dir,
                source_timeout_seconds=source_timeout_seconds,
                playwright_timeout_ms=playwright_timeout_ms,
            ),
        }
    except Exception as e:
        return {
            "status": "failed",
            "task_name": "run_scheduled_tender_harvest_smoke",
            "error": str(e),
        }


@router.post("/run-source-by-source-live-smoke")
def run_source_by_source_live_smoke_now(
    source_file: Optional[str] = None,
    source_name: Optional[str] = None,
    source_group: Optional[str] = None,
    limit: int = 1,
    runtime_dir: Optional[str] = None,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 12000,
    fail_fast: bool = False,
    emit_progress: bool = False,
):
    try:
        if source_file is None:
            source_file = str(Path(__file__).resolve().parents[1] / "data" / "harvest_sources.json")
        result = run_source_by_source_live_smoke_helper(
            source_file=source_file,
            source_name=source_name,
            source_group=source_group,
            limit=limit,
            runtime_dir=runtime_dir,
            source_timeout_seconds=source_timeout_seconds,
            playwright_timeout_ms=playwright_timeout_ms,
            fail_fast=fail_fast,
            emit_progress=emit_progress,
        )
        return {
            "status": "ok" if result.get("status") == "ok" else "failed",
            "task_name": "run_source_by_source_live_smoke",
            "result": result,
        }
    except Exception as e:
        return {
            "status": "failed",
            "task_name": "run_source_by_source_live_smoke",
            "error": str(e),
        }


@router.get("/scheduled-harvest-summary")
def get_scheduled_harvest_summary():
    try:
        from app.services.harvest_scheduler_service import get_latest_scheduled_harvest_summaries

        return get_latest_scheduled_harvest_summaries()
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
        }


@router.get("/status/{task_id}")
def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery)

    response = {
        "task_id": task_id,
        "state": result.state,
    }

    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)

    return response
