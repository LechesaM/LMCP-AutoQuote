from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"
REVIEW_WINDOW_DAYS = 7


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


def _priority_status(*statuses: str) -> str:
    status_order = {"FAIL": 0, "WARN": 1, "PASS": 2, "ok": 2, "watch": 1, "not_found": -1}
    current = "PASS"
    for status in statuses:
        if status_order.get(status, 1) < status_order.get(current, 1):
            current = status
    return current


class PilotReviewBoardService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
        review_window_days: int = REVIEW_WINDOW_DAYS,
    ) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.review_window_days = max(1, review_window_days)

    def _cycle_runs(self) -> List[Path]:
        return _run_dirs(self.cycle_root, "pilot_cycle_summary.json")

    def _export_runs(self) -> List[Path]:
        return _run_dirs(self.export_root, "pilot_rehearsal_summary.json")

    def _review_session(self, export: Dict[str, Any], cycle: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        readiness = _safe_dict(export.get("readiness_summary"))
        cadence = _safe_dict(readiness.get("cadence"))
        section = _safe_dict(export.get("governance_review_section"))
        signoff = _safe_dict(export.get("operator_sign_off_section"))
        no_go = _safe_dict(export.get("no_go_condition_summary"))
        lock = _safe_dict(export.get("submission_lock_verification"))
        dry_run = _safe_dict(export.get("dry_run_enforcement_verification"))
        latest_pack = _safe_dict(export.get("latest_evidence_pack"))
        trends = _safe_dict(export.get("PASS/WARN/FAIL_trends"))
        summary_counts = _safe_dict(export.get("summary_counts"))
        review_items = _safe_list(section.get("items"))
        operator_items = _safe_list(signoff.get("items"))
        outstanding_actions = [
            {
                "source": "governance_review",
                "item": _safe_str(item.get("item"), "Review item"),
                "status": _safe_str(item.get("status"), "UNKNOWN"),
            }
            for item in review_items
            if _safe_str(item.get("status"), "PASS") != "PASS"
        ]
        outstanding_actions.extend(
            {
                "source": "operator_sign_off",
                "item": _safe_str(item.get("item"), "Sign-off item"),
                "status": _safe_str(item.get("status"), "UNKNOWN"),
            }
            for item in operator_items
            if _safe_str(item.get("status"), "PASS") != "PASS"
        )
        unresolved_exceptions = [
            {
                "type": "no_go_indicator",
                "value": _safe_str(indicator, "unknown"),
            }
            for indicator in _safe_list(no_go.get("indicators"))
        ]
        if _safe_str(no_go.get("status"), "PASS") != "PASS":
            unresolved_exceptions.append({"type": "no_go_status", "value": _safe_str(no_go.get("status"), "UNKNOWN")})

        escalation_items = [
            {
                "type": "review_exception",
                "value": entry["item"],
                "status": entry["status"],
            }
            for entry in outstanding_actions
        ]
        escalation_items.extend(unresolved_exceptions)

        review_status = "ok"
        if outstanding_actions or unresolved_exceptions or _safe_str(no_go.get("status"), "PASS") != "PASS":
            review_status = "watch"
        if _safe_float(readiness.get("readiness_score"), 0.0) < 85.0:
            review_status = "watch"
        if _safe_str(lock.get("status"), "PASS") != "PASS" or _safe_str(dry_run.get("status"), "PASS") != "PASS":
            review_status = "watch"

        cadence_status = "on_track"
        if _safe_int(cadence.get("runs_last_7_days"), 0) <= 0 or _safe_float(cadence.get("average_gap_hours"), 0.0) > float(self.review_window_days * 24):
            cadence_status = "overdue"

        return {
            "kind": "review_session",
            "review_id": _safe_str(export.get("export_id"), "unknown"),
            "cycle_id": _safe_str(_safe_dict(cycle).get("cycle_id"), ""),
            "generated_at": _safe_str(export.get("generated_at"), _now_iso()),
            "age_hours": round(_age_hours(export.get("generated_at")), 2),
            "review_board_status": review_status,
            "readiness_score": _safe_float(readiness.get("readiness_score"), 0.0),
            "readiness_grade": _safe_str(readiness.get("readiness_grade"), "watch"),
            "readiness_trend": _safe_str(_safe_dict(readiness.get("trend_summary")).get("trend"), "stable"),
            "governance_review_cadence": {
                "status": cadence_status,
                "runs_last_7_days": _safe_int(cadence.get("runs_last_7_days"), 0),
                "average_gap_hours": _safe_float(cadence.get("average_gap_hours"), 0.0),
                "most_recent_run_at": _safe_str(cadence.get("most_recent_run_at"), ""),
                "previous_run_at": _safe_str(cadence.get("previous_run_at"), ""),
                "runs_total": _safe_int(cadence.get("runs_total"), 0),
                "window_days": self.review_window_days,
            },
            "pilot_authorization_recommendation": _safe_str(export.get("pilot_authorization_recommendation"), "review_required"),
            "submission_lock_status": _safe_str(lock.get("status"), "UNKNOWN"),
            "dry_run_status": _safe_str(dry_run.get("status"), "UNKNOWN"),
            "no_go_status": _safe_str(no_go.get("status"), "UNKNOWN"),
            "no_go_indicators": _safe_list(no_go.get("indicators")),
            "review_guidance": _safe_list(section.get("guidance")),
            "sign_off_guidance": _safe_list(signoff.get("guidance")),
            "outstanding_governance_actions": outstanding_actions,
            "unresolved_operational_exceptions": unresolved_exceptions,
            "escalation_review_tracking": {
                "count": len(escalation_items),
                "items": escalation_items,
                "status": "PASS" if not escalation_items else "WARN",
            },
            "institutional_review_summary": {
                "session_count": 1,
                "latest_readiness_score": _safe_float(readiness.get("readiness_score"), 0.0),
                "latest_readiness_grade": _safe_str(readiness.get("readiness_grade"), "watch"),
                "latest_summary_counts": {
                    "PASS": _safe_int(summary_counts.get("PASS"), 0),
                    "WARN": _safe_int(summary_counts.get("WARN"), 0),
                    "FAIL": _safe_int(summary_counts.get("FAIL"), 0),
                },
                "latest_trend": _safe_str(_safe_dict(readiness.get("trend_summary")).get("trend"), "stable"),
                "review_guidance_count": len(_safe_list(section.get("guidance"))),
                "sign_off_guidance_count": len(_safe_list(signoff.get("guidance"))),
                "latest_evidence_pack_id": _safe_str(latest_pack.get("pack_id"), ""),
                "review_board_status": review_status,
            },
            "summary_counts": {
                "PASS": _safe_int(summary_counts.get("PASS"), 0),
                "WARN": _safe_int(summary_counts.get("WARN"), 0),
                "FAIL": _safe_int(summary_counts.get("FAIL"), 0),
            },
            "trend_counts": {
                "PASS": _safe_int(_safe_dict(trends.get("summary")).get("PASS"), 0),
                "WARN": _safe_int(_safe_dict(trends.get("summary")).get("WARN"), 0),
                "FAIL": _safe_int(_safe_dict(trends.get("summary")).get("FAIL"), 0),
            },
            "checks": {
                "submission_lock_verified": _safe_str(lock.get("status"), "UNKNOWN") == "PASS",
                "dry_run_verified": _safe_str(dry_run.get("status"), "UNKNOWN") == "PASS",
                "no_go_clear": _safe_str(no_go.get("status"), "UNKNOWN") == "PASS",
            },
        }

    def _sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        sessions: List[Dict[str, Any]] = []
        exports = self._export_runs()[: max(1, int(limit))]
        cycles = self._cycle_runs()[: max(1, int(limit))]
        for index, path in enumerate(exports):
            export = _governance_export(path)
            if not export:
                continue
            cycle_payload = _cycle_summary(cycles[index]) if index < len(cycles) else {}
            session = self._review_session(export, cycle_payload)
            session["source_paths"] = {
                "governance_export": str(path),
                "pilot_cycle": str(self.cycle_root / _safe_str(session.get("cycle_id"), "")) if session.get("cycle_id") else "",
            }
            sessions.append(session)
        return sessions

    def list_review_board(self, limit: int = 20) -> Dict[str, Any]:
        sessions = self._sessions(limit=limit)
        latest = sessions[0] if sessions else {}
        windowed = _window_entries(sessions, self.review_window_days)
        cadence_runs = len(windowed)
        cadence_average = _average_gap_hours(windowed)
        warnings = [
            "missing_review_history" if not sessions else "",
            "overdue_governance_review_warning" if cadence_runs <= 0 or cadence_average > float(self.review_window_days * 24) else "",
        ]
        warnings.extend(
            [
                "unresolved_operational_exceptions" if _safe_int(latest.get("escalation_review_tracking", {}).get("count"), 0) > 0 else "",
                "outstanding_governance_actions" if _safe_list(latest.get("outstanding_governance_actions")) else "",
                "no_go_warning" if _safe_str(latest.get("no_go_status"), "PASS") != "PASS" else "",
                "submission_lock_warning" if _safe_str(latest.get("submission_lock_status"), "PASS") != "PASS" else "",
                "dry_run_warning" if _safe_str(latest.get("dry_run_status"), "PASS") != "PASS" else "",
            ]
        )
        warnings = [warning for warning in warnings if warning]
        review_board_status = "not_found" if not sessions else ("ok" if not warnings else "watch")
        readiness_score = _safe_float(latest.get("readiness_score"), 0.0)
        review_board_score = round(
            mean([
                readiness_score if sessions else 0.0,
                100.0 if not latest.get("outstanding_governance_actions") else 65.0,
                100.0 if not latest.get("unresolved_operational_exceptions") else 65.0,
                100.0 if latest.get("checks", {}).get("submission_lock_verified") else 65.0,
                100.0 if latest.get("checks", {}).get("dry_run_verified") else 65.0,
            ]),
            2,
        ) if sessions else 0.0
        return {
            "status": review_board_status,
            "generated_at": _now_iso(),
            "review_board_score": review_board_score,
            "review_board_grade": "institutional_ready" if review_board_score >= 85.0 else "watch",
            "review_board_status": review_board_status,
            "latest_session": latest,
            "review_board_history": sessions,
            "governance_review_history": sessions,
            "review_board_cadence": {
                "status": "on_track" if cadence_runs > 0 and cadence_average <= float(self.review_window_days * 24) else "overdue",
                "runs_last_7_days": cadence_runs,
                "average_gap_hours": cadence_average,
                "most_recent_review_at": _safe_str(latest.get("generated_at"), ""),
                "previous_review_at": _safe_str(sessions[1].get("generated_at"), "") if len(sessions) > 1 else "",
                "runs_total": len(sessions),
                "window_days": self.review_window_days,
            },
            "outstanding_governance_actions": latest.get("outstanding_governance_actions", []),
            "unresolved_operational_exceptions": latest.get("unresolved_operational_exceptions", []),
            "escalation_review_tracking": latest.get("escalation_review_tracking", {"count": 0, "items": [], "status": "PASS"}),
            "no_go_review_history": [
                {
                    "review_id": session.get("review_id", ""),
                    "generated_at": session.get("generated_at", ""),
                    "status": session.get("no_go_status", "UNKNOWN"),
                    "indicators": session.get("no_go_indicators", []),
                }
                for session in sessions
            ],
            "readiness_review_history": [
                {
                    "review_id": session.get("review_id", ""),
                    "generated_at": session.get("generated_at", ""),
                    "readiness_score": session.get("readiness_score", 0.0),
                    "readiness_grade": session.get("readiness_grade", "watch"),
                    "trend": session.get("readiness_trend", "stable"),
                }
                for session in sessions
            ],
            "institutional_review_summary": {
                "session_count": len(sessions),
                "latest_review_id": _safe_str(latest.get("review_id"), ""),
                "latest_readiness_score": readiness_score,
                "latest_readiness_grade": _safe_str(latest.get("readiness_grade"), "watch"),
                "latest_recommendation": _safe_str(latest.get("pilot_authorization_recommendation"), "review_required"),
                "latest_summary_counts": _safe_dict(latest.get("summary_counts")),
                "latest_trend_counts": _safe_dict(latest.get("trend_counts")),
                "review_guidance_count": len(_safe_list(latest.get("review_guidance", []))),
                "sign_off_guidance_count": len(_safe_list(latest.get("sign_off_guidance", []))),
                "review_board_status": review_board_status,
            },
            "warning_indicators": {
                "missing_review_history": not bool(sessions),
                "overdue_governance_review_warning": cadence_runs <= 0 or cadence_average > float(self.review_window_days * 24),
                "outstanding_governance_actions_warning": bool(latest.get("outstanding_governance_actions")),
                "unresolved_operational_exceptions_warning": bool(latest.get("unresolved_operational_exceptions")),
                "no_go_warning": _safe_str(latest.get("no_go_status"), "PASS") != "PASS",
                "submission_lock_warning": _safe_str(latest.get("submission_lock_status"), "PASS") != "PASS",
                "dry_run_warning": _safe_str(latest.get("dry_run_status"), "PASS") != "PASS",
            },
            "warnings": warnings,
        }

    def latest_review_board(self) -> Dict[str, Any]:
        response = self.list_review_board(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No governance review board history has been recorded yet.",
                "review_board": {},
            }
        return {
            "status": response.get("status", "ok"),
            "latest_session": response.get("latest_session", {}),
            "review_board_score": response.get("review_board_score", 0.0),
            "review_board_grade": response.get("review_board_grade", "watch"),
            "review_board_status": response.get("review_board_status", "watch"),
            "review_board_cadence": response.get("review_board_cadence", {}),
            "outstanding_governance_actions": response.get("outstanding_governance_actions", []),
            "unresolved_operational_exceptions": response.get("unresolved_operational_exceptions", []),
            "escalation_review_tracking": response.get("escalation_review_tracking", {}),
            "institutional_review_summary": response.get("institutional_review_summary", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def review_board_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_review_board(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("review_board_history", [])),
            "review_board_history": response.get("review_board_history", []),
            "governance_review_history": response.get("governance_review_history", []),
            "no_go_review_history": response.get("no_go_review_history", []),
            "readiness_review_history": response.get("readiness_review_history", []),
            "review_board_cadence": response.get("review_board_cadence", {}),
            "institutional_review_summary": response.get("institutional_review_summary", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
