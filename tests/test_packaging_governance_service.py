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
        "generated_at": "2026-06-23T16:12:00+00:00",
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
        "supervision_window": {"active": active, "started_at": "2026-06-23T16:12:00+00:00", "ends_at": "2026-06-24T16:12:00+00:00"},
    }


def test_packaging_governance_service_approves_well_formed_package(tmp_path) -> None:
    module = importlib.import_module("app.services.packaging_governance_service")
    service = module.PackagingGovernanceService(
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
                "rfq_id": "RFQ-PKG-001",
                "title": "Bid packaging ready",
                "submission_pack": {"ready": True},
                "attachments": ["pricing.pdf", "annexure-a.pdf"],
                "zip_path": "/tmp/package.zip",
                "print_pack_path": "/tmp/print-pack.pdf",
                "upload_package_path": "/tmp/upload",
                "folder_structure_valid": True,
                "naming_convention_ok": True,
            }
        ]
    )

    latest = service.latest_packaging_governance()
    history = service.packaging_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["packaging_governance_status"] == "ok"
    assert latest["packaging_readiness_score"] >= 85.0
    assert latest["latest_packaging_governance"]["submission_bundle_completeness"] is True
    assert latest["latest_packaging_governance"]["attachment_bundle_validation"] is True
    assert latest["latest_packaging_governance"]["zip_package_integrity"] is True
    assert latest["latest_packaging_governance"]["print_pack_readiness"] is True
    assert latest["latest_packaging_governance"]["folder_structure_validation"] is True
    assert latest["latest_packaging_governance"]["naming_convention_governance"] is True
    assert latest["latest_packaging_governance"]["upload_package_readiness"] is True
    assert history["count"] >= 1


def test_packaging_governance_service_flags_incomplete_bundle(tmp_path) -> None:
    module = importlib.import_module("app.services.packaging_governance_service")
    service = module.PackagingGovernanceService(
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
                "rfq_id": "RFQ-PKG-002",
                "title": "Incomplete package",
                "submission_pack": {"ready": False},
                "attachments": [],
                "zip_path": "",
                "print_pack_path": "",
                "upload_package_path": "",
            }
        ]
    )

    latest = service.latest_packaging_governance()

    assert latest["status"] == "blocked"
    assert latest["packaging_governance_status"] == "blocked"
    assert latest["latest_packaging_governance"]["incomplete_package_warnings"]
    assert latest["latest_packaging_governance"]["malformed_bundle_indicators"]["zip_package_integrity"] is True
    assert latest["latest_packaging_governance"]["packaging_governance_decision"] == "block_packaging_governance"
