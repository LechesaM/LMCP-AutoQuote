from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.tender_harvester import (
    HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE,
    HARVEST_MINIMUM_AI_SCORE,
    DEFAULT_MINIMUM_MARGIN_PCT,
    DEFAULT_MINIMUM_PROFIT,
    HARVEST_RUNS_DIR,
    run_national_tender_radar,
)
from app.services.harvest_source_registry_service import get_curated_live_source_file

logger = logging.getLogger(__name__)

HARVEST_SCHEDULER_DIR = HARVEST_RUNS_DIR / "scheduled"
HARVEST_SCHEDULER_DIR.mkdir(parents=True, exist_ok=True)
SMOKE_SOURCE_FILE_SUFFIX = "smoke_harvest_sources.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _safe_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")


def _load_summary_file(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    data.setdefault("summary_path", str(path))
    data.setdefault("run_dir", str(path.parent))
    controlled_mode = bool(data.get("controlled_mode"))
    persist_to_live_store = bool(data.get("persist_to_live_store"))
    data.setdefault("run_mode", "controlled" if controlled_mode else "live")
    data.setdefault("mutating", bool(persist_to_live_store))
    return _normalize_manual_quote_ready_projection(data)


def _load_cycle_summary_file(path: Path) -> Dict[str, Any]:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return {}
        data = json.loads(lines[-1])
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    summary = data.get("summary")
    if not isinstance(summary, dict):
        return {}

    cycle_summary = dict(summary)
    cycle_summary.setdefault("summary_path", str(path))
    cycle_summary.setdefault("cycles_log_path", str(path))
    cycle_summary.setdefault("run_dir", str(path.parent))
    cycle_summary.setdefault("run_id", path.parent.name)
    cycle_summary.setdefault("completed_at", data.get("completed_at"))
    cycle_summary.setdefault("started_at", data.get("cycle_started_at"))
    controlled_mode = bool(cycle_summary.get("controlled_mode"))
    persist_to_live_store = bool(cycle_summary.get("persist_to_live_store"))
    cycle_summary.setdefault("run_mode", "controlled" if controlled_mode else "live")
    cycle_summary.setdefault("mutating", bool(persist_to_live_store))
    return _normalize_manual_quote_ready_projection(cycle_summary)


def _artifact_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _pick_newest_artifact(run_dir: Path) -> Optional[Dict[str, Any]]:
    summary_path = run_dir / "summary.json"
    cycles_path = run_dir / "cycles.jsonl"

    summary_mtime = _artifact_mtime(summary_path)
    cycles_mtime = _artifact_mtime(cycles_path)

    if summary_mtime <= 0.0 and cycles_mtime <= 0.0:
        return None

    if summary_mtime >= cycles_mtime and summary_mtime > 0.0:
        summary = _load_summary_file(summary_path)
        if summary:
            summary.setdefault("_artifact_mtime", summary_mtime)
            summary.setdefault("_artifact_path", str(summary_path))
            return summary

    if cycles_mtime > 0.0:
        summary = _load_cycle_summary_file(cycles_path)
        if summary:
            summary.setdefault("_artifact_mtime", cycles_mtime)
            summary.setdefault("_artifact_path", str(cycles_path))
            return summary

    if summary_mtime > 0.0:
        summary = _load_summary_file(summary_path)
        if summary:
            summary.setdefault("_artifact_mtime", summary_mtime)
            summary.setdefault("_artifact_path", str(summary_path))
            return summary

    return None


def _strip_internal_fields(summary: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(summary)
    cleaned.pop("_artifact_mtime", None)
    cleaned.pop("_artifact_path", None)
    return cleaned


def _is_manual_quote_ready_visible(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    if not bool(item.get("eligible")):
        return False
    pipeline_status = str(item.get("pipeline_status") or "").strip().lower()
    quantity_status = str(item.get("quantity_safety_status") or "").strip().lower()
    return (
        bool(item.get("quote_ready"))
        or pipeline_status == "quantity_verification_required"
        or quantity_status == "quantity_verification_required"
        or bool(item.get("requires_quantity_verification"))
    )


def _normalize_manual_quote_ready_projection(result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result

    projected = dict(result)
    projected_items = []
    for raw_item in _safe_list(projected.get("items") or []):
        item = dict(raw_item)
        if _is_manual_quote_ready_visible(item):
            item["quote_ready"] = True
        projected_items.append(item)
    if projected_items:
        projected["items"] = projected_items

    live_store_result = projected.get("live_store_result")
    if isinstance(live_store_result, dict):
        projected_live_store = dict(live_store_result)
        projected_live_items = []
        for raw_item in _safe_list(projected_live_store.get("items") or []):
            item = dict(raw_item)
            if _is_manual_quote_ready_visible(item):
                item["quote_ready"] = True
            projected_live_items.append(item)
        if projected_live_items:
            projected_live_store["items"] = projected_live_items
            projected_live_store["count"] = len(projected_live_items)
        projected["live_store_result"] = projected_live_store

    projected_item_rows = _safe_list(projected.get("items") or [])
    if projected_item_rows:
        projected["quote_ready_total"] = sum(1 for item in projected_item_rows if _is_manual_quote_ready_visible(item))
        return projected

    projected_live_store_rows = _safe_list((projected.get("live_store_result") or {}).get("items") or [])
    if projected_live_store_rows:
        projected["quote_ready_total"] = sum(1 for item in projected_live_store_rows if _is_manual_quote_ready_visible(item))
        return projected

    projected["quote_ready_total"] = int(projected.get("quote_ready_total") or 0)
    return projected


def _is_smoke_summary(summary: Dict[str, Any]) -> bool:
    if bool(summary.get("controlled_mode")):
        return True
    source_file = str(summary.get("source_file") or "")
    if source_file.endswith(SMOKE_SOURCE_FILE_SUFFIX):
        return True
    run_id = str(summary.get("run_id") or "")
    return "smoke" in run_id.lower()


def get_latest_scheduled_harvest_summaries(runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    scheduled_root = Path(runtime_dir).expanduser().resolve() / "harvest_runs" / "scheduled" if runtime_dir else HARVEST_SCHEDULER_DIR
    run_dirs = [run_dir for run_dir in scheduled_root.iterdir() if run_dir.is_dir()]

    def _run_dir_mtime(run_dir: Path) -> float:
        return max(
            _artifact_mtime(run_dir),
            _artifact_mtime(run_dir / "summary.json"),
            _artifact_mtime(run_dir / "cycles.jsonl"),
        )

    run_dirs.sort(key=_run_dir_mtime, reverse=True)

    latest_any_raw: Dict[str, Any] = {}
    latest_smoke_raw: Dict[str, Any] = {}
    latest_regular_raw: Dict[str, Any] = {}

    for run_dir in run_dirs:
        summary = _pick_newest_artifact(run_dir)
        if not summary:
            continue

        if not latest_any_raw:
            latest_any_raw = summary

        if not latest_smoke_raw and _is_smoke_summary(summary):
            latest_smoke_raw = summary

        if not latest_regular_raw and not _is_smoke_summary(summary):
            latest_regular_raw = summary

        if latest_any_raw and latest_smoke_raw and latest_regular_raw:
            break

    return {
        "status": "ok",
        "latest_any": _strip_internal_fields(latest_any_raw),
        "latest_smoke": _strip_internal_fields(latest_smoke_raw),
        "latest_regular": _strip_internal_fields(latest_regular_raw),
        "run_count": len(run_dirs),
        "scheduled_runs_dir": str(scheduled_root),
    }


def run_scheduled_tender_harvest(
    duration_minutes: int = 60,
    sleep_seconds: int = 600,
    max_total: int = 20,
    max_per_source: int = 3,
    max_sources_per_cycle: int = 10,
    headless: bool = True,
    include_bad_sources: bool = False,
    source_file: Optional[str] = None,
    enable_auto_quote: bool = False,
    true_autonomous: bool = False,
    persist_to_live_store: bool = True,
    minimum_margin_pct: float = DEFAULT_MINIMUM_MARGIN_PCT,
    minimum_profit: float = DEFAULT_MINIMUM_PROFIT,
    controlled_mode: bool = False,
    runtime_dir: Optional[str] = None,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
) -> Dict[str, Any]:
    if source_file is None and not controlled_mode:
        source_file = get_curated_live_source_file()

    safe_duration_minutes = max(1, _safe_int(duration_minutes, 60))
    safe_sleep_seconds = max(1, _safe_int(sleep_seconds, 600))
    deadline = time.monotonic() + (safe_duration_minutes * 60)
    run_id = datetime.now(timezone.utc).strftime("scheduled_harvest_%Y%m%dT%H%M%SZ")
    if controlled_mode and persist_to_live_store:
        raise ValueError("controlled_mode requires persist_to_live_store=False")
    if controlled_mode and not source_file:
        raise ValueError("controlled_mode requires a bundled fixture source_file")

    scheduled_root = Path(runtime_dir).expanduser().resolve() / "harvest_runs" / "scheduled" if runtime_dir else HARVEST_SCHEDULER_DIR
    run_dir = scheduled_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cycles_log_path = run_dir / "cycles.jsonl"
    summary_path = run_dir / "summary.json"

    started_at = _utc_now_iso()
    cycle_summaries: List[Dict[str, Any]] = []
    cycles_completed = 0
    stop_reason = "duration_elapsed"

    while True:
        cycle_started_at = _utc_now_iso()
        result = run_national_tender_radar(
            max_total=max_total,
            max_per_source=max_per_source,
            enable_auto_quote=enable_auto_quote,
            persist_to_live_store=persist_to_live_store,
            headless=headless,
            minimum_margin_pct=minimum_margin_pct,
            minimum_profit=minimum_profit,
            source_file=source_file,
            max_sources_per_cycle=max_sources_per_cycle,
            true_autonomous=true_autonomous,
            include_bad_sources=include_bad_sources,
            controlled_mode=controlled_mode,
            source_timeout_seconds=source_timeout_seconds,
            playwright_timeout_ms=playwright_timeout_ms,
            run_id=run_id,
        )

        result = _normalize_manual_quote_ready_projection(result)

        cycle_record = {
            "cycle": cycles_completed + 1,
            "cycle_started_at": cycle_started_at,
            "completed_at": _utc_now_iso(),
            "summary": {
                "status": result.get("status"),
                "run_started_at": result.get("run_started_at"),
                "source_file": source_file,
                "controlled_mode": controlled_mode,
                "run_mode": "controlled" if controlled_mode else "live",
                "mutating": bool(persist_to_live_store),
                "source_count": result.get("source_count"),
                "selected_source_count": result.get("selected_source_count"),
                "harvested_total": result.get("harvested_total"),
                "blocked_total": result.get("blocked_total"),
                "screened_out_total": result.get("screened_out_total"),
                "eligible_total": result.get("eligible_total"),
                "quote_ready_total": result.get("quote_ready_total"),
                "persist_to_live_store": result.get("persist_to_live_store"),
                "live_store_result": result.get("live_store_result"),
                "minimum_ai_score": result.get("minimum_ai_score"),
                "minimum_auto_submit_ai_score": result.get("minimum_auto_submit_ai_score"),
                "source_timeout_seconds": result.get("source_timeout_seconds"),
                "playwright_timeout_ms": result.get("playwright_timeout_ms"),
                "screened_out_rejection_counts_by_reason": result.get("screened_out_rejection_counts_by_reason"),
                "blocked_rejection_counts_by_reason": result.get("blocked_rejection_counts_by_reason"),
                "source_health_overview": result.get("source_health_overview"),
                "source_runs": result.get("source_runs"),
            },
        }
        _append_jsonl(cycles_log_path, cycle_record)
        cycle_summaries.append(cycle_record)
        cycles_completed += 1

        if result.get("status") != "ok":
            stop_reason = "cycle_failed"
            break

        if time.monotonic() >= deadline:
            break

        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            break

        time.sleep(min(safe_sleep_seconds, max(1, remaining)))

    completed_at = _utc_now_iso()
    summary = {
        "status": "ok" if stop_reason == "duration_elapsed" else "failed",
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_minutes": safe_duration_minutes,
        "sleep_seconds": safe_sleep_seconds,
        "source_file": source_file,
        "controlled_mode": controlled_mode,
        "run_mode": "controlled" if controlled_mode else "live",
        "mutating": bool(persist_to_live_store),
        "persist_to_live_store": persist_to_live_store,
        "minimum_ai_score": HARVEST_MINIMUM_AI_SCORE,
        "minimum_auto_submit_ai_score": HARVEST_AUTO_SUBMIT_MINIMUM_AI_SCORE,
        "source_timeout_seconds": source_timeout_seconds,
        "playwright_timeout_ms": playwright_timeout_ms,
        "cycles_completed": cycles_completed,
        "stop_reason": stop_reason,
        "cycles": cycle_summaries,
        "source_health_overview": cycle_summaries[-1]["summary"].get("source_health_overview") if cycle_summaries else {},
        "cycles_log_path": str(cycles_log_path),
        "summary_path": str(summary_path),
    }
    _write_json(summary_path, summary)
    logger.info(
        "Scheduled tender harvest finished | run_id=%s | cycles=%s | stop_reason=%s",
        run_id,
        cycles_completed,
        stop_reason,
    )
    return summary
