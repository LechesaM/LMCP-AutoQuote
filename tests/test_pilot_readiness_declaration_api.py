from __future__ import annotations

import importlib


class _DummyDeclarationService:
    def list_declarations(self, limit: int = 20):
        return {
            "status": "ok",
            "declaration_status": "READY_FOR_CONTROLLED_PILOT",
            "declaration_grade": "ready",
            "declaration_score": 96.5,
            "declaration_rationale_summary": {"status": "PASS"},
            "declaration_rationale_text": "Ready.",
            "declaration_history": [{"declaration_id": "summary-ready:declaration"}],
            "declaration_history_summary": {"count": 1, "latest_declaration_id": "summary-ready:declaration", "latest_declaration_status": "READY_FOR_CONTROLLED_PILOT"},
            "governance_override_indicators": {"history_override_required": False},
            "escalation_triggers": [],
            "unresolved_blocker_summary": {"open_remediation_count": 0, "blocking_remediation_count": 0, "open_exception_count": 0, "readiness_score": 96.5, "stability_score": 95.5, "unresolved_blockers": 0},
            "no_go_history": [{"status": "PASS"}],
            "governance_recommendation_history": [{"recommendation": "pilot_continuation_review"}],
            "warning_indicators": {"missing_declaration_history": False},
            "warnings": [],
        }

    def latest_declaration(self):
        return {
            "status": "ok",
            "declaration_status": "READY_FOR_CONTROLLED_PILOT",
            "declaration_grade": "ready",
            "declaration_score": 96.5,
            "declaration_rationale_summary": {"status": "PASS"},
            "declaration_rationale_text": "Ready.",
            "declaration_history": [{"declaration_id": "summary-ready:declaration"}],
            "declaration_history_summary": {"count": 1, "latest_declaration_id": "summary-ready:declaration", "latest_declaration_status": "READY_FOR_CONTROLLED_PILOT"},
            "governance_override_indicators": {"history_override_required": False},
            "escalation_triggers": [],
            "unresolved_blocker_summary": {"open_remediation_count": 0, "blocking_remediation_count": 0, "open_exception_count": 0, "readiness_score": 96.5, "stability_score": 95.5, "unresolved_blockers": 0},
            "no_go_history": [{"status": "PASS"}],
            "governance_recommendation_history": [{"recommendation": "pilot_continuation_review"}],
            "warning_indicators": {"missing_declaration_history": False},
            "warnings": [],
        }

    def declaration_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "declaration_history": [{"declaration_id": "summary-ready:declaration"}],
            "declaration_history_summary": {"count": 1, "latest_declaration_id": "summary-ready:declaration", "latest_declaration_status": "READY_FOR_CONTROLLED_PILOT"},
            "governance_override_indicators": {"history_override_required": False},
            "escalation_triggers": [],
            "unresolved_blocker_summary": {"open_remediation_count": 0, "blocking_remediation_count": 0, "open_exception_count": 0, "readiness_score": 96.5, "stability_score": 95.5, "unresolved_blockers": 0},
            "no_go_history": [{"status": "PASS"}],
            "governance_recommendation_history": [{"recommendation": "pilot_continuation_review"}],
            "warning_indicators": {"missing_declaration_history": False},
            "warnings": [],
        }


def test_readiness_declaration_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "declaration_service", lambda: _DummyDeclarationService())

    assert module.declaration(limit=5)["declaration_status"] == "READY_FOR_CONTROLLED_PILOT"
    assert module.declaration_latest()["declaration_grade"] == "ready"
    assert module.declaration_history(limit=5)["count"] == 1
