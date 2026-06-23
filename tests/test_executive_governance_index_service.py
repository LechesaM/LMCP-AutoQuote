from __future__ import annotations

import importlib


class _DummyLatestService:
    def __init__(self, payload):
        self._payload = payload

    def latest_activation_governance(self):
        return self._payload

    def latest_supervision_command(self):
        return self._payload

    def latest_operations_audit(self):
        return self._payload

    def latest_incident_governance(self):
        return self._payload

    def latest_continuity_governance(self):
        return self._payload

    def latest_release_governance(self):
        return self._payload

    def latest_operational_intelligence(self):
        return self._payload

    def latest_executive_command(self):
        return self._payload


def _snapshot_payload(
    *,
    analysis_id: str,
    generated_at: str,
    status_key: str,
    authority_key: str,
    score_key: str,
    grade_key: str,
    history_key: str,
    status: str,
    authority: str,
    score: float,
    grade: str,
    warnings: list[str] | None = None,
    extra: dict | None = None,
):
    history_item = {
        "analysis_id": analysis_id,
        "generated_at": generated_at,
        status_key: status,
        authority_key: authority,
        score_key: score,
        grade_key: grade,
    }
    payload = {
        "analysis_id": analysis_id,
        "generated_at": generated_at,
        status_key: status,
        authority_key: authority,
        score_key: score,
        grade_key: grade,
        history_key: [history_item],
        "warnings": warnings or [],
    }
    if extra:
        payload.update(extra)
    return payload


