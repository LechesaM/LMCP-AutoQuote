from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.automation_execution_plan_service import AutomationExecutionPlanService
from app.services.automation_guardrail_service import AutomationGuardrailService
from app.services.automation_readiness_service import AutomationReadinessService, _safe_float, _safe_str, _unique


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "controlled-automation-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "controlled_automation_orchestration_history.json"


class ControlledAutomationOrchestrationService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.readiness_service = AutomationReadinessService(runtime_dir=self.runtime_dir)
        self.guardrail_service = AutomationGuardrailService(runtime_dir=self.runtime_dir)
        self.execution_plan_service = AutomationExecutionPlanService(runtime_dir=self.runtime_dir)

    def _load_history(self) -> List[Dict[str, Any]]:
        path = _history_file(self.runtime_dir)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text())
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        path = _history_file(self.runtime_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history[-250:], indent=2, default=str))

    def _build_snapshot(self) -> Dict[str, Any]:
        readiness = self.readiness_service.latest_automation_readiness()
        guardrail = self.guardrail_service.latest_automation_guardrail()
        execution_plan = self.execution_plan_service.latest_automation_execution_plan()

        readiness_score = _safe_float(readiness.get("automation_readiness_score"), 0.0)
        guardrail_score = _safe_float(guardrail.get("automation_guardrail_score"), 0.0)
        execution_score = _safe_float(execution_plan.get("automation_execution_plan_score"), 0.0)
        orchestration_score = round(mean([readiness_score, guardrail_score, execution_score]), 2)

        ready = bool(readiness.get("ready")) and bool(guardrail.get("guardrail_readiness", {}).get("ready")) and bool(execution_plan.get("orchestration_plan_readiness", {}).get("ready"))
        status = "ok" if ready else "watch" if orchestration_score >= 55.0 else "blocked"
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"
        blocked_indicators = {
            "final_automation_blocked": True,
            "autonomous_procurement_execution_blocked": True,
            "autonomous_tender_submission_blocked": True,
            "autonomous_supplier_award_blocked": True,
            "live_external_alerting_blocked": True,
            "production_credentials_blocked": True,
            "procurement_commitment_generation_blocked": True,
            "dry_run_only": True,
            "human_supervision_active": True,
            "human_approval_checkpoints_required": True,
            "rollback_planning_required": True,
            "auditability_required": True,
        }
        blocked_indicators.update(guardrail.get("blocked_automation_indicators") or {})
        blockers = _unique(
            list(readiness.get("unresolved_automation_blockers") or [])
            + list(guardrail.get("unresolved_automation_blockers") or [])
            + list(execution_plan.get("unresolved_automation_blockers") or [])
        )
        history = [
            {
                "event": "controlled_automation_orchestration_initialized",
                "status": status,
                "score": orchestration_score,
                "timestamp": _now_iso(),
            },
            {
                "event": "controlled_automation_orchestration_verified_dry_run_only",
                "status": "passed" if bool(execution_plan.get("dry_run_enforced")) else "failed",
                "timestamp": _now_iso(),
            },
        ]
        safety_boundaries = {
            "read_only": True,
            "staging_only": True,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "human_approval_checkpoints_required": True,
            "auditability_required": True,
            "rollback_planning_required": True,
            "lmcp_allow_final_automation": False,
            "final_automation_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_tender_submission_enabled": False,
            "autonomous_supplier_award_enabled": False,
            "live_external_alerting_enabled": False,
            "production_credentials_present": False,
            "procurement_commitment_generation_enabled": False,
        }
        unresolved_blockers = _unique(blockers)
        automation_rationale = {
            "summary": "Controlled automation orchestration is advisory only, dry-run only, and supervised." if ready else "Controlled automation orchestration is blocked until unresolved blockers are cleared.",
            "score_impact": {
                "automation_readiness_score": readiness_score,
                "guardrail_score": guardrail_score,
                "execution_plan_score": execution_score,
                "final_score": orchestration_score,
            },
        }
        return {
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "controlled_automation_orchestration_id": f"controlled-automation-orchestration:{_now_iso()}",
            "controlled_automation_orchestration_status": status,
            "controlled_automation_orchestration_score": orchestration_score,
            "controlled_automation_orchestration_grade": grade,
            "automation_readiness_score": readiness_score,
            "automation_readiness": readiness,
            "guardrail_readiness": guardrail.get("guardrail_readiness") or {},
            "automation_guardrail": guardrail,
            "orchestration_plan_readiness": execution_plan.get("orchestration_plan_readiness") or {},
            "automation_execution_plan": execution_plan,
            "supervised_step_planning_readiness": execution_plan.get("supervised_step_planning_readiness") or {},
            "dry_run_execution_plan_readiness": execution_plan.get("dry_run_execution_plan_readiness") or {},
            "human_approval_checkpoint_readiness": execution_plan.get("human_approval_checkpoint_readiness") or {},
            "rollback_planning_readiness": execution_plan.get("rollback_planning_readiness") or {},
            "auditability_readiness": execution_plan.get("auditability_readiness") or {},
            "final_automation_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_tender_submission_enabled": False,
            "autonomous_supplier_award_enabled": False,
            "live_external_alerting_enabled": False,
            "production_credentials_present": False,
            "procurement_commitment_generation_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "human_approval_checkpoints_required": True,
            "auditability_required": True,
            "rollback_planning_required": True,
            "blocked_automation_indicators": blocked_indicators,
            "unresolved_automation_blockers": unresolved_blockers,
            "safety_boundaries": safety_boundaries,
            "governance_rules": {
                "advisory_only": True,
                "read_only": True,
                "staging_only": True,
                "dry_run_enforced": True,
                "human_supervision_required": True,
                "human_approval_checkpoints_required": True,
                "auditability_required": True,
                "rollback_planning_required": True,
                "lmcp_allow_final_automation": False,
                "no_autonomous_procurement_execution": True,
                "no_autonomous_tender_submission": True,
                "no_autonomous_supplier_award": True,
                "no_live_external_alerting": True,
                "no_production_credentials": True,
                "no_procurement_commitment_generation": True,
            },
            "automation_orchestration_history": history,
            "automation_orchestration_history_summary": {
                "history_count": len(history),
                "latest_score": orchestration_score,
                "recovery_state_history": [{"recovery_state": "recovered" if ready else "unresolved-blocked"}],
            },
            "ready": ready,
            "status": status,
            "score": orchestration_score,
            "grade": grade,
            "automation_orchestration_rationale": automation_rationale,
            "what_this_unlocks": [
                "automation readiness coordination",
                "dry-run execution planning",
                "human approval checkpoints",
                "rollback planning",
                "auditability evidence",
            ],
            "warnings": [
                "Controlled automation orchestration remains advisory only" if status != "ok" else "",
                "Final automation remains disabled" if not ready else "",
            ],
        }

    def analyze_controlled_automation_orchestration(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "generated_at": snapshot["generated_at"],
                    "controlled_automation_orchestration_id": snapshot["controlled_automation_orchestration_id"],
                    "controlled_automation_orchestration_status": snapshot["controlled_automation_orchestration_status"],
                    "controlled_automation_orchestration_score": snapshot["controlled_automation_orchestration_score"],
                    "ready": snapshot["ready"],
                }
            )
            self._write_history(history)
        return snapshot

    def list_controlled_automation_orchestration(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self.analyze_controlled_automation_orchestration(record_history=True)
        history = self._load_history()[-max(1, int(limit)) :]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_controlled_automation_orchestration"] = dict(snapshot)
        payload["controlled_automation_orchestration_history"] = history
        payload["controlled_automation_orchestration_history_summary"] = {
            "history_count": len(history),
            "latest_score": snapshot["controlled_automation_orchestration_score"],
            "recovery_state_history": snapshot["automation_orchestration_history_summary"]["recovery_state_history"],
        }
        payload["summary_counts"] = {
            "PASS": 1 if snapshot["status"] == "ok" else 0,
            "WARN": 1 if snapshot["status"] == "watch" else 0,
            "FAIL": 1 if snapshot["status"] == "blocked" else 0,
        }
        return payload

    def latest_controlled_automation_orchestration(self) -> Dict[str, Any]:
        return self.analyze_controlled_automation_orchestration(record_history=True)

    def controlled_automation_orchestration_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("controlled_automation_orchestration_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "controlled_automation_orchestration_history": history,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "human_approval_checkpoints_required": True,
            "auditability_required": True,
            "rollback_planning_required": True,
            "final_automation_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_tender_submission_enabled": False,
            "autonomous_supplier_award_enabled": False,
            "live_external_alerting_enabled": False,
            "production_credentials_present": False,
            "procurement_commitment_generation_enabled": False,
            "unresolved_automation_blockers": latest.get("unresolved_automation_blockers", []) if history else [],
            "warnings": latest.get("warnings", []) if history else [],
        }
