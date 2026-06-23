from __future__ import annotations

import importlib


class _DummyReadinessService:
    def __init__(self, declaration):
        self._declaration = declaration

    def latest_declaration(self):
        return self._declaration


class _DummyOperatorSessionsService:
    def __init__(self, session):
        self._session = session

    def latest_operator_session(self):
        return {
            "status": "ok",
            "operator_session_status": self._session["status"],
            "operator_session": self._session,
            "active_operator_sessions": [self._session] if self._session.get("active_operator_session") else [],
            "active_operator_session_count": 1 if self._session.get("active_operator_session") else 0,
            "supervision_score": self._session.get("operator_supervision_score", 0.0),
            "supervision_grade": "ready" if self._session.get("operator_supervision_score", 0.0) >= 90 else "watch",
            "supervision_coverage": self._session.get("supervision_coverage", {"coverage_rate": 0.0}),
            "operator_workload": self._session.get("operator_workload", {"assigned_rfq_count": 0, "pending_approval_count": 0}),
            "warning_indicators": self._session.get("warning_indicators", {}),
            "warnings": self._session.get("warnings", []),
        }


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def _session(*, active: bool = True, acknowledged: bool = True, supervision_score: float = 95.0):
    return {
        "operator_session_id": "cycle-1:operator-session",
        "cycle_id": "cycle-1",
        "generated_at": "2026-06-23T16:04:00+00:00",
        "status": "active" if active else "blocked",
        "operator_name": "staging-governance-operator",
        "operator_role": "governance_reviewer",
        "operator_acknowledgement": {
            "acknowledged": acknowledged,
            "approved_at": "2026-06-23T00:00:00+00:00" if acknowledged else "",
            "approved_rehearsal_sequence": ["operator_review", "governance_checkpoint"] if acknowledged else [],
            "notes": [],
        },
        "approved_rehearsal_sequence": ["operator_review", "governance_checkpoint"] if acknowledged else [],
        "active_operator_session": active,
        "pending_approval_checkpoints": [],
        "operator_supervision_score": supervision_score,
        "supervision_coverage": {"coverage_rate": 100.0 if acknowledged and active else 0.0},
        "supervision_window": {"active": active, "started_at": "2026-06-23T16:04:00+00:00", "ends_at": "2026-06-24T16:04:00+00:00"},
    }


def test_returnable_governance_service_approves_complete_bid_response(tmp_path) -> None:
    module = importlib.import_module("app.services.returnable_governance_service")
    service = module.ReturnableGovernanceService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        export_root=tmp_path / "runtime" / "staging" / "governance-exports",
    )
    service.operator_sessions = _DummyOperatorSessionsService(_session())
    service.readiness = _DummyReadinessService(
        {
            "status": "ok",
            "declaration_status": "READY_FOR_CONTROLLED_PILOT",
            "declaration_score": 96.0,
            "declaration_rationale_summary": {"no_go_status": "PASS"},
        }
    )
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-RET-001",
                "title": "Complete returnables schedule",
                "returnable_requirements": {
                    "annexure": True,
                    "mandatory_returnable": True,
                    "pricing_schedule": True,
                    "declaration": True,
                    "technical_schedule": True,
                    "compulsory_form": True,
                    "mandatory_attachment": True,
                },
                "returnables": {
                    "annexure": "annexure-a.pdf",
                    "mandatory_returnable": "mandatory.pdf",
                    "pricing_schedule": "pricing.xlsx",
                    "declaration": "declaration.pdf",
                    "technical_schedule": "technical.pdf",
                    "compulsory_form": "form.pdf",
                    "mandatory_attachment": "attachment.pdf",
                },
                "signed_by": "operator",
            }
        ]
    )

    latest = service.latest_returnable_governance()
    history = service.returnable_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["returnable_governance_status"] == "ok"
    assert latest["bid_response_completeness_score"] >= 90.0
    assert latest["latest_returnable_governance"]["annexure_classification"] == "annexure_detected"
    assert latest["latest_returnable_governance"]["pricing_schedule_completeness"] is True
    assert latest["latest_returnable_governance"]["declaration_completeness"] is True
    assert latest["latest_returnable_governance"]["technical_schedule_completeness"] is True
    assert latest["latest_returnable_governance"]["compulsory_form_readiness"] is True
    assert latest["latest_returnable_governance"]["mandatory_attachment_completeness"] is True
    assert latest["latest_returnable_governance"]["governance_approval_gating"] is True
    assert history["count"] >= 1


def test_returnable_governance_service_flags_missing_and_unsigned_returnables(tmp_path) -> None:
    module = importlib.import_module("app.services.returnable_governance_service")
    service = module.ReturnableGovernanceService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        export_root=tmp_path / "runtime" / "staging" / "governance-exports",
    )
    service.operator_sessions = _DummyOperatorSessionsService(_session(active=False, acknowledged=False, supervision_score=70.0))
    service.readiness = _DummyReadinessService(
        {
            "status": "watch",
            "declaration_status": "NO_GO",
            "declaration_score": 70.0,
            "declaration_rationale_summary": {"no_go_status": "FAIL"},
        }
    )
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-RET-002",
                "title": "Incomplete returnables schedule",
                "returnable_requirements": {
                    "annexure": True,
                    "mandatory_returnable": True,
                    "pricing_schedule": True,
                    "declaration": True,
                },
                "returnables": {
                    "pricing_schedule": "pricing.xlsx",
                },
            }
        ]
    )

    latest = service.latest_returnable_governance()

    assert latest["status"] == "blocked"
    assert latest["returnable_governance_status"] == "blocked"
    assert latest["latest_returnable_governance"]["incomplete_returnable_warnings"]
    assert latest["latest_returnable_governance"]["missing_annexure_indicators"]["annexure_missing"] is True
    assert latest["latest_returnable_governance"]["unsigned_returnable_warnings"]
    assert latest["latest_returnable_governance"]["returnable_governance_decision"] == "block_returnable_governance"
