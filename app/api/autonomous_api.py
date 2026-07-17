from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

try:
    from celery.result import AsyncResult
except Exception:
    AsyncResult = None  # type: ignore

try:
    from app.celery_app import celery as celery_app
except Exception:
    celery_app = None  # type: ignore

try:
    from app.tasks import run_autonomous_cycle as run_autonomous_cycle_task
except Exception:
    run_autonomous_cycle_task = None  # type: ignore

try:
    from app.services.autonomous_engine import (
        get_autonomous_status as get_engine_autonomous_status,
    )
except Exception:
    get_engine_autonomous_status = None  # type: ignore

try:
    from app.services.autonomous_engine import (
        run_autonomous_cycle as run_autonomous_cycle_sync,
    )
except Exception:
    run_autonomous_cycle_sync = None  # type: ignore

router = APIRouter(prefix="/autonomous", tags=["Autonomous"])

_AUTONOMOUS_STATE: Dict[str, Any] = {
    "enabled": False,
    "updated_at": None,
    "last_run_at": None,
    "last_status": None,
    "last_message": None,
    "last_result": None,
    "last_task_id": None,
    "last_run_mode": None,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _safe_task_result(task_id: Optional[str]) -> Dict[str, Any]:
    if not task_id:
        return {}

    if AsyncResult is None or celery_app is None:
        return {
            "task_id": task_id,
            "status": "unknown",
            "message": "Celery result backend not available",
        }

    try:
        result = AsyncResult(task_id, app=celery_app)

        payload: Dict[str, Any] = {
            "task_id": task_id,
            "celery_state": result.state,
        }

        if result.state == "PENDING":
            payload["status"] = "queued"
        elif result.state == "RECEIVED":
            payload["status"] = "received"
        elif result.state == "STARTED":
            payload["status"] = "running"
        elif result.successful():
            payload["status"] = "completed"
            payload["result"] = result.result
        elif result.failed():
            payload["status"] = "failed"
            payload["result"] = str(result.result)
        else:
            payload["status"] = str(result.state).lower()

        return payload

    except Exception as exc:
        return {
            "task_id": task_id,
            "status": "error",
            "message": str(exc),
        }


def _refresh_autonomous_state_from_task() -> None:
    task_id = _AUTONOMOUS_STATE.get("last_task_id")
    if not task_id:
        return

    task_details = _safe_task_result(task_id)
    task_status = task_details.get("status")

    if not task_status:
        return

    _AUTONOMOUS_STATE["updated_at"] = _utc_now_iso()

    if task_status in {"queued", "received", "running"}:
        _AUTONOMOUS_STATE["last_status"] = task_status
        if task_status == "queued":
            _AUTONOMOUS_STATE["last_message"] = "Autonomous cycle queued"
        elif task_status == "received":
            _AUTONOMOUS_STATE["last_message"] = "Autonomous cycle received by worker"
        elif task_status == "running":
            _AUTONOMOUS_STATE["last_message"] = "Autonomous cycle running"

    elif task_status == "completed":
        _AUTONOMOUS_STATE["last_status"] = "completed"
        _AUTONOMOUS_STATE["last_message"] = "Autonomous cycle completed"
        _AUTONOMOUS_STATE["last_result"] = task_details.get("result")

    elif task_status == "failed":
        _AUTONOMOUS_STATE["last_status"] = "failed"
        _AUTONOMOUS_STATE["last_message"] = "Autonomous cycle failed"
        _AUTONOMOUS_STATE["last_result"] = task_details.get("result")


def _engine_status_payload() -> Dict[str, Any]:
    if get_engine_autonomous_status is None:
        return {
            "status": "unknown",
            "message": "Autonomous engine status function not available",
        }

    try:
        status = get_engine_autonomous_status()
        return status if isinstance(status, dict) else {"status": "unknown"}
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
        }


@router.get("/status")
def autonomous_status() -> Dict[str, Any]:
    _refresh_autonomous_state_from_task()
    task_details = _safe_task_result(_AUTONOMOUS_STATE.get("last_task_id"))
    engine_status = _engine_status_payload()

    return {
        "enabled": _AUTONOMOUS_STATE["enabled"],
        "updated_at": _AUTONOMOUS_STATE["updated_at"],
        "last_run_at": _AUTONOMOUS_STATE["last_run_at"],
        "last_status": _AUTONOMOUS_STATE["last_status"],
        "last_message": _AUTONOMOUS_STATE["last_message"],
        "last_task_id": _AUTONOMOUS_STATE["last_task_id"],
        "last_run_mode": _AUTONOMOUS_STATE["last_run_mode"],
        "task_details": task_details,
        "engine_status": engine_status,
    }


