from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
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


def _window_entries(entries: List[Dict[str, Any]], window_days: int = REVIEW_WINDOW_DAYS) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    windowed: List[Dict[str, Any]] = []
    for entry in entries:
        parsed = _parse_iso(entry.get("generated_at"))
        if parsed is None or parsed >= cutoff:
            windowed.append(entry)
    return windowed


def _average_gap_hours(entries: List[Dict[str, Any]]) -> float:
    timestamps = sorted(
        [ts for ts in (_parse_iso(entry.get("generated_at")) for entry in entries) if ts is not None]
    )
    if len(timestamps) < 2:
        return 0.0
    gaps = [
        (later - earlier).total_seconds() / 3600.0
        for earlier, later in zip(timestamps, timestamps[1:])
    ]
    return round(mean(gaps), 2) if gaps else 0.0


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


def _safe_status(value: Any, default: str = "WARN") -> str:
    status = _safe_str(value, default).upper()
    if status in {"PASS", "WARN", "FAIL"}:
        return status
    return default


def _bool_status(value: bool) -> str:
    return "PASS" if value else "WARN"


def _merge_cycle_status(pass_count: int, warn_count: int, fail_count: int, checks: List[bool]) -> str:
    if fail_count > 0 or not all(checks):
        return "FAIL"
    if warn_count > 0 or not checks:
        return "WARN"
    return "PASS"


