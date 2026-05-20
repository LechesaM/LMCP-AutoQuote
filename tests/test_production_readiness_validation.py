from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_readiness_artifacts_exist_and_scorecard_is_conditional_go() -> None:
    required_files = [
        "docs/production_readiness_validation.md",
        "docs/internal_launch_runbook.md",
        "docs/supervised_live_launch_checklist.md",
        "docs/production_cutover/daily_operational_rituals.md",
        "docs/production_cutover/supervised_live_rollout_profile.md",
        "docs/operator_onboarding_checklist.md",
        "docs/governance_integrity_report.md",
        "docs/no_autonomous_execution_certification.md",
        "docs/deployment_validation_report.md",
        "docs/production_readiness_scorecard.md",
        "scripts/validate_production_stack.sh",
        "scripts/validate_frontend_build.sh",
        "scripts/validate_backend_stack.sh",
        "scripts/validate_auth_stack.sh",
    ]

    for relative_path in required_files:
        assert (ROOT / relative_path).exists(), f"Missing required artifact: {relative_path}"

    scorecard = _read("docs/production_readiness_scorecard.md").lower()
    assert "conditional_go" in scorecard
    for term in [
        "governance",
        "security",
        "telemetry",
        "operator operations",
        "deployment",
        "frontend stability",
        "backend stability",
        "auth/rbac",
        "auditability",
        "operational readiness",
    ]:
        assert term in scorecard


def test_validation_docs_cover_launch_sequence_and_governance_preservation() -> None:
    validation = _read("docs/production_readiness_validation.md").lower()
    runbook = _read("docs/internal_launch_runbook.md").lower()
    checklist = _read("docs/supervised_live_launch_checklist.md").lower()
    rituals = _read("docs/production_cutover/daily_operational_rituals.md").lower()
    operator_protocol = _read("docs/production_cutover/operator_launch_protocol.md").lower()
    onboarding = _read("docs/operator_onboarding_checklist.md").lower()
    report = _read("docs/deployment_validation_report.md").lower()
    certification = _read("docs/no_autonomous_execution_certification.md").lower()

    for phrase in [
        "deployment readiness",
        "governance integrity",
        "auth/rbac",
        "frontend production stability",
        "backend production stability",
    ]:
        assert phrase in validation

    for phrase in [
        "deployment sequence",
        "backend startup",
        "frontend startup",
        "docker deployment",
        "rollback procedure",
        "telemetry checks",
        "governance verification",
    ]:
        assert phrase in runbook

    for phrase in [
        "supervised-live",
        "manual approval",
        "review_ready",
        "proof capture",
        "operator onboarding",
    ]:
        assert phrase in checklist
        assert phrase in onboarding

    for phrase in [
        "proof capture is mandatory",
        "review_ready is mandatory",
        "final submission is manual-only",
        "escalate uncertainty",
        "never bypass governance",
        "use ao tooling daily",
        "stabilization",
        "observability",
        "governance",
        "workload balancing",
        "fatigue monitoring",
        "runtime resilience",
        "blind approvals",
        "shortcut submissions",
        "evidence skipping",
        "governance overrides",
    ]:
        assert phrase in operator_protocol

    for phrase in [
        "daily runtime review",
        "runtime alerts",
        "queue lag",
        "stale evidence",
        "source failures",
        "anomalies",
        "degraded states",
        "sla warnings",
        "daily governance review",
        "proof capture",
        "operator attribution",
        "audit continuity",
        "stale reviews",
    ]:
        assert phrase in rituals

    for phrase in [
        "frontend build",
        "backend stack",
        "auth stack",
        "docker-compose",
        "nginx",
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


def test_frontend_production_sources_do_not_hardcode_localhost_dependencies() -> None:
    api_files = [
        "frontend/command-centre/src/auth/authClient.ts",
        "frontend/command-centre/src/api/httpClient.ts",
        "frontend/command-centre/src/api/dashboardTelemetryClient.ts",
        "frontend/command-centre/src/api/sourceHealthClient.ts",
        "frontend/command-centre/src/api/reviewQueueClient.ts",
        "frontend/command-centre/src/api/qualificationClient.ts",
        "frontend/command-centre/src/api/operatorActionsClient.ts",
        "frontend/command-centre/src/api/operatorAssignmentsClient.ts",
        "frontend/command-centre/src/api/operatorTimelineClient.ts",
        "frontend/command-centre/src/api/operatorNotificationsClient.ts",
    ]
    combined = "\n".join(_read(relative_path).lower() for relative_path in api_files)

    assert "http://localhost" not in combined
    assert "https://localhost" not in combined
    assert "127.0.0.1" not in combined
