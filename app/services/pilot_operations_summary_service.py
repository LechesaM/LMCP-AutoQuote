from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import OperationalExceptionService, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.operational_remediation_service import OperationalRemediationService
from app.services.operational_stability_service import OperationalStabilityService
from app.services.pilot_cadence_service import PilotCadenceService
from app.services.pilot_progression_service import PilotProgressionService
from app.services.pilot_review_board_service import PilotReviewBoardService
from app.services.recurring_pilot_cycle_service import RecurringPilotCycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_to_score(status: Any) -> float:
    normalized = _safe_str(status, "WARN").lower()
    return {
        "pass": 100.0,
        "ok": 100.0,
        "warn": 65.0,
        "watch": 65.0,
        "fail": 0.0,
        "blocked": 0.0,
        "not_found": 0.0,
    }.get(normalized, 40.0)


def _score_to_status(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _is_watch_state(value: Any) -> bool:
    status = _safe_str(value, "").lower()
    return status in {"watch", "warn", "fail", "blocked"}


class PilotOperationsSummaryService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
    ) -> None:
        cycle_root = cycle_root or PILOT_CYCLE_ROOT
        export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.review_board = PilotReviewBoardService(cycle_root=cycle_root, export_root=export_root)
        self.remediation = OperationalRemediationService(cycle_root=cycle_root, export_root=export_root)
        self.progression = PilotProgressionService(cycle_root=cycle_root, export_root=export_root)
        self.exceptions = OperationalExceptionService(cycle_root=cycle_root, export_root=export_root)
        self.cadence = PilotCadenceService(cycle_root=cycle_root, export_root=export_root)
        self.stability = OperationalStabilityService(cycle_root=cycle_root, export_root=export_root)
        self.recurring_cycles = RecurringPilotCycleService(cycle_root=cycle_root)

    def _current_surfaces(self) -> Dict[str, Dict[str, Any]]:
        return {
            "review_board": self.review_board.latest_review_board(),
            "remediation": self.remediation.latest_remediation(),
            "progression": self.progression.latest_progression(),
            "exceptions": self.exceptions.latest_exceptions(),
            "cadence": self.cadence.latest_cadence(),
            "stability": self.stability.latest_stability(),
            "recurring": self.recurring_cycles.latest_recurring_cycles(),
        }

    def _history_entries(self, limit: int = 20) -> List[Dict[str, Any]]:
        sessions = _safe_list(self.review_board.review_board_history(limit=limit).get("review_board_history", []))
        entries: List[Dict[str, Any]] = []
        for session in sessions:
            progression = self.progression.latest_progression()
            remediation = self.remediation.latest_remediation()
            exceptions = self.exceptions.latest_exceptions()
            cadence = self.cadence.latest_cadence()
            stability = self.stability.latest_stability()
            recurring = self.recurring_cycles.latest_recurring_cycles()
            readiness = _safe_float(session.get("readiness_score"), 0.0)
            review_score = _safe_float(session.get("review_board_score"), 0.0)
            remediation_score = 100.0 if _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0) == 0 else 60.0
            exception_score = 100.0 if _safe_int(_safe_dict(exceptions.get("exception_summary")).get("open_exception_count"), 0) == 0 else 60.0
            cadence_score = 100.0 if _safe_str(_safe_dict(cadence.get("latest")).get("status"), "PASS").upper() == "PASS" else 65.0
            progression_score = _safe_float(progression.get("progression_score"), 0.0)
            stability_score = _safe_float(stability.get("stability_score"), 0.0)
            recurring_score = _safe_float(recurring.get("score"), 0.0)
            consolidated_score = round(
                mean([
                    readiness,
                    review_score,
                    remediation_score,
                    exception_score,
                    cadence_score,
                    progression_score,
                    stability_score,
                    recurring_score,
                ]),
                2,
            )
            entries.append(
                {
                    "summary_id": f"{_safe_str(session.get('review_id'), 'review')}:summary",
                    "review_id": _safe_str(session.get("review_id"), ""),
                    "cycle_id": _safe_str(session.get("cycle_id"), ""),
                    "generated_at": _safe_str(session.get("generated_at"), _now_iso()),
                    "readiness_status": _safe_str(session.get("review_board_status"), "watch"),
                    "stability_status": _safe_str(stability.get("status"), "watch"),
                    "remediation_status": _safe_str(remediation.get("remediation_status"), "watch"),
                    "progression_status": _safe_str(progression.get("progression_status"), "watch"),
                    "no_go_status": _safe_str(session.get("no_go_status"), "UNKNOWN"),
                    "cadence_status": _safe_str(_safe_dict(cadence.get("latest")).get("cadence_status"), "unknown"),
                    "exception_status": _safe_str(exceptions.get("exception_status"), "watch"),
                    "governance_review_status": _safe_str(session.get("review_board_status"), "watch"),
                    "consolidated_governance_score": consolidated_score,
                    "consolidated_watch_indicators": {
                        "readiness_watch": _safe_str(session.get("review_board_status"), "watch") != "ok",
                        "stability_watch": _safe_str(stability.get("status"), "watch") != "ok",
                        "remediation_watch": _safe_str(remediation.get("remediation_status"), "watch") != "ok",
                        "progression_watch": _safe_str(progression.get("progression_status"), "watch") != "ok",
                        "no_go_watch": _safe_str(session.get("no_go_status"), "PASS") != "PASS",
                        "cadence_watch": _safe_str(_safe_dict(cadence.get("latest")).get("cadence_status"), "on_track") != "on_track",
                        "exception_watch": _safe_str(exceptions.get("exception_status"), "watch") != "ok",
                    },
                    "unresolved_blocker_summary": {
                        "open_remediation_count": _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0),
                        "blocking_remediation_count": _safe_int(_safe_dict(remediation.get("remediation_summary")).get("blocking_remediation_count"), 0),
                        "open_exception_count": _safe_int(_safe_dict(exceptions.get("exception_summary")).get("open_exception_count"), 0),
                    },
                    "governance_recommendation_summary": {
                        "recommendation": _safe_str(progression.get("progression_decision"), "review_required"),
                        "rationale": _safe_list(_safe_dict(progression.get("governance_rationale_summary")).get("rationale")),
                        "latest_readiness_score": readiness,
                        "latest_stability_score": _safe_float(stability.get("stability_score"), 0.0),
                    },
                    "institutional_summary_history": [],
                    "summary_components": {
                        "readiness_score": readiness,
                        "review_board_score": review_score,
                        "remediation_score": remediation_score,
                        "exception_score": exception_score,
                        "cadence_score": cadence_score,
                        "progression_score": progression_score,
                        "stability_score": stability_score,
                        "recurring_cycle_score": recurring_score,
                    },
                }
            )
        for index, entry in enumerate(entries):
            entry["institutional_summary_history"] = [
                {
                    "summary_id": item["summary_id"],
                    "generated_at": item["generated_at"],
                    "consolidated_governance_score": item["consolidated_governance_score"],
                    "governance_review_status": item["governance_review_status"],
                    "progression_status": item["progression_status"],
                    "remediation_status": item["remediation_status"],
                    "stability_status": item["stability_status"],
                }
                for item in entries[index:]
            ]
        return entries

    def list_operations_summary(self, limit: int = 20) -> Dict[str, Any]:
        current = self._current_surfaces()
        review_board = current["review_board"]
        remediation = current["remediation"]
        progression = current["progression"]
        exceptions = current["exceptions"]
        cadence = current["cadence"]
        stability = current["stability"]
        recurring = current["recurring"]

        latest_review_summary = _safe_dict(review_board.get("institutional_review_summary"))
        latest_progression_summary = _safe_dict(progression.get("governance_rationale_summary"))
        latest_remediation_summary = _safe_dict(remediation.get("operational_risk_closure_summary"))
        latest_exception_summary = _safe_dict(exceptions.get("exception_summary"))
        latest_cadence = _safe_dict(cadence.get("latest"))
        latest_stability = _safe_dict(stability)
        latest_recurring = _safe_dict(recurring.get("latest"))

        component_scores = {
            "readiness": _safe_float(latest_review_summary.get("latest_readiness_score"), 0.0),
            "stability": _safe_float(latest_stability.get("stability_score"), 0.0),
            "remediation": 100.0 if _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0) == 0 else 60.0,
            "progression": _safe_float(progression.get("progression_score"), 0.0),
            "exception": 100.0 if _safe_int(latest_exception_summary.get("open_exception_count"), 0) == 0 else 60.0,
            "cadence": 100.0 if _safe_str(latest_cadence.get("cadence_status"), "on_track") == "on_track" else 65.0,
            "review_board": _safe_float(review_board.get("review_board_score"), 0.0),
            "recurring_cycles": _safe_float(latest_recurring.get("score"), 0.0),
        }
        consolidated_score = round(mean(component_scores.values()), 2) if component_scores else 0.0
        no_go_status = _safe_str(review_board.get("latest_session", {}).get("no_go_status"), "UNKNOWN")
        watch_indicators = {
            "readiness_watch": _is_watch_state(review_board.get("review_board_status")),
            "stability_watch": _is_watch_state(latest_stability.get("status")),
            "remediation_watch": _is_watch_state(remediation.get("remediation_status")),
            "progression_watch": _is_watch_state(progression.get("progression_status")),
            "no_go_watch": no_go_status != "PASS",
            "cadence_watch": _is_watch_state(_safe_dict(latest_cadence).get("status")) or _safe_str(latest_cadence.get("cadence_status"), "on_track") not in {"on_track", "PASS", "ok"},
            "exception_watch": _is_watch_state(exceptions.get("exception_status")),
            "governance_review_watch": _is_watch_state(review_board.get("review_board_status")),
        }
        status = "not_found"
        if any(component_scores.values()):
            status = _score_to_status(consolidated_score)
            has_watch = any(
                [
                    watch_indicators["readiness_watch"],
                    watch_indicators["stability_watch"],
                    watch_indicators["remediation_watch"],
                    watch_indicators["progression_watch"],
                    watch_indicators["cadence_watch"],
                    watch_indicators["exception_watch"],
                    watch_indicators["governance_review_watch"],
                    no_go_status != "PASS",
                ]
            )
            has_blockers = _safe_int(_safe_dict(remediation.get("remediation_summary")).get("blocking_remediation_count"), 0) > 0
            if has_blockers:
                status = "blocked"
            elif has_watch:
                status = "watch"
        warnings = [
            "missing_summary_history" if not review_board.get("review_board_history") else "",
            "unresolved_blocker_warning" if _safe_int(_safe_dict(remediation.get("remediation_summary")).get("blocking_remediation_count"), 0) > 0 else "",
            "no_go_warning" if no_go_status != "PASS" else "",
            "exception_warning" if _safe_int(latest_exception_summary.get("open_exception_count"), 0) > 0 else "",
            "cadence_warning" if _safe_str(latest_cadence.get("cadence_status"), "on_track") != "on_track" else "",
        ]
        warnings = [warning for warning in warnings if warning]
        history = self._history_entries(limit=limit)
        latest = history[0] if history else {}
        return {
            "status": status,
            "generated_at": _now_iso(),
            "operations_summary_status": status,
            "consolidated_governance_score": consolidated_score,
            "consolidated_governance_grade": _score_to_status(consolidated_score),
            "readiness_status": _safe_str(review_board.get("review_board_status"), "watch"),
            "stability_status": _safe_str(latest_stability.get("status"), "watch"),
            "remediation_status": "ok" if _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0) == 0 else "watch",
            "progression_status": _safe_str(progression.get("progression_status"), "watch"),
            "no_go_status": no_go_status,
            "cadence_status": _safe_str(latest_cadence.get("cadence_status"), "on_track"),
            "exception_status": _safe_str(exceptions.get("exception_status"), "watch"),
            "governance_review_status": _safe_str(review_board.get("review_board_status"), "watch"),
            "consolidated_watch_indicators": watch_indicators,
            "unresolved_blocker_summary": {
                "open_remediation_count": _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0),
                "blocking_remediation_count": _safe_int(_safe_dict(remediation.get("remediation_summary")).get("blocking_remediation_count"), 0),
                "open_exception_count": _safe_int(latest_exception_summary.get("open_exception_count"), 0),
            },
            "governance_recommendation_summary": {
                "recommendation": _safe_str(progression.get("progression_decision"), "review_required"),
                "rationale": _safe_list(_safe_dict(progression.get("governance_rationale_summary")).get("rationale")),
                "latest_readiness_score": _safe_float(latest_review_summary.get("latest_readiness_score"), 0.0),
                "latest_stability_score": _safe_float(latest_stability.get("stability_score"), 0.0),
            },
            "summary_components": component_scores,
            "institutional_operational_summary_history": history,
            "latest_summary": latest,
            "warning_indicators": {
                **watch_indicators,
                "no_go_warning": no_go_status != "PASS",
            },
            "warnings": warnings,
        }

    def latest_operations_summary(self) -> Dict[str, Any]:
        response = self.list_operations_summary(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No pilot operations summary history has been recorded yet.",
                "operations_summary": {},
            }
        return {
            "status": response.get("status", "ok"),
            "operations_summary_status": response.get("operations_summary_status", "watch"),
            "consolidated_governance_score": response.get("consolidated_governance_score", 0.0),
            "consolidated_governance_grade": response.get("consolidated_governance_grade", "blocked"),
            "readiness_status": response.get("readiness_status", "watch"),
            "stability_status": response.get("stability_status", "watch"),
            "remediation_status": response.get("remediation_status", "watch"),
            "progression_status": response.get("progression_status", "watch"),
            "no_go_status": response.get("no_go_status", "UNKNOWN"),
            "cadence_status": response.get("cadence_status", "on_track"),
            "exception_status": response.get("exception_status", "watch"),
            "governance_review_status": response.get("governance_review_status", "watch"),
            "consolidated_watch_indicators": response.get("consolidated_watch_indicators", {}),
            "unresolved_blocker_summary": response.get("unresolved_blocker_summary", {}),
            "governance_recommendation_summary": response.get("governance_recommendation_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "latest_summary": response.get("latest_summary", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def operations_summary_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_operations_summary(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("institutional_operational_summary_history", [])),
            "institutional_operational_summary_history": response.get("institutional_operational_summary_history", []),
            "consolidated_governance_score": response.get("consolidated_governance_score", 0.0),
            "consolidated_governance_grade": response.get("consolidated_governance_grade", "blocked"),
            "consolidated_watch_indicators": response.get("consolidated_watch_indicators", {}),
            "unresolved_blocker_summary": response.get("unresolved_blocker_summary", {}),
            "governance_recommendation_summary": response.get("governance_recommendation_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
