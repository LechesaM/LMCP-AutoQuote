from __future__ import annotations

import importlib


class _DummyOperatorSessionService:
    def list_operator_sessions(self, limit: int = 20):
        return {
            "status": "ok",
            "operator_session_status": "ok",
            "active_operator_session_count": 1,
            "active_operator_sessions": [{"operator_session_id": "session-1"}],
            "operator_sessions": [{"operator_session_id": "session-1"}],
            "operator_session_history": [{"operator_session_id": "session-1"}],
            "supervision_score": 95.0,
            "supervision_grade": "ready",
            "supervision_coverage": {"coverage_rate": 100.0},
            "operator_workload": {"assigned_rfq_count": 2, "pending_approval_count": 0},
            "active_sessions_summary": {"latest_operator_session_id": "session-1"},
            "warning_indicators": {"unattended_rfq_warning": False},
            "warnings": [],
        }

    def latest_operator_session(self):
        return {
            "status": "ok",
            "operator_session_status": "ok",
            "operator_session": {"operator_session_id": "session-1"},
            "active_operator_sessions": [{"operator_session_id": "session-1"}],
            "active_operator_session_count": 1,
            "supervision_score": 95.0,
            "supervision_grade": "ready",
            "supervision_coverage": {"coverage_rate": 100.0},
            "operator_workload": {"assigned_rfq_count": 2, "pending_approval_count": 0},
            "warning_indicators": {"unattended_rfq_warning": False},
            "warnings": [],
        }

    def operator_session_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "operator_session_history": [{"operator_session_id": "session-1"}],
            "supervision_score": 95.0,
            "supervision_grade": "ready",
            "operator_workload": {"assigned_rfq_count": 2, "pending_approval_count": 0},
            "warning_indicators": {"unattended_rfq_warning": False},
            "warnings": [],
        }


def test_operator_session_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "operator_session_service", lambda: _DummyOperatorSessionService())

    assert module.operator_sessions(limit=5)["active_operator_session_count"] == 1
    assert module.operator_sessions_latest()["operator_session_status"] == "ok"
    assert module.operator_sessions_history(limit=5)["count"] == 1
