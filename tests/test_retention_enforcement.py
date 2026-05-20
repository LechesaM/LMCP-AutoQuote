from __future__ import annotations

import json

from app.governance.legal_hold_manager import get_legal_holds, register_legal_hold, release_legal_hold
from app.governance.retention_enforcement import build_retention_enforcement_report


def test_retention_dry_run_safe():
    payload = build_retention_enforcement_report()
    json.dumps(payload)
    assert payload["dry_run_only"] is True
    assert payload["requires_explicit_confirmation"] is True


def test_legal_hold_overrides_retention():
    hold = register_legal_hold(scope="audit_events", reason="Litigation hold", case_reference="CASE-001", operator_id="tester", note="pytest")
    try:
        payload = build_retention_enforcement_report()
        json.dumps(payload)
        assert payload["blocked_by_legal_hold"]
    finally:
        release_legal_hold(hold["hold"]["hold_id"], operator_id="tester", note="cleanup")


def test_no_destructive_deletion_by_default():
    payload = build_retention_enforcement_report(dry_run=True, confirm=False)
    json.dumps(payload)
    assert payload["dry_run_result"]["deleted"] == []

