from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.system_state_service import get_block_reason, get_system_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autonomous", tags=["Autonomous"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


AUTONOMOUS_STATE: Dict[str, Any] = {
    "enabled": False,
    "last_run_at": None,
    "last_status": "idle",
    "last_message": "System not yet run",
    "last_result": None,
}


class AutonomousRunResponse(BaseModel):
    status: str = Field(..., description="Run status")
    message: str = Field(..., description="Human-readable result")
    triggered_at: str = Field(..., description="UTC timestamp")
    task_name: str = Field(..., description="Triggered task name")
    task_id: Optional[str] = Field(default=None, description="Celery task id if available")
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Immediate task result if executed inline",
    )


class AutonomousStatusResponse(BaseModel):
    enabled: bool
    last_run_at: Optional[str]
    last_status: str
    last_message: str
    updated_at: str
    last_result: Optional[Dict[str, Any]] = None


def _build_harvest_run_result(
    max_total: int,
    max_per_source: int,
    enable_auto_quote: bool,
    persist_to_live_store: bool,
) -> Dict[str, Any]:
    """
    Executes one autonomous harvest + auto-quote run inline.
    """
    from app.services.tender_harvester import run_national_tender_radar

    result = run_national_tender_radar(
        max_total=max_total,
        max_per_source=max_per_source,
        enable_auto_quote=enable_auto_quote,
        persist_to_live_store=persist_to_live_store,
    )

    if not isinstance(result, dict):
        return {
            "status": "failed",
            "message": "Tender radar returned a non-dict result",
            "result_type": type(result).__name__,
        }

    return result


@router.get("/status", response_model=AutonomousStatusResponse)
def get_autonomous_status() -> AutonomousStatusResponse:
    return AutonomousStatusResponse(
        enabled=bool(AUTONOMOUS_STATE.get("enabled", True)),
        last_run_at=AUTONOMOUS_STATE.get("last_run_at"),
        last_status=str(AUTONOMOUS_STATE.get("last_status", "unknown")),
        last_message=str(AUTONOMOUS_STATE.get("last_message", "")),
        updated_at=_now_iso(),
        last_result=AUTONOMOUS_STATE.get("last_result"),
    )


@router.post("/enable", response_model=AutonomousStatusResponse)
def enable_autonomous() -> AutonomousStatusResponse:
    AUTONOMOUS_STATE["enabled"] = True
    AUTONOMOUS_STATE["last_status"] = "ready"
    AUTONOMOUS_STATE["last_message"] = "Autonomous mode enabled"

    return AutonomousStatusResponse(
        enabled=True,
        last_run_at=AUTONOMOUS_STATE.get("last_run_at"),
        last_status=AUTONOMOUS_STATE["last_status"],
        last_message=AUTONOMOUS_STATE["last_message"],
        updated_at=_now_iso(),
        last_result=AUTONOMOUS_STATE.get("last_result"),
    )


@router.post("/disable", response_model=AutonomousStatusResponse)
def disable_autonomous() -> AutonomousStatusResponse:
    AUTONOMOUS_STATE["enabled"] = False
    AUTONOMOUS_STATE["last_status"] = "disabled"
    AUTONOMOUS_STATE["last_message"] = "Autonomous mode disabled"

    return AutonomousStatusResponse(
        enabled=False,
        last_run_at=AUTONOMOUS_STATE.get("last_run_at"),
        last_status=AUTONOMOUS_STATE["last_status"],
        last_message=AUTONOMOUS_STATE["last_message"],
        updated_at=_now_iso(),
        last_result=AUTONOMOUS_STATE.get("last_result"),
    )


