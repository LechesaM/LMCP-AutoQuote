from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import OperationalExceptionService, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.operational_remediation_service import OperationalRemediationService
from app.services.pilot_review_board_service import PilotReviewBoardService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score_from_session(session: Dict[str, Any], remediation: Dict[str, Any], exceptions: Dict[str, Any]) -> float:
    readiness_score = _safe_float(session.get("readiness_score"), 0.0)
    review_score = _safe_float(session.get("review_board_score"), 0.0)
    open_remediation = _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0)
    unresolved = _safe_int(_safe_dict(exceptions.get("exception_summary")).get("open_exception_count"), 0)
    blocking = _safe_int(_safe_dict(remediation.get("remediation_summary")).get("blocking_remediation_count"), 0)
    expansion_bonus = 10.0 if readiness_score >= 95.0 and open_remediation == 0 and unresolved == 0 else 0.0
    return round(
        max(
            0.0,
            mean([
                readiness_score,
                review_score,
                100.0 if open_remediation == 0 else 55.0,
                100.0 if unresolved == 0 else 55.0,
                100.0 if blocking == 0 else 60.0,
            ]) + expansion_bonus,
        ),
        2,
    )


def _decision_for_score(score: float, session: Dict[str, Any], remediation: Dict[str, Any], exceptions: Dict[str, Any]) -> str:
    readiness_score = _safe_float(session.get("readiness_score"), 0.0)
    review_status = _safe_str(session.get("review_board_status"), "watch")
    open_remediation = _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0)
    blocking = _safe_int(_safe_dict(remediation.get("remediation_summary")).get("blocking_remediation_count"), 0)
    unresolved = _safe_int(_safe_dict(exceptions.get("exception_summary")).get("open_exception_count"), 0)
    if blocking > 0 or unresolved > 0:
        return "closure_review"
    if readiness_score >= 95.0 and score >= 92.0 and open_remediation == 0 and review_status == "ok":
        return "scope_expansion_review"
    if readiness_score >= 85.0 and score >= 85.0 and open_remediation == 0:
        return "pilot_continuation_review"
    if review_status == "watch" or open_remediation > 0:
        return "watch_status_review"
    return "pilot_closure_review"


def _eligibility_indicators(session: Dict[str, Any], remediation: Dict[str, Any], exceptions: Dict[str, Any]) -> Dict[str, Any]:
    readiness_score = _safe_float(session.get("readiness_score"), 0.0)
    review_status = _safe_str(session.get("review_board_status"), "watch")
    open_remediation = _safe_int(_safe_dict(remediation.get("remediation_summary")).get("open_remediation_count"), 0)
    blocking = _safe_int(_safe_dict(remediation.get("remediation_summary")).get("blocking_remediation_count"), 0)
    unresolved = _safe_int(_safe_dict(exceptions.get("exception_summary")).get("open_exception_count"), 0)
    no_go_clear = _safe_str(session.get("no_go_status"), "PASS") == "PASS"
    dry_run_clear = _safe_str(session.get("dry_run_status"), "PASS") == "PASS"
    submission_lock_clear = _safe_str(session.get("submission_lock_status"), "PASS") == "PASS"
    return {
        "continuation_eligible": readiness_score >= 85.0 and open_remediation == 0 and unresolved == 0 and no_go_clear and dry_run_clear and submission_lock_clear,
        "watch_eligible": review_status == "watch" or open_remediation > 0 or unresolved > 0,
        "closure_eligible": open_remediation == 0 and unresolved == 0 and no_go_clear and dry_run_clear,
        "expansion_eligible": readiness_score >= 95.0 and review_status == "ok" and open_remediation == 0 and unresolved == 0 and blocking == 0,
        "no_go_clear": no_go_clear,
        "dry_run_clear": dry_run_clear,
        "submission_lock_clear": submission_lock_clear,
        "unresolved_blocker_count": blocking,
        "unresolved_exception_count": unresolved,
    }


