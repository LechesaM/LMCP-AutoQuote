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

    def operator_session_history(self, limit: int = 20):
        return {"status": "ok", "count": 1, "operator_session_history": [self._session], "warning_indicators": {}, "warnings": []}


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def get_item(self, rfq_id: str):
        item = self._items.get(rfq_id)
        return {"status": "ok", "item": item} if item else {"status": "not_found", "rfq_id": rfq_id}


def _session(*, status: str = "active", acknowledged: bool = True, active: bool = True, supervision_score: float = 95.0):
    return {
        "operator_session_id": "cycle-1:operator-session",
        "cycle_id": "cycle-1",
        "generated_at": "2026-06-23T15:55:59.582013+00:00",
        "status": status,
        "operator_name": "staging-governance-operator",
        "operator_role": "governance_reviewer",
        "operator_acknowledgement": {
            "acknowledged": acknowledged,
            "approved_at": "2026-06-23T00:00:00+00:00" if acknowledged else "",
            "approved_rehearsal_sequence": [
                "operator_review",
                "governance_checkpoint",
                "cadence_verification",
                "readiness_verification",
                "evidence_pack_validation",
            ] if acknowledged else [],
            "notes": [],
        },
        "approved_rehearsal_sequence": [
            "operator_review",
            "governance_checkpoint",
            "cadence_verification",
            "readiness_verification",
            "evidence_pack_validation",
        ] if acknowledged else [],
        "active_operator_session": active,
        "supervised_rfq_assignments": [
            {"rfq_id": "REHEARSAL-RETRY-001", "source_cycle_id": "cycle-1", "assigned_at": "2026-06-23T15:55:59.582013+00:00", "supervision_state": "assigned"},
            {"rfq_id": "REHEARSAL-DLQ-001", "source_cycle_id": "cycle-1", "assigned_at": "2026-06-23T15:55:59.582013+00:00", "supervision_state": "assigned"},
        ],
        "assigned_rfq_count": 2,
        "active_rfq_count": 2 if active else 0,
        "approval_checkpoints": [],
        "pending_approval_checkpoints": [],
        "escalation_acknowledgements": [],
        "supervision_window": {
            "started_at": "2026-06-23T15:55:59.582013+00:00",
            "ends_at": "2026-06-24T15:55:59.582013+00:00" if active else "2026-06-22T15:55:59.582013+00:00",
            "active": active,
            "window_hours": 24,
        },
        "operator_supervision_score": supervision_score,
        "unattended_rfq_warnings": [] if acknowledged else ["operator_acknowledgement_missing"],
        "supervision_lapse_indicators": {
            "operator_acknowledgement_missing": not acknowledged,
            "supervision_window_closed": not active,
            "approval_backlog_present": False,
            "readiness_not_ready": False,
            "no_go_history_present": False,
        },
        "escalation_sla_tracking": {"sla_hours": 12, "cycle_age_hours": 0.25, "within_sla": True},
        "supervision_coverage": {"coverage_rate": 100.0 if acknowledged and active else 0.0},
        "warnings": [] if acknowledged and active else ["operator_acknowledgement_missing"],
    }


def test_supervised_rfq_intake_service_approves_in_scope_rfqs(tmp_path) -> None:
    module = importlib.import_module("app.services.supervised_rfq_intake_service")
    service = module.SupervisedRfqIntakeService(cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles", export_root=tmp_path / "runtime" / "staging" / "governance-exports")
    service.operator_sessions = _DummyOperatorSessionsService(_session())
    service.readiness = _DummyReadinessService({"status": "ok", "declaration_status": "READY_FOR_CONTROLLED_PILOT", "declaration_grade": "ready", "declaration_score": 96.0, "declaration_rationale_summary": {"no_go_status": "PASS"}})
    service.lifecycle = _DummyLifecycleService({
        "REHEARSAL-RETRY-001": {"rfq_id": "REHEARSAL-RETRY-001", "title": "Office consumables", "category": "Office Consumables"},
        "REHEARSAL-DLQ-001": {"rfq_id": "REHEARSAL-DLQ-001", "title": "Stationery", "category": "Stationery Supplies"},
    })

    latest = service.latest_intake()
    history = service.intake_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["intake_status"] == "ok"
    assert latest["intake_eligibility_score"] >= 90.0
    assert latest["governance_approval_gating"] is True
    assert latest["supervision_capacity_validation"] is True
    assert latest["pilot_scope_enforced"] is True
    assert latest["restricted_category_warning"] is False
    assert history["count"] >= 1
    assert history["intake_decision_history"][0]["intake_decision"] == "approve_intake"


def test_supervised_rfq_intake_service_blocks_restricted_categories(tmp_path) -> None:
    module = importlib.import_module("app.services.supervised_rfq_intake_service")
    service = module.SupervisedRfqIntakeService(cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles", export_root=tmp_path / "runtime" / "staging" / "governance-exports")
    service.operator_sessions = _DummyOperatorSessionsService(_session(acknowledged=False, active=False, status="blocked", supervision_score=72.0))
    service.readiness = _DummyReadinessService({"status": "watch", "declaration_status": "WATCH", "declaration_grade": "watch", "declaration_score": 72.0, "declaration_rationale_summary": {"no_go_status": "PASS"}})
    service.lifecycle = _DummyLifecycleService({
        "REHEARSAL-RETRY-001": {"rfq_id": "REHEARSAL-RETRY-001", "title": "Catering services", "category": "Catering"},
        "REHEARSAL-DLQ-001": {"rfq_id": "REHEARSAL-DLQ-001", "title": "Office consumables", "category": "Office Consumables"},
    })

    latest = service.latest_intake()

    assert latest["status"] == "blocked"
    assert latest["intake_status"] == "blocked"
    assert latest["restricted_category_warnings"]
    assert latest["restricted_category_warning"] is True
    assert latest["supervision_capacity_validation"] is False
    assert latest["governance_approval_gating"] is False
    assert latest["operator_assignment_readiness"] is False
    assert "restricted_category_warning" in latest["warnings"]
