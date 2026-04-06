from fastapi import APIRouter
from celery.result import AsyncResult

from app.tasks import celery, run_harvest_only, run_harvest_pipeline

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/run-harvest-only")
def trigger_run_harvest_only():
    task = run_harvest_only.delay()
    return {
        "status": "queued",
        "task_name": "run_harvest_only",
        "task_id": task.id,
    }


@router.post("/run-harvest-pipeline")
def trigger_run_harvest_pipeline():
    task = run_harvest_pipeline.delay()
    return {
        "status": "queued",
        "task_name": "run_harvest_pipeline",
        "task_id": task.id,
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
