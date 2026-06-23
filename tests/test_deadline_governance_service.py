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


class _DummyPackagingService:
    def latest_packaging_governance(self):
        return {
            "status": "ok",
            "latest_packaging_governance": {
                "submission_bundle_completeness": True,
                "upload_package_readiness": True,
            },
        }


class _DummyModalityService:
    def latest_submission_modality(self):
        return {
            "status": "ok",
            "selected_modality": "portal",
            "latest_submission_modality": {"selected_modality": "portal"},
        }


class _DummyPhysicalService:
    def latest_physical_submission(self):
        return {
            "status": "ok",
            "latest_physical_submission": {"physical_submission_required": False},
        }


def _session(*, active: bool = True, acknowledged: bool = True, supervision_score: float = 95.0):
    return {
        "operator_session_id": "cycle-1:operator-session",
        "cycle_id": "cycle-1",
        "generated_at": "2026-06-23T16:18:00+00:00",
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
        "supervision_window": {"active": active, "started_at": "2026-06-23T16:18:00+00:00", "ends_at": "2026-06-24T16:18:00+00:00"},
    }


def test_deadline_governance_service_flags_overdue_deadlines(tmp_path) -> None:
    module = importlib.import_module("app.services.deadline_governance_service")
    service = module.DeadlineGovernanceService(
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
    service.packaging = _DummyPackagingService()
    service.modality = _DummyModalityService()
    service.physical = _DummyPhysicalService()
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-DL-001",
                "title": "Deadline ready",
                "submission_deadline": "2099-12-31T12:00:00+00:00",
                "submission_pack": {"ready": True, "upload_package_path": "/tmp/upload", "submission_bundle_complete": True},
                "zip_path": "/tmp/package.zip",
                "print_pack_path": "/tmp/print-pack.pdf",
                "submission_method": "portal",
                "folder_structure_valid": True,
                "attachments": ["annexure-a.pdf"],
            }
        ]
    )

    latest = service.latest_deadline_governance()
    history = service.deadline_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["deadline_governance_status"] == "ok"
    assert latest["timing_readiness_score"] >= 85.0
    assert latest["latest_deadline_governance"]["deadline_risk_warnings"] == []
    assert latest["latest_deadline_governance"]["late_submission_prevention"] is False
    assert latest["latest_deadline_governance"]["governance_approval_gating"] is True
    assert history["count"] >= 1


def test_deadline_governance_service_warns_when_overdue_and_congested(tmp_path) -> None:
    module = importlib.import_module("app.services.deadline_governance_service")
    service = module.DeadlineGovernanceService(
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
    service.packaging = _DummyPackagingService()
    service.modality = _DummyModalityService()
    service.physical = _DummyPhysicalService()
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-DL-002",
                "title": "Overdue deadline",
                "submission_deadline": "2024-01-01T00:00:00+00:00",
                "submission_pack": {"ready": False},
                "zip_path": "",
                "print_pack_path": "",
                "submission_method": "courier_hand_delivery",
            }
        ]
    )

    latest = service.latest_deadline_governance()

    assert latest["status"] == "blocked"
    assert latest["deadline_governance_status"] == "blocked"
    assert latest["latest_deadline_governance"]["deadline_risk_warnings"]
    assert latest["latest_deadline_governance"]["overdue_submission_indicators"]["deadline_overdue"] is True
    assert latest["latest_deadline_governance"]["late_submission_prevention"] is True
    assert latest["latest_deadline_governance"]["deadline_governance_decision"] == "block_deadline_governance"
