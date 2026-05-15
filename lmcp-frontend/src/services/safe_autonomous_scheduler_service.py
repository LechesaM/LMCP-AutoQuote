from __future__ import annotations

import asyncio
import inspect
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "runtime"))
SCHEDULER_DIR = RUNTIME_DIR / "safe_autonomous_scheduler"
SCHEDULER_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = SCHEDULER_DIR / "state.json"
HISTORY_FILE = SCHEDULER_DIR / "history.json"
LAST_RUN_FILE = SCHEDULER_DIR / "last_run.json"

DEFAULT_INTERVAL_SECONDS = int(os.getenv("LMCP_SAFE_SCHEDULER_INTERVAL_SECONDS", "21600"))
DEFAULT_MAX_TOTAL = int(os.getenv("LMCP_SAFE_SCHEDULER_MAX_TOTAL", "10"))
DEFAULT_MAX_SUBMISSIONS = int(os.getenv("LMCP_SAFE_SCHEDULER_MAX_SUBMISSIONS", "3"))
DEFAULT_ENABLE_SUBMIT = os.getenv("LMCP_SAFE_SCHEDULER_ENABLE_SUBMIT", "false").lower() in {"1", "true", "yes", "on"}

_scheduler_task: Optional[asyncio.Task] = None
_scheduler_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _append_history(item: Dict[str, Any]) -> None:
    history = _read_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    history.append(item)
    _write_json(HISTORY_FILE, history[-500:])


def _default_state() -> Dict[str, Any]:
    return {
        "enabled": False,
        "mode": "safe_controlled",
        "interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "max_total": DEFAULT_MAX_TOTAL,
        "max_submissions": DEFAULT_MAX_SUBMISSIONS,
        "enable_submit": DEFAULT_ENABLE_SUBMIT,
        "require_production_lock": True,
        "last_started_at": None,
        "last_finished_at": None,
        "last_status": "idle",
        "last_message": "Safe scheduler installed but not running.",
        "updated_at": _now(),
    }


def get_scheduler_state() -> Dict[str, Any]:
    state = _read_json(STATE_FILE, None)
    if not isinstance(state, dict):
        state = _default_state()
        _write_json(STATE_FILE, state)
    return state


