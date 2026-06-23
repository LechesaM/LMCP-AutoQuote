from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
import json

from app.services.operational_rehearsal_service import OperationalRehearsalService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"


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


def _score_from_status(status: str) -> float:
    return {
        "PASS": 100.0,
        "WARN": 65.0,
        "FAIL": 0.0,
    }.get(status, 40.0)


def _status_from_metric(value: float, threshold: float = 80.0, reverse: bool = False) -> str:
    if reverse:
        return "PASS" if value <= threshold else "WARN"
    return "PASS" if value >= threshold else "WARN"


def _trend_from_delta(delta: float) -> str:
    if delta > 2.0:
        return "improving"
    if delta < -2.0:
        return "declining"
    return "stable"


def _run_dirs(root: Path, marker: str) -> List[Path]:
    if not root.exists():
        return []
    runs = [path for path in root.iterdir() if path.is_dir() and (path / marker).exists()]
    runs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return runs


def _cycle_summary(path: Path) -> Dict[str, Any]:
    payload = _read_json(path / "pilot_cycle_summary.json", {})
    return payload if isinstance(payload, dict) else {}


def _governance_export(path: Path) -> Dict[str, Any]:
    payload = _read_json(path / "pilot_rehearsal_summary.json", {})
    return payload if isinstance(payload, dict) else {}


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    return {
        "trend": _trend_from_delta(delta),
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


class OperationalStabilityService:
    def __init__(self, cycle_root: Optional[Path] = None, export_root: Optional[Path] = None) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.rehearsal_service = OperationalRehearsalService()

    def _cycle_runs(self) -> List[Path]:
        return _run_dirs(self.cycle_root, "pilot_cycle_summary.json")

    def _export_runs(self) -> List[Path]:
        return _run_dirs(self.export_root, "pilot_rehearsal_summary.json")

    def _load_cycle_summaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        for path in self._cycle_runs()[: max(1, int(limit))]:
            payload = _cycle_summary(path)
            if payload:
                payload["evidence_dir"] = str(path)
                summaries.append(payload)
        return summaries

    def _load_export_summaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        for path in self._export_runs()[: max(1, int(limit))]:
            payload = _governance_export(path)
            if payload:
                payload["evidence_dir"] = str(path)
                summaries.append(payload)
        return summaries

    def _cycle_status_score(self, cycle: Dict[str, Any], section: str) -> float:
        evidence = _safe_dict(cycle.get("evidence_pack"))
        section_payload = _safe_dict(evidence.get(section))
        return _score_from_status(_safe_str(section_payload.get("status"), "WARN"))

    def _cycle_readiness(self, cycle: Dict[str, Any]) -> float:
        readiness = _safe_dict(_safe_dict(cycle.get("governance_export")).get("readiness_summary"))
        return _safe_float(readiness.get("readiness_score"), _safe_float(_safe_dict(cycle.get("metrics")).get("readiness_score"), 0.0))

    def _cycle_cadence(self, cycle: Dict[str, Any]) -> float:
        readiness = _safe_dict(_safe_dict(cycle.get("governance_export")).get("readiness_summary"))
        cadence = _safe_dict(readiness.get("cadence"))
        return _safe_float(cadence.get("runs_last_7_days"), 0.0)

    def _cycle_summary_view(self, cycle: Dict[str, Any]) -> Dict[str, Any]:
        readiness = _safe_dict(_safe_dict(cycle.get("governance_export")).get("readiness_summary"))
        readiness_score = self._cycle_readiness(cycle)
        cadence = _safe_dict(readiness.get("cadence"))
        return {
            "cycle_id": _safe_str(cycle.get("cycle_id"), "unknown"),
            "generated_at": _safe_str(cycle.get("generated_at"), _now_iso()),
            "readiness_score": readiness_score,
            "readiness_grade": _safe_str(readiness.get("readiness_grade"), "not_ready"),
            "cadence_runs_last_7_days": _safe_int(cadence.get("runs_last_7_days"), 0),
            "queue_score": self._cycle_status_score(cycle, "queue_stability_evidence"),
            "worker_score": self._cycle_status_score(cycle, "worker_stability_evidence"),
            "telemetry_score": self._cycle_status_score(cycle, "telemetry_health_evidence"),
            "retry_score": self._cycle_status_score(cycle, "retry_recovery_evidence"),
            "rollback_score": self._cycle_status_score(cycle, "rollback_evidence"),
            "operator_score": self._cycle_status_score(cycle, "operator_intervention_summary"),
            "submission_lock_score": self._cycle_status_score(cycle, "submission_lock_verification"),
            "dry_run_score": self._cycle_status_score(cycle, "dry_run_enforcement_verification"),
        }

    def _rehearsal_summary_view(self, rehearsal: Dict[str, Any]) -> Dict[str, Any]:
        readiness = _safe_dict(rehearsal.get("readiness_summary")) or _safe_dict(rehearsal)
        metrics = _safe_dict(readiness.get("metrics"))
        warnings = _safe_dict(readiness.get("warning_threshold_indicators"))
        history = _safe_list(_safe_dict(rehearsal.get("rehearsal_history_summary")).get("runs"))
        latest_run = history[0] if history else {}
        latest_metrics = _safe_dict(latest_run.get("metrics"))
        latest_pack = _safe_dict(rehearsal.get("latest_evidence_pack"))
        latest_drill = _safe_dict(latest_pack.get("drill_outcomes"))
        queue_metric = _safe_float(metrics.get("queue_stability"), 0.0)
        worker_metric = _safe_float(metrics.get("worker_stability"), 0.0)
        telemetry_metric = _safe_float(metrics.get("telemetry_health"), 0.0)
        retry_metric = _safe_float(metrics.get("retry_recovery_success"), 0.0)
        dlq_metric = _safe_float(metrics.get("dlq_escalation_frequency"), 0.0)
        operator_metric = _safe_float(metrics.get("operator_intervention_frequency"), 0.0)
        return {
            "run_id": _safe_str(rehearsal.get("export_id"), _safe_str(latest_pack.get("pack_id"), "unknown")),
            "generated_at": _safe_str(rehearsal.get("generated_at"), _now_iso()),
            "readiness_score": _safe_float(readiness.get("readiness_score"), 0.0),
            "cadence_runs_last_7_days": _safe_int(_safe_dict(readiness.get("cadence")).get("runs_last_7_days"), 0),
            "queue_score": _score_from_status(_safe_str(_safe_dict(rehearsal.get("queue_stability_summary")).get("status"), _status_from_metric(queue_metric))),
            "worker_score": _score_from_status(_safe_str(_safe_dict(latest_pack.get("worker_stability_evidence")).get("status"), _status_from_metric(worker_metric))),
            "telemetry_score": _score_from_status(_safe_str(_safe_dict(rehearsal.get("telemetry_health_summary")).get("status"), _status_from_metric(telemetry_metric))),
            "retry_score": _score_from_status(_safe_str(_safe_dict(latest_pack.get("retry_recovery_evidence")).get("status"), _status_from_metric(retry_metric))),
            "dlq_score": _score_from_status(_safe_str(latest_drill.get("dlq_drill", {}).get("status"), _status_from_metric(dlq_metric, threshold=10.0, reverse=True))),
            "operator_score": _score_from_status(_safe_str(_safe_dict(rehearsal.get("operator_intervention_summary")).get("status"), _status_from_metric(operator_metric, threshold=20.0, reverse=True))),
            "cadence_warning": warnings,
            "metrics": metrics,
            "latest_metrics": latest_metrics,
        }

    def _build_stability_summary(self, cycle_views: List[Dict[str, Any]], rehearsal_views: List[Dict[str, Any]]) -> Dict[str, Any]:
        readiness_values = [view["readiness_score"] for view in cycle_views if view]
        cadence_values = [view["cadence_runs_last_7_days"] for view in cycle_views if view]
        queue_values = [view["queue_score"] for view in cycle_views if view]
        worker_values = [view["worker_score"] for view in cycle_views if view]
        telemetry_values = [view["telemetry_score"] for view in cycle_views if view]
        retry_values = [view["retry_score"] for view in cycle_views if view]
        rollback_values = [view["rollback_score"] for view in cycle_views if view]
        operator_values = [view["operator_score"] for view in cycle_views if view]

        rehearsal_queue_values = [view["queue_score"] for view in rehearsal_views if view]
        rehearsal_worker_values = [view["worker_score"] for view in rehearsal_views if view]
        rehearsal_telemetry_values = [view["telemetry_score"] for view in rehearsal_views if view]
        rehearsal_retry_values = [view["retry_score"] for view in rehearsal_views if view]
        rehearsal_dlq_values = [view["dlq_score"] for view in rehearsal_views if view]
        rehearsal_operator_values = [view["operator_score"] for view in rehearsal_views if view]
        rehearsal_cadence_values = [view["cadence_runs_last_7_days"] for view in rehearsal_views if view]

        readiness_history = _history_points(readiness_values)
        cadence_history = _history_points(cadence_values)
        queue_history = _history_points(queue_values + rehearsal_queue_values)
        worker_history = _history_points(worker_values + rehearsal_worker_values)
        telemetry_history = _history_points(telemetry_values + rehearsal_telemetry_values)
        retry_history = _history_points(retry_values + rehearsal_retry_values)
        dlq_history = _history_points(rehearsal_dlq_values)
        operator_history = _history_points(operator_values + rehearsal_operator_values)
        cadence_rehearsal_history = _history_points(rehearsal_cadence_values)

        stability_score = round(
            mean([
                readiness_history["average"] or 0.0,
                queue_history["average"] or 0.0,
                worker_history["average"] or 0.0,
                telemetry_history["average"] or 0.0,
                retry_history["average"] or 0.0,
                dlq_history["average"] or 0.0,
                operator_history["average"] or 0.0,
            ]),
            2,
        ) if any([readiness_values, queue_values, worker_values, telemetry_values, retry_values, rehearsal_dlq_values, operator_values]) else 0.0

        warning_indicators = {
            "readiness_drift_warning": abs(readiness_history["delta"]) >= 5.0,
            "cadence_drift_warning": abs(cadence_history["delta"]) >= 1.0 or cadence_history["latest"] < 1.0,
            "queue_stability_warning": queue_history["latest"] < 80.0,
            "worker_stability_warning": worker_history["latest"] < 80.0,
            "telemetry_degradation_warning": telemetry_history["latest"] < 80.0,
            "retry_escalation_warning": retry_history["latest"] < 80.0,
            "dlq_frequency_warning": dlq_history["latest"] < 80.0,
            "operator_intervention_warning": operator_history["latest"] < 80.0,
        }

        drift_warnings = [name for name, flag in warning_indicators.items() if flag]
        cadence_compliance = cadence_history["latest"] >= 1.0 and cadence_rehearsal_history["latest"] >= 1.0

        return {
            "status": "ok" if not drift_warnings else "watch",
            "generated_at": _now_iso(),
            "stability_score": stability_score,
            "stability_grade": "stable" if stability_score >= 85.0 else "watch" if stability_score >= 70.0 else "unstable",
            "readiness_drift": readiness_history,
            "cadence_drift": cadence_history,
            "queue_stability_trend": queue_history,
            "worker_stability_trend": worker_history,
            "telemetry_degradation": telemetry_history,
            "retry_escalation_trend": retry_history,
            "dlq_frequency_trend": dlq_history,
            "operator_intervention_trend": operator_history,
            "cadence_compliance": {
                "compliant": cadence_compliance,
                "pilot_cycle_cadence": cadence_history,
                "rehearsal_cadence": cadence_rehearsal_history,
            },
            "drift_warnings": drift_warnings,
            "warning_indicators": warning_indicators,
            "cycle_count": len(cycle_views),
            "rehearsal_count": len(rehearsal_views),
        }

    def list_stability(self, limit: int = 20) -> Dict[str, Any]:
        cycle_summaries = self._load_cycle_summaries(limit=limit)
        rehearsal_summary = self.rehearsal_service.readiness_summary(limit=limit)
        rehearsal_history = self.rehearsal_service.readiness_history(limit=limit)
        rehearsal_views = [self._rehearsal_summary_view(rehearsal_summary)] if rehearsal_summary.get("status") != "not_found" else []
        if rehearsal_history.get("status") != "not_found":
            for item in _safe_list(rehearsal_history.get("runs")):
                item = _safe_dict(item)
                readiness = _safe_float(item.get("readiness_score"), 0.0)
                rehearsal_views.append(
                    {
                        "run_id": _safe_str(item.get("run_id")),
                        "generated_at": _safe_str(item.get("generated_at")),
                        "readiness_score": readiness,
                        "cadence_runs_last_7_days": _safe_int(_safe_dict(rehearsal_history.get("cadence")).get("runs_last_7_days"), 0),
                        "queue_score": _score_from_status("PASS" if _safe_float(_safe_dict(item.get("metrics")).get("queue_stability"), 0.0) >= 80.0 else "WARN"),
                        "worker_score": _score_from_status("PASS" if _safe_float(_safe_dict(item.get("metrics")).get("worker_stability"), 0.0) >= 80.0 else "WARN"),
                        "telemetry_score": _score_from_status("PASS" if _safe_float(_safe_dict(item.get("metrics")).get("telemetry_health"), 0.0) >= 80.0 else "WARN"),
                        "retry_score": _score_from_status("PASS" if _safe_float(_safe_dict(item.get("metrics")).get("retry_recovery_success"), 0.0) >= 80.0 else "WARN"),
                        "dlq_score": _score_from_status("PASS" if _safe_float(_safe_dict(item.get("metrics")).get("dlq_escalation_frequency"), 0.0) <= 10.0 else "WARN"),
                        "operator_score": _score_from_status("PASS" if _safe_float(_safe_dict(item.get("metrics")).get("operator_intervention_frequency"), 0.0) <= 20.0 else "WARN"),
                    }
                )

        cycle_views = [self._cycle_summary_view(cycle) for cycle in cycle_summaries]
        stability = self._build_stability_summary(cycle_views, rehearsal_views)
        latest_cycle = cycle_views[0] if cycle_views else {}
        export_runs = self._load_export_summaries(limit=limit)
        latest_export = export_runs[0] if export_runs else {}

        return {
            "status": stability["status"],
            "latest_cycle": latest_cycle,
            "latest_governance_export": latest_export,
            "stability": stability,
            "cycle_history": cycle_views,
            "rehearsal_history": rehearsal_views,
            "stability_score": stability["stability_score"],
            "stability_grade": stability["stability_grade"],
            "warning_indicators": stability["warning_indicators"],
            "drift_warnings": stability["drift_warnings"],
        }

    def stability_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_stability(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("cycle_history", [])),
            "cycles": response.get("cycle_history", []),
            "rehearsals": response.get("rehearsal_history", []),
            "stability": response.get("stability", {}),
            "warning_indicators": response.get("warning_indicators", {}),
        }

    def latest_stability(self) -> Dict[str, Any]:
        response = self.list_stability(limit=20)
        if not response.get("cycle_history") and not response.get("rehearsal_history"):
            return {
                "status": "not_found",
                "message": "No controlled pilot cycles have been recorded yet.",
                "stability": {},
            }
        return {
            "status": response.get("status", "ok"),
            "latest_cycle": response.get("latest_cycle", {}),
            "stability": response.get("stability", {}),
            "stability_score": response.get("stability_score", 0.0),
            "stability_grade": response.get("stability_grade", "unstable"),
            "warning_indicators": response.get("warning_indicators", {}),
            "drift_warnings": response.get("drift_warnings", []),
        }