class RecurringPilotCycleService:
    def __init__(self, cycle_root: Optional[Path] = None, review_window_days: int = REVIEW_WINDOW_DAYS) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.review_window_days = max(1, review_window_days)

    def _cycles(self) -> List[Path]:
        return _run_dirs(self.cycle_root, "pilot_cycle_summary.json")

    def _cycle_view(self, cycle: Dict[str, Any]) -> Dict[str, Any]:
        summary_counts = _safe_dict(cycle.get("summary_counts"))
        evidence_pack = _safe_dict(cycle.get("evidence_pack"))
        readiness = _safe_dict(_safe_dict(cycle.get("governance_export")).get("readiness_summary"))
        read_cadence = _safe_dict(readiness.get("cadence"))
        no_go = _safe_dict(cycle.get("no_go_condition_summary"))
        submission_lock = _safe_dict(evidence_pack.get("submission_lock_verification"))
        dry_run = _safe_dict(evidence_pack.get("dry_run_enforcement_verification"))
        artifacts = _safe_dict(_safe_dict(evidence_pack.get("artifact_summary")))
        latest_rehearsal = _safe_dict(evidence_pack.get("latest_rehearsal"))
        timeline = _safe_list(latest_rehearsal.get("timeline"))
        evidence_sections = _safe_dict(evidence_pack)
        queue_evidence = _safe_dict(evidence_sections.get("queue_stability_evidence"))
        worker_evidence = _safe_dict(evidence_sections.get("worker_stability_evidence"))
        telemetry_evidence = _safe_dict(evidence_sections.get("telemetry_health_evidence"))
        retry_evidence = _safe_dict(evidence_sections.get("retry_recovery_evidence"))
        rollback_evidence = _safe_dict(evidence_sections.get("rollback_evidence"))
        operator_summary = _safe_dict(evidence_sections.get("operator_intervention_summary"))
        checks = _safe_list(cycle.get("checks"))
        check_statuses = [_safe_str(check.get("status"), "WARN").upper() == "PASS" for check in checks if isinstance(check, dict)]
        metric_statuses = [
            _safe_status(queue_evidence.get("status")),
            _safe_status(worker_evidence.get("status")),
            _safe_status(telemetry_evidence.get("status")),
            _safe_status(retry_evidence.get("status")),
            _safe_status(rollback_evidence.get("status")),
            _safe_status(operator_summary.get("status")),
            _safe_status(submission_lock.get("status")),
            _safe_status(dry_run.get("status")),
            _safe_status(no_go.get("status")),
        ]
        pass_count = _safe_int(summary_counts.get("PASS"), 0)
        warn_count = _safe_int(summary_counts.get("WARN"), 0)
        fail_count = _safe_int(summary_counts.get("FAIL"), 0)
        cycle_status = _merge_cycle_status(pass_count, warn_count, fail_count, check_statuses + [status == "PASS" for status in metric_statuses if status in {"PASS", "FAIL"}])
        generated_at = _safe_str(cycle.get("generated_at"), _now_iso())
        return {
            "kind": "recurring_cycle",
            "cycle_id": _safe_str(cycle.get("cycle_id"), "unknown"),
            "generated_at": generated_at,
            "age_hours": round(_age_hours(generated_at), 2),
            "status": cycle_status,
            "readiness_score": _safe_float(readiness.get("readiness_score"), 0.0),
            "readiness_grade": _safe_str(readiness.get("readiness_grade"), "watch"),
            "trend": _safe_str(_safe_dict(readiness.get("trend_summary")).get("trend"), "stable"),
            "readiness_delta": _safe_float(_safe_dict(readiness.get("trend_summary")).get("delta"), 0.0),
            "summary_counts": {
                "PASS": pass_count,
                "WARN": warn_count,
                "FAIL": fail_count,
            },
            "no_go_status": _safe_status(no_go.get("status")),
            "no_go_indicators": _safe_list(no_go.get("indicators")),
            "governance_checkpoint_verified": bool(cycle.get("governance_checkpoint_verified", False)),
            "rehearsal_cadence_enforced": bool(cycle.get("rehearsal_cadence_enforced", False)),
            "concurrency_limit_enforced": bool(cycle.get("concurrency_limit_enforced", False)),
            "operator_acknowledged": bool(_safe_dict(cycle.get("operator_acknowledgement")).get("acknowledged", False)),
            "submission_lock_status": _safe_status(submission_lock.get("status")),
            "dry_run_status": _safe_status(dry_run.get("status")),
            "artifact_count": _safe_int(artifacts.get("artifact_count"), 0),
            "total_size_bytes": _safe_int(artifacts.get("total_size_bytes"), 0),
            "timeline_steps": len(timeline),
            "evidence_paths": _safe_dict(evidence_pack.get("artifact_paths")),
            "stability_snapshot": {
                "queue_status": _safe_status(queue_evidence.get("status")),
                "worker_status": _safe_status(worker_evidence.get("status")),
                "telemetry_status": _safe_status(telemetry_evidence.get("status")),
                "retry_status": _safe_status(retry_evidence.get("status")),
                "rollback_status": _safe_status(rollback_evidence.get("status")),
                "operator_status": _safe_status(operator_summary.get("status")),
            },
        }

    def _cycles_view(self, limit: int = 20) -> List[Dict[str, Any]]:
        views: List[Dict[str, Any]] = []
        for path in self._cycles()[: max(1, int(limit))]:
            payload = _cycle_summary(path)
            if payload:
                views.append(self._cycle_view(payload))
        return views

    def _endurance_indicators(self, cycle_views: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not cycle_views:
            return {
                "clean_cycle_count": 0,
                "clean_cycle_rate": 0.0,
                "readiness_pass_rate": 0.0,
                "governance_compliance_rate": 0.0,
                "submission_lock_pass_rate": 0.0,
                "dry_run_pass_rate": 0.0,
                "no_go_clear_rate": 0.0,
                "evidence_generation_rate": 0.0,
                "stability_snapshot_count": 0,
            }
        clean_cycles = [cycle for cycle in cycle_views if cycle["status"] == "PASS"]
        readiness_passes = [cycle for cycle in cycle_views if cycle["readiness_score"] >= 85.0]
        governance_passes = [
            cycle
            for cycle in cycle_views
            if cycle["governance_checkpoint_verified"] and cycle["rehearsal_cadence_enforced"] and cycle["concurrency_limit_enforced"]
        ]
        lock_passes = [cycle for cycle in cycle_views if cycle["submission_lock_status"] == "PASS"]
        dry_run_passes = [cycle for cycle in cycle_views if cycle["dry_run_status"] == "PASS"]
        no_go_clear = [cycle for cycle in cycle_views if cycle["no_go_status"] == "PASS"]
        evidence_generation = [cycle for cycle in cycle_views if cycle["artifact_count"] > 0]
        return {
            "clean_cycle_count": len(clean_cycles),
            "clean_cycle_rate": round((len(clean_cycles) / len(cycle_views)) * 100.0, 2),
            "readiness_pass_rate": round((len(readiness_passes) / len(cycle_views)) * 100.0, 2),
            "governance_compliance_rate": round((len(governance_passes) / len(cycle_views)) * 100.0, 2),
            "submission_lock_pass_rate": round((len(lock_passes) / len(cycle_views)) * 100.0, 2),
            "dry_run_pass_rate": round((len(dry_run_passes) / len(cycle_views)) * 100.0, 2),
            "no_go_clear_rate": round((len(no_go_clear) / len(cycle_views)) * 100.0, 2),
            "evidence_generation_rate": round((len(evidence_generation) / len(cycle_views)) * 100.0, 2),
            "stability_snapshot_count": len(cycle_views),
        }

    def _trend_summary(self, cycle_views: List[Dict[str, Any]]) -> Dict[str, Any]:
        readiness_points = [cycle["readiness_score"] for cycle in cycle_views]
        pass_points = [cycle["summary_counts"]["PASS"] for cycle in cycle_views]
        warn_points = [cycle["summary_counts"]["WARN"] for cycle in cycle_views]
        fail_points = [cycle["summary_counts"]["FAIL"] for cycle in cycle_views]
        no_go_points = [1.0 if cycle["no_go_status"] == "PASS" else 0.0 for cycle in cycle_views]
        governance_points = [1.0 if cycle["governance_checkpoint_verified"] and cycle["rehearsal_cadence_enforced"] and cycle["concurrency_limit_enforced"] else 0.0 for cycle in cycle_views]
        evidence_points = [cycle["artifact_count"] for cycle in cycle_views]
        return {
            "readiness": _history_points(readiness_points),
            "pass_fail": {
                "trend": _history_points(pass_points)["trend"],
                "delta": _history_points(pass_points)["delta"],
                "average_passes": _history_points(pass_points)["average"],
                "latest_passes": _history_points(pass_points)["latest"],
                "previous_passes": _history_points(pass_points)["previous"],
            },
            "warnings": {
                "trend": _history_points(warn_points)["trend"],
                "delta": _history_points(warn_points)["delta"],
                "average_warnings": _history_points(warn_points)["average"],
                "latest_warnings": _history_points(warn_points)["latest"],
                "previous_warnings": _history_points(warn_points)["previous"],
            },
            "failures": {
                "trend": _history_points(fail_points)["trend"],
                "delta": _history_points(fail_points)["delta"],
                "average_failures": _history_points(fail_points)["average"],
                "latest_failures": _history_points(fail_points)["latest"],
                "previous_failures": _history_points(fail_points)["previous"],
            },
            "no_go": {
                "trend": _history_points(no_go_points)["trend"],
                "delta": _history_points(no_go_points)["delta"],
                "average_clear_rate": _history_points(no_go_points)["average"] * 100.0,
                "latest_clear": _history_points(no_go_points)["latest"],
                "previous_clear": _history_points(no_go_points)["previous"],
            },
            "governance_compliance": {
                "trend": _history_points(governance_points)["trend"],
                "delta": _history_points(governance_points)["delta"],
                "average_compliance_rate": _history_points(governance_points)["average"] * 100.0,
                "latest_compliant": _history_points(governance_points)["latest"],
                "previous_compliant": _history_points(governance_points)["previous"],
            },
            "operational_evidence": {
                "trend": _history_points(evidence_points)["trend"],
                "delta": _history_points(evidence_points)["delta"],
                "average_artifact_count": _history_points(evidence_points)["average"],
                "latest_artifact_count": _history_points(evidence_points)["latest"],
                "previous_artifact_count": _history_points(evidence_points)["previous"],
            },
        }

    def _stability_snapshots(self, cycle_views: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "cycle_id": cycle["cycle_id"],
                "generated_at": cycle["generated_at"],
                "readiness_score": cycle["readiness_score"],
                "queue_status": cycle["stability_snapshot"]["queue_status"],
                "worker_status": cycle["stability_snapshot"]["worker_status"],
                "telemetry_status": cycle["stability_snapshot"]["telemetry_status"],
                "retry_status": cycle["stability_snapshot"]["retry_status"],
                "rollback_status": cycle["stability_snapshot"]["rollback_status"],
                "operator_status": cycle["stability_snapshot"]["operator_status"],
                "status": cycle["status"],
            }
            for cycle in cycle_views
        ]

    def _compliance_summary(self, cycle_views: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not cycle_views:
            return {
                "status": "not_found",
                "compliance_rate": 0.0,
                "governance_checkpoint_pass_rate": 0.0,
                "submission_lock_pass_rate": 0.0,
                "dry_run_pass_rate": 0.0,
                "no_go_clear_rate": 0.0,
                "operator_acknowledgement_rate": 0.0,
            }
        governance_passes = [
            cycle
            for cycle in cycle_views
            if cycle["governance_checkpoint_verified"] and cycle["rehearsal_cadence_enforced"] and cycle["concurrency_limit_enforced"]
        ]
        lock_passes = [cycle for cycle in cycle_views if cycle["submission_lock_status"] == "PASS"]
        dry_run_passes = [cycle for cycle in cycle_views if cycle["dry_run_status"] == "PASS"]
        no_go_passes = [cycle for cycle in cycle_views if cycle["no_go_status"] == "PASS"]
        ack_passes = [cycle for cycle in cycle_views if cycle["operator_acknowledged"]]
        compliance_rate = round(
            mean([
                (len(governance_passes) / len(cycle_views)) * 100.0,
                (len(lock_passes) / len(cycle_views)) * 100.0,
                (len(dry_run_passes) / len(cycle_views)) * 100.0,
                (len(no_go_passes) / len(cycle_views)) * 100.0,
                (len(ack_passes) / len(cycle_views)) * 100.0,
            ]),
            2,
        )
        status = "PASS" if compliance_rate >= 85.0 else "WARN" if compliance_rate >= 70.0 else "FAIL"
        return {
            "status": status,
            "compliance_rate": compliance_rate,
            "governance_checkpoint_pass_rate": round((len(governance_passes) / len(cycle_views)) * 100.0, 2),
            "submission_lock_pass_rate": round((len(lock_passes) / len(cycle_views)) * 100.0, 2),
            "dry_run_pass_rate": round((len(dry_run_passes) / len(cycle_views)) * 100.0, 2),
            "no_go_clear_rate": round((len(no_go_passes) / len(cycle_views)) * 100.0, 2),
            "operator_acknowledgement_rate": round((len(ack_passes) / len(cycle_views)) * 100.0, 2),
            "approved_cycle_count": len(governance_passes),
            "submission_lock_verified_count": len(lock_passes),
            "dry_run_verified_count": len(dry_run_passes),
            "no_go_clear_count": len(no_go_passes),
        }

    def list_recurring_cycles(self, limit: int = 20) -> Dict[str, Any]:
        cycle_views = self._cycles_view(limit=limit)
        latest = cycle_views[0] if cycle_views else {}
        trend_summary = self._trend_summary(cycle_views)
        endurance = self._endurance_indicators(cycle_views)
        compliance = self._compliance_summary(cycle_views)
        stability_snapshots = self._stability_snapshots(cycle_views)
        readiness_values = [cycle["readiness_score"] for cycle in cycle_views]
        latest_readiness = _safe_float(latest.get("readiness_score"), 0.0)
        warnings = []
        warning_indicators = {
            "no_cycles_recorded": not bool(cycle_views),
            "readiness_drift_warning": latest_readiness < 85.0 or trend_summary["readiness"]["delta"] < -5.0,
            "governance_compliance_warning": compliance["compliance_rate"] < 85.0 if cycle_views else True,
            "endurance_warning": endurance["clean_cycle_rate"] < 85.0 if cycle_views else True,
            "stability_snapshot_warning": not bool(stability_snapshots),
        }
        if warning_indicators["no_cycles_recorded"]:
            warnings.append("no_recurring_cycles_recorded")
        if warning_indicators["readiness_drift_warning"]:
            warnings.append("readiness_drift_warning")
        if warning_indicators["governance_compliance_warning"]:
            warnings.append("governance_compliance_warning")
        if warning_indicators["endurance_warning"]:
            warnings.append("operational_endurance_warning")
        if warning_indicators["stability_snapshot_warning"]:
            warnings.append("stability_snapshot_warning")
        status = "not_found" if not cycle_views else ("ok" if not warnings else "watch")
        recurring_cycle_score = round(
            mean([
                trend_summary["readiness"]["average"] if cycle_views else 0.0,
                compliance["compliance_rate"] if cycle_views else 0.0,
                endurance["clean_cycle_rate"] if cycle_views else 0.0,
                endurance["governance_compliance_rate"] if cycle_views else 0.0,
                endurance["readiness_pass_rate"] if cycle_views else 0.0,
            ]),
            2,
        ) if cycle_views else 0.0
        recurring_cycle_grade = "sustainable" if recurring_cycle_score >= 85.0 else "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "recurring_cycle_score": recurring_cycle_score,
            "recurring_cycle_grade": recurring_cycle_grade,
            "recurring_cycle_status": status,
            "latest_cycle": latest,
            "cycle_history": cycle_views,
            "longitudinal_pilot_history": cycle_views,
            "recurring_cycle_trends": trend_summary,
            "governance_compliance_summary": compliance,
            "operational_endurance_indicators": endurance,
            "recurring_stability_snapshots": stability_snapshots,
            "readiness_history": [
                {
                    "cycle_id": cycle["cycle_id"],
                    "generated_at": cycle["generated_at"],
                    "readiness_score": cycle["readiness_score"],
                    "readiness_grade": cycle["readiness_grade"],
                    "trend": cycle["trend"],
                    "status": cycle["status"],
                }
                for cycle in cycle_views
            ],
            "no_go_history": [
                {
                    "cycle_id": cycle["cycle_id"],
                    "generated_at": cycle["generated_at"],
                    "no_go_status": cycle["no_go_status"],
                    "indicators": cycle["no_go_indicators"],
                }
                for cycle in cycle_views
            ],
            "governance_checkpoint_history": [
                {
                    "cycle_id": cycle["cycle_id"],
                    "generated_at": cycle["generated_at"],
                    "governance_checkpoint_verified": cycle["governance_checkpoint_verified"],
                    "rehearsal_cadence_enforced": cycle["rehearsal_cadence_enforced"],
                    "concurrency_limit_enforced": cycle["concurrency_limit_enforced"],
                    "submission_lock_status": cycle["submission_lock_status"],
                    "dry_run_status": cycle["dry_run_status"],
                }
                for cycle in cycle_views
            ],
            "operational_evidence_history": [
                {
                    "cycle_id": cycle["cycle_id"],
                    "generated_at": cycle["generated_at"],
                    "artifact_count": cycle["artifact_count"],
                    "total_size_bytes": cycle["total_size_bytes"],
                    "timeline_steps": cycle["timeline_steps"],
                    "status": cycle["status"],
                }
                for cycle in cycle_views
            ],
            "summary_counts": {
                "PASS": len([cycle for cycle in cycle_views if cycle["status"] == "PASS"]),
                "WARN": len([cycle for cycle in cycle_views if cycle["status"] == "WARN"]),
                "FAIL": len([cycle for cycle in cycle_views if cycle["status"] == "FAIL"]),
            },
            "warning_indicators": warning_indicators,
            "warnings": warnings,
            "window_days": self.review_window_days,
        }

    def latest_recurring_cycles(self) -> Dict[str, Any]:
        response = self.list_recurring_cycles(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No recurring pilot cycles have been recorded yet.",
                "recurring_cycles": {},
            }
        return {
            "status": response.get("status", "ok"),
            "latest_cycle": response.get("latest_cycle", {}),
            "recurring_cycle_score": response.get("recurring_cycle_score", 0.0),
            "recurring_cycle_grade": response.get("recurring_cycle_grade", "watch"),
            "recurring_cycle_status": response.get("recurring_cycle_status", "watch"),
            "recurring_cycle_trends": response.get("recurring_cycle_trends", {}),
            "governance_compliance_summary": response.get("governance_compliance_summary", {}),
            "operational_endurance_indicators": response.get("operational_endurance_indicators", {}),
            "recurring_stability_snapshots": response.get("recurring_stability_snapshots", []),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
            "summary_counts": response.get("summary_counts", {}),
            "longitudinal_pilot_history": response.get("longitudinal_pilot_history", []),
            "window_days": response.get("window_days", self.review_window_days),
        }

    def recurring_cycles_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_recurring_cycles(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("cycle_history", [])),
            "cycle_history": response.get("cycle_history", []),
            "longitudinal_pilot_history": response.get("longitudinal_pilot_history", []),
            "recurring_cycle_trends": response.get("recurring_cycle_trends", {}),
            "governance_compliance_summary": response.get("governance_compliance_summary", {}),
            "operational_endurance_indicators": response.get("operational_endurance_indicators", {}),
            "recurring_stability_snapshots": response.get("recurring_stability_snapshots", []),
            "readiness_history": response.get("readiness_history", []),
            "no_go_history": response.get("no_go_history", []),
            "governance_checkpoint_history": response.get("governance_checkpoint_history", []),
            "operational_evidence_history": response.get("operational_evidence_history", []),
            "summary_counts": response.get("summary_counts", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
            "window_days": response.get("window_days", self.review_window_days),
        }
