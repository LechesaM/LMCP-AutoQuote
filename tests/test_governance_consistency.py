import json

from app.governance.audit_chain_validator import build_audit_chain_validation
from app.governance.compliance_controls import build_compliance_controls
from app.stabilization.governance_consistency_validator import build_governance_consistency_report


def _assert_json_safe(payload):
    json.dumps(payload, default=str)


def test_governance_consistency_checks_are_json_safe():
    payload = build_governance_consistency_report(limit=25)
    _assert_json_safe(payload)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert isinstance(payload["checks"], list)
    assert "manual-only governance" in " ".join(check["label"] for check in payload["checks"])


def test_audit_chain_validation_reports_continuity():
    payload = build_audit_chain_validation(limit=25)
    _assert_json_safe(payload)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert "integrity_score" in payload
    assert "defensibility_report" in payload


def test_compliance_controls_preserve_manual_only_governance():
    payload = build_compliance_controls(limit=25)
    _assert_json_safe(payload)
    assert payload["manual_governance_only"] is True
    assert payload["controls"]["manual_submission_only"] is True
    assert payload["controls"]["review_ready_enforced"] is True
    assert payload["controls"]["proof_capture_enforced"] is True

