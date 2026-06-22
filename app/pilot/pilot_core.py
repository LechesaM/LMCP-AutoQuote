from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.persistence import db as persistence_db
from app.services import pilot_run_log_service
from app.services import submission_history_service


class PilotMode(str, Enum):
    DISABLED = "disabled"
    SUPERVISED_LIVE = "supervised_live"


_METRICS = {"rfqs_processed": 0, "rfqs_refused": 0, "blocked_workflows": 0}


def reset_pilot_metrics() -> None:
    for key in list(_METRICS):
        _METRICS[key] = 0


def _paths() -> Path:
    return get_runtime_paths().manual_production_dir


def _runs_path() -> Path:
    return _paths() / "pilot_runs.jsonl"


def _signoffs_path() -> Path:
    return _paths() / "pilot_signoffs.jsonl"


def _pilot_wave_status_files() -> List[Path]:
    base = _paths()
    if not base.exists():
        return []
    files = [path for path in base.glob("pilot_wave_*/*/submission_logs/pilot_status.json") if path.is_file()]
    return sorted(files)


def _load_json_object(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pilot_wave_status_records() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in _pilot_wave_status_files():
        payload = _load_json_object(path)
        if payload:
            payload["_source_path"] = str(path)
            records.append(payload)
    return records


def _sprint7_runtime_roots() -> Dict[str, Path]:
    runtime_root = get_runtime_paths().runtime_root
    return {
        "runtime_sprint7": runtime_root / "sprint_7",
        "runtime_pilot_runs": runtime_root / "pilot_runs",
        "execution_log": get_runtime_paths().project_root / "docs" / "operations_validation_pack" / "sprint_7_execution_log.md",
    }


def _read_markdown_field_values(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|") or line.count("|") < 3:
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 2:
                continue
            key, value = cells
            if key and value and key not in values:
                values[key] = value.strip("`").strip()
    except Exception:
        return values
    return values


def _read_json_records(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    try:
        if path.is_file() and path.suffix.lower() == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
        elif path.is_file() and path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                records.append(payload)
            elif isinstance(payload, list):
                records.extend(item for item in payload if isinstance(item, dict))
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in {".json", ".jsonl"}:
                    records.extend(_read_json_records(child))
    except Exception:
        return []
    return records


def _sum_numeric_fields(records: List[Dict[str, Any]], keys: List[str]) -> Dict[str, int]:
    totals = {key: 0 for key in keys}
    for record in records:
        for key in keys:
            value = record.get(key)
            if isinstance(value, bool):
                totals[key] += int(value)
            elif isinstance(value, (int, float)):
                totals[key] += int(value)
    return totals


def build_current_sprint7_dashboard(limit: int = 50) -> Dict[str, Any]:
    roots = _sprint7_runtime_roots()
    sprint7_records = _read_json_records(roots["runtime_sprint7"])
    pilot_run_records = _read_json_records(roots["runtime_pilot_runs"])
    execution_log_fields = _read_markdown_field_values(roots["execution_log"])
    all_records = sprint7_records + pilot_run_records

    totals = _sum_numeric_fields(
        all_records,
        [
            "rfqs_harvested",
            "rfqs_qualified",
            "rfqs_rejected",
            "quote_packs_generated",
            "submission_packs_generated",
            "submission_packs_approved",
            "approval_gate_bypass_count",
            "submission_ready_without_approval_count",
            "duplicate_audit_events",
            "orphaned_audit_events",
            "state_drift_count",
        ],
    )

    if not all_records:
        status = "INITIALIZED_EMPTY_WORKLOAD"
    elif totals["rfqs_harvested"] == 0:
        status = "INITIALIZED_EMPTY_WORKLOAD"
    else:
        status = "ACTIVE"

    metrics = {
        "rfqs_harvested": totals["rfqs_harvested"],
        "rfqs_qualified": totals["rfqs_qualified"],
        "rfqs_rejected": totals["rfqs_rejected"],
        "quote_packs_generated": totals["quote_packs_generated"],
        "submission_packs_generated": totals["submission_packs_generated"],
        "submission_packs_approved": totals["submission_packs_approved"],
        "approval_gate_bypass_count": totals["approval_gate_bypass_count"],
        "submission_ready_without_approval_count": totals["submission_ready_without_approval_count"],
        "duplicate_audit_events": totals["duplicate_audit_events"],
        "orphaned_audit_events": totals["orphaned_audit_events"],
        "state_drift_count": totals["state_drift_count"],
    }

    return {
        "source": "current_sprint_7_live_state",
        "timestamp": _now_iso(),
        "status": status,
        "portal_submission": "DISABLED",
        "human_approval": "REQUIRED",
        "audit": "AUTHORITATIVE",
        "execution_log": {
            "path": str(roots["execution_log"]),
            "pilot_start_date": execution_log_fields.get("Pilot Start Date", ""),
            "lmcp_version": execution_log_fields.get("LMCP Version", ""),
            "portal_submission_status": execution_log_fields.get("Portal Submission Status", "DISABLED"),
            "human_approval_status": execution_log_fields.get("Human Approval Status", "REQUIRED"),
            "audit_status": execution_log_fields.get("Audit Status", "AUTHORITATIVE"),
        },
        "runtime_sources": {
            "runtime_sprint_7": str(roots["runtime_sprint7"]),
            "runtime_pilot_runs": str(roots["runtime_pilot_runs"]),
        },
        **metrics,
        "current_sprint7_dashboard": metrics,
        "notes": [
            "This endpoint excludes historical pilot_wave_* wave records by design.",
            "It reads only the Sprint 7 execution log and current Sprint 7 runtime sources.",
        ],
    }


def get_pilot_mode() -> PilotMode:
    return PilotMode.DISABLED if str(__import__("os").getenv("LMCP_PILOT_MODE", "supervised_live")).strip().lower() == "disabled" else PilotMode.SUPERVISED_LIVE


def get_pilot_execution_metadata() -> Dict[str, Any]:
    enabled = get_pilot_mode() != PilotMode.DISABLED
    return {"pilot_enabled": enabled, "pilot_mode": get_pilot_mode().value}


def assert_pilot_guardrails(payload: Dict[str, Any]) -> None:
    if bool(payload.get("final_submission_attempted")):
        raise ValueError("final submission is not allowed in pilot")


def record_pilot_run(record: Dict[str, Any]) -> Dict[str, Any]:
    assert_pilot_guardrails(record)
    payload = dict(record)
    _METRICS["rfqs_processed"] += 1
    if str(payload.get("outcome")) == "refused" or str(payload.get("status")) == "refused":
        _METRICS["rfqs_refused"] += 1
        _METRICS["blocked_workflows"] += 1
    path = _runs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
    try:
        persistence_db.insert_json_record("pilot_run_records", payload)
    except Exception:
        pass
    return payload


def record_signoff(record: Dict[str, Any]) -> Dict[str, Any]:
    if not str(record.get("operator") or "").strip():
        raise ValueError("operator required")
    payload = dict(record)
    path = _signoffs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
    try:
        persistence_db.insert_json_record("pilot_signoff_records", payload)
    except Exception:
        pass
    return payload


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                items.append(payload)
    return items


def _is_pilot_run(record: Dict[str, Any]) -> bool:
    outcome = str(record.get("outcome") or "").strip().lower()
    status = str(record.get("status") or "").strip().lower()
    return outcome in {"completed", "refused", "failed"} or status in {"recorded", "refused", "failed", "completed"}


def _is_successful_pilot_run(record: Dict[str, Any]) -> bool:
    outcome = str(record.get("outcome") or "").strip().lower()
    status = str(record.get("status") or "").strip().lower()
    return outcome == "completed" or status == "recorded"


def get_pilot_signoffs() -> List[Dict[str, Any]]:
    return _read_jsonl(_signoffs_path())


def get_pilot_successes() -> List[Dict[str, Any]]:
    return [item for item in _read_jsonl(_runs_path()) if _is_successful_pilot_run(item)]


def get_pilot_failures() -> List[Dict[str, Any]]:
    return [item for item in _read_jsonl(_runs_path()) if str(item.get("outcome") or item.get("status") or "").strip().lower() in {"refused", "failed"}]


def get_pilot_summary() -> Dict[str, Any]:
    runs = [item for item in _read_jsonl(_runs_path()) if _is_pilot_run(item)]
    return {"total_runs": len(runs), "successful_runs": len(get_pilot_successes()), "failed_runs": len(get_pilot_failures())}


def get_pilot_metrics() -> Dict[str, Any]:
    runs = _read_jsonl(_runs_path())
    metrics = {
        "rfqs_processed": len(runs),
        "rfqs_refused": sum(
            1
            for item in runs
            if str(item.get("outcome") or item.get("status") or "").strip().lower() in {"refused", "failed"}
        ),
        "blocked_workflows": sum(
            1
            for item in runs
            if str(item.get("outcome") or item.get("status") or "").strip().lower() in {"refused", "failed"}
        ),
        "recovery_events": sum(len(item.get("recovery_events") or []) for item in runs),
    }
    return metrics


def calculate_success_rate() -> float:
    summary = get_pilot_summary()
    total = int(summary.get("total_runs", 0) or 0)
    return int(summary.get("successful_runs", 0) or 0) / total if total else 0.0


def calculate_readiness_score() -> float:
    return max(0.0, min(100.0, calculate_success_rate() * 100.0))


def build_pilot_readiness_report(limit: int = 20) -> Dict[str, Any]:
    summary = get_pilot_summary()
    readiness = calculate_readiness_score()
    return {
        "pilot_readiness_score": readiness,
        "quality_summary": {"quality_score": readiness / 100.0},
        "tender_success_analytics": {"quote_conversion_rate": calculate_success_rate()},
        "supervised_live_governance_summary": {
            "governance_advisory_only": True,
            "manual_only_final_submission": True,
            "manual_submission_remains_required": True,
        },
        "governance_compliance_score": readiness,
        "manual_governance_integrity_score": readiness,
        "summary": summary,
    }


def build_controlled_pilot_dashboard(limit: int = 50) -> Dict[str, Any]:
    wave_items = _pilot_wave_status_records()
    if wave_items:
        rfqs_harvested = len(wave_items)
        rfqs_rejected = sum(
            1
            for item in wave_items
            if str(item.get("status") or "").strip().lower() in {"rejected", "refused", "blocked"}
            or bool(item.get("rejected"))
        )
        rfqs_approved = sum(
            1
            for item in wave_items
            if bool(item.get("submission_ready"))
            or str(_safe_dict(item.get("latest_run")).get("status") or "").strip().lower() == "approved"
            or bool(_safe_dict(item.get("latest_run")).get("submission_ready"))
        )
        quote_packs_generated = sum(
            1
            for item in wave_items
            if bool(_safe_dict(item.get("latest_run")))
            and str(_safe_dict(item.get("latest_run")).get("quote_pack_quality_status") or "").strip()
        )
        submission_records = sum(
            1
            for item in wave_items
            if bool(item.get("manual_submission_recorded"))
            or str(item.get("status") or "").strip().lower() == "submitted"
        )
        proof_records = sum(
            1
            for item in wave_items
            if bool(_safe_dict(item.get("latest_submission_proof")).get("manual_submission_recorded"))
            or str(_safe_dict(item.get("latest_submission_proof")).get("status") or "").strip().lower() == "recorded"
        )
        pilot_success_rate = round((proof_records / rfqs_harvested) * 100.0, 2) if rfqs_harvested else 0.0

        if rfqs_harvested >= 25 and submission_records > 0 and proof_records == submission_records:
            go_no_go = "GO"
        elif rfqs_harvested >= 5 and quote_packs_generated > 0:
            go_no_go = "HOLD"
        else:
            go_no_go = "NOT_READY"

        if rfqs_harvested >= 25 and proof_records == submission_records and submission_records > 0:
            pilot_wave = "stage_4_autonomous_expansion"
        elif rfqs_harvested >= 25:
            pilot_wave = "stage_3_production_candidate"
        elif rfqs_harvested >= 5:
            pilot_wave = "stage_2_pilot_dashboard"
        else:
            pilot_wave = "stage_1_controlled_pilot"
    else:
        pilot_runs = pilot_run_log_service.list_recent_pilot_runs(limit=limit)
        run_items = [item for item in pilot_runs.get("items", []) if isinstance(item, dict)]
        submission_summary = submission_history_service.get_submission_summary()
        submission_items = submission_history_service.list_submission_history(limit=limit).get("items", [])

        metrics = get_pilot_metrics()
        rfqs_harvested = int(metrics.get("rfqs_processed", 0) or 0)
        rfqs_rejected = int(metrics.get("rfqs_refused", 0) or 0)
        rfqs_approved = sum(
            1
            for item in get_pilot_signoffs()
            if str(item.get("signoff_type") or "").strip().lower() == "approval"
            and str(item.get("signoff_status") or "").strip().lower() in {"signed", "approved", "recorded"}
        )
        quote_packs_generated = sum(1 for item in run_items if bool(item.get("quote_pack_generated")))
        submission_records = int(submission_summary.get("total", 0) or 0)
        proof_records = sum(1 for item in submission_items if str(item.get("proof_path") or "").strip())
        pilot_success_rate = round(calculate_success_rate() * 100.0, 2)

        if rfqs_harvested >= 25 and submission_records > 0 and proof_records == submission_records:
            go_no_go = "GO"
        elif rfqs_harvested >= 5 and quote_packs_generated > 0:
            go_no_go = "HOLD"
        else:
            go_no_go = "NOT_READY"

        if rfqs_harvested >= 25 and proof_records == submission_records and submission_records > 0:
            pilot_wave = "stage_4_autonomous_expansion"
        elif rfqs_harvested >= 25:
            pilot_wave = "stage_3_production_candidate"
        elif rfqs_harvested >= 5:
            pilot_wave = "stage_2_pilot_dashboard"
        else:
            pilot_wave = "stage_1_controlled_pilot"

    return {
        "rfqs_harvested": rfqs_harvested,
        "rfqs_rejected": rfqs_rejected,
        "rfqs_approved": rfqs_approved,
        "quote_packs_generated": quote_packs_generated,
        "submission_records": submission_records,
        "proof_records": proof_records,
        "pilot_success_rate": pilot_success_rate,
        "go_no_go": go_no_go,
        "pilot_wave": pilot_wave,
    }


def render_pilot_readiness_text(report: Dict[str, Any]) -> str:
    return f"Pilot readiness score: {report.get('pilot_readiness_score', 0)}\nSupervised-live governance: advisory only"