def _build_service(tmp_path, *, score: float = 96.0, authority: str = "GO", status: str = "ok", grade: str = "ready", warnings: list[str] | None = None):
    module = importlib.import_module("app.services.executive_governance_index_service")
    generated_at = "2026-06-24T12:00:00+00:00"
    service = module.ExecutiveGovernanceIndexService(
        validation_root=tmp_path / "runtime" / "staging" / "production-rollout-validations",
        release_certification_root=tmp_path / "runtime" / "staging" / "release-certifications",
    )

    activation = _snapshot_payload(
        analysis_id="20260624T120000Z-activation",
        generated_at=generated_at,
        status_key="activation_governance_status",
        authority_key="activation_governance_authority",
        score_key="activation_governance_score",
        grade_key="activation_governance_grade",
        history_key="activation_governance_history",
        status=status,
        authority=authority,
        score=score,
        grade=grade,
        warnings=warnings,
        extra={
            "activation_governance_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
            "rollout_freeze_indicators": {"freeze_active": False},
            "institutional_rollout_certification_evidence": {"rollout_ready_for_supervised_deployment": True},
            "summary_counts": {"PASS": 1, "WARN": 0, "FAIL": 0},
        },
    )
    supervision = _snapshot_payload(
        analysis_id="20260624T120000Z-supervision",
        generated_at=generated_at,
        status_key="supervision_command_status",
        authority_key="supervision_command_authority",
        score_key="supervision_command_score",
        grade_key="supervision_command_grade",
        history_key="supervision_governance_history",
        status=status,
        authority=authority,
        score=score,
        grade=grade,
        warnings=warnings,
        extra={
            "supervision_governance_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
            "active_supervised_operators": [{"operator_name": "staging-operator"}],
            "supervision_coverage": {"supervision_coverage_score": score, "supervision_coverage_ready": True},
            "active_rfq_oversight": {"assigned_rfqs": ["RFQ-001"], "pending_approvals": []},
            "escalation_command_visibility": {"escalation_ready": True},
            "supervision_saturation": {"supervision_saturation_active": False},
            "supervision_lapse_indicators": {"operator_certification_lapse": False},
            "operational_workload_visibility": {"workload_pressure": "low"},
            "supervision_sla_visibility": {"sla_ready": True},
            "operational_freeze_indicators": {"freeze_active": False},
            "production_rollout_readiness": True,
            "latest_release_certification": {"release_authority": "GO"},
        },
    )
    audit = _snapshot_payload(
        analysis_id="20260624T120000Z-audit",
        generated_at=generated_at,
        status_key="operations_audit_status",
        authority_key="operations_audit_authority",
        score_key="operations_audit_score",
        grade_key="operations_audit_grade",
        history_key="operations_audit_history",
        status=status,
        authority=authority,
        score=score,
        grade=grade,
        warnings=warnings,
        extra={
            "operations_audit_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
            "audit_retention_indicators": {"retention_compliant": True},
            "audit_completeness_indicators": {"audit_completeness_ready": True},
            "supervised_rollout_actions": [{"action": "approve_supervised_rollout"}],
            "escalation_acknowledgements": [{"ack": True}],
            "operational_freeze_history": [{"freeze_active": False}],
            "governance_override_history": [{"override_active": False}],
            "operator_acknowledgement_history": [{"acknowledged": True}],
            "supervision_approval_history": [{"approved": True}],
            "release_decision_history": [{"decision": "support_enterprise_deployment"}],
        },
    )
    incident = _snapshot_payload(
        analysis_id="20260624T120000Z-incident",
        generated_at=generated_at,
        status_key="incident_governance_status",
        authority_key="incident_governance_authority",
        score_key="incident_governance_score",
        grade_key="incident_governance_grade",
        history_key="incident_governance_history",
        status=status,
        authority=authority,
        score=score,
        grade=grade,
        warnings=warnings,
        extra={
            "incident_governance_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
            "operational_incidents": [],
            "supervision_failures": [],
            "escalation_failures": [],
            "rollout_anomalies": [],
            "governance_breach_indicators": [],
            "operational_recovery_coordination": {"recovery_ready": True},
            "freeze_escalation_indicators": {"freeze_active": False},
            "recovery_readiness_indicators": {"recovery_ready": True},
            "incident_severity_indicators": [],
            "audit_retention_indicators": {"retention_compliant": True},
            "audit_completeness_indicators": {"audit_completeness_ready": True},
        },
    )
    continuity = _snapshot_payload(
        analysis_id="20260624T120000Z-continuity",
        generated_at=generated_at,
        status_key="continuity_governance_status",
        authority_key="continuity_governance_authority",
        score_key="continuity_governance_score",
        grade_key="continuity_governance_grade",
        history_key="continuity_governance_history",
        status=status,
        authority=authority,
        score=score,
        grade=grade,
        warnings=warnings,
        extra={
            "continuity_governance_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
            "recovery_drill_readiness": [{"status": "PASS"}],
            "disaster_recovery_rehearsal_status": [{"status": "PASS"}],
            "operator_failover_readiness": [{"status": "PASS"}],
            "supervision_continuity_readiness": [{"status": "PASS"}],
            "continuity_freeze_indicators": [{"freeze_active": False}],
            "recovery_escalation_readiness": [{"status": "PASS"}],
            "recovery_timing_indicators": [{"status": "PASS"}],
            "audit_retention_indicators": {"retention_compliant": True},
            "audit_completeness_indicators": {"continuity_governance_history_recorded": True},
        },
    )
    release = _snapshot_payload(
        analysis_id="20260624T120000Z-release",
        generated_at=generated_at,
        status_key="release_governance_status",
        authority_key="release_governance_authority",
        score_key="release_governance_score",
        grade_key="release_governance_grade",
        history_key="release_governance_history",
        status=status,
        authority=authority,
        score=score,
        grade=grade,
        warnings=warnings,
        extra={
            "release_governance_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
            "deployment_risk_indicators": {"deployment_risk": False},
            "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True, "history_available": True, "overall_validation_passed": True},
            "release_readiness_indicators": {"runtime_segmentation_ready": True, "operator_access_ready": True, "observability_ready": True, "backup_restore_ready": True, "disaster_recovery_ready": True, "high_availability_ready": True, "audit_retention_ready": True, "deployment_governance_ready": True, "submission_lock_ready": True, "dry_run_ready": True},
            "release_authority_indicators": {"go_release_authority": True, "watch_release_authority": False, "no_go_release_authority": False, "active_authority": authority},
            "summary_counts": {"PASS": 1, "WARN": 0, "FAIL": 0},
        },
    )
    intelligence = {
        "analysis_id": "20260624T120000Z-intelligence",
        "generated_at": generated_at,
        "operational_intelligence_status": status,
        "operational_intelligence_score": score,
        "operational_intelligence_grade": grade,
        "operational_intelligence_history": [
            {
                "analysis_id": "20260624T120000Z-intelligence",
                "generated_at": generated_at,
                "operational_intelligence_status": status,
                "operational_intelligence_score": score,
                "rfq_trend_score": score,
                "warnings": warnings or [],
            }
        ],
        "operational_intelligence_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
        "latest_operational_intelligence": {"analysis_id": "20260624T120000Z-intelligence", "operational_intelligence_decision": "support_supervised_pilot"},
        "summary_components": {"rfq_trend": score},
        "warnings": warnings or [],
    }
    executive_command = {
        "analysis_id": "20260624T120000Z-executive",
        "generated_at": generated_at,
        "executive_governance_status": status,
        "executive_governance_score": score,
        "executive_governance_grade": grade,
        "executive_intelligence_history": [
            {
                "analysis_id": "20260624T120000Z-executive",
                "generated_at": generated_at,
                "executive_governance_score": score,
                "executive_governance_status": status,
            }
        ],
        "executive_intelligence_history_summary": {"analysis_count": 1, "latest_score": score, "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]}},
        "latest_executive_intelligence": {"analysis_id": "20260624T120000Z-executive", "executive_governance_decision": "support_supervised_pilot"},
        "summary_components": {"procurement_health_score": score},
        "warnings": warnings or [],
    }

    service.activation_service = _DummyLatestService(activation)
    service.supervision_command_service = _DummyLatestService(supervision)
    service.audit_service = _DummyLatestService(audit)
    service.incident_service = _DummyLatestService(incident)
    service.continuity_service = _DummyLatestService(continuity)
    service.release_service = _DummyLatestService(release)
    service.intelligence_service = _DummyLatestService(intelligence)
    service.executive_command_service = _DummyLatestService(executive_command)
    return service


def test_executive_governance_index_service_ready_path(tmp_path):
    service = _build_service(tmp_path, score=96.0, authority="GO", status="ok", grade="ready")
    latest = service.latest_executive_governance_index()
    history = service.executive_governance_index_history(limit=5)

    assert latest["executive_governance_index_status"] == "ok"
    assert latest["executive_governance_index_authority"] == "GO"
    assert latest["executive_governance_index_score"] >= 85.0
    assert latest["institutional_rollout_readiness"]["ready_for_controlled_rollout"] is True
    assert latest["governance_degradation_indicators"] and not any(latest["governance_degradation_indicators"].values())
    assert latest["executive_escalation_indicators"]["human_supervision_required"] is True
    assert history["count"] == 1
    assert history["executive_governance_index_history"][0]["executive_governance_index_authority"] == "GO"


def test_executive_governance_index_service_watch_path(tmp_path):
    service = _build_service(tmp_path, score=74.0, authority="WATCH", status="watch", grade="watch", warnings=["watch governance index"])
    latest = service.latest_executive_governance_index()

    assert latest["executive_governance_index_status"] == "watch"
    assert latest["executive_governance_index_authority"] == "WATCH"
    assert latest["executive_governance_index_score"] < 85.0
    assert latest["institutional_rollout_readiness"]["ready_for_controlled_rollout"] is False
    assert latest["warnings"]
