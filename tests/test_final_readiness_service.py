from __future__ import annotations

import importlib


class _DummyComponentService:
    def __init__(self, response):
        self._response = response

    def __getattr__(self, name: str):
        if name.startswith("latest_") or name.startswith("list_"):
            return lambda *args, **kwargs: self._response
        raise AttributeError(name)


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def _session(active: bool = True, acknowledged: bool = True):
    return {
        "operator_session_id": "cycle-1:operator-session",
        "cycle_id": "cycle-1",
        "generated_at": "2026-06-23T16:18:00+00:00",
        "status": "active" if active else "blocked",
        "operator_name": "staging-governance-operator",
        "operator_role": "governance_reviewer",
        "operator_acknowledgement": {"acknowledged": acknowledged},
        "active_operator_session": active,
        "supervision_window": {"active": active},
    }


def _ready_components():
    return {
        "readiness": {
            "status": "ok",
            "declaration_status": "READY_FOR_CONTROLLED_PILOT",
            "declaration_grade": "ready",
            "declaration_score": 96.5,
            "declaration_rationale_summary": {"no_go_status": "PASS"},
            "declaration_history_summary": {"latest_declaration_status": "READY_FOR_CONTROLLED_PILOT"},
        },
        "operator_sessions": {
            "status": "ok",
            "operator_session_status": "active",
            "operator_session": _session(),
            "active_operator_sessions": [_session()],
            "active_operator_session_count": 1,
        },
        "returnable": {
            "status": "ok",
            "returnable_governance_status": "ok",
            "bid_response_completeness_score": 96.0,
            "latest_returnable_governance": {"returnable_governance_id": "RFQ-FR-001:returnable-governance"},
        },
        "packaging": {
            "status": "ok",
            "packaging_governance_status": "ok",
            "packaging_readiness_score": 95.0,
            "latest_packaging_governance": {
                "packaging_governance_id": "RFQ-FR-001:packaging-governance",
                "submission_bundle_completeness": True,
                "upload_package_readiness": True,
            },
        },
        "compliance": {
            "status": "ok",
            "compliance_artifact_governance_status": "ok",
            "compliance_readiness_score": 94.0,
            "latest_compliance_governance": {"compliance_artifact_governance_id": "RFQ-FR-001:compliance-governance"},
        },
        "signature": {
            "status": "ok",
            "signature_governance_status": "ok",
            "signature_governance_score": 95.0,
            "latest_signature_governance": {"signature_governance_id": "RFQ-FR-001:signature-governance"},
        },
        "deadline": {
            "status": "ok",
            "deadline_governance_status": "ok",
            "timing_readiness_score": 95.0,
            "latest_deadline_governance": {
                "deadline_governance_id": "RFQ-FR-001:deadline-governance",
                "overdue_submission_indicators": {"deadline_overdue": False},
                "submission_cutoff_tracking": {"deadline": "2099-12-31T12:00:00+00:00"},
            },
        },
        "modality": {
            "status": "ok",
            "modality_governance_status": "ok",
            "modality_governance_score": 95.0,
            "selected_modality": "portal",
            "latest_submission_modality": {"selected_modality": "portal"},
        },
        "physical": {
            "status": "ok",
            "physical_rfq_governance_status": "ok",
            "physical_submission_readiness_score": 95.0,
            "latest_physical_submission": {
                "physical_submission_required": False,
                "physical_submission_classification": "physical_delivery",
            },
        },
    }


def _not_ready_components():
    components = _ready_components()
    components["readiness"] = {
        "status": "watch",
        "declaration_status": "NO_GO",
        "declaration_grade": "no_go",
        "declaration_score": 70.0,
        "declaration_rationale_summary": {"no_go_status": "FAIL"},
        "declaration_history_summary": {"latest_declaration_status": "NO_GO"},
    }
    components["packaging"]["packaging_governance_status"] = "blocked"
    components["packaging"]["packaging_readiness_score"] = 65.0
    components["compliance"]["compliance_artifact_governance_status"] = "blocked"
    components["signature"]["signature_governance_status"] = "blocked"
    components["deadline"]["deadline_governance_status"] = "blocked"
    components["modality"]["modality_governance_status"] = "blocked"
    components["physical"]["physical_rfq_governance_status"] = "blocked"
    return components


def _make_service(components, items):
    module = importlib.import_module("app.services.final_readiness_governance_service")
    service = module.FinalReadinessGovernanceService(cycle_root=None, export_root=None)
    service.readiness = _DummyComponentService(components["readiness"])
    service.operator_sessions = _DummyComponentService(components["operator_sessions"])
    service.returnable = _DummyComponentService(components["returnable"])
    service.packaging = _DummyComponentService(components["packaging"])
    service.compliance = _DummyComponentService(components["compliance"])
    service.signature = _DummyComponentService(components["signature"])
    service.deadline = _DummyComponentService(components["deadline"])
    service.modality = _DummyComponentService(components["modality"])
    service.physical = _DummyComponentService(components["physical"])
    service.lifecycle = _DummyLifecycleService(items)
    return service


def test_final_readiness_service_ready_path() -> None:
    module = importlib.import_module("app.services.final_readiness_governance_service")
    service = _make_service(
        _ready_components(),
        [
            {
                "rfq_id": "RFQ-FR-001",
                "title": "Final readiness RFQ",
                "submission_deadline": "2099-12-31T12:00:00+00:00",
                "submission_method": "portal",
                "submission_pack": {"ready": True, "upload_package_path": "/tmp/upload"},
                "returnable_requirements": {"annexure": {"required": True}},
                "signature_requirements": {},
                "compliance_artifacts": {"tax_clearance": {"present": True, "valid": True}},
            }
        ],
    )

    latest = service.latest_final_readiness()
    history = service.final_readiness_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["final_submission_readiness_status"] == "READY_TO_SUBMIT"
    assert latest["latest_final_readiness"]["final_completeness_verification"]["final_completeness_ok"] is True
    assert latest["latest_final_readiness"]["final_compliance_verification"]["final_compliance_ok"] is True
    assert latest["latest_final_readiness"]["final_supervision_verification"]["supervision_ok"] is True
    assert latest["latest_final_readiness"]["governance_override_indicators"]["final_override_required"] is False
    assert latest["latest_final_readiness"]["unresolved_blocker_indicators"]["final_completeness_blocker"] is False
    assert latest["latest_final_readiness"]["final_escalation_authority"] == "operator_session"
    assert history["count"] >= 1


def test_final_readiness_service_not_ready_path() -> None:
    service = _make_service(
        _not_ready_components(),
        [
            {
                "rfq_id": "RFQ-FR-002",
                "title": "Final readiness blocked RFQ",
                "submission_deadline": "2024-01-01T00:00:00+00:00",
                "submission_method": "courier hand delivery",
                "submission_pack": {"ready": False},
                "returnable_requirements": {"annexure": {"required": True}},
                "signature_requirements": {"wet_signature_required": True},
                "compliance_artifacts": {"tax_clearance": {"present": False}},
            }
        ],
    )

    latest = service.latest_final_readiness()

    assert latest["status"] == "blocked"
    assert latest["final_submission_readiness_status"] == "NOT_READY_TO_SUBMIT"
    assert latest["latest_final_readiness"]["governance_override_indicators"]["final_override_required"] is True
    assert latest["latest_final_readiness"]["unresolved_blocker_indicators"]["final_completeness_blocker"] is True
    assert latest["latest_final_readiness"]["final_escalation_authority"] == "governance_review_board"
    assert latest["warnings"]