def update_scheduler_state(updates: Dict[str, Any]) -> Dict[str, Any]:
    state = get_scheduler_state()
    allowed = {
        "enabled",
        "mode",
        "interval_seconds",
        "max_total",
        "max_submissions",
        "enable_submit",
        "require_production_lock",
    }
    for key, value in (updates or {}).items():
        if key in allowed:
            state[key] = value
    state["updated_at"] = _now()
    _write_json(STATE_FILE, state)
    return state


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _normalise_tenders(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        for key in ["tenders", "opportunities", "items", "results", "data"]:
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            return [raw]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


async def _safe_harvest(max_total: int) -> Dict[str, Any]:
    try:
        from app.services.tender_harvester import run_national_tender_radar
    except Exception as exc:
        return {"status": "error", "message": "Could not import tender harvester.", "error": str(exc), "tenders": []}

    attempts = [
        {"max_total": max_total, "max_per_source": 1, "enable_auto_quote": False, "persist_to_live_store": True},
        {"max_total": max_total, "enable_auto_quote": False},
        {"max_total": max_total},
    ]

    errors: List[str] = []
    for kwargs in attempts:
        try:
            result = await _maybe_await(run_national_tender_radar(**kwargs))
            tenders = _normalise_tenders(result)
            return {"status": "ok", "method": "run_national_tender_radar", "kwargs": kwargs, "count": len(tenders), "tenders": tenders[:max_total]}
        except TypeError as exc:
            errors.append(str(exc))
            continue
        except Exception as exc:
            return {"status": "error", "message": "Harvester failed during safe scheduler cycle.", "error": str(exc), "errors": errors, "tenders": []}

    return {"status": "error", "message": "No compatible tender_harvester signature worked.", "errors": errors, "tenders": []}


def _inject_existing_pricing_fields(tender: Dict[str, Any]) -> Dict[str, Any]:
    tender = dict(tender or {})
    pricing = tender.get("pricing") or tender.get("pricing_summary") or {}
    if isinstance(pricing, dict):
        if "estimated_profit" not in tender and pricing.get("total_profit") is not None:
            tender["estimated_profit"] = pricing.get("total_profit")
        if "estimated_margin_percent" not in tender and pricing.get("achieved_margin_percent") is not None:
            tender["estimated_margin_percent"] = pricing.get("achieved_margin_percent")
    return tender


async def _production_check(tender: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from app.services.production_lock_service import assert_production_submission_allowed
        return assert_production_submission_allowed(tender)
    except Exception as exc:
        return {"status": "blocked", "allowed": False, "submission_status": "blocked_by_production_lock_error", "message": "Production Lock failed closed.", "error": str(exc)}


async def _submit_if_allowed(tender: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from app.services.portal_submission_service import auto_submit_portal
    except Exception as exc:
        return {"status": "error", "submitted": False, "submission_status": "portal_submit_import_error", "message": "Could not import auto_submit_portal.", "error": str(exc)}
    try:
        result = auto_submit_portal(tender)
        result = await _maybe_await(result)
        return result if isinstance(result, dict) else {"status": "unknown", "submitted": False, "raw_result": str(result)}
    except Exception as exc:
        return {"status": "error", "submitted": False, "submission_status": "portal_submit_error", "message": "Portal submission failed.", "error": str(exc)}


async def run_safe_autonomous_cycle(
    max_total: Optional[int] = None,
    max_submissions: Optional[int] = None,
    enable_submit: Optional[bool] = None,
    reason: str = "manual",
) -> Dict[str, Any]:
    async with _scheduler_lock:
        state = get_scheduler_state()
        max_total = int(max_total if max_total is not None else state.get("max_total", DEFAULT_MAX_TOTAL))
        max_submissions = int(max_submissions if max_submissions is not None else state.get("max_submissions", DEFAULT_MAX_SUBMISSIONS))
        enable_submit = bool(enable_submit if enable_submit is not None else state.get("enable_submit", DEFAULT_ENABLE_SUBMIT))

        run = {
            "status": "running",
            "service_version": "LMCP_SAFE_AUTONOMOUS_SCHEDULER_V1",
            "reason": reason,
            "started_at": _now(),
            "finished_at": None,
            "settings": {"max_total": max_total, "max_submissions": max_submissions, "enable_submit": enable_submit},
            "harvest": {},
            "summary": {"harvested": 0, "allowed": 0, "blocked": 0, "submitted": 0, "failed": 0, "skipped_submit_disabled": 0},
            "items": [],
        }

        state["last_status"] = "running"
        state["last_started_at"] = run["started_at"]
        state["last_message"] = "Safe autonomous cycle running."
        state["updated_at"] = _now()
        _write_json(STATE_FILE, state)

        try:
            harvest = await _safe_harvest(max_total=max_total)
            run["harvest"] = {k: v for k, v in harvest.items() if k != "tenders"}
            tenders = harvest.get("tenders", [])
            run["summary"]["harvested"] = len(tenders)
            submissions_used = 0

            for tender in tenders[:max_total]:
                tender = _inject_existing_pricing_fields(tender)
                rfq = tender.get("buyer_rfq_number") or tender.get("rfq_number") or tender.get("reference_number") or tender.get("title") or "UNKNOWN"
                item = {"buyer_rfq_number": rfq, "title": tender.get("title"), "checked_at": _now(), "production_decision": None, "submission_result": None}

                decision = await _production_check(tender)
                item["production_decision"] = decision

                if not decision.get("allowed"):
                    run["summary"]["blocked"] += 1
                    item["final_status"] = "blocked_by_production_lock"
                    run["items"].append(item)
                    continue

                run["summary"]["allowed"] += 1

                if not enable_submit:
                    run["summary"]["skipped_submit_disabled"] += 1
                    item["final_status"] = "allowed_submit_disabled"
                    run["items"].append(item)
                    continue

                if submissions_used >= max_submissions:
                    item["final_status"] = "allowed_submission_limit_reached"
                    run["items"].append(item)
                    continue

                submit_result = await _submit_if_allowed(tender)
                item["submission_result"] = submit_result

                if submit_result.get("submitted") is True:
                    run["summary"]["submitted"] += 1
                    item["final_status"] = "submitted"
                else:
                    run["summary"]["failed"] += 1
                    item["final_status"] = submit_result.get("submission_status") or submit_result.get("status") or "submission_failed"

                submissions_used += 1
                run["items"].append(item)

            run["status"] = "ok"
            run["finished_at"] = _now()
            run["message"] = "Safe autonomous cycle completed."
        except Exception as exc:
            run["status"] = "error"
            run["finished_at"] = _now()
            run["message"] = "Safe autonomous cycle failed."
            run["error"] = str(exc)

        _write_json(LAST_RUN_FILE, run)
        _append_history(run)

        state = get_scheduler_state()
        state["last_status"] = run["status"]
        state["last_finished_at"] = run["finished_at"]
        state["last_message"] = run.get("message")
        state["updated_at"] = _now()
        _write_json(STATE_FILE, state)

        return run


async def start_safe_scheduler_loop() -> None:
    while True:
        state = get_scheduler_state()
        interval = int(state.get("interval_seconds", DEFAULT_INTERVAL_SECONDS))
        if state.get("enabled") is True:
            await run_safe_autonomous_cycle(reason="scheduled")
        await asyncio.sleep(max(interval, 300))


def start_background_scheduler() -> Dict[str, Any]:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return {"status": "ok", "message": "Safe scheduler loop already running."}
    try:
        loop = asyncio.get_running_loop()
        _scheduler_task = loop.create_task(start_safe_scheduler_loop())
        return {"status": "ok", "message": "Safe scheduler loop started."}
    except RuntimeError:
        return {"status": "error", "message": "No running event loop available."}


def get_safe_scheduler_status(limit: int = 20) -> Dict[str, Any]:
    history = _read_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    return {
        "status": "ok",
        "service_version": "LMCP_SAFE_AUTONOMOUS_SCHEDULER_V1",
        "state": get_scheduler_state(),
        "last_run": _read_json(LAST_RUN_FILE, {}),
        "recent_runs": history[-limit:],
        "background_loop_running": bool(_scheduler_task and not _scheduler_task.done()),
        "files": {"state": str(STATE_FILE), "history": str(HISTORY_FILE), "last_run": str(LAST_RUN_FILE)},
        "updated_at": _now(),
    }


async def enable_safe_scheduler() -> Dict[str, Any]:
    state = update_scheduler_state({"enabled": True})
    loop_result = start_background_scheduler()
    return {"status": "ok", "state": state, "loop": loop_result}


def disable_safe_scheduler() -> Dict[str, Any]:
    state = update_scheduler_state({"enabled": False})
    return {"status": "ok", "state": state, "message": "Safe scheduler disabled."}
