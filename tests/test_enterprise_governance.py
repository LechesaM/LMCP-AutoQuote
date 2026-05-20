from __future__ import annotations

import json

from app.governance.audit_chain_validator import build_audit_chain_validation
from app.governance.compliance_controls import build_compliance_controls
from app.governance.compliance_reporting import build_compliance_report
from app.governance.governance_risk_register import build_governance_risk_register
from app.governance.policy_registry import build_policy_registry


def test_policy_registry_json_safe_and_manual_only():
    payload = build_policy_registry()
    json.dumps(payload)
    assert payload["summary"]["manualEnforcementOnly"] is True
    assert payload["summary"]["policy_count"] >= 6


def test_compliance_controls_valid():
    payload = build_compliance_controls()
    json.dumps(payload)
    assert payload["controls"]["manual_submission_only"] is True
    assert payload["controls"]["review_ready_enforced"] is True
    assert payload["controls"]["proof_capture_enforced"] is True


def test_governance_risk_register_json_safe():
    payload = build_governance_risk_register()
    json.dumps(payload)
    assert "risks" in payload
    assert "summary" in payload


def test_compliance_report_json_safe():
    payload = build_compliance_report()
    json.dumps(payload)
    assert payload["manualGovernanceOnly"] is True
    assert payload["export_ready"] is True

