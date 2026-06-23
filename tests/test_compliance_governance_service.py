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


def test_compliance_governance_service_approves_complete_artifacts(tmp_path) -> None:
    module = importlib.import_module("app.services.compliance_governance_service")
    service = module.ComplianceGovernanceService(
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
                "rfq_id": "RFQ-COMP-001",
                "title": "Tax clearance and BBBEE compliance",
                "compliance_requirements": {
                    "tax_clearance": {"required": True},
                    "bbbee": {"required": True},
                    "cidb": {"required": True},
                    "coida": {"required": True},
                    "nhbrc": {"required": True},
                    "company_registration": {"required": True},
                    "bank_letter": {"required": True},
                },
                "compliance_artifacts": {
                    "tax_clearance": {"present": True, "valid": True},
                    "bbbee": {"present": True, "valid": True},
                    "cidb": {"present": True, "valid": True},
                    "coida": {"present": True, "valid": True},
                    "nhbrc": {"present": True, "valid": True},
                    "company_registration": {"present": True, "valid": True},
                    "bank_letter": {"present": True, "valid": True},
                },
                "tax_clearance_document": "tax-clearance.pdf",
                "bbbee_document": "bbbee-certificate.pdf",
                "cidb_document": "cidb-certificate.pdf",
                "coida_document": "coida-certificate.pdf",
                "nhbrc_document": "nhbrc-certificate.pdf",
                "company_registration_document": "cipc.pdf",
                "bank_letter_document": "bank-letter.pdf",
                "tax_clearance_expiry": "2026-12-31T00:00:00+00:00",
                "bbbee_expiry": "2026-12-31T00:00:00+00:00",
                "cidb_expiry": "2026-12-31T00:00:00+00:00",
                "coida_expiry": "2026-12-31T00:00:00+00:00",
                "nhbrc_expiry": "2026-12-31T00:00:00+00:00",
                "company_registration_expiry": "2026-12-31T00:00:00+00:00",
                "bank_letter_expiry": "2026-12-31T00:00:00+00:00",
            }
        ]
    )

    latest = service.latest_compliance_governance()
    history = service.compliance_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["compliance_artifact_governance_status"] == "ok"
    assert latest["compliance_readiness_score"] >= 90.0
    assert latest["latest_compliance_governance"]["tax_clearance_present"] is True
    assert latest["latest_compliance_governance"]["bbbee_present"] is True
    assert latest["latest_compliance_governance"]["cidb_present"] is True
    assert latest["latest_compliance_governance"]["coida_present"] is True
    assert latest["latest_compliance_governance"]["nhbrc_present"] is True
    assert latest["latest_compliance_governance"]["company_registration_present"] is True
    assert latest["latest_compliance_governance"]["bank_letter_present"] is True
    assert latest["latest_compliance_governance"]["governance_approval_gating"] is True
    assert latest["operator_assignment_readiness_summary"]["ready_count"] >= 1
    assert history["count"] >= 1


def test_compliance_governance_service_flags_missing_and_expired_artifacts(tmp_path) -> None:
    module = importlib.import_module("app.services.compliance_governance_service")
    service = module.ComplianceGovernanceService(
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
                "rfq_id": "RFQ-COMP-002",
                "title": "Compliance gap tender",
                "compliance_requirements": {
                    "tax_clearance": {"required": True},
                    "bbbee": {"required": True},
                    "cidb": {"required": True},
                },
                "compliance_artifacts": {
                    "tax_clearance": {"present": True, "valid": False},
                    "bbbee": {"present": False, "valid": False},
                    "cidb": {"present": True, "valid": True},
                },
                "tax_clearance_expiry": "2024-01-01T00:00:00+00:00",
                "cidb_expiry": "2026-07-01T00:00:00+00:00",
            }
        ]
    )

    latest = service.latest_compliance_governance()

    assert latest["status"] == "blocked"
    assert latest["compliance_artifact_governance_status"] == "blocked"
    assert latest["latest_compliance_governance"]["missing_artifact_warnings"]
    assert any(latest["latest_compliance_governance"]["invalid_artifact_indicators"].values())
    assert latest["latest_compliance_governance"]["expiry_warnings"]
    assert latest["latest_compliance_governance"]["compliance_governance_decision"] == "block_compliance_governance"