@router.post("/run-once", response_model=AutonomousRunResponse)
def run_autonomous_once(
    max_total: int = Query(default=300, ge=1, le=5000),
    max_per_source: int = Query(default=25, ge=1, le=500),
    enable_auto_quote: bool = Query(default=True),
    persist_to_live_store: bool = Query(default=True),
) -> AutonomousRunResponse:
    """
    Runs one autonomous cycle immediately.

    Current behavior:
    - Honors autonomous enabled/disabled state
    - Tries Celery async task first if available
    - Falls back to inline harvest + auto-quote execution
    - Updates AUTONOMOUS_STATE in all cases
    """
    triggered_at = _now_iso()

    # Channel 1 control-layer gate: stop BEFORE Celery dispatch or harvest.
    system_state = get_system_state()
    block_reason = get_block_reason("system")
    if block_reason:
        AUTONOMOUS_STATE["last_run_at"] = triggered_at
        AUTONOMOUS_STATE["last_status"] = "blocked"
        AUTONOMOUS_STATE["last_message"] = f"Autonomous blocked: {block_reason}"
        AUTONOMOUS_STATE["last_result"] = {
            "status": "skipped",
            "reason": block_reason,
            "system_state": system_state,
        }

        return AutonomousRunResponse(
            status="skipped",
            message=f"Autonomous blocked by system control: {block_reason}",
            triggered_at=triggered_at,
            task_name="run_autonomous_cycle",
            task_id=None,
            result={
                "status": "skipped",
                "reason": block_reason,
                "system_state": system_state,
            },
        )


    if not AUTONOMOUS_STATE.get("enabled", True):
        AUTONOMOUS_STATE["last_run_at"] = triggered_at
        AUTONOMOUS_STATE["last_status"] = "blocked"
        AUTONOMOUS_STATE["last_message"] = "Autonomous mode is disabled"

        return AutonomousRunResponse(
            status="blocked",
            message="Autonomous mode is disabled",
            triggered_at=triggered_at,
            task_name="run_national_tender_radar",
            task_id=None,
            result=None,
        )

    # ---------------------------------------------------------------------
    # Try Celery async dispatch first
    # ---------------------------------------------------------------------
    try:
        from app.tasks import run_autonomous_cycle  # type: ignore

        try:
            async_result = run_autonomous_cycle.delay()

            AUTONOMOUS_STATE["last_run_at"] = triggered_at
            AUTONOMOUS_STATE["last_status"] = "queued"
            AUTONOMOUS_STATE["last_message"] = "Autonomous cycle queued"
            AUTONOMOUS_STATE["last_result"] = {
                "task_id": async_result.id,
                "mode": "celery",
                "max_total": max_total,
                "max_per_source": max_per_source,
                "enable_auto_quote": enable_auto_quote,
                "persist_to_live_store": persist_to_live_store,
            }

            return AutonomousRunResponse(
                status="queued",
                message="Autonomous cycle queued",
                triggered_at=triggered_at,
                task_name="run_autonomous_cycle",
                task_id=async_result.id,
                result={
                    "mode": "celery",
                    "max_total": max_total,
                    "max_per_source": max_per_source,
                    "enable_auto_quote": enable_auto_quote,
                    "persist_to_live_store": persist_to_live_store,
                },
            )

        except Exception:
            logger.warning(
                "Celery async dispatch unavailable, falling back to inline execution.",
                exc_info=True,
            )

    except Exception:
        logger.info("Celery task import unavailable, using inline autonomous execution.")

    # ---------------------------------------------------------------------
    # Inline fallback: direct harvest + auto-quote run
    # ---------------------------------------------------------------------
    try:
        inline_result = _build_harvest_run_result(
            max_total=max_total,
            max_per_source=max_per_source,
            enable_auto_quote=enable_auto_quote,
            persist_to_live_store=persist_to_live_store,
        )

        inline_status = str(inline_result.get("status", "ok"))
        inline_message = str(
            inline_result.get("message", "Autonomous cycle completed inline")
        )

        AUTONOMOUS_STATE["last_run_at"] = triggered_at
        AUTONOMOUS_STATE["last_status"] = inline_status
        AUTONOMOUS_STATE["last_message"] = inline_message
        AUTONOMOUS_STATE["last_result"] = inline_result

        return AutonomousRunResponse(
            status=inline_status,
            message=inline_message,
            triggered_at=triggered_at,
            task_name="run_national_tender_radar",
            task_id=None,
            result=inline_result,
        )

    except Exception as exc:
        logger.exception("run_autonomous_once failed")

        AUTONOMOUS_STATE["last_run_at"] = triggered_at
        AUTONOMOUS_STATE["last_status"] = "failed"
        AUTONOMOUS_STATE["last_message"] = f"Autonomous cycle failed: {exc}"
        AUTONOMOUS_STATE["last_result"] = None

        return AutonomousRunResponse(
            status="failed",
            message=f"Autonomous cycle failed: {exc}",
            triggered_at=triggered_at,
            task_name="run_national_tender_radar",
            task_id=None,
            result=None,
        )


@router.get("/last-result")
def get_last_autonomous_result() -> Dict[str, Any]:
    return {
        "updated_at": _now_iso(),
        "enabled": AUTONOMOUS_STATE.get("enabled", True),
        "last_run_at": AUTONOMOUS_STATE.get("last_run_at"),
        "last_status": AUTONOMOUS_STATE.get("last_status"),
        "last_message": AUTONOMOUS_STATE.get("last_message"),
        "last_result": AUTONOMOUS_STATE.get("last_result"),
    }