class PilotProgressionService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
        review_window_days: int = 7,
    ) -> None:
        self.review_board = PilotReviewBoardService(cycle_root=cycle_root or PILOT_CYCLE_ROOT, export_root=export_root or GOVERNANCE_EXPORT_ROOT, review_window_days=review_window_days)
        self.remediation = OperationalRemediationService(cycle_root=cycle_root or PILOT_CYCLE_ROOT, export_root=export_root or GOVERNANCE_EXPORT_ROOT)
        self.exceptions = OperationalExceptionService(cycle_root=cycle_root or PILOT_CYCLE_ROOT, export_root=export_root or GOVERNANCE_EXPORT_ROOT)

    def _sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        sessions = _safe_list(self.review_board.list_review_board(limit=limit).get("review_board_history", []))
        remediation_latest = self.remediation.latest_remediation()
        exceptions_latest = self.exceptions.latest_exceptions()
        decisions: List[Dict[str, Any]] = []
        for index, session in enumerate(sessions):
            score = _score_from_session(session, remediation_latest, exceptions_latest)
            decision = _decision_for_score(score, session, remediation_latest, exceptions_latest)
            eligibility = _eligibility_indicators(session, remediation_latest, exceptions_latest)
            unresolved_summary = {
                "open_remediation_count": _safe_int(_safe_dict(remediation_latest.get("remediation_summary")).get("open_remediation_count"), 0),
                "overdue_remediation_count": _safe_int(_safe_dict(remediation_latest.get("remediation_summary")).get("overdue_remediation_count"), 0),
                "open_exception_count": _safe_int(_safe_dict(exceptions_latest.get("exception_summary")).get("open_exception_count"), 0),
                "blocking_remediation_count": _safe_int(_safe_dict(remediation_latest.get("remediation_summary")).get("blocking_remediation_count"), 0),
            }
            rationale = [
                f"Review board status is { _safe_str(session.get('review_board_status'), 'watch') }.",
                f"Readiness score is {_safe_float(session.get('readiness_score'), 0.0):.2f}.",
                f"Open remediation count is {unresolved_summary['open_remediation_count']}.",
                f"Open exception count is {unresolved_summary['open_exception_count']}.",
            ]
            decisions.append(
                {
                    "progression_id": f"{_safe_str(session.get('review_id'), 'unknown')}:progression",
                    "review_id": _safe_str(session.get("review_id"), ""),
                    "cycle_id": _safe_str(session.get("cycle_id"), ""),
                    "generated_at": _safe_str(session.get("generated_at"), _now_iso()),
                    "progression_score": score,
                    "progression_decision": decision,
                    "progression_status": "ok" if decision in {"pilot_continuation_review", "pilot_closure_review", "scope_expansion_review"} else "watch",
                    "pilot_continuation_review": decision == "pilot_continuation_review",
                    "watch_status_review": decision == "watch_status_review",
                    "pilot_closure_review": decision == "pilot_closure_review",
                    "scope_expansion_review": decision == "scope_expansion_review",
                    "unresolved_anomaly_impact_review": decision == "closure_review",
                    "expansion_eligibility_indicators": eligibility,
                    "unresolved_blocker_summary": unresolved_summary,
                    "progression_decision_history": [
                        {
                            "decision": decision,
                            "score": score,
                            "generated_at": _safe_str(session.get("generated_at"), _now_iso()),
                        }
                    ],
                    "governance_rationale_summary": {
                        "status": "PASS" if decision != "closure_review" else "WARN",
                        "rationale": rationale,
                        "latest_readiness_score": _safe_float(session.get("readiness_score"), 0.0),
                        "latest_review_board_status": _safe_str(session.get("review_board_status"), "watch"),
                        "latest_remediation_status": _safe_str(remediation_latest.get("remediation_status"), "watch"),
                        "latest_exception_status": _safe_str(exceptions_latest.get("exception_status"), "watch"),
                    },
                    "governance_decision_recommendation": decision,
                    "decision_summary": {
                        "continuation_review": decision == "pilot_continuation_review",
                        "watch_review": decision == "watch_status_review",
                        "closure_review": decision == "pilot_closure_review",
                        "expansion_review": decision == "scope_expansion_review",
                        "unresolved_anomaly_impact_review": decision == "closure_review",
                    },
                    "latest_review_board_status": _safe_str(session.get("review_board_status"), "watch"),
                    "latest_readiness_score": _safe_float(session.get("readiness_score"), 0.0),
                    "latest_readiness_grade": _safe_str(session.get("readiness_grade"), "watch"),
                    "latest_review_board_summary": _safe_dict(session.get("institutional_review_summary")),
                    "latest_remediation_summary": _safe_dict(remediation_latest.get("remediation_summary")),
                    "latest_exception_summary": _safe_dict(exceptions_latest.get("exception_summary")),
                    "latest_no_go_status": _safe_str(session.get("no_go_status"), "UNKNOWN"),
                    "latest_submission_lock_status": _safe_str(session.get("submission_lock_status"), "UNKNOWN"),
                    "latest_dry_run_status": _safe_str(session.get("dry_run_status"), "UNKNOWN"),
                }
            )
        return decisions

    def list_progression(self, limit: int = 20) -> Dict[str, Any]:
        decisions = self._sessions(limit=limit)
        latest = decisions[0] if decisions else {}
        score = _safe_float(latest.get("progression_score"), 0.0)
        status = "not_found" if not decisions else ("ok" if latest.get("progression_decision") in {"pilot_continuation_review", "pilot_closure_review", "scope_expansion_review"} else "watch")
        unresolved_blockers = _safe_dict(latest.get("unresolved_blocker_summary"))
        eligibility = _safe_dict(latest.get("expansion_eligibility_indicators"))
        warnings = [
            "missing_progression_history" if not decisions else "",
            "unresolved_anomaly_impact_warning" if latest.get("unresolved_anomaly_impact_review") else "",
            "watch_status_review_warning" if latest.get("watch_status_review") else "",
            "scope_expansion_ineligible_warning" if not eligibility.get("expansion_eligible", False) else "",
            "continuation_ineligible_warning" if not eligibility.get("continuation_eligible", False) else "",
            "closure_ineligible_warning" if not eligibility.get("closure_eligible", False) else "",
            "unresolved_blocker_warning" if unresolved_blockers.get("blocking_remediation_count", 0) > 0 else "",
        ]
        warnings = [warning for warning in warnings if warning]
        return {
            "status": status,
            "generated_at": _now_iso(),
            "progression_status": status,
            "progression_score": score,
            "progression_grade": "ready" if score >= 92.0 else "watch" if score >= 80.0 else "blocked",
            "progression_decision": latest.get("progression_decision", "review_required"),
            "pilot_continuation_review": latest.get("pilot_continuation_review", False),
            "watch_status_review": latest.get("watch_status_review", False),
            "pilot_closure_review": latest.get("pilot_closure_review", False),
            "scope_expansion_review": latest.get("scope_expansion_review", False),
            "unresolved_anomaly_impact_review": latest.get("unresolved_anomaly_impact_review", False),
            "expansion_eligibility_indicators": eligibility,
            "unresolved_blocker_summary": unresolved_blockers,
            "progression_decision_history": decisions,
            "governance_rationale_summary": latest.get("governance_rationale_summary", {}),
            "governance_progression_decisions": [decision.get("progression_decision", "review_required") for decision in decisions],
            "pilot_progression_score": score,
            "pilot_progression_grade": "ready" if score >= 92.0 else "watch" if score >= 80.0 else "blocked",
            "pilot_progression_summary": {
                "continuation_review": bool(latest.get("pilot_continuation_review")),
                "watch_review": bool(latest.get("watch_status_review")),
                "closure_review": bool(latest.get("pilot_closure_review")),
                "expansion_review": bool(latest.get("scope_expansion_review")),
                "unresolved_anomaly_impact_review": bool(latest.get("unresolved_anomaly_impact_review")),
            },
            "warning_indicators": {
                "missing_progression_history": not bool(decisions),
                "unresolved_anomaly_impact_warning": bool(latest.get("unresolved_anomaly_impact_review")),
                "watch_status_review_warning": bool(latest.get("watch_status_review")),
                "scope_expansion_ineligible_warning": not bool(eligibility.get("expansion_eligible", False)),
                "continuation_ineligible_warning": not bool(eligibility.get("continuation_eligible", False)),
                "closure_ineligible_warning": not bool(eligibility.get("closure_eligible", False)),
                "unresolved_blocker_warning": _safe_int(unresolved_blockers.get("blocking_remediation_count"), 0) > 0,
            },
            "warnings": warnings,
        }

    def latest_progression(self) -> Dict[str, Any]:
        response = self.list_progression(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No pilot progression history has been recorded yet.",
                "progression": {},
            }
        return {
            "status": response.get("status", "ok"),
            "progression_status": response.get("progression_status", "watch"),
            "progression_score": response.get("progression_score", 0.0),
            "progression_grade": response.get("progression_grade", "watch"),
            "progression_decision": response.get("progression_decision", "review_required"),
            "pilot_progression_score": response.get("pilot_progression_score", 0.0),
            "pilot_progression_grade": response.get("pilot_progression_grade", "watch"),
            "pilot_progression_summary": response.get("pilot_progression_summary", {}),
            "pilot_continuation_review": bool(response.get("pilot_continuation_review", False)),
            "watch_status_review": bool(response.get("watch_status_review", False)),
            "pilot_closure_review": bool(response.get("pilot_closure_review", False)),
            "scope_expansion_review": bool(response.get("scope_expansion_review", False)),
            "unresolved_anomaly_impact_review": bool(response.get("unresolved_anomaly_impact_review", False)),
            "expansion_eligibility_indicators": response.get("expansion_eligibility_indicators", {}),
            "unresolved_blocker_summary": response.get("unresolved_blocker_summary", {}),
            "progression_decision_history": response.get("progression_decision_history", []),
            "governance_rationale_summary": response.get("governance_rationale_summary", {}),
            "governance_progression_decisions": response.get("governance_progression_decisions", []),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def progression_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_progression(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("progression_decision_history", [])),
            "progression_decision_history": response.get("progression_decision_history", []),
            "pilot_continuation_review": bool(response.get("pilot_continuation_review", False)),
            "watch_status_review": bool(response.get("watch_status_review", False)),
            "pilot_closure_review": bool(response.get("pilot_closure_review", False)),
            "scope_expansion_review": bool(response.get("scope_expansion_review", False)),
            "unresolved_anomaly_impact_review": bool(response.get("unresolved_anomaly_impact_review", False)),
            "expansion_eligibility_indicators": response.get("expansion_eligibility_indicators", {}),
            "unresolved_blocker_summary": response.get("unresolved_blocker_summary", {}),
            "governance_rationale_summary": response.get("governance_rationale_summary", {}),
            "governance_progression_decisions": response.get("governance_progression_decisions", []),
            "pilot_progression_score": response.get("pilot_progression_score", 0.0),
            "pilot_progression_grade": response.get("pilot_progression_grade", "watch"),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
