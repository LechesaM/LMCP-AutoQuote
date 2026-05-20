from __future__ import annotations

import json

from app.governance.audit_chain_validator import build_audit_chain_validation
from app.governance.audit_integrity_monitor import build_audit_integrity_monitor
from app.governance.evidence_chain_tracker import build_evidence_chain_tracker


def test_audit_chain_append_only_and_integrity(monkeypatch):
    events = [
        {"id": "1", "event_type": "operator_review", "created_at": "2024-01-01T00:00:00+00:00", "source": "test", "severity": "info", "payload": {}},
        {"id": "2", "event_type": "operator_review", "created_at": "2024-01-01T00:01:00+00:00", "source": "test", "severity": "info", "payload": {}},
    ]
    monkeypatch.setattr("app.governance.audit_chain_validator.load_audit_events", lambda: events)
    payload = build_audit_chain_validation()
    json.dumps(payload)
    assert payload["append_only_assumed"] is True
    assert payload["timestamps_sorted"] is True
    assert payload["integrity_score"] <= 100


def test_audit_chain_missing_events_and_orphan_detection(monkeypatch):
    events = [
        {"id": "1", "event_type": "operator_review", "created_at": "2024-01-01T00:00:00+00:00", "source": "test", "severity": "info", "payload": {}},
        {"id": "", "event_type": "", "created_at": "", "source": "test", "severity": "info", "payload": {}},
        {"id": "2", "event_type": "operator_action", "created_at": "2024-01-01T00:02:00+00:00", "source": "test", "severity": "info"},
    ]
    monkeypatch.setattr("app.governance.audit_chain_validator.load_audit_events", lambda: events)
    payload = build_audit_chain_validation()
    json.dumps(payload)
    assert payload["missing_required_fields"] >= 1
    assert payload["orphaned_actions"]


def test_audit_integrity_monitor_json_safe(monkeypatch):
    monkeypatch.setattr("app.governance.audit_chain_validator.load_audit_events", lambda: [])
    payload = build_audit_integrity_monitor()
    json.dumps(payload)
    assert "integrity_score" in payload


def test_evidence_chain_tracker_json_safe(monkeypatch):
    events = [
        {"id": "1", "event_type": "proof_captured", "created_at": "2024-01-01T00:00:00+00:00", "source": "test", "severity": "info", "payload": {"proof": True}},
    ]
    monkeypatch.setattr("app.governance.evidence_chain_tracker.load_audit_events", lambda: events)
    payload = build_evidence_chain_tracker()
    json.dumps(payload)
    assert payload["evidence_chain_complete"] is True