@router.post("/run-once")
def run_once(
    synchronous: bool = Query(
        default=False,
        description="Run immediately in API process instead of queuing through Celery",
    ),
    include_non_quote_ready: bool = Query(
        default=False,
        description="Include supply RFQs that are not yet marked quote-ready",
    ),
    max_items: Optional[int] = Query(
        default=None,
        ge=1,
        description="Optional maximum number of RFQs to send into the pipeline",
    ),
) -> Dict[str, Any]:
    if not _AUTONOMOUS_STATE["enabled"]:
        return {
            "status": "failed",
            "message": "Autonomous mode is disabled",
        }

    started_at = _utc_now_iso()

    if synchronous:
        if run_autonomous_cycle_sync is None:
            return {
                "status": "failed",
                "message": "Synchronous autonomous engine is not available",
            }

        try:
            result = run_autonomous_cycle_sync(
                db=None,
                include_non_quote_ready=include_non_quote_ready,
                max_items=max_items,
            )

            final_status = "completed"
            if isinstance(result, dict) and result.get("status") == "failed":
                final_status = "failed"

            _AUTONOMOUS_STATE["updated_at"] = _utc_now_iso()
            _AUTONOMOUS_STATE["last_run_at"] = started_at
            _AUTONOMOUS_STATE["last_status"] = final_status
            _AUTONOMOUS_STATE["last_message"] = (
                "Autonomous cycle completed synchronously"
                if final_status == "completed"
                else "Autonomous cycle failed synchronously"
            )
            _AUTONOMOUS_STATE["last_result"] = result
            _AUTONOMOUS_STATE["last_task_id"] = None
            _AUTONOMOUS_STATE["last_run_mode"] = "synchronous"

            return {
                "status": final_status,
                "message": _AUTONOMOUS_STATE["last_message"],
                "run_mode": "synchronous",
                "started_at": started_at,
                "result": result,
            }

        except Exception as exc:
            _AUTONOMOUS_STATE["updated_at"] = _utc_now_iso()
            _AUTONOMOUS_STATE["last_run_at"] = started_at
            _AUTONOMOUS_STATE["last_status"] = "failed"
            _AUTONOMOUS_STATE["last_message"] = f"Autonomous cycle failed synchronously: {exc}"
            _AUTONOMOUS_STATE["last_result"] = {"error": str(exc)}
            _AUTONOMOUS_STATE["last_task_id"] = None
            _AUTONOMOUS_STATE["last_run_mode"] = "synchronous"

            return {
                "status": "failed",
                "message": f"Autonomous cycle failed synchronously: {exc}",
                "run_mode": "synchronous",
                "started_at": started_at,
            }

    if run_autonomous_cycle_task is None:
        return {
            "status": "failed",
            "message": "run_autonomous_cycle task is not available",
        }

    queued_at = started_at

    try:
        task_kwargs: Dict[str, Any] = {
            "include_non_quote_ready": include_non_quote_ready,
        }
        if max_items is not None:
            task_kwargs["max_items"] = max_items

        task = run_autonomous_cycle_task.delay(**task_kwargs)
        task_id = str(task.id)

        _AUTONOMOUS_STATE["updated_at"] = queued_at
        _AUTONOMOUS_STATE["last_run_at"] = queued_at
        _AUTONOMOUS_STATE["last_status"] = "queued"
        _AUTONOMOUS_STATE["last_message"] = "Autonomous cycle queued"
        _AUTONOMOUS_STATE["last_result"] = None
        _AUTONOMOUS_STATE["last_task_id"] = task_id
        _AUTONOMOUS_STATE["last_run_mode"] = "celery"

        return {
            "status": "queued",
            "message": "Autonomous cycle queued",
            "task_id": task_id,
            "queued_at": queued_at,
            "run_mode": "celery",
            "status_url": "/autonomous/status",
            "result_url": "/autonomous/last-result",
        }

    except TypeError:
        try:
            task = run_autonomous_cycle_task.delay()
            task_id = str(task.id)

            _AUTONOMOUS_STATE["updated_at"] = queued_at
            _AUTONOMOUS_STATE["last_run_at"] = queued_at
            _AUTONOMOUS_STATE["last_status"] = "queued"
            _AUTONOMOUS_STATE["last_message"] = "Autonomous cycle queued"
            _AUTONOMOUS_STATE["last_result"] = None
            _AUTONOMOUS_STATE["last_task_id"] = task_id
            _AUTONOMOUS_STATE["last_run_mode"] = "celery"

            return {
                "status": "queued",
                "message": "Autonomous cycle queued",
                "task_id": task_id,
                "queued_at": queued_at,
                "run_mode": "celery",
                "status_url": "/autonomous/status",
                "result_url": "/autonomous/last-result",
                "warning": "Task signature does not yet accept filter parameters; queued with default arguments.",
            }

        except Exception as exc:
            _AUTONOMOUS_STATE["updated_at"] = queued_at
            _AUTONOMOUS_STATE["last_status"] = "failed"
            _AUTONOMOUS_STATE["last_message"] = f"Failed to queue autonomous cycle: {exc}"
            _AUTONOMOUS_STATE["last_result"] = {"error": str(exc)}
            _AUTONOMOUS_STATE["last_run_mode"] = "celery"

            return {
                "status": "failed",
                "message": f"Failed to queue autonomous cycle: {exc}",
            }

    except Exception as exc:
        _AUTONOMOUS_STATE["updated_at"] = queued_at
        _AUTONOMOUS_STATE["last_status"] = "failed"
        _AUTONOMOUS_STATE["last_message"] = f"Failed to queue autonomous cycle: {exc}"
        _AUTONOMOUS_STATE["last_result"] = {"error": str(exc)}
        _AUTONOMOUS_STATE["last_run_mode"] = "celery"

        return {
            "status": "failed",
            "message": f"Failed to queue autonomous cycle: {exc}",
        }


