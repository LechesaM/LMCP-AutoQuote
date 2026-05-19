from __future__ import annotations

from pathlib import Path

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.dashboard import dashboard_service
from app.domain.workflow import WorkflowStage
from app.monitoring.reporting_service import build_operational_report
from app.pilot import build_pilot_readiness_report, record_pilot_run, record_signoff, render_pilot_readiness_text
from app.pilot.pilot_metrics import reset_pilot_metrics
from app.persistence import db as persistence_db


def _prepare_runtime(monkeypatch, tmp_path: Path, pilot_mode: str = "supervised_live") -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audit_trail").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_PILOT_MODE", pilot_mode)
    monkeypatch.setenv("LMCP_OBSERVABILITY_ENABLED", "1")

    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    reset_pilot_metrics()
    persistence_db._INITIALIZED = False
    persistence_db._INITIALIZED_PATH = None

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    return runtime_dir


def _seed_governed_workflow() -> None:
    workflow_state_engine.record_transition("SL-001", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "operator", "discover")
    workflow_state_engine.record_transition("SL-001", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "operator", "evaluate")
    workflow_state_engine.record_transition("SL-001", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "operator", "price")
    workflow_state_engine.record_transition("SL-001", WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "operator", "quote")
    workflow_state_engine.record_transition(
        "SL-001",
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        "operator",
        "approval required",
    )
    workflow_state_engine.record_transition(
        "SL-001",
        WorkflowStage.APPROVAL_REQUIRED,
        WorkflowStage.APPROVED,
        "operator",
        "approved",
    )
    workflow_state_engine.record_transition(
        "SL-001",
        WorkflowStage.APPROVED,
        WorkflowStage.REVIEW_READY,
        "operator",
        "review ready",
    )
    workflow_state_engine.record_transition(
        "SL-001",
        WorkflowStage.REVIEW_READY,
        WorkflowStage.PROOF_RECORDED,
        "operator",
        "proof recorded",
    )


def test_governance_templates_require_manual_controls() -> None:
    docs_dir = Path(__file__).resolve().parents[1] / "docs"
    plan = (docs_dir / "supervised_live_pilot_plan.md").read_text(encoding="utf-8")
    governance = (docs_dir / "supervised_live_governance_checklist.md").read_text(encoding="utf-8")
    signoff = (docs_dir / "supervised_live_operator_signoff.md").read_text(encoding="utf-8")

    assert "final submission remains manual-only" in plan.lower()
    assert "manual approval completed" in governance.lower()
    assert "review_ready confirmed" in governance
    assert "proof captured" in governance.lower()
    assert "manual submission confirmation" in signoff.lower()


def test_governance_report_includes_advisory_summary(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_governed_workflow()
    record_pilot_run(
        {
            "tender_id": "SL-001",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator A",
            "actor": "Operator A",
            "outcome": "completed",
            "status": "recorded",
            "proof_confirmed": True,
        }
    )
    record_signoff(
        {
            "tender_id": "SL-001",
            "workflow_stage": "approved",
            "signoff_type": "approval",
            "signoff_status": "signed",
            "operator": "Operator A",
            "actor": "Operator A",
            "manual_submission_confirmed": True,
        }
    )
    record_signoff(
        {
            "tender_id": "SL-001",
            "workflow_stage": "review_ready",
            "signoff_type": "review",
            "signoff_status": "signed",
            "operator": "Operator A",
            "actor": "Operator A",
            "manual_submission_confirmed": True,
        }
    )
    record_signoff(
        {
            "tender_id": "SL-001",
            "workflow_stage": "proof_recorded",
            "signoff_type": "proof",
            "signoff_status": "signed",
            "operator": "Operator A",
            "actor": "Operator A",
            "manual_submission_confirmed": True,
        }
    )

    report = build_pilot_readiness_report()
    text = render_pilot_readiness_text(report)

    assert report["supervised_live_governance_summary"]["manual_only_final_submission"] is True
    assert report["governance_compliance_score"] >= 0
    assert report["manual_governance_integrity_score"] >= 0
    assert "Supervised-live governance: advisory only" in text


def test_dashboard_and_operational_reports_expose_governance_scores(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_governed_workflow()
    record_pilot_run(
        {
            "tender_id": "SL-002",
            "workflow_stage": "proof_recorded",
            "pilot_mode": "supervised_live",
            "operator": "Operator B",
            "actor": "Operator B",
            "outcome": "completed",
            "status": "recorded",
            "proof_confirmed": True,
        }
    )

    dashboard_summary = dashboard_service.get_dashboard_summary(limit=20)
    operational_report = build_operational_report(limit=20)

    assert dashboard_summary["governance_compliance_score"] >= 0
    assert dashboard_summary["manual_governance_integrity_score"] >= 0
    assert dashboard_summary["supervised_live_governance_summary"]["governance_advisory_only"] is True
    assert operational_report["governance_compliance_score"] >= 0
    assert operational_report["manual_governance_integrity_score"] >= 0
    assert operational_report["supervised_live_governance_summary"]["manual_submission_remains_required"] is True


def test_operator_signoff_requires_explicit_confirmation_documentation(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    result = record_signoff(
        {
            "tender_id": "SL-003",
            "workflow_stage": "approval_required",
            "signoff_type": "approval",
            "signoff_status": "signed",
            "operator": "Operator C",
            "actor": "Operator C",
            "manual_submission_confirmed": True,
            "note": "explicit confirmation recorded",
        }
    )

    assert result["manual_submission_confirmed"] is True
    assert result["note"] == "explicit confirmation recorded"


def test_governance_summaries_remain_advisory_only(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    report = build_pilot_readiness_report()
    assert report["supervised_live_governance_summary"]["governance_advisory_only"] is True
    assert report["supervised_live_governance_summary"]["manual_only_final_submission"] is True
