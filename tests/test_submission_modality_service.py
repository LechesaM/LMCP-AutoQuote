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


def test_submission_modality_service_approves_mixed_supported_modalities(tmp_path) -> None:
    module = importlib.import_module("app.services.submission_modality_governance_service")
    service = module.SubmissionModalityGovernanceService(
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
                "rfq_id": "RFQ-MODALITY-001",
                "title": "Office stationery procurement",
                "submission_method": "email",
                "submission_channel": "email",
                "recipient_email": "buyer@example.org",
                "submission_pack": {"ready": True},
            },
            {
                "rfq_id": "RFQ-MODALITY-002",
                "title": "Portal tender",
                "submission_method": "portal",
                "submission_channel": "portal",
                "portal_url": "https://example.org/tender",
                "submission_pack": {"ready": True},
            },
            {
                "rfq_id": "RFQ-MODALITY-003",
                "title": "Courier hand delivery",
                "submission_method": "courier_hand_delivery",
                "submission_channel": "physical",
                "submission_pack": {"ready": True},
                "manual_handoff": "handoff-1",
                "chain_of_custody": "custody-1",
                "proof_of_delivery": "pod-1",
                "signature_placeholder": "{{signature}}",
                "seal_placeholder": "{{seal}}",
            },
        ]
    )

    latest = service.latest_submission_modality()
    history = service.submission_modality_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["submission_modality_status"] == "ok"
    assert latest["modality_governance_score"] >= 85.0
    assert latest["latest_submission_modality"]["selected_modality"] in {"email", "portal", "physical"}
    assert latest["latest_submission_modality"]["governance_approval_gating"] is True
    assert history["count"] >= 1


def test_submission_modality_service_blocks_unsupported_and_conflicts(tmp_path) -> None:
    module = importlib.import_module("app.services.submission_modality_governance_service")
    service = module.SubmissionModalityGovernanceService(
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
                    "rfq_id": "RFQ-MODALITY-004",
                    "title": "Unsupported channel tender",
                    "submission_method": "fax",
                    "submission_channel": "fax",
                    "submission_pack": {"ready": False},
                }
            ]
        )

    latest = service.latest_submission_modality()

    assert latest["status"] == "blocked"
    assert latest["submission_modality_status"] == "blocked"
    assert latest["latest_submission_modality"]["selected_modality"] == "unsupported"
    assert latest["latest_submission_modality"]["unsupported_modality_warnings"]
    assert latest["latest_submission_modality"]["modality_conflict_indicators"]["selected_modality_missing"] is True
