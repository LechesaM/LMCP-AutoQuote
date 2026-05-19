from __future__ import annotations

from pathlib import Path

import pytest

from app.auth.auth_models import AuthPermission
from app.auth.rbac import ROLE_PERMISSIONS
from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import dispatch_operator_action


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_no_autonomous_or_bypass_permissions_exist() -> None:
    forbidden = {
        "autonomous_submit",
        "auto_approve",
        "bypass_review_ready",
        "bypass_proof_capture",
    }
    all_permissions = {permission.value for permission in AuthPermission}

    assert forbidden.isdisjoint(all_permissions)
    for permissions in ROLE_PERMISSIONS.values():
        assert forbidden.isdisjoint(set(permissions))


def test_operator_actions_require_explicit_operator_and_target() -> None:
    with pytest.raises(Exception):
        dispatch_operator_action(
            OperatorActionRequest.validate_payload({"action": "mark_reviewed", "tender_id": "RFQ-001"})
        )

    with pytest.raises(Exception):
        dispatch_operator_action(
            OperatorActionRequest.validate_payload({"operator_id": "operator-1", "action": "mark_reviewed"})
        )


def test_audit_trail_service_is_append_only() -> None:
    text = _read("app/services/audit_trail_service.py").lower()

    assert "events.append(item)" in text
    assert "save_audit_events(events)" in text
    assert "delete" not in text
    assert "truncate" not in text
    assert "overwrite" not in text


def test_governance_reports_preserve_manual_only_language() -> None:
    report = _read("docs/governance_integrity_report.md").lower()
    certification = _read("docs/no_autonomous_execution_certification.md").lower()

    for phrase in [
        "manual approval remains mandatory",
        "review_ready remains mandatory",
        "proof capture remains mandatory",
        "final submission remains manual-only",
        "append-only",
    ]:
        assert phrase in report

    for phrase in [
        "no autonomous submission",
        "no autonomous approval",
        "no review bypass",
        "no proof-capture bypass",
        "human-controlled procurement operations only",
    ]:
        assert phrase in certification
