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


class _DummyModalityService:
    def latest_submission_modality(self):
        return {
            "status": "ok",
            "submission_modality_status": "ok",
            "selected_modality": "physical",
            "fallback_modality": "physical",
            "latest_submission_modality": {"selected_modality": "physical"},
            "warnings": [],
        }


class _DummyPhysicalService:
    def latest_physical_submission(self):
        return {
            "status": "ok",
            "latest_physical_submission": {
                "physical_submission_required": True,
            },
            "warnings": [],
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
            "approved_rehearsal_sequence": ["operator_review", "governance_checkpoint"] if acknowledged else [],
            "notes": [],
        },
        "approved_rehearsal_sequence": ["operator_review", "governance_checkpoint"] if acknowledged else [],
        "active_operator_session": active,
        "pending_approval_checkpoints": [],
        "operator_supervision_score": supervision_score,
        "supervision_coverage": {"coverage_rate": 100.0 if acknowledged and active else 0.0},
        "supervision_window": {"active": active, "started_at": "2026-06-23T15:55:59.582013+00:00", "ends_at": "2026-06-24T15:55:59.582013+00:00"},
    }


def test_signature_governance_service_flags_signature_workflows_and_supervision(tmp_path) -> None:
    module = importlib.import_module("app.services.signature_governance_service")
    service = module.SignatureGovernanceService(
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
    service.modality = _DummyModalityService()
    service.physical = _DummyPhysicalService()
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-SIGN-001",
                "title": "Wet signature affidavit requirement",
                "signature_requirements": {
                    "wet_signature_required": True,
                    "handwritten_declaration_required": True,
                    "witness_required": True,
                    "commissioner_required": True,
                    "affidavit_required": True,
                    "manual_attestation_required": True,
                },
                "wet_signature": "signed",
                "handwritten_declaration": "written declaration",
                "witness_name": "Witness One",
                "commissioner_name": "Commissioner One",
                "affidavit_reference": "affidavit-1",
                "manual_attestation": "attested",
            }
        ]
    )

    latest = service.latest_signature_governance()
    history = service.signature_governance_history(limit=5)

    assert latest["status"] == "watch"
    assert latest["signature_governance_status"] == "watch"
    assert latest["signature_governance_score"] >= 90.0
    assert latest["latest_signature_governance"]["wet_signature_required"] is True
    assert latest["latest_signature_governance"]["handwritten_declaration_required"] is True
    assert latest["latest_signature_governance"]["witness_required"] is True
    assert latest["latest_signature_governance"]["commissioner_required"] is True
    assert latest["latest_signature_governance"]["affidavit_required"] is True
    assert latest["latest_signature_governance"]["manual_attestation_required"] is True
    assert latest["latest_signature_governance"]["signature_completion_supervision"]["signature_supervision_ok"] is True
    assert latest["latest_signature_governance"]["operator_assignment_readiness"] is True
    assert latest["operator_assignment_readiness_summary"]["ready_count"] >= 1
    assert latest["latest_signature_governance"]["human_completion_required_warnings"]
    assert latest["latest_signature_governance"]["signature_decision"] == "watch_signature_governance"
    assert history["count"] >= 1


def test_signature_governance_service_blocks_missing_attestation_and_no_go(tmp_path) -> None:
    module = importlib.import_module("app.services.signature_governance_service")
    service = module.SignatureGovernanceService(
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
    service.modality = _DummyModalityService()
    service.physical = _DummyPhysicalService()
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-SIGN-002",
                "title": "Unsigned affidavit requirement",
                "signature_requirements": {
                    "wet_signature_required": True,
                    "handwritten_declaration_required": True,
                    "witness_required": True,
                    "commissioner_required": True,
                    "affidavit_required": True,
                    "manual_attestation_required": True,
                },
            }
        ]
    )

    latest = service.latest_signature_governance()

    assert latest["status"] == "blocked"
    assert latest["signature_governance_status"] == "blocked"
    assert latest["latest_signature_governance"]["signature_completion_supervision"]["signature_supervision_ok"] is False
    assert latest["latest_signature_governance"]["unsigned_document_indicators"]
    assert latest["latest_signature_governance"]["signature_decision"] == "block_signature_governance"
