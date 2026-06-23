from __future__ import annotations

import json
from statistics import mean
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REHEARSAL_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "rehearsals"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload
    except Exception:
        return default
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text if text else default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return default


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


class OperationalRehearsalService:
    def __init__(self, runtime_dir: Optional[Path] = None) -> None:
        self.runtime_dir = runtime_dir or REHEARSAL_RUNTIME_DIR

    def _run_dirs(self) -> List[Path]:
        if not self.runtime_dir.exists():
            return []
        runs = [path for path in self.runtime_dir.iterdir() if path.is_dir() and (path / "operational_rehearsal_summary.json").exists()]
        runs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return runs

    def _load_run_summary(self, run_dir: Path) -> Dict[str, Any]:
        summary = _read_json(run_dir / "operational_rehearsal_summary.json", {})
        if not isinstance(summary, dict):
            summary = {}
        summary.setdefault("run_id", run_dir.name)
        summary.setdefault("generated_at", _now_iso())
        summary.setdefault("scenario_summaries", [])
        summary.setdefault("scenario_statuses", {})
        summary.setdefault("overall_counts", {"PASS": 0, "WARN": 0, "FAIL": 0})
        summary.setdefault("dry_run_guarantees", {})
        summary.setdefault("environment_contract", {})
        summary["evidence_dir"] = str(run_dir)
        summary["evidence_files"] = self._artifact_files(run_dir)
        summary["timeline"] = self._timeline(summary)
        summary["warning_banners"] = self._warning_banners(summary)
        summary["drill_outcomes"] = self._drill_outcomes(summary)
        summary["operational_health"] = self._operational_health(summary)
        summary["artifact_summary"] = self._artifact_summary(run_dir)
        return summary

    def _artifact_files(self, run_dir: Path) -> List[Dict[str, Any]]:
        files: List[Dict[str, Any]] = []
        for path in sorted(run_dir.rglob("*")):
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except Exception:
                size = 0
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "relative_path": str(path.relative_to(run_dir)),
                    "size_bytes": size,
                }
            )
        return files

    def _artifact_summary(self, run_dir: Path) -> Dict[str, Any]:
        files = self._artifact_files(run_dir)
        total_size = sum(_safe_int(entry.get("size_bytes"), 0) for entry in files)
        return {
            "artifact_count": len(files),
            "total_size_bytes": total_size,
            "has_summary": (run_dir / "operational_rehearsal_summary.json").exists(),
            "has_environment_contract": (run_dir / "environment_contract.json").exists(),
        }

    def _timeline(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        timeline: List[Dict[str, Any]] = []
        for index, scenario in enumerate(summary.get("scenario_summaries") or [], start=1):
            if not isinstance(scenario, dict):
                continue
            timeline.append(
                {
                    "index": index,
                    "scenario": _safe_str(scenario.get("name"), f"scenario-{index}"),
                    "status": _safe_str(scenario.get("status"), "unknown"),
                    "warnings": _safe_int(scenario.get("warnings"), 0),
                    "failures": _safe_int(scenario.get("failures"), 0),
                    "checks": _safe_int(scenario.get("checks"), 0),
                    "evidence_dir": _safe_str(scenario.get("evidence_dir")),
                }
            )
        return timeline

    def _drill_outcomes(self, summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        statuses = summary.get("scenario_statuses") if isinstance(summary.get("scenario_statuses"), dict) else {}
        mapping = {
            "normal_rfq": "normal_rfq",
            "retry_rehearsal": "retry_drill",
            "queue_congestion_rehearsal": "queue_drill",
            "worker_recovery_rehearsal": "worker_recovery_drill",
            "dead_letter_rehearsal": "dlq_drill",
            "rollback_rehearsal": "rollback_drill",
            "telemetry_validation_rehearsal": "telemetry_validation",
        }
        outcomes: Dict[str, Dict[str, Any]] = {}
        for scenario_name, label in mapping.items():
            outcomes[label] = {
                "scenario": scenario_name,
                "status": _safe_str(statuses.get(scenario_name), "unknown"),
                "pass": statuses.get(scenario_name) == "PASS",
                "warn": statuses.get(scenario_name) == "WARN",
                "fail": statuses.get(scenario_name) == "FAIL",
            }
        return outcomes

    def _warning_banners(self, summary: Dict[str, Any]) -> List[str]:
        counts = summary.get("overall_counts") if isinstance(summary.get("overall_counts"), dict) else {}
        env_contract = summary.get("environment_contract") if isinstance(summary.get("environment_contract"), dict) else {}
        dry_run = summary.get("dry_run_guarantees") if isinstance(summary.get("dry_run_guarantees"), dict) else {}
        banners: List[str] = []
        if _safe_int(counts.get("WARN"), 0):
            banners.append(f"Rehearsal completed with {counts.get('WARN')} warning(s).")
        if _safe_int(counts.get("FAIL"), 0):
            banners.append(f"Rehearsal completed with {counts.get('FAIL')} failure(s).")
        if dry_run and not all(dry_run.get(name) is False for name in ("live_submissions", "production_queues", "production_databases", "irreversible_operations")):
            banners.append("Dry-run guarantees are not fully enforced in the latest rehearsal summary.")
        if not _safe_str(env_contract.get("path")):
            banners.append("Environment contract snapshot is missing from the latest rehearsal summary.")
        return banners

    def _operational_health(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        counts = summary.get("overall_counts") if isinstance(summary.get("overall_counts"), dict) else {}
        healthy = _safe_int(counts.get("FAIL"), 0) == 0 and _safe_int(counts.get("WARN"), 0) == 0
        return {
            "status": "ok" if healthy else "degraded",
            "healthy": healthy,
            "pass_count": _safe_int(counts.get("PASS"), 0),
            "warn_count": _safe_int(counts.get("WARN"), 0),
            "fail_count": _safe_int(counts.get("FAIL"), 0),
        }

    def _scenario_lookup(self, summary: Dict[str, Any]) -> Dict[str, str]:
        statuses = summary.get("scenario_statuses") if isinstance(summary.get("scenario_statuses"), dict) else {}
        if not isinstance(statuses, dict):
            return {}
        return {str(key): _safe_str(value, "unknown") for key, value in statuses.items()}

    def _score_component(self, status: str) -> float:
        if status == "PASS":
            return 100.0
        if status == "WARN":
            return 60.0
        if status == "FAIL":
            return 0.0
        return 40.0

    def _readiness_metrics(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        scenarios = self._scenario_lookup(summary)
        total_scenarios = len(scenarios)
        pass_scenarios = sum(1 for status in scenarios.values() if status == "PASS")
        warn_scenarios = sum(1 for status in scenarios.values() if status == "WARN")
        fail_scenarios = sum(1 for status in scenarios.values() if status == "FAIL")

        retry_status = scenarios.get("retry_rehearsal", "unknown")
        queue_status = scenarios.get("queue_congestion_rehearsal", "unknown")
        worker_status = scenarios.get("worker_recovery_rehearsal", "unknown")
        dlq_status = scenarios.get("dead_letter_rehearsal", "unknown")
        rollback_status = scenarios.get("rollback_rehearsal", "unknown")
        telemetry_status = scenarios.get("telemetry_validation_rehearsal", "unknown")

        rehearsal_success_rate = round((pass_scenarios / max(total_scenarios, 1)) * 100.0, 2)
        retry_recovery_success = self._score_component(retry_status)
        rollback_success = self._score_component(rollback_status)
        queue_stability = self._score_component(queue_status)
        worker_stability = self._score_component(worker_status)
        telemetry_health = self._score_component(telemetry_status)
        dlq_escalation_frequency = round((1.0 if dlq_status in {"WARN", "FAIL"} else 0.0) * 100.0, 2)
        operator_intervention_frequency = round(((warn_scenarios + fail_scenarios) / max(total_scenarios, 1)) * 100.0, 2)

        readiness_score = round(
            (
                rehearsal_success_rate * 0.35
                + retry_recovery_success * 0.10
                + rollback_success * 0.10
                + queue_stability * 0.15
                + worker_stability * 0.15
                + telemetry_health * 0.10
                + (100.0 - dlq_escalation_frequency) * 0.025
                + (100.0 - operator_intervention_frequency) * 0.025
            ),
            2,
        )

        return {
            "readiness_score": readiness_score,
            "readiness_grade": "ready" if readiness_score >= 85 else "watch" if readiness_score >= 70 else "not_ready",
            "metrics": {
                "rehearsal_success_rate": rehearsal_success_rate,
                "retry_recovery_success": retry_recovery_success,
                "rollback_success": rollback_success,
                "queue_stability": queue_stability,
                "worker_stability": worker_stability,
                "telemetry_health": telemetry_health,
                "dlq_escalation_frequency": dlq_escalation_frequency,
                "operator_intervention_frequency": operator_intervention_frequency,
            },
            "warning_threshold_indicators": {
                "score_below_threshold": readiness_score < 70.0,
                "success_rate_below_threshold": rehearsal_success_rate < 80.0,
                "retry_recovery_below_threshold": retry_recovery_success < 80.0,
                "rollback_below_threshold": rollback_success < 80.0,
                "queue_stability_below_threshold": queue_stability < 80.0,
                "worker_stability_below_threshold": worker_stability < 80.0,
                "telemetry_health_below_threshold": telemetry_health < 80.0,
                "dlq_escalation_above_threshold": dlq_escalation_frequency > 10.0,
                "operator_intervention_above_threshold": operator_intervention_frequency > 20.0,
            },
            "thresholds": {
                "readiness_score": 70.0,
                "success_rate": 80.0,
                "drill_success": 80.0,
                "dlq_escalation_frequency": 10.0,
                "operator_intervention_frequency": 20.0,
            },
        }

    def _readiness_trend(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores = [float(item.get("readiness_score") or 0.0) for item in history if isinstance(item, dict)]
        generated = [item for item in history if isinstance(item, dict) and _parse_iso(item.get("generated_at"))]
        if not scores:
            return {
                "trend": "unknown",
                "delta": 0.0,
                "average_score": 0.0,
                "score_history": [],
            }
        latest = scores[0]
        previous = scores[1] if len(scores) > 1 else latest
        delta = round(latest - previous, 2)
        trend = "improving" if delta > 2 else "declining" if delta < -2 else "stable"
        score_history = [
            {
                "run_id": _safe_str(item.get("run_id")),
                "generated_at": _safe_str(item.get("generated_at")),
                "readiness_score": _safe_float(item.get("readiness_score"), 0.0),
                "readiness_grade": _safe_str(item.get("readiness_grade"), "unknown"),
            }
            for item in history
        ]
        average_score = round(mean(scores), 2) if scores else 0.0
        return {
            "trend": trend,
            "delta": delta,
            "average_score": average_score,
            "score_history": score_history,
            "latest_score": latest,
            "previous_score": previous,
            "points": len(scores),
            "points_with_timestamp": len(generated),
        }

    def _cadence(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        timestamps = [dt for dt in (_parse_iso(item.get("generated_at")) for item in history) if dt is not None]
        timestamps.sort(reverse=True)
        if len(timestamps) < 2:
            return {
                "runs_total": len(history),
                "runs_last_7_days": len(history),
                "average_gap_hours": 0.0,
                "most_recent_run_at": _safe_str(history[0].get("generated_at")) if history else "",
                "previous_run_at": _safe_str(history[1].get("generated_at")) if len(history) > 1 else "",
            }
        gaps = []
        for previous, current in zip(timestamps, timestamps[1:]):
            gaps.append(max(0.0, (previous - current).total_seconds() / 3600.0))
        seven_day_cutoff = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=7)
        runs_last_7_days = sum(1 for timestamp in timestamps if timestamp >= seven_day_cutoff)
        return {
            "runs_total": len(history),
            "runs_last_7_days": runs_last_7_days,
            "average_gap_hours": round(mean(gaps), 2) if gaps else 0.0,
            "most_recent_run_at": _safe_str(history[0].get("generated_at")) if history else "",
            "previous_run_at": _safe_str(history[1].get("generated_at")) if len(history) > 1 else "",
        }

    def _build_readiness_summary(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not runs:
            return {
                "status": "not_found",
                "message": "No rehearsal evidence has been recorded yet.",
                "readiness_score": 0.0,
                "readiness_grade": "not_ready",
                "metrics": {
                    "rehearsal_success_rate": 0.0,
                    "retry_recovery_success": 0.0,
                    "rollback_success": 0.0,
                    "queue_stability": 0.0,
                    "worker_stability": 0.0,
                    "telemetry_health": 0.0,
                    "dlq_escalation_frequency": 0.0,
                    "operator_intervention_frequency": 0.0,
                },
                "warning_threshold_indicators": {},
                "thresholds": {},
                "trend_summary": {"trend": "unknown", "delta": 0.0, "average_score": 0.0, "score_history": []},
                "cadence": {"runs_total": 0, "runs_last_7_days": 0, "average_gap_hours": 0.0, "most_recent_run_at": "", "previous_run_at": ""},
                "history": [],
            }
        history = []
        for run in runs:
            metrics = self._readiness_metrics(run)
            history.append(
                {
                    "run_id": run.get("run_id", ""),
                    "generated_at": run.get("generated_at", ""),
                    "readiness_score": metrics["readiness_score"],
                    "readiness_grade": metrics["readiness_grade"],
                    "metrics": metrics["metrics"],
                    "warning_threshold_indicators": metrics["warning_threshold_indicators"],
                    "timeline": run.get("timeline", []),
                    "overall_counts": run.get("overall_counts", {}),
                }
            )
        latest = history[0]
        readiness = self._readiness_metrics(runs[0])
        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "latest_run_id": latest.get("run_id", ""),
            "readiness_score": readiness["readiness_score"],
            "readiness_grade": readiness["readiness_grade"],
            "metrics": readiness["metrics"],
            "warning_threshold_indicators": readiness["warning_threshold_indicators"],
            "thresholds": readiness["thresholds"],
            "trend_summary": self._readiness_trend(history),
            "cadence": self._cadence(runs),
            "history": history,
        }

    def list_rehearsals(self, limit: int = 20) -> Dict[str, Any]:
        runs = [self._load_run_summary(path) for path in self._run_dirs()[: max(1, int(limit))]]
        latest = runs[0] if runs else {}
        return {
            "status": "ok",
            "count": len(runs),
            "runs": runs,
            "latest_run_id": latest.get("run_id", ""),
            "latest_generated_at": latest.get("generated_at", ""),
        }

    def readiness_summary(self, limit: int = 20) -> Dict[str, Any]:
        runs = [self._load_run_summary(path) for path in self._run_dirs()[: max(1, int(limit))]]
        return self._build_readiness_summary(runs)

    def readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        runs = [self._load_run_summary(path) for path in self._run_dirs()[: max(1, int(limit))]]
        readiness = self._build_readiness_summary(runs)
        return {
            "status": readiness.get("status", "ok"),
            "count": len(readiness.get("history", [])),
            "runs": readiness.get("history", []),
            "trend_summary": readiness.get("trend_summary", {}),
            "cadence": readiness.get("cadence", {}),
            "warning_threshold_indicators": readiness.get("warning_threshold_indicators", {}),
        }

    def latest_rehearsal(self) -> Dict[str, Any]:
        runs = self._run_dirs()
        if not runs:
            return {
                "status": "not_found",
                "message": "No rehearsal evidence has been recorded yet.",
                "run": {},
                "timeline": [],
                "warning_banners": ["No rehearsal evidence has been recorded yet."],
                "operational_health": {"status": "unknown", "healthy": False, "pass_count": 0, "warn_count": 0, "fail_count": 0},
                "drill_outcomes": {},
                "artifact_summary": {"artifact_count": 0, "total_size_bytes": 0, "has_summary": False, "has_environment_contract": False},
            }
        run = self._load_run_summary(runs[0])
        return {
            "status": "ok",
            "run": run,
            "run_id": run.get("run_id", ""),
            "generated_at": run.get("generated_at", ""),
            "timeline": run.get("timeline", []),
            "warning_banners": run.get("warning_banners", []),
            "operational_health": run.get("operational_health", {}),
            "drill_outcomes": run.get("drill_outcomes", {}),
            "artifact_summary": run.get("artifact_summary", {}),
            "readiness": self._build_readiness_summary([run]),
        }

    def get_rehearsal(self, run_id: str) -> Dict[str, Any]:
        target = self.runtime_dir / str(run_id)
        summary_file = target / "operational_rehearsal_summary.json"
        if not summary_file.exists():
            return {
                "status": "not_found",
                "run_id": run_id,
                "message": "Rehearsal evidence run was not found.",
            }
        run = self._load_run_summary(target)
        return {
            "status": "ok",
            "run": run,
            "run_id": run.get("run_id", run_id),
            "generated_at": run.get("generated_at", ""),
            "timeline": run.get("timeline", []),
            "warning_banners": run.get("warning_banners", []),
            "operational_health": run.get("operational_health", {}),
            "drill_outcomes": run.get("drill_outcomes", {}),
            "artifact_summary": run.get("artifact_summary", {}),
        }
