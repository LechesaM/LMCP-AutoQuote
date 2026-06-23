from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_operations_summary_service import PilotOperationsSummaryService
from app.services.pilot_review_board_service import PilotReviewBoardService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"

READY = "READY_FOR_CONTROLLED_PILOT"
WATCH = "WATCH"
NO_GO = "NO_GO"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_to_score(status: Any) -> float:
    normalized = _safe_str(status, "WARN").lower()
    return {
        "pass": 100.0,
        "ok": 100.0,
        "on_track": 100.0,
        "ready": 100.0,
        "warn": 65.0,
        "watch": 65.0,
        "blocked": 0.0,
        "fail": 0.0,
        "no_go": 0.0,
        "not_found": 0.0,
    }.get(normalized, 40.0)


def _has_recent_no_go(no_go_history: List[Dict[str, Any]]) -> bool:
    recent = no_go_history[:3]
    return any(_safe_str(entry.get("status"), "PASS") != "PASS" for entry in recent)


def _history_clear(no_go_history: List[Dict[str, Any]], recommendation_history: List[Dict[str, Any]]) -> bool:
    recent_no_go = no_go_history[:3]
    recent_recommendations = recommendation_history[:3]
    no_go_clear = all(_safe_str(entry.get("status"), "PASS") == "PASS" for entry in recent_no_go)
    recommendation_clear = all(_safe_str(entry.get("recommendation"), "review_required") in {"pilot_continuation_review", "pilot_closure_review", "scope_expansion_review"} for entry in recent_recommendations)
    return no_go_clear and recommendation_clear


