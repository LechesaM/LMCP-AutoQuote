from __future__ import annotations

import importlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.runtime_paths import get_runtime_paths
from app.services.submission_retry_service import retry_failed_submissions

logger = logging.getLogger(__name__)

_RUNTIME_DIR = get_runtime_paths().runtime_root
_SCHEDULER_DIR = _RUNTIME_DIR / "submission_scheduler"
_LAST_RUN_FILE = _SCHEDULER_DIR / "last_run.json"

DEFAULT_LOOP_LIMIT = int(str(os.getenv("AUTONOMOUS_SUBMISSION_LOOP_LIMIT", "10")).strip() or "10")
AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED = (
    str(os.getenv("AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED", "false")).strip().lower() == "true"
)
AUTONOMOUS_PENDING_STAGE_ENABLED = (
    str(os.getenv("AUTONOMOUS_PENDING_STAGE_ENABLED", "true")).strip().lower() == "true"
)
AUTONOMOUS_PENDING_STAGE_HOOK = str(os.getenv("AUTONOMOUS_PENDING_STAGE_HOOK", "")).strip()

CANDIDATE_PENDING_STAGE_HOOKS: List[str] = [
    hook
    for hook in [
        AUTONOMOUS_PENDING_STAGE_HOOK,
        "app.services.tender_submission_pipeline:process_pending_submissions",
        "app.services.tender_submission_pipeline:run_pending_submission_stage",
        "app.services.tender_pipeline:run_pending_submission_stage",
        "app.services.tender_pipeline:run_pending_submission_stage",
        "app.services.autonomous_engine:process_pending_submissions",
        "app.services.autonomous_engine:run_pending_submission_stage",
    ]
    if hook
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(_RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


def _scheduler_dir(runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return _SCHEDULER_DIR
    return _resolve_runtime_path(_SCHEDULER_DIR, runtime_dir)


def _ensure_scheduler_dir(runtime_dir: Optional[str] = None) -> None:
    _scheduler_dir(runtime_dir).mkdir(parents=True, exist_ok=True)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _write_last_run(payload: Dict[str, Any], runtime_dir: Optional[str] = None) -> None:
    try:
        last_run_file = _resolve_runtime_path(_LAST_RUN_FILE, runtime_dir)
        _ensure_scheduler_dir(runtime_dir)
        last_run_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to write submission scheduler last-run file: %s", exc)


def get_last_autonomous_submission_loop_run(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    last_run_file = _resolve_runtime_path(_LAST_RUN_FILE, runtime_dir)
    try:
        if not last_run_file.exists():
            return {
                "status": "not_found",
                "checked_at": _utc_now_iso(),
                "last_run_file": str(last_run_file),
                "message": "No autonomous submission loop run has been recorded yet.",
            }

        raw = last_run_file.read_text(encoding="utf-8").strip()
        if not raw:
            return {
                "status": "not_found",
                "checked_at": _utc_now_iso(),
                "last_run_file": str(last_run_file),
                "message": "Autonomous submission loop last-run file is empty.",
            }

        data = json.loads(raw)
        if not isinstance(data, dict):
            return {
                "status": "invalid",
                "checked_at": _utc_now_iso(),
                "last_run_file": str(last_run_file),
                "message": "Autonomous submission loop last-run file does not contain an object.",
            }

        return data
    except Exception as exc:
        return {
            "status": "error",
            "checked_at": _utc_now_iso(),
            "last_run_file": str(last_run_file),
            "message": f"Failed to read autonomous submission loop last-run file: {exc}",
        }


def get_autonomous_submission_loop_health(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    last_run_file = _resolve_runtime_path(_LAST_RUN_FILE, runtime_dir)
    return {
        "status": "ok",
        "checked_at": _utc_now_iso(),
        "autonomous_submission_scheduler_enabled": AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED,
        "autonomous_pending_stage_enabled": AUTONOMOUS_PENDING_STAGE_ENABLED,
        "default_loop_limit": DEFAULT_LOOP_LIMIT,
        "last_run_file": str(last_run_file),
        "candidate_pending_stage_hooks": CANDIDATE_PENDING_STAGE_HOOKS,
    }


def _resolve_callable_from_hook(hook: str) -> Optional[Callable[..., Any]]:
    hook = str(hook or "").strip()
    if not hook or ":" not in hook:
        return None

    module_name, function_name = hook.split(":", 1)
    module_name = module_name.strip()
    function_name = function_name.strip()

    if not module_name or not function_name:
        return None

    try:
        module = importlib.import_module(module_name)
        fn = getattr(module, function_name, None)
        if callable(fn):
            return fn
    except Exception as exc:
        logger.info("Pending submission hook unavailable: %s | %s", hook, exc)

    return None


def _find_pending_stage_callable() -> Tuple[Optional[Callable[..., Any]], str]:
    for hook in CANDIDATE_PENDING_STAGE_HOOKS:
        fn = _resolve_callable_from_hook(hook)
        if fn is not None:
            return fn, hook
    return None, ""


def run_retry_stage(limit: int) -> Dict[str, Any]:
    result = retry_failed_submissions(limit=limit)
    if not isinstance(result, dict):
        return {
            "status": "failed",
            "stage": "retry",
            "message": "Retry stage returned unexpected response.",
            "total_retried": 0,
            "retried": [],
            "skipped": [],
        }

    return {
        "status": "ok",
        "stage": "retry",
        **result,
    }


def run_pending_submission_stage(limit: int) -> Dict[str, Any]:
    if not AUTONOMOUS_PENDING_STAGE_ENABLED:
        return {
            "status": "disabled",
            "stage": "pending_submission",
            "message": "Pending submission stage disabled by environment flag.",
            "processed": 0,
            "items": [],
            "hook": "",
        }

    fn, hook = _find_pending_stage_callable()
    if fn is None:
        return {
            "status": "not_configured",
            "stage": "pending_submission",
            "message": "No pending submission stage hook is currently available.",
            "processed": 0,
            "items": [],
            "hook": "",
        }

    try:
        result = fn(limit=limit)
    except TypeError:
        result = fn()

    if isinstance(result, dict):
        processed = _safe_int(result.get("processed"), 0)
        if processed <= 0:
            processed = _safe_int(result.get("total_processed"), 0)
        if processed <= 0 and isinstance(result.get("items"), list):
            processed = len(result.get("items"))

        return {
            "status": str(result.get("status") or "ok"),
            "stage": "pending_submission",
            "hook": hook,
            "processed": processed,
            **result,
        }

    if isinstance(result, list):
        return {
            "status": "ok",
            "stage": "pending_submission",
            "hook": hook,
            "processed": len(result),
            "items": result,
        }

    return {
        "status": "ok",
        "stage": "pending_submission",
        "hook": hook,
        "processed": 0,
        "items": [],
        "message": "Pending submission hook executed but returned no structured payload.",
    }


def run_autonomous_submission_loop(limit: int | None = None, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    safe_limit = max(1, _safe_int(limit, DEFAULT_LOOP_LIMIT))

    if not AUTONOMOUS_SUBMISSION_SCHEDULER_ENABLED:
        payload = {
            "status": "disabled",
            "checked_at": _utc_now_iso(),
            "scheduler": "autonomous_submission_loop",
            "message": "Autonomous submission scheduler is disabled by environment flag.",
            "limit": safe_limit,
            "retry_stage": {
                "status": "disabled",
                "stage": "retry",
                "total_retried": 0,
                "retried": [],
                "skipped": [],
            },
            "pending_submission_stage": {
                "status": "disabled",
                "stage": "pending_submission",
                "processed": 0,
                "items": [],
            },
            "total_processed": 0,
            "last_run_file": str(_resolve_runtime_path(_LAST_RUN_FILE, runtime_dir)),
        }
        _write_last_run(payload, runtime_dir=runtime_dir)
        return payload

    logger.info("Running autonomous submission loop | limit=%s", safe_limit)

    retry_stage = run_retry_stage(limit=safe_limit)
    pending_stage = run_pending_submission_stage(limit=safe_limit)

    total_processed = _safe_int(retry_stage.get("total_retried"), 0) + _safe_int(
        pending_stage.get("processed") or pending_stage.get("total_processed"), 0
    )

    payload = {
        "status": "ok",
        "checked_at": _utc_now_iso(),
        "scheduler": "autonomous_submission_loop",
        "limit": safe_limit,
        "retry_stage": _safe_dict(retry_stage),
        "pending_submission_stage": _safe_dict(pending_stage),
        "total_processed": total_processed,
        "last_run_file": str(_LAST_RUN_FILE),
    }
    _write_last_run(payload, runtime_dir=runtime_dir)
    return payload
