from __future__ import annotations

import json

from app.governance.governance_attestations import build_governance_attestation


def test_governance_attestation_timestamped_and_export_safe():
    payload = build_governance_attestation(operator_id="tester", note="pytest")
    json.dumps(payload)
    assert payload["signed_style"] is True
    assert payload["export_safe"] is True
    assert payload["attestation"]["operator_id"] == "tester"
    assert payload["generated_at"]


def test_no_autonomous_execution_attestation_valid():
    payload = build_governance_attestation()
    attestation = payload["attestation"]
    assert attestation["manual_only_governance"] is True
    assert attestation["no_autonomous_submission"] is True
    assert attestation["proof_capture_enforced"] is True

