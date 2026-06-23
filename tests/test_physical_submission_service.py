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
        "generated_at": "2026-06-23T15:55:59.582013+00:00",
        "status": "active" if active else "blocked",
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
        "pending_approval_checkpoints": [],
        "operator_supervision_score": supervision_score,
        "supervision_coverage": {"coverage_rate": 100.0 if acknowledged and active else 0.0},
        "supervision_window": {"active": active, "started_at": "2026-06-23T15:55:59.582013+00:00", "ends_at": "2026-06-24T15:55:59.582013+00:00"},
    }


def test_physical_submission_service_approves_physical_courier_rfqs(tmp_path) -> None:
    module = importlib.import_module("app.services.physical_submission_governance_service")
    service = module.PhysicalSubmissionGovernanceService(
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
                "rfq_id": "RFQ-PHYSICAL-001",
                "title": "Courier delivery of stationery",
                "submission_method": "courier_hand_delivery",
                "current_state": "APPROVAL_READY",
                "submission_pack": {"ready": True},
                "chain_of_custody": "custody-log-1",
                "proof_of_delivery": "pod-1",
                "manual_handoff": "handoff-1",
                "signature_placeholder": "{{signature}}",
                "seal_placeholder": "{{seal}}",
                "submission_deadline": "2026-06-26T12:00:00+00:00",
            }
        ]
    )

    latest = service.latest_physical_submission()
    history = service.physical_submission_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["physical_rfq_governance_status"] == "ok"
    assert latest["physical_submission_readiness_score"] >= 90.0
    assert latest["latest_physical_submission"]["physical_submission_required"] is True
    assert latest["latest_physical_submission"]["submission_pack_readiness"] is True
    assert latest["latest_physical_submission"]["chain_of_custody_tracking"]["chain_of_custody_present"] is True
    assert latest["latest_physical_submission"]["governance_approval_gating"] is True
    assert history["count"] >= 1


def test_physical_submission_service_blocks_missing_proof_and_no_go(tmp_path) -> None:
    module = importlib.import_module("app.services.physical_submission_governance_service")
    service = module.PhysicalSubmissionGovernanceService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        export_root=tmp_path / "runtime" / "staging" / "governance-exports",
    )
    service.operator_sessions = _DummyOperatorSessionsService(_session(active=False, acknowledged=False, supervision_score=72.0))
    service.readiness = _DummyReadinessService(
        {
            "status": "watch",
            "declaration_status": "NO_GO",
            "declaration_score": 72.0,
            "declaration_rationale_summary": {"no_go_status": "FAIL"},
        }
    )
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-PHYSICAL-002",
                "title": "Manual hand delivery of documents",
                "submission_method": "physical_delivery",
                "current_state": "REVIEW_REQUIRED",
                "submission_pack": {"ready": False},
                "submission_deadline": "",
            }
        ]
    )

    latest = service.latest_physical_submission()

    assert latest["status"] == "blocked"
    assert latest["physical_rfq_governance_status"] == "blocked"
    assert latest["physical_submission_readiness_score"] < 85.0
    assert latest["latest_physical_submission"]["submission_pack_readiness"] is False
    assert latest["latest_physical_submission"]["missing_proof_warnings"]
    assert latest["latest_physical_submission"]["delivery_deadline_warnings"]
    assert latest["latest_physical_submission"]["physical_submission_decision"] == "block_physical_submission"