def _decision_for_snapshot(snapshot: Dict[str, Any], no_go_history: List[Dict[str, Any]], recommendation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    readiness_score = _safe_float(snapshot.get("readiness_score"), 0.0)
    stability_score = _safe_float(snapshot.get("stability_score"), 0.0)
    remediation_status = _safe_str(snapshot.get("remediation_status"), "watch")
    progression_status = _safe_str(snapshot.get("progression_status"), "watch")
    cadence_status = _safe_str(snapshot.get("cadence_status"), "on_track")
    exception_status = _safe_str(snapshot.get("exception_status"), "watch")
    review_status = _safe_str(snapshot.get("governance_review_status"), "watch")
    no_go_status = _safe_str(snapshot.get("no_go_status"), "UNKNOWN")
    blockers = _safe_dict(snapshot.get("unresolved_blocker_summary"))
    open_remediation_count = _safe_int(blockers.get("open_remediation_count"), 0)
    blocking_remediation_count = _safe_int(blockers.get("blocking_remediation_count"), 0)
    open_exception_count = _safe_int(blockers.get("open_exception_count"), 0)
    recommendation = _safe_str(_safe_dict(snapshot.get("governance_recommendation_summary")).get("recommendation"), "review_required")
    ready_core = (
        readiness_score >= 85.0
        and stability_score >= 85.0
        and remediation_status == "ok"
        and cadence_status == "on_track"
        and progression_status in {"ok", "ready"}
        and exception_status == "ok"
        and review_status == "ok"
        and no_go_status == "PASS"
        and open_remediation_count == 0
        and blocking_remediation_count == 0
        and open_exception_count == 0
    )
    history_safe = _history_clear(no_go_history, recommendation_history)
    severe_risk = (
        no_go_status != "PASS"
        or readiness_score < 70.0
        or stability_score < 70.0
        or blocking_remediation_count > 0
        or open_exception_count > 0
    )
    watch_risk = (
        not severe_risk
        and (
            readiness_score < 85.0
            or stability_score < 85.0
            or open_remediation_count > 0
            or remediation_status != "ok"
            or cadence_status != "on_track"
            or progression_status not in {"ok", "ready"}
            or exception_status != "ok"
            or review_status != "ok"
            or recommendation == "review_required"
            or _has_recent_no_go(no_go_history)
        )
    )

    if severe_risk:
        declaration_status = NO_GO
    elif ready_core and history_safe:
        declaration_status = READY
    else:
        declaration_status = WATCH if watch_risk or not ready_core else WATCH

    override_indicators = {
        "history_override_required": ready_core and not history_safe,
        "recommendation_override_required": ready_core and recommendation == "review_required",
        "blocker_override_required": blocking_remediation_count > 0 or open_exception_count > 0,
        "no_go_override_required": no_go_status != "PASS",
        "declaration_override_required": ready_core and not history_safe,
    }
    escalation_triggers = [
        "no_go_status_not_pass" if no_go_status != "PASS" else "",
        "readiness_below_threshold" if readiness_score < 85.0 else "",
        "stability_below_threshold" if stability_score < 85.0 else "",
        "unresolved_blockers_present" if open_remediation_count > 0 or blocking_remediation_count > 0 or open_exception_count > 0 else "",
        "remediation_not_ok" if remediation_status != "ok" else "",
        "cadence_not_on_track" if cadence_status != "on_track" else "",
        "progression_not_ready" if progression_status not in {"ok", "ready"} else "",
        "recent_no_go_history" if _has_recent_no_go(no_go_history) else "",
        "governance_recommendation_review_required" if recommendation == "review_required" else "",
    ]
    escalation_triggers = [trigger for trigger in escalation_triggers if trigger]
    rationale = [
        f"Readiness score {readiness_score:.2f}.",
        f"Stability score {stability_score:.2f}.",
        f"Remediation status {remediation_status}.",
        f"Cadence status {cadence_status}.",
        f"Progression status {progression_status}.",
        f"NO-GO status {no_go_status}.",
        f"Recommendation {recommendation}.",
    ]
    return {
        "declaration_status": declaration_status,
        "declaration_grade": "ready" if declaration_status == READY else "watch" if declaration_status == WATCH else "no_go",
        "declaration_score": round(
            mean([
                readiness_score,
                stability_score,
                100.0 if open_remediation_count == 0 else 60.0,
                100.0 if open_exception_count == 0 else 60.0,
                100.0 if cadence_status == "on_track" else 65.0,
                100.0 if progression_status in {"ok", "ready"} else 65.0,
                100.0 if review_status == "ok" else 65.0,
            ]),
            2,
        ),
        "declaration_rationale_summary": {
            "status": "PASS" if declaration_status == READY else "WARN" if declaration_status == WATCH else "FAIL",
            "rationale": rationale,
            "readiness_score": readiness_score,
            "stability_score": stability_score,
            "remediation_status": remediation_status,
            "cadence_status": cadence_status,
            "progression_status": progression_status,
            "no_go_status": no_go_status,
            "governance_recommendation": recommendation,
        },
        "escalation_triggers": escalation_triggers,
        "governance_override_indicators": override_indicators,
        "declaration_rationale_text": "; ".join(rationale),
        "readiness_criteria": {
            "readiness_score": readiness_score,
            "stability_score": stability_score,
            "open_remediation_count": open_remediation_count,
            "blocking_remediation_count": blocking_remediation_count,
            "open_exception_count": open_exception_count,
            "unresolved_blockers": open_remediation_count + blocking_remediation_count + open_exception_count,
            "remediation_status": remediation_status,
            "cadence_status": cadence_status,
            "progression_status": progression_status,
            "no_go_status": no_go_status,
            "recommendation": recommendation,
        },
        "history_safe": history_safe,
    }


class PilotReadinessDeclarationService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
    ) -> None:
        cycle_root = cycle_root or PILOT_CYCLE_ROOT
        export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.operations_summary = PilotOperationsSummaryService(cycle_root=cycle_root, export_root=export_root)
        self.review_board = PilotReviewBoardService(cycle_root=cycle_root, export_root=export_root)

    def _summary_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        summary_history = _safe_list(self.operations_summary.operations_summary_history(limit=limit).get("institutional_operational_summary_history", []))
        no_go_history = _safe_list(self.review_board.latest_review_board().get("no_go_review_history", []))
        recommendation_history = [
            {
                "summary_id": entry.get("summary_id", ""),
                "generated_at": entry.get("generated_at", ""),
                "recommendation": _safe_str(_safe_dict(entry.get("governance_recommendation_summary")).get("recommendation"), "review_required"),
            }
            for entry in summary_history
        ]
        declarations: List[Dict[str, Any]] = []
        for entry in summary_history:
            decision = _decision_for_snapshot(entry, no_go_history, recommendation_history)
            declarations.append(
                {
                    "declaration_id": f"{_safe_str(entry.get('summary_id'), 'summary')}:declaration",
                    "summary_id": _safe_str(entry.get("summary_id"), ""),
                    "review_id": _safe_str(entry.get("review_id"), ""),
                    "cycle_id": _safe_str(entry.get("cycle_id"), ""),
                    "generated_at": _safe_str(entry.get("generated_at"), _now_iso()),
                    "declaration_status": decision["declaration_status"],
                    "declaration_grade": decision["declaration_grade"],
                    "declaration_score": decision["declaration_score"],
                    "readiness_status": _safe_str(entry.get("readiness_status"), "watch"),
                    "stability_status": _safe_str(entry.get("stability_status"), "watch"),
                    "remediation_status": _safe_str(entry.get("remediation_status"), "watch"),
                    "progression_status": _safe_str(entry.get("progression_status"), "watch"),
                    "no_go_status": _safe_str(entry.get("no_go_status"), "UNKNOWN"),
                    "cadence_status": _safe_str(entry.get("cadence_status"), "on_track"),
                    "exception_status": _safe_str(entry.get("exception_status"), "watch"),
                    "governance_review_status": _safe_str(entry.get("governance_review_status"), "watch"),
                    "declaration_rationale_summary": decision["declaration_rationale_summary"],
                    "declaration_rationale_text": decision["declaration_rationale_text"],
                    "escalation_triggers": decision["escalation_triggers"],
                    "governance_override_indicators": decision["governance_override_indicators"],
                    "governance_recommendation_history": recommendation_history,
                    "no_go_history": no_go_history,
                    "readiness_criteria": decision["readiness_criteria"],
                }
            )
        return declarations

    def list_declarations(self, limit: int = 20) -> Dict[str, Any]:
        declarations = self._summary_history(limit=limit)
        latest = declarations[0] if declarations else {}
        no_go_history = latest.get("no_go_history", [])
        recommendation_history = latest.get("governance_recommendation_history", [])
        latest_status = _safe_str(latest.get("declaration_status"), "WATCH")
        declaration_status = "not_found" if not declarations else latest_status
        override_indicators = _safe_dict(latest.get("governance_override_indicators"))
        rationale = _safe_dict(latest.get("declaration_rationale_summary"))
        unresolved_blockers = _safe_dict(latest.get("readiness_criteria"))
        escalation_triggers = _safe_list(latest.get("escalation_triggers"))
        warnings = [
            "missing_declaration_history" if not declarations else "",
            "no_go_warning" if _safe_str(latest.get("no_go_status"), "PASS") != "PASS" else "",
            "override_warning" if any(override_indicators.values()) else "",
            "escalation_warning" if escalation_triggers else "",
        ]
        warnings = [warning for warning in warnings if warning]
        return {
            "status": "not_found" if not declarations else ("ok" if declaration_status == READY else "watch" if declaration_status == WATCH else "blocked"),
            "generated_at": _now_iso(),
            "declaration_status": declaration_status,
            "declaration_grade": _safe_str(latest.get("declaration_grade"), "watch"),
            "declaration_score": _safe_float(latest.get("declaration_score"), 0.0),
            "declaration_rationale_summary": rationale,
            "declaration_rationale_text": _safe_str(latest.get("declaration_rationale_text"), ""),
            "declaration_history": declarations,
            "declaration_history_summary": {
                "count": len(declarations),
                "latest_declaration_id": _safe_str(latest.get("declaration_id"), ""),
                "latest_declaration_status": declaration_status,
                "latest_readiness_score": _safe_float(rationale.get("readiness_score"), 0.0),
                "latest_stability_score": _safe_float(rationale.get("stability_score"), 0.0),
            },
            "governance_override_indicators": override_indicators,
            "escalation_triggers": escalation_triggers,
            "unresolved_blocker_summary": {
                "open_remediation_count": _safe_int(unresolved_blockers.get("open_remediation_count"), 0),
                "blocking_remediation_count": _safe_int(unresolved_blockers.get("blocking_remediation_count"), 0),
                "open_exception_count": _safe_int(unresolved_blockers.get("open_exception_count"), 0),
                "readiness_score": _safe_float(unresolved_blockers.get("readiness_score"), 0.0),
                "stability_score": _safe_float(unresolved_blockers.get("stability_score"), 0.0),
                "unresolved_blockers": _safe_int(unresolved_blockers.get("unresolved_blockers"), 0),
            },
            "no_go_history": no_go_history,
            "governance_recommendation_history": recommendation_history,
            "warning_indicators": {
                "missing_declaration_history": not bool(declarations),
                "no_go_warning": _safe_str(latest.get("no_go_status"), "PASS") != "PASS",
                "override_warning": any(override_indicators.values()),
                "escalation_warning": bool(escalation_triggers),
            },
            "warnings": warnings,
        }

    def latest_declaration(self) -> Dict[str, Any]:
        response = self.list_declarations(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No pilot readiness declaration history has been recorded yet.",
                "declaration": {},
            }
        return {
            "status": response.get("status", "ok"),
            "declaration_status": response.get("declaration_status", WATCH),
            "declaration_grade": response.get("declaration_grade", "watch"),
            "declaration_score": response.get("declaration_score", 0.0),
            "declaration_rationale_summary": response.get("declaration_rationale_summary", {}),
            "declaration_rationale_text": response.get("declaration_rationale_text", ""),
            "declaration_history": response.get("declaration_history", []),
            "declaration_history_summary": response.get("declaration_history_summary", {}),
            "governance_override_indicators": response.get("governance_override_indicators", {}),
            "escalation_triggers": response.get("escalation_triggers", []),
            "unresolved_blocker_summary": response.get("unresolved_blocker_summary", {}),
            "no_go_history": response.get("no_go_history", []),
            "governance_recommendation_history": response.get("governance_recommendation_history", []),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def declaration_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_declarations(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("declaration_history", [])),
            "declaration_history": response.get("declaration_history", []),
            "declaration_history_summary": response.get("declaration_history_summary", {}),
            "governance_override_indicators": response.get("governance_override_indicators", {}),
            "escalation_triggers": response.get("escalation_triggers", []),
            "unresolved_blocker_summary": response.get("unresolved_blocker_summary", {}),
            "no_go_history": response.get("no_go_history", []),
            "governance_recommendation_history": response.get("governance_recommendation_history", []),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