@router.post("/run-sync")
def run_sync(
    include_non_quote_ready: bool = Query(
        default=False,
        description="Include supply RFQs that are not yet marked quote-ready",
    ),
    max_items: Optional[int] = Query(
        default=None,
        ge=1,
        description="Optional maximum number of RFQs to send into the pipeline",
    ),
) -> Dict[str, Any]:
    return run_once(
        synchronous=True,
        include_non_quote_ready=include_non_quote_ready,
        max_items=max_items,
    )


@router.post("/enable")
def enable_autonomous() -> Dict[str, Any]:
    _AUTONOMOUS_STATE["enabled"] = True
    _AUTONOMOUS_STATE["updated_at"] = _utc_now_iso()
    return {
        "status": "ok",
        "message": "Autonomous mode enabled",
        "enabled": True,
        "updated_at": _AUTONOMOUS_STATE["updated_at"],
    }


@router.post("/disable")
def disable_autonomous() -> Dict[str, Any]:
    _AUTONOMOUS_STATE["enabled"] = False
    _AUTONOMOUS_STATE["updated_at"] = _utc_now_iso()
    return {
        "status": "ok",
        "message": "Autonomous mode disabled",
        "enabled": False,
        "updated_at": _AUTONOMOUS_STATE["updated_at"],
    }


@router.get("/last-result")
def get_last_result() -> Dict[str, Any]:
    _refresh_autonomous_state_from_task()
    task_details = _safe_task_result(_AUTONOMOUS_STATE.get("last_task_id"))

    return {
        "updated_at": _AUTONOMOUS_STATE["updated_at"],
        "enabled": _AUTONOMOUS_STATE["enabled"],
        "last_run_at": _AUTONOMOUS_STATE["last_run_at"],
        "last_status": _AUTONOMOUS_STATE["last_status"],
        "last_message": _AUTONOMOUS_STATE["last_message"],
        "last_result": _AUTONOMOUS_STATE["last_result"],
        "last_task_id": _AUTONOMOUS_STATE["last_task_id"],
        "last_run_mode": _AUTONOMOUS_STATE["last_run_mode"],
        "task_details": task_details,
    }


@router.get("/health")
def autonomous_health() -> Dict[str, Any]:
    _refresh_autonomous_state_from_task()
    engine_status = _engine_status_payload()

    ok = bool(_AUTONOMOUS_STATE["enabled"])
    if _AUTONOMOUS_STATE.get("last_status") == "failed":
        ok = False

    return {
        "status": "ok" if ok else "degraded",
        "enabled": _AUTONOMOUS_STATE["enabled"],
        "last_status": _AUTONOMOUS_STATE["last_status"],
        "last_message": _AUTONOMOUS_STATE["last_message"],
        "last_run_at": _AUTONOMOUS_STATE["last_run_at"],
        "updated_at": _AUTONOMOUS_STATE["updated_at"],
        "engine_status": engine_status,
    }
