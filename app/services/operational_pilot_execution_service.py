from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
EVIDENCE_PACK_ROOT = PROJECT_ROOT / "runtime" / "staging" / "evidence-packs"
REVIEW_WINDOW_DAYS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text if text else default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _age_hours(value: Any) -> float:
    parsed = _parse_iso(value)
    if parsed is None:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0)


def _run_dirs(root: Path, marker: str) -> List[Path]:
    if not root.exists():
        return []
    runs = [path for path in root.iterdir() if path.is_dir() and (path / marker).exists()]
    runs.sort(
        key=lambda path: (
            _parse_iso((_read_json(path / marker, {}) or {}).get("generated_at")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            path.name,
        ),
        reverse=True,
    )
    return runs


def _cycle_summary(path: Path) -> Dict[str, Any]:
    payload = _read_json(path / "pilot_cycle_summary.json", {})
    return payload if isinstance(payload, dict) else {}


def _evidence_pack(path: Path) -> Dict[str, Any]:
    payload = _read_json(path / "pilot_evidence_pack.json", {})
    return payload if isinstance(payload, dict) else {}


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "PASS"
    if score >= 65.0:
        return "WARN"
    return "FAIL"


def _status_score(status: Any) -> float:
    normalized = _safe_str(status, "WARN").upper()
    return {"PASS": 100.0, "WARN": 65.0, "FAIL": 0.0}.get(normalized, 40.0)


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    if delta > 2.0:
        trend = "improving"
    elif delta < -2.0:
        trend = "declining"
    else:
        trend = "stable"
    return {
        "trend": trend,
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


class OperationalPilotExecutionService:
    def __init__(self, cycle_root: Optional[Path] = None, evidence_pack_root: Optional[Path] = None) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.evidence_pack_root = evidence_pack_root or EVIDENCE_PACK_ROOT

    def _cycles(self) -> List[Path]:
        return _run_dirs(self.cycle_root, "pilot_cycle_summary.json")

    def _packs(self) -> List[Path]:
        return _run_dirs(self.evidence_pack_root, "pilot_evidence_pack.json")

    def _lookup_pack(self, pack_id: str) -> Dict[str, Any]:
        if not pack_id:
            return {}
        pack_dir = self.evidence_pack_root / pack_id
        if not pack_dir.exists():
            return {}
        return _evidence_pack(pack_dir)

    def _cycle_view(self, cycle: Dict[str, Any]) -> Dict[str, Any]:
        evidence_pack = _safe_dict(cycle.get("evidence_pack"))
        governance_export = _safe_dict(cycle.get("governance_export"))
        metrics = _safe_dict(cycle.get("metrics"))
        readiness = _safe_dict(governance_export.get("readiness_summary"))
        cadence = _safe_dict(readiness.get("cadence"))
        no_go = _safe_dict(cycle.get("no_go_condition_summary"))
        operator_ack = _safe_dict(cycle.get("operator_acknowledgement"))
        checks = _safe_list(cycle.get("checks"))
        latest_rehearsal = _safe_dict(evidence_pack.get("latest_rehearsal"))
        latest_rehearsal_metrics = _safe_dict(latest_rehearsal.get("metrics"))
        latest_pack_id = _safe_str(evidence_pack.get("pack_id"), "")
        pack_from_disk = self._lookup_pack(latest_pack_id)
        pack_source = pack_from_disk if pack_from_disk else evidence_pack
        queue_evidence = _safe_dict(pack_source.get("queue_stability_evidence"))
        worker_evidence = _safe_dict(pack_source.get("worker_stability_evidence"))
        telemetry_evidence = _safe_dict(pack_source.get("telemetry_health_evidence"))
        retry_evidence = _safe_dict(pack_source.get("retry_recovery_evidence"))
        rollback_evidence = _safe_dict(pack_source.get("rollback_evidence"))
        operator_summary = _safe_dict(pack_source.get("operator_intervention_summary"))
        lock = _safe_dict(pack_source.get("submission_lock_verification"))
        dry_run = _safe_dict(pack_source.get("dry_run_enforcement_verification"))
        evidence_paths = _safe_dict(pack_source.get("artifact_paths"))
        drift = _safe_dict(readiness.get("trend_summary"))
        overall_checks = all(_safe_str(check.get("status"), "WARN").upper() == "PASS" for check in checks if isinstance(check, dict))
        component_statuses = [
            _safe_str(queue_evidence.get("status"), "WARN"),
            _safe_str(worker_evidence.get("status"), "WARN"),
            _safe_str(telemetry_evidence.get("status"), "WARN"),
            _safe_str(retry_evidence.get("status"), "WARN"),
            _safe_str(rollback_evidence.get("status"), "WARN"),
            _safe_str(operator_summary.get("status"), "WARN"),
            _safe_str(lock.get("status"), "WARN"),
            _safe_str(dry_run.get("status"), "WARN"),
            _safe_str(no_go.get("status"), "WARN"),
        ]
        reliability_indicators = {
            "governance_checkpoint_verified": bool(cycle.get("governance_checkpoint_verified", False)),
            "rehearsal_cadence_enforced": bool(cycle.get("rehearsal_cadence_enforced", False)),
            "concurrency_limit_enforced": bool(cycle.get("concurrency_limit_enforced", False)),
            "operator_acknowledged": bool(operator_ack.get("acknowledged", False)),
            "submission_lock_verified": _safe_str(lock.get("status"), "WARN") == "PASS",
            "dry_run_verified": _safe_str(dry_run.get("status"), "WARN") == "PASS",
            "no_go_clear": _safe_str(no_go.get("status"), "WARN") == "PASS",
            "evidence_aggregated": bool(pack_source),
        }
        degradation_indicators = {
            "queue_degradation": _safe_str(queue_evidence.get("status"), "WARN") != "PASS",
            "worker_degradation": _safe_str(worker_evidence.get("status"), "WARN") != "PASS",
            "telemetry_degradation": _safe_str(telemetry_evidence.get("status"), "WARN") != "PASS",
            "retry_degradation": _safe_str(retry_evidence.get("status"), "WARN") != "PASS",
            "rollback_degradation": _safe_str(rollback_evidence.get("status"), "WARN") != "PASS",
            "operator_degradation": _safe_str(operator_summary.get("status"), "WARN") != "PASS" or not bool(operator_ack.get("acknowledged", False)),
            "no_go_degradation": _safe_str(no_go.get("status"), "WARN") != "PASS",
            "cadence_degradation": _safe_int(cadence.get("runs_last_7_days"), 0) <= 0,
        }
        readiness_score = _safe_float(readiness.get("readiness_score"), _safe_float(metrics.get("readiness_score"), 0.0))
        queue_score = _status_score(queue_evidence.get("status"))
        worker_score = _status_score(worker_evidence.get("status"))
        telemetry_score = _status_score(telemetry_evidence.get("status"))
        retry_score = _status_score(retry_evidence.get("status"))
        rollback_score = _status_score(rollback_evidence.get("status"))
        operator_score = _status_score(operator_summary.get("status"))
        lock_score = _status_score(lock.get("status"))
        dry_run_score = _status_score(dry_run.get("status"))
        no_go_score = _status_score(no_go.get("status"))
        cadence_score = 100.0 if _safe_int(cadence.get("runs_last_7_days"), 0) > 0 and _safe_float(cadence.get("average_gap_hours"), 0.0) <= 72.0 else 65.0
        endurance_score = round(
            mean([
                readiness_score,
                queue_score,
                worker_score,
                telemetry_score,
                retry_score,
                rollback_score,
                operator_score,
                lock_score,
                dry_run_score,
                no_go_score,
                cadence_score,
            ]),
            2,
        )
        sustained_stability_score = round(mean([endurance_score, readiness_score, queue_score, worker_score, telemetry_score]), 2)
        cycle_status = _safe_str(cycle.get("status"), "WARN").upper()
        governance_status = "ok" if cycle_status == "PASS" else "watch" if cycle_status == "WARN" else "blocked"
        return {
            "kind": "operational_pilot_execution",
            "cycle_id": _safe_str(cycle.get("cycle_id"), "unknown"),
            "generated_at": _safe_str(cycle.get("generated_at"), _now_iso()),
            "age_hours": round(_age_hours(cycle.get("generated_at")), 2),
            "operational_pilot_execution_status": governance_status,
            "operational_pilot_execution_grade": "ready" if sustained_stability_score >= 85.0 and governance_status == "ok" else "watch" if governance_status == "watch" else "not_ready",
            "operational_endurance_score": endurance_score,
            "sustained_stability_score": sustained_stability_score,
            "operational_pilot_execution_decision": "authorize_supervised_pilot"
            if sustained_stability_score >= 85.0 and not any(degradation_indicators.values()) and all(reliability_indicators.values())
            else "watch_supervised_pilot"
            if sustained_stability_score >= 65.0
            else "defer_supervised_pilot",
            "supervised_execution_reliability_indicators": reliability_indicators,
            "operational_degradation_indicators": degradation_indicators,
            "operational_review_interval_hours": round(_safe_float(cadence.get("average_gap_hours"), 0.0), 2),
            "operational_review_interval_status": "PASS" if _safe_int(cadence.get("runs_last_7_days"), 0) > 0 and _safe_float(cadence.get("average_gap_hours"), 0.0) <= 72.0 else "WARN" if _safe_int(cadence.get("runs_last_7_days"), 0) > 0 else "FAIL",
            "pilot_execution_cadence_governance": {
                "runs_last_7_days": _safe_int(cadence.get("runs_last_7_days"), 0),
                "average_gap_hours": _safe_float(cadence.get("average_gap_hours"), 0.0),
                "latest_run_at": _safe_str(cadence.get("most_recent_run_at"), ""),
                "previous_run_at": _safe_str(cadence.get("previous_run_at"), ""),
                "status": _safe_str(cadence.get("status"), "unknown"),
            },
            "supervised_execution_evidence_aggregation": {
                "pack_id": latest_pack_id,
                "evidence_pack_present": bool(pack_source),
                "evidence_dir": _safe_str(pack_source.get("evidence_dir"), ""),
                "queue_stability_evidence": queue_evidence,
                "worker_stability_evidence": worker_evidence,
                "telemetry_health_evidence": telemetry_evidence,
                "retry_recovery_evidence": retry_evidence,
                "rollback_evidence": rollback_evidence,
                "operator_intervention_summary": operator_summary,
                "submission_lock_verification": lock,
                "dry_run_enforcement_verification": dry_run,
                "latest_rehearsal": latest_rehearsal,
            },
            "execution_governance_history_entry": {
                "cycle_id": _safe_str(cycle.get("cycle_id"), "unknown"),
                "generated_at": _safe_str(cycle.get("generated_at"), _now_iso()),
                "status": governance_status,
                "operational_endurance_score": endurance_score,
                "sustained_stability_score": sustained_stability_score,
                "readiness_score": readiness_score,
                "queue_status": _safe_str(queue_evidence.get("status"), "WARN"),
                "worker_status": _safe_str(worker_evidence.get("status"), "WARN"),
                "telemetry_status": _safe_str(telemetry_evidence.get("status"), "WARN"),
                "retry_status": _safe_str(retry_evidence.get("status"), "WARN"),
                "rollback_status": _safe_str(rollback_evidence.get("status"), "WARN"),
                "operator_status": _safe_str(operator_summary.get("status"), "WARN"),
                "submission_lock_status": _safe_str(lock.get("status"), "WARN"),
                "dry_run_status": _safe_str(dry_run.get("status"), "WARN"),
                "no_go_status": _safe_str(no_go.get("status"), "WARN"),
                "governance_checkpoint_verified": bool(cycle.get("governance_checkpoint_verified", False)),
                "operator_acknowledged": bool(operator_ack.get("acknowledged", False)),
                "rehearsal_cadence_enforced": bool(cycle.get("rehearsal_cadence_enforced", False)),
                "concurrency_limit_enforced": bool(cycle.get("concurrency_limit_enforced", False)),
                "warnings": [],
            },
            "warnings": [
                warning
                for warning in [
                    "operational_pilot_execution_warning" if sustained_stability_score < 85.0 or governance_status != "ok" else "",
                    "degradation_warning" if any(degradation_indicators.values()) else "",
                    "supervision_warning" if not reliability_indicators["operator_acknowledged"] else "",
                    "submission_lock_warning" if not reliability_indicators["submission_lock_verified"] else "",
                    "dry_run_warning" if not reliability_indicators["dry_run_verified"] else "",
                    "no_go_warning" if not reliability_indicators["no_go_clear"] else "",
                ]
                if warning
            ],
            "readiness_summary": {
                "readiness_score": readiness_score,
                "readiness_grade": _safe_str(readiness.get("readiness_grade"), "watch"),
                "trend_summary": _safe_dict(readiness.get("trend_summary")),
                "cadence": _safe_dict(readiness.get("cadence")),
            },
            "summary_counts": {
                "PASS": _safe_int(cycle.get("summary_counts", {}).get("PASS"), 0),
                "WARN": _safe_int(cycle.get("summary_counts", {}).get("WARN"), 0),
                "FAIL": _safe_int(cycle.get("summary_counts", {}).get("FAIL"), 0),
            },
        }

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        cycles: List[Dict[str, Any]] = []
        for path in self._cycles()[: max(1, int(limit))]:
            payload = _cycle_summary(path)
            if payload:
                cycles.append(self._cycle_view(payload))
        return cycles

    def list_operational_pilot_execution(self, limit: int = 20) -> Dict[str, Any]:
        history = self._history(limit=limit)
        latest = history[0] if history else {}
        endurance_values = [entry.get("operational_endurance_score", 0.0) for entry in history]
        stability_values = [entry.get("sustained_stability_score", 0.0) for entry in history]
        readiness_values = [entry.get("readiness_summary", {}).get("readiness_score", 0.0) for entry in history]
        queue_values = [entry.get("execution_governance_history_entry", {}).get("queue_status") for entry in history]
        worker_values = [entry.get("execution_governance_history_entry", {}).get("worker_status") for entry in history]
        telemetry_values = [entry.get("execution_governance_history_entry", {}).get("telemetry_status") for entry in history]
        retry_values = [entry.get("execution_governance_history_entry", {}).get("retry_status") for entry in history]
        rollback_values = [entry.get("execution_governance_history_entry", {}).get("rollback_status") for entry in history]
        operator_values = [entry.get("execution_governance_history_entry", {}).get("operator_status") for entry in history]
        review_window = history[:]
        evidence_pack_count = sum(1 for entry in history if entry.get("supervised_execution_evidence_aggregation", {}).get("evidence_pack_present"))
        status = "not_found"
        if history:
            status = "ok"
            if any(entry.get("operational_pilot_execution_status") == "blocked" for entry in history):
                status = "blocked"
            elif any(entry.get("operational_pilot_execution_status") == "watch" for entry in history):
                status = "watch"

        readiness_history = _history_points(readiness_values)
        endurance_history = _history_points(endurance_values)
        stability_history = _history_points(stability_values)
        cadence_values = [entry.get("pilot_execution_cadence_governance", {}).get("runs_last_7_days", 0) for entry in history]
        cadence_history = _history_points([_safe_float(value, 0.0) for value in cadence_values])
        queue_history = _history_points([_status_score(value) for value in queue_values])
        worker_history = _history_points([_status_score(value) for value in worker_values])
        telemetry_history = _history_points([_status_score(value) for value in telemetry_values])
        retry_history = _history_points([_status_score(value) for value in retry_values])
        rollback_history = _history_points([_status_score(value) for value in rollback_values])
        operator_history = _history_points([_status_score(value) for value in operator_values])

        warnings = [
            warning
            for warning in [
                "no_history_warning" if not history else "",
                "degradation_warning" if any(any(entry.get("operational_degradation_indicators", {}).values()) for entry in history) else "",
            ]
            if warning
        ]

        return {
            "status": status,
            "generated_at": _now_iso(),
            "operational_pilot_execution_status": status,
            "operational_pilot_execution_grade": _safe_str(latest.get("operational_pilot_execution_grade"), "not_ready"),
            "operational_endurance_score": round(mean(endurance_values), 2) if endurance_values else 0.0,
            "sustained_stability_score": round(mean(stability_values), 2) if stability_values else 0.0,
            "operational_endurance_history": endurance_history,
            "sustained_stability_history": stability_history,
            "readiness_history": readiness_history,
            "pilot_execution_cadence_history": cadence_history,
            "operational_review_interval_summary": {
                "runs_last_7_days": _safe_int(_safe_dict(latest.get("pilot_execution_cadence_governance")).get("runs_last_7_days"), 0),
                "average_gap_hours": _safe_float(_safe_dict(latest.get("pilot_execution_cadence_governance")).get("average_gap_hours"), 0.0),
                "status": _safe_str(_safe_dict(latest.get("pilot_execution_cadence_governance")).get("status"), "unknown"),
            },
            "supervised_execution_reliability_indicators": _safe_dict(latest.get("supervised_execution_reliability_indicators")),
            "operational_degradation_indicators": _safe_dict(latest.get("operational_degradation_indicators")),
            "execution_governance_decision_counts": {
                "authorize_supervised_pilot": sum(1 for entry in history if entry.get("operational_pilot_execution_decision") == "authorize_supervised_pilot"),
                "watch_supervised_pilot": sum(1 for entry in history if entry.get("operational_pilot_execution_decision") == "watch_supervised_pilot"),
                "defer_supervised_pilot": sum(1 for entry in history if entry.get("operational_pilot_execution_decision") == "defer_supervised_pilot"),
            },
            "execution_governance_history": history,
            "latest_operational_pilot_execution": latest,
            "operational_pilot_execution_history_summary": {
                "cycle_count": len(history),
                "evidence_pack_count": evidence_pack_count,
                "supervision_pass_count": sum(1 for entry in history if entry.get("supervised_execution_reliability_indicators", {}).get("operator_acknowledged")),
                "lock_pass_count": sum(1 for entry in history if entry.get("supervised_execution_reliability_indicators", {}).get("submission_lock_verified")),
                "dry_run_pass_count": sum(1 for entry in history if entry.get("supervised_execution_reliability_indicators", {}).get("dry_run_verified")),
                "no_go_clear_count": sum(1 for entry in history if entry.get("supervised_execution_reliability_indicators", {}).get("no_go_clear")),
            },
            "operational_review_intervals": {
                "queue": queue_history,
                "worker": worker_history,
                "telemetry": telemetry_history,
                "retry": retry_history,
                "rollback": rollback_history,
                "operator": operator_history,
            },
            "warnings": warnings + _safe_list(latest.get("warnings")),
        }

    def latest_operational_pilot_execution(self) -> Dict[str, Any]:
        response = self.list_operational_pilot_execution(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No operational pilot execution records have been recorded yet.",
                "operational_pilot_execution": {},
            }
        return {
            "status": response.get("status", "ok"),
            "operational_pilot_execution_status": response.get("operational_pilot_execution_status", "watch"),
            "operational_endurance_score": response.get("operational_endurance_score", 0.0),
            "sustained_stability_score": response.get("sustained_stability_score", 0.0),
            "latest_operational_pilot_execution": response.get("latest_operational_pilot_execution", {}),
            "execution_governance_history": response.get("execution_governance_history", []),
            "operational_pilot_execution_history_summary": response.get("operational_pilot_execution_history_summary", {}),
            "operational_review_intervals": response.get("operational_review_intervals", {}),
            "warnings": response.get("warnings", []),
        }

    def operational_pilot_execution_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_operational_pilot_execution(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("execution_governance_history", [])),
            "execution_governance_history": response.get("execution_governance_history", []),
            "operational_pilot_execution_history_summary": response.get("operational_pilot_execution_history_summary", {}),
            "operational_review_intervals": response.get("operational_review_intervals", {}),
            "warnings": response.get("warnings", []),
        }
