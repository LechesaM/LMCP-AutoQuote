from __future__ import annotations

import importlib


class _DummySummaryService:
    def __init__(self, *, history):
        self._history = history

    def operations_summary_history(self, limit: int = 20):
        return {"institutional_operational_summary_history": self._history[:limit]}


class _DummyReviewBoardService:
    def __init__(self, *, no_go_history):
        self._no_go_history = no_go_history

    def latest_review_board(self):
        return {"no_go_review_history": self._no_go_history}


def _make_summary(
    *,
    summary_id: str,
    generated_at: str,
    readiness_score: float,
    stability_score: float,
    remediation_status: str,
    progression_status: str,
    no_go_status: str,
    cadence_status: str,
    exception_status: str,
    governance_review_status: str,
    recommendation: str,
    open_remediation_count: int = 0,
    blocking_remediation_count: int = 0,
    open_exception_count: int = 0,
):
    return {
        "summary_id": summary_id,
        "review_id": f"{summary_id}-review",
        "cycle_id": f"{summary_id}-cycle",
        "generated_at": generated_at,
        "readiness_score": readiness_score,
        "stability_score": stability_score,
        "remediation_status": remediation_status,
        "progression_status": progression_status,
        "no_go_status": no_go_status,
        "cadence_status": cadence_status,
        "exception_status": exception_status,
        "governance_review_status": governance_review_status,
        "governance_recommendation_summary": {"recommendation": recommendation},
        "unresolved_blocker_summary": {
            "open_remediation_count": open_remediation_count,
            "blocking_remediation_count": blocking_remediation_count,
            "open_exception_count": open_exception_count,
        },
        "readiness_criteria": {
            "open_remediation_count": open_remediation_count,
            "blocking_remediation_count": blocking_remediation_count,
            "open_exception_count": open_exception_count,
        },
    }


def _make_service(history, no_go_history):
    module = importlib.import_module("app.services.pilot_readiness_declaration_service")
    service = module.PilotReadinessDeclarationService(cycle_root=None, export_root=None)
    service.operations_summary = _DummySummaryService(history=history)
    service.review_board = _DummyReviewBoardService(no_go_history=no_go_history)
    return service


def test_pilot_readiness_declaration_service_ready_path() -> None:
    module = importlib.import_module("app.services.pilot_readiness_declaration_service")
    history = [
        _make_summary(
            summary_id="summary-ready",
            generated_at="2026-06-23T11:30:52+00:00",
            readiness_score=97.0,
            stability_score=96.0,
            remediation_status="ok",
            progression_status="ok",
            no_go_status="PASS",
            cadence_status="on_track",
            exception_status="ok",
            governance_review_status="ok",
            recommendation="pilot_continuation_review",
        ),
        _make_summary(
            summary_id="summary-older",
            generated_at="2026-06-22T11:30:52+00:00",
            readiness_score=93.0,
            stability_score=91.0,
            remediation_status="ok",
            progression_status="ok",
            no_go_status="PASS",
            cadence_status="on_track",
            exception_status="ok",
            governance_review_status="ok",
            recommendation="pilot_continuation_review",
        ),
    ]
    service = _make_service(history=history, no_go_history=[{"status": "PASS"}, {"status": "PASS"}])

    latest = service.latest_declaration()
    history_response = service.declaration_history(limit=5)

    assert latest["declaration_status"] == module.READY
    assert latest["declaration_grade"] == "ready"
    assert latest["declaration_score"] >= 90.0
    assert latest["unresolved_blocker_summary"]["unresolved_blockers"] == 0
    assert latest["governance_override_indicators"]["history_override_required"] is False
    assert latest["governance_override_indicators"]["no_go_override_required"] is False
    assert latest["escalation_triggers"] == []
    assert latest["warning_indicators"]["override_warning"] is False
    assert history_response["count"] == 2
    assert history_response["declaration_history"][0]["declaration_status"] == module.READY
    assert history_response["declaration_history_summary"]["latest_declaration_status"] == module.READY


def test_pilot_readiness_declaration_service_watch_path() -> None:
    module = importlib.import_module("app.services.pilot_readiness_declaration_service")
    history = [
        _make_summary(
            summary_id="summary-watch",
            generated_at="2026-06-23T10:30:52+00:00",
            readiness_score=80.0,
            stability_score=83.0,
            remediation_status="watch",
            progression_status="watch",
            no_go_status="PASS",
            cadence_status="on_track",
            exception_status="watch",
            governance_review_status="watch",
            recommendation="pilot_closure_review",
            open_remediation_count=1,
        )
    ]
    service = _make_service(history=history, no_go_history=[{"status": "PASS"}])

    latest = service.latest_declaration()

    assert latest["declaration_status"] == module.WATCH
    assert latest["declaration_grade"] == "watch"
    assert latest["declaration_rationale_summary"]["status"] == "WARN"
    assert latest["unresolved_blocker_summary"]["open_remediation_count"] == 1
    assert latest["governance_override_indicators"]["history_override_required"] is False
    assert latest["governance_override_indicators"]["blocker_override_required"] is False
    assert latest["warnings"]


def test_pilot_readiness_declaration_service_no_go_path() -> None:
    module = importlib.import_module("app.services.pilot_readiness_declaration_service")
    history = [
        _make_summary(
            summary_id="summary-no-go",
            generated_at="2026-06-23T09:30:52+00:00",
            readiness_score=64.0,
            stability_score=72.0,
            remediation_status="watch",
            progression_status="watch",
            no_go_status="WARN",
            cadence_status="watch",
            exception_status="watch",
            governance_review_status="watch",
            recommendation="watch_status_review",
            open_remediation_count=1,
            blocking_remediation_count=1,
            open_exception_count=1,
        )
    ]
    service = _make_service(history=history, no_go_history=[{"status": "WARN"}])

    latest = service.latest_declaration()

    assert latest["declaration_status"] == module.NO_GO
    assert latest["declaration_grade"] == "no_go"
    assert latest["governance_override_indicators"]["no_go_override_required"] is True
    assert latest["governance_override_indicators"]["blocker_override_required"] is True
    assert "no_go_status_not_pass" in latest["escalation_triggers"]
    assert latest["unresolved_blocker_summary"]["blocking_remediation_count"] == 1
