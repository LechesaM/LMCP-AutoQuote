from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List


RUNTIME_DIR = Path("runtime")
PILOT_RUN_DIR = RUNTIME_DIR / "manual_production"
PILOT_RUN_DIR.mkdir(parents=True, exist_ok=True)
PILOT_RUN_LOG_FILE = PILOT_RUN_DIR / "pilot_runs.jsonl"

_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def append_workspace_log_entry(
    workspace_root: str | Path,
    pilot_id: str,
    section: str,
    *,
    fields: Dict[str, Any] | None = None,
    notes: List[str] | None = None,
) -> str:
    root = Path(workspace_root).expanduser()
    log_path = root / _clean(pilot_id) / "submission_logs" / "live_run_log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"## {_clean(section) or 'Log'}", f"- Pilot ID: {_clean(pilot_id) or 'unknown'}"]
    for key, value in (fields or {}).items():
        if value is None:
            continue
        lines.append(f"- {_clean(key)}: {value}")
    for note in notes or []:
        text = _clean(note)
        if text:
            lines.append(f"- {text}")

    block = "\n".join(lines) + "\n\n"
    with _LOCK:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(block)
    return str(log_path)


def _quote_pack_quality_status(item: Dict[str, Any]) -> str:
    status = _clean(item.get("quote_pack_quality_status"))
    if status:
        return status

    if _clean(item.get("status")) == "blocked":
        return "blocked"

    if bool(item.get("quote_pack_generated")) and not bool(item.get("submission_pack_generated")):
        return "needs_pricing"

    return "unknown"


