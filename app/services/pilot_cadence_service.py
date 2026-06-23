from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
import json

from app.services.operational_stability_service import OperationalStabilityService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"
CADENCE_WINDOW_DAYS = 7


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


def _window_entries(entries: List[Dict[str, Any]], window_days: int = CADENCE_WINDOW_DAYS) -> List[Dict[str, Any]]:
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


def _governance_export(path: Path) -> Dict[str, Any]:
    payload = _read_json(path / "pilot_rehearsal_summary.json", {})
    return payload if isinstance(payload, dict) else {}


def _component_score(is_compliant: bool, present: bool) -> float:
    if not present:
        return 0.0
    return 100.0 if is_compliant else 65.0


def _grade_from_score(score: float) -> str:
    if score >= 85.0:
        return "on_track"
    if score >= 70.0:
        return "watch"
    return "late"


def _status_from_score(score: float, present: bool = True) -> str:
    if not present:
        return "not_found"
    if score >= 85.0:
        return "PASS"
    if score >= 70.0:
        return "WARN"
    return "FAIL"


class PilotCadenceService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
        cadence_window_days: int = CADENCE_WINDOW_DAYS,
    ) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.cadence_window_days = max(1, cadence_window_days)

    def _cycle_runs(self) -> List[Path]:
        return _run_dirs(self.cycle_root, "pilot_cycle_summary.json")

    def _export_runs(self) -> List[Path]:
        return _run_dirs(self.export_root, "pilot_rehearsal_summary.json")

    def _cycle_views(self, limit: int = 20) -> List[Dict[str, Any]]:
        views: List[Dict[str, Any]] = []
        for path in self._cycle_runs()[: max(1, int(limit))]:
            payload = _cycle_summary(path)
            if not payload:
                continue
            readiness = _safe_dict(_safe_dict(payload.get("governance_export")).get("readiness_summary"))
            generated_at = _safe_str(payload.get("generated_at"), _now_iso())
            views.append(
                {
                    "kind": "pilot_cycle",
                    "id": _safe_str(payload.get("cycle_id"), path.name),
                    "generated_at": generated_at,
                    "age_hours": round(_age_hours(generated_at), 2),
                    "readiness_score": _safe_float(readiness.get("readiness_score"), 0.0),
                    "readiness_grade": _safe_str(readiness.get("readiness_grade"), "watch"),
                    "runs_last_7_days": _safe_int(_safe_dict(readiness.get("cadence")).get("runs_last_7_days"), 0),
                    "average_gap_hours": _safe_float(_safe_dict(readiness.get("cadence")).get("average_gap_hours"), 0.0),
                    "status": _status_from_score(
                        _safe_float(readiness.get("readiness_score"), 0.0),
                        present=True,
                    ),
                }
            )
        return views

    def _governance_views(self, limit: int = 20) -> List[Dict[str, Any]]:
        views: List[Dict[str, Any]] = []
        for path in self._export_runs()[: max(1, int(limit))]:
            payload = _governance_export(path)
            if not payload:
                continue
            readiness = _safe_dict(payload.get("readiness_summary"))
            cadence = _safe_dict(readiness.get("cadence"))
            generated_at = _safe_str(payload.get("generated_at"), _now_iso())
            views.append(
                {
                    "kind": "governance_review",
                    "id": _safe_str(payload.get("export_id"), path.name),
                    "generated_at": generated_at,
                    "age_hours": round(_age_hours(generated_at), 2),
                    "readiness_score": _safe_float(readiness.get("readiness_score"), 0.0),
                    "readiness_grade": _safe_str(readiness.get("readiness_grade"), "watch"),
                    "runs_last_7_days": _safe_int(cadence.get("runs_last_7_days"), 0),
                    "average_gap_hours": _safe_float(cadence.get("average_gap_hours"), 0.0),
                    "status": _status_from_score(
                        _safe_float(readiness.get("readiness_score"), 0.0),
                        present=True,
                    ),
                }
            )
        return views

    def _latest_stability(self) -> Dict[str, Any]:
        try:
            stability_service = OperationalStabilityService(cycle_root=self.cycle_root, export_root=self.export_root)
            return stability_service.latest_stability()
        except Exception:
            return {
                "status": "not_found",
                "stability": {},
                "stability_score": 0.0,
                "stability_grade": "unstable",
                "warning_indicators": {},
                "drift_warnings": [],
            }

    def _stability_history(self) -> Dict[str, Any]:
        try:
            stability_service = OperationalStabilityService(cycle_root=self.cycle_root, export_root=self.export_root)
            return stability_service.stability_history(limit=20)
        except Exception:
            return {"status": "not_found", "count": 0, "cycles": [], "rehearsals": [], "stability": {}, "warning_indicators": {}}

    def _cycle_cadence(self, cycle_views: List[Dict[str, Any]]) -> Dict[str, Any]:
        windowed = _window_entries(cycle_views, self.cadence_window_days)
        latest = cycle_views[0] if cycle_views else {}
        latest_generated_at = _safe_str(latest.get("generated_at"), "")
        latest_dt = _parse_iso(latest_generated_at)
        next_due_at = (latest_dt + timedelta(days=self.cadence_window_days)).isoformat() if latest_dt else ""
        missed_cycle_warning = not windowed or _age_hours(latest_generated_at) > (self.cadence_window_days * 24.0)
        return {
            "kind": "pilot_cycle",
            "status": _status_from_score(100.0 if not missed_cycle_warning else 65.0, present=bool(cycle_views)),
            "cadence_status": "on_track" if not missed_cycle_warning else "missed_cycle_warning",
            "compliant": not missed_cycle_warning and bool(cycle_views),
            "runs_last_7_days": len(windowed),
            "average_gap_hours": _average_gap_hours(windowed),
            "latest_cycle_id": _safe_str(latest.get("id"), ""),
            "latest_run_at": latest_generated_at,
            "next_cycle_due_at": next_due_at,
            "warning_threshold_days": self.cadence_window_days,
            "missed_cycle_warning": missed_cycle_warning,
        }

    def _governance_cadence(self, governance_views: List[Dict[str, Any]]) -> Dict[str, Any]:
        windowed = _window_entries(governance_views, self.cadence_window_days)
        latest = governance_views[0] if governance_views else {}
        latest_generated_at = _safe_str(latest.get("generated_at"), "")
        latest_dt = _parse_iso(latest_generated_at)
        next_due_at = (latest_dt + timedelta(days=self.cadence_window_days)).isoformat() if latest_dt else ""
        overdue_warning = not windowed or _age_hours(latest_generated_at) > (self.cadence_window_days * 24.0)
        return {
            "kind": "governance_review",
            "status": _status_from_score(100.0 if not overdue_warning else 65.0, present=bool(governance_views)),
            "cadence_status": "on_track" if not overdue_warning else "overdue_governance_review_warning",
            "compliant": not overdue_warning and bool(governance_views),
            "runs_last_7_days": len(windowed),
            "average_gap_hours": _average_gap_hours(windowed),
            "latest_export_id": _safe_str(latest.get("id"), ""),
            "latest_review_at": latest_generated_at,
            "next_review_due_at": next_due_at,
            "warning_threshold_days": self.cadence_window_days,
            "overdue_governance_review_warning": overdue_warning,
        }

    def _stability_checkpoint(self, stability: Dict[str, Any]) -> Dict[str, Any]:
        latest_stability = _safe_dict(stability)
        raw = _safe_dict(latest_stability.get("stability"))
        drift_warnings = _safe_list(latest_stability.get("drift_warnings"))
        status = _safe_str(latest_stability.get("status"), "not_found")
        score = _safe_float(latest_stability.get("stability_score"), 0.0)
        return {
            "kind": "stability_checkpoint",
            "status": status if status in {"ok", "watch", "not_found"} else ("ok" if score >= 85.0 else "watch"),
            "cadence_status": "on_track" if score >= 85.0 and not drift_warnings else "warning",
            "compliant": score >= 85.0 and not drift_warnings,
            "latest_generated_at": _safe_str(latest_stability.get("latest_cycle", {}).get("generated_at"), _now_iso()),
            "latest_score": score,
            "latest_grade": _safe_str(latest_stability.get("stability_grade"), "unstable"),
            "drift_warnings": drift_warnings,
            "history_count": _safe_int(latest_stability.get("stability", {}).get("cycle_count"), 0),
            "rehearsal_count": _safe_int(raw.get("rehearsal_count"), 0),
        }

    def _readiness_checkpoints(
        self,
        cycle_views: List[Dict[str, Any]],
        governance_views: List[Dict[str, Any]],
        stability_checkpoint: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        checkpoints: List[Dict[str, Any]] = []
        if cycle_views:
            latest_cycle = cycle_views[0]
            checkpoints.append(
                {
                    "kind": "pilot_cycle",
                    "id": latest_cycle.get("id", ""),
                    "generated_at": latest_cycle.get("generated_at", ""),
                    "age_hours": latest_cycle.get("age_hours", 0.0),
                    "readiness_score": latest_cycle.get("readiness_score", 0.0),
                    "readiness_grade": latest_cycle.get("readiness_grade", "watch"),
                    "status": latest_cycle.get("status", "WARN"),
                }
            )
        if governance_views:
            latest_review = governance_views[0]
            checkpoints.append(
                {
                    "kind": "governance_review",
                    "id": latest_review.get("id", ""),
                    "generated_at": latest_review.get("generated_at", ""),
                    "age_hours": latest_review.get("age_hours", 0.0),
                    "readiness_score": latest_review.get("readiness_score", 0.0),
                    "readiness_grade": latest_review.get("readiness_grade", "watch"),
                    "status": latest_review.get("status", "WARN"),
                }
            )
        checkpoints.append(
            {
                "kind": "stability_checkpoint",
                "id": _safe_str(stability_checkpoint.get("latest_generated_at"), "stability"),
                "generated_at": _safe_str(stability_checkpoint.get("latest_generated_at"), _now_iso()),
                "age_hours": round(_age_hours(stability_checkpoint.get("latest_generated_at")), 2),
                "stability_score": stability_checkpoint.get("latest_score", 0.0),
                "stability_grade": stability_checkpoint.get("latest_grade", "unstable"),
                "status": stability_checkpoint.get("status", "WARN"),
            }
        )
        return checkpoints

    def list_cadence(self, limit: int = 20) -> Dict[str, Any]:
        cycle_views = self._cycle_views(limit=limit)
        governance_views = self._governance_views(limit=limit)
        latest_stability = self._latest_stability()
        stability_history = self._stability_history()
        cycle_cadence = self._cycle_cadence(cycle_views)
        governance_cadence = self._governance_cadence(governance_views)
        stability_checkpoint = self._stability_checkpoint(latest_stability)
        readiness_checkpoints = self._readiness_checkpoints(cycle_views, governance_views, stability_checkpoint)

        component_scores = [
            _component_score(cycle_cadence["compliant"], bool(cycle_views)),
            _component_score(governance_cadence["compliant"], bool(governance_views)),
            _component_score(stability_checkpoint["compliant"], stability_checkpoint["status"] != "not_found"),
        ]
        cadence_score = round(sum(component_scores) / len(component_scores), 2) if component_scores else 0.0
        warning_indicators = {
            "missed_cycle_warning": bool(cycle_cadence["missed_cycle_warning"]),
            "overdue_governance_review_warning": bool(governance_cadence["overdue_governance_review_warning"]),
            "stability_checkpoint_warning": not bool(stability_checkpoint["compliant"]),
            "cadence_compliance_warning": not (cycle_cadence["compliant"] and governance_cadence["compliant"] and stability_checkpoint["compliant"]),
        }
        warnings = [name for name, flag in warning_indicators.items() if flag]
        cadence_grade = _grade_from_score(cadence_score)
        status = "ok" if not warnings else "watch"
        if not cycle_views and not governance_views:
            status = "not_found"

        return {
            "status": status,
            "generated_at": _now_iso(),
            "cadence_score": cadence_score,
            "cadence_grade": cadence_grade,
            "warnings": warnings,
            "warning_indicators": warning_indicators,
            "pilot_cycle_cadence": cycle_cadence,
            "governance_review_cadence": governance_cadence,
            "stability_trend_checkpoints": {
                "kind": "stability",
                "status": stability_checkpoint["status"],
                "latest_score": stability_checkpoint["latest_score"],
                "latest_grade": stability_checkpoint["latest_grade"],
                "latest_generated_at": stability_checkpoint["latest_generated_at"],
                "drift_warnings": stability_checkpoint["drift_warnings"],
                "history_count": _safe_int(stability_history.get("count"), 0),
                "stability_cycle_count": _safe_int(stability_history.get("stability", {}).get("cycle_count"), 0),
                "stability_rehearsal_count": _safe_int(stability_history.get("stability", {}).get("rehearsal_count"), 0),
                "cadence_compliant": bool(stability_checkpoint["compliant"]),
            },
            "readiness_checkpoints": readiness_checkpoints,
            "cycle_history": cycle_views,
            "governance_review_history": governance_views,
            "stability_snapshot": latest_stability,
        }

    def latest_cadence(self) -> Dict[str, Any]:
        response = self.list_cadence(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No controlled pilot cadence data has been recorded yet.",
                "cadence": {},
            }
        return {
            "status": response.get("status", "ok"),
            "latest_cycle": response.get("cycle_history", [{}])[0] if response.get("cycle_history") else {},
            "latest_governance_review": response.get("governance_review_history", [{}])[0] if response.get("governance_review_history") else {},
            "latest_stability": response.get("stability_snapshot", {}),
            "cadence_score": response.get("cadence_score", 0.0),
            "cadence_grade": response.get("cadence_grade", "late"),
            "warnings": response.get("warnings", []),
            "warning_indicators": response.get("warning_indicators", {}),
            "cadence": {
                "pilot_cycle_cadence": response.get("pilot_cycle_cadence", {}),
                "governance_review_cadence": response.get("governance_review_cadence", {}),
                "stability_trend_checkpoints": response.get("stability_trend_checkpoints", {}),
                "readiness_checkpoints": response.get("readiness_checkpoints", []),
            },
        }

    def cadence_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_cadence(limit=limit)
        checkpoints = response.get("readiness_checkpoints", [])
        return {
            "status": response.get("status", "ok"),
            "count": len(checkpoints),
            "cycles": response.get("cycle_history", []),
            "governance_reviews": response.get("governance_review_history", []),
            "checkpoints": checkpoints,
            "cadence": {
                "pilot_cycle_cadence": response.get("pilot_cycle_cadence", {}),
                "governance_review_cadence": response.get("governance_review_cadence", {}),
                "stability_trend_checkpoints": response.get("stability_trend_checkpoints", {}),
            },
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
