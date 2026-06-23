from __future__ import annotations

import importlib


class _DummyReviewBoardService:
    def list_review_board(self, limit: int = 20):
        return {
            "status": "ok",
            "review_board_score": 100.0,
            "review_board_grade": "institutional_ready",
            "review_board_status": "ok",
            "latest_session": {"review_id": "export-1"},
            "review_board_history": [{"review_id": "export-1"}],
            "governance_review_history": [{"review_id": "export-1"}],
            "review_board_cadence": {"runs_last_7_days": 1},
            "outstanding_governance_actions": [],
            "unresolved_operational_exceptions": [],
            "escalation_review_tracking": {"count": 0, "items": [], "status": "PASS"},
            "institutional_review_summary": {"session_count": 1},
            "warning_indicators": {},
            "warnings": [],
        }

    def latest_review_board(self):
        return {
            "status": "ok",
            "latest_session": {"review_id": "export-1"},
            "review_board_score": 100.0,
            "review_board_grade": "institutional_ready",
            "review_board_status": "ok",
            "review_board_cadence": {"runs_last_7_days": 1},
            "outstanding_governance_actions": [],
            "unresolved_operational_exceptions": [],
            "escalation_review_tracking": {"count": 0, "items": [], "status": "PASS"},
            "institutional_review_summary": {"session_count": 1},
            "warning_indicators": {},
            "warnings": [],
        }

    def review_board_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "review_board_history": [{"review_id": "export-1"}],
            "governance_review_history": [{"review_id": "export-1"}],
            "no_go_review_history": [{"review_id": "export-1", "status": "PASS", "indicators": []}],
            "readiness_review_history": [{"review_id": "export-1"}],
            "review_board_cadence": {"runs_last_7_days": 1},
            "institutional_review_summary": {"session_count": 1},
            "warning_indicators": {},
            "warnings": [],
        }


def test_review_board_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "review_board_service", lambda: _DummyReviewBoardService())

    assert module.review_board(limit=5)["status"] == "ok"
    assert module.review_board_latest()["review_board_score"] == 100.0
    assert module.review_board_history(limit=5)["count"] == 1