def append_pilot_run(record: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("timestamp", _now_iso())
    PILOT_RUN_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(item, ensure_ascii=False, default=str)
    with _LOCK:
        with PILOT_RUN_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return item


def list_recent_pilot_runs(limit: int = 20) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    if PILOT_RUN_LOG_FILE.exists():
        try:
            for line in PILOT_RUN_LOG_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
        except Exception:
            records = []
    recent = list(reversed(records[-max(1, int(limit or 20)) :]))
    return {
        "status": "ok",
        "items": recent,
        "total": len(records),
        "log_file": str(PILOT_RUN_LOG_FILE),
        "updated_at": _now_iso(),
    }


def build_pilot_run_record(result: Dict[str, Any]) -> Dict[str, Any]:
    classification = result.get("classification") if isinstance(result.get("classification"), dict) else {}
    form_plan = result.get("form_plan") if isinstance(result.get("form_plan"), dict) else {}
    submission_pack = result.get("submission_pack") if isinstance(result.get("submission_pack"), dict) else {}
    final_files = [str(item) for item in _safe_list(result.get("final_files")) if _clean(item)]
    warnings: List[str] = [str(item) for item in _safe_list(result.get("warnings")) if _clean(item)]
    if str(result.get("status") or "").strip() == "blocked":
        warnings.extend(str(item) for item in _safe_list(classification.get("reasons")) if _clean(item))
    pipeline_stages = _safe_list(result.get("pipeline_stages"))
    quote_pack_generated = result.get("quote_pack_generated")
    if quote_pack_generated is None:
        quote_pack_generated = any(path.endswith(".pdf") for path in final_files)
    submission_pack_generated = result.get("submission_pack_generated")
    if submission_pack_generated is None:
        submission_pack_generated = bool(submission_pack.get("submission_pack_ready_count", 0))
    return {
        "tender_id": _clean(result.get("tender_id")),
        "tender_root": _clean(result.get("tender_root")),
        "detected_category": _clean(classification.get("decision") or "unknown"),
        "excluded": not bool(classification.get("eligible", False)),
        "mandatory_forms_detected": [
            str(item.get("form_code"))
            for item in _safe_list(form_plan.get("required_forms"))
            if isinstance(item, dict) and _clean(item.get("form_code"))
        ],
        "quote_pack_generated": bool(quote_pack_generated),
        "submission_pack_generated": bool(submission_pack_generated),
        "quote_pack_quality_status": _clean(result.get("quote_pack_quality_status") or "unknown"),
        "approval_blocked": bool(result.get("approval_blocked", False)),
        "quote_pack_quality_reason": _clean(result.get("quote_pack_quality_reason")),
        "extracted_line_item_count": int(result.get("extracted_line_item_count", 0) or 0),
        "extracted_line_item_descriptions": _safe_list(result.get("extracted_line_item_descriptions")),
        "pricing_file_loaded": bool(result.get("pricing_file_loaded", False)),
        "pricing_file_item_count": int(result.get("pricing_file_item_count", 0) or 0),
        "pricing_items_matched": int(result.get("pricing_items_matched", 0) or 0),
        "pricing_items_unmatched": int(result.get("pricing_items_unmatched", 0) or 0),
        "human_approval_required": bool(result.get("human_approval_required", False)),
        "human_approval_granted": bool(result.get("human_approval_granted", False)),
        "final_submission_attempted": bool("final_submission_result" in result),
        "errors": [str(result.get("message"))] if _clean(result.get("message")) and str(result.get("status")) == "blocked" else [],
        "warnings": warnings,
        "status": _clean(result.get("status")),
        "mode": _clean(result.get("mode")),
        "timestamp": _clean(result.get("logged_at") or _now_iso()),
        "pipeline_stage_count": len(pipeline_stages),
    }


def _counter_summary(counter: Counter) -> List[Dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common()]


def build_pilot_run_report(limit: int = 100) -> Dict[str, Any]:
    recent_payload = list_recent_pilot_runs(limit=limit)
    items = list(recent_payload.get("items") or [])

    warning_counter: Counter = Counter()
    error_counter: Counter = Counter()
    excluded_counter: Counter = Counter()
    mandatory_form_counter: Counter = Counter()
    quality_counter: Counter = Counter()

    blocked_runs = 0
    approval_blocked_runs = 0
    dry_run_ready_runs = 0
    pending_approval_runs = 0
    approved_submit_attempts = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        status = _clean(item.get("status"))
        if status == "blocked":
            blocked_runs += 1
        elif status == "dry_run_ready":
            dry_run_ready_runs += 1
        elif status == "pending_human_approval":
            pending_approval_runs += 1

        if bool(item.get("final_submission_attempted")):
            approved_submit_attempts += 1
        if bool(item.get("approval_blocked")):
            approval_blocked_runs += 1

        quality_status = _quote_pack_quality_status(item)
        if quality_status:
            quality_counter[quality_status] += 1

        for warning in _safe_list(item.get("warnings")):
            text = _clean(warning)
            if text:
                warning_counter[text] += 1
        for error in _safe_list(item.get("errors")):
            text = _clean(error)
            if text:
                error_counter[text] += 1
        if bool(item.get("excluded")):
            category = _clean(item.get("detected_category") or "unknown")
            excluded_counter[category] += 1
        for form in _safe_list(item.get("mandatory_forms_detected")):
            text = _clean(form)
            if text:
                mandatory_form_counter[text] += 1

    total_runs = len(items)
    non_blocked_runs = total_runs - blocked_runs
    most_recent_quality = _quote_pack_quality_status(items[0]) if items else "unknown"

    if total_runs == 0:
        recommendation = "needs_more_testing"
    elif blocked_runs == total_runs:
        recommendation = "blocked"
    elif total_runs >= 3 and non_blocked_runs == total_runs and most_recent_quality == "approval_ready":
        recommendation = "ready_for_manual_production"
    else:
        recommendation = "needs_more_testing"

    return {
        "status": "ok",
        "review_report": {
            "total_runs": total_runs,
            "blocked_runs": blocked_runs,
            "dry_run_ready_runs": dry_run_ready_runs,
            "pending_approval_runs": pending_approval_runs,
            "approved_submit_attempts": approved_submit_attempts,
            "approval_blocked_runs": approval_blocked_runs,
            "common_warnings": _counter_summary(warning_counter),
            "common_errors": _counter_summary(error_counter),
            "excluded_tender_categories_found": _counter_summary(excluded_counter),
            "mandatory_forms_most_often_detected": _counter_summary(mandatory_form_counter),
            "quote_pack_quality_statuses": _counter_summary(quality_counter),
            "readiness_recommendation": recommendation,
            "autonomous_submission_enabled": False,
        },
        "items": items,
        "total": int(recent_payload.get("total", 0) or 0),
        "log_file": recent_payload.get("log_file"),
        "updated_at": _now_iso(),
    }
