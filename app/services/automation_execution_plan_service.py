from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.automation_guardrail_service import AutomationGuardrailService
from app.services.automation_readiness_service import AutomationReadinessService, _safe_float, _safe_str, _unique


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "controlled-automation-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "automation_execution_plan_history.json"


class AutomationExecutionPlanService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.readiness_service = AutomationReadinessService(runtime_dir=self.runtime_dir)
        self.guardrail_service = AutomationGuardrailService(runtime_dir=self.runtime_dir)

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
        blockers = _unique(list(readiness.get("unresolved_automation_blockers") or []) + list(guardrail.get("unresolved_automation_blockers") or []))
        orchestration_ready = bool(readiness.get("ready")) and bool(guardrail.get("guardrail_readiness", {}).get("ready")) and not blockers
        supervised_plan_steps = [
            {
                "step": "Collect readiness evidence",
                "mode": "dry_run",
                "requires_human_approval": True,
                "executed": False,
            },
            {
                "step": "Review guardrails and blockers",
                "mode": "dry_run",
                "requires_human_approval": True,
                "executed": False,
            },
            {
                "step": "Prepare rollback plan",
                "mode": "dry_run",
                "requires_human_approval": True,
                "executed": False,
            },
            {
                "step": "Record audit evidence",
                "mode": "dry_run",
                "requires_human_approval": True,
                "executed": False,
            },
            {
                "step": "Hold execution pending supervision",
                "mode": "dry_run",
                "requires_human_approval": True,
                "executed": False,
            },
        ]
        plan_score = mean([
            100.0 if orchestration_ready else 0.0,
            100.0 if bool(guardrail.get("supervised_step_planning_readiness", {}).get("ready")) else 0.0,
            100.0 if bool(guardrail.get("blocked_automation_indicators", {}).get("dry_run_only")) else 0.0,
            100.0 if bool(guardrail.get("blocked_automation_indicators", {}).get("human_approval_checkpoints_required")) else 0.0,
            100.0 if bool(guardrail.get("blocked_automation_indicators", {}).get("rollback_planning_required")) else 0.0,
            100.0 if bool(guardrail.get("blocked_automation_indicators", {}).get("auditability_required")) else 0.0,
        ])
        human_approval = True
        rollback_ready = True
        auditability_ready = True
        dry_run_ready = True
        if not orchestration_ready:
            blockers.append("orchestration_plan_not_ready")
        history = [
            {
                "event": "automation_execution_plan_initialized",
                "status": "ready" if orchestration_ready else "blocked",
                "score": round(plan_score, 2),
                "timestamp": _now_iso(),
            },
            {
                "event": "automation_execution_plan_is_dry_run_only",
                "status": "passed" if dry_run_ready else "failed",
                "timestamp": _now_iso(),
            },
        ]
        return {
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "automation_execution_plan_id": f"automation-execution-plan:{_now_iso()}",
            "automation_execution_plan_status": "ok" if orchestration_ready else "blocked",
            "automation_execution_plan_score": round(plan_score, 2),
            "orchestration_plan_readiness": {
                "ready": orchestration_ready,
                "status": "ok" if orchestration_ready else "blocked",
                "score": round(plan_score, 2),
                "blockers": list(blockers),
                "source": readiness,
            },
            "dry_run_execution_plan_readiness": {
                "ready": dry_run_ready,
                "status": "ok",
                "score": 100.0,
                "blockers": [],
                "source": guardrail,
            },
            "human_approval_checkpoint_readiness": {
                "ready": human_approval,
                "status": "ok",
                "score": 100.0,
                "blockers": [],
                "source": guardrail,
            },
            "rollback_planning_readiness": {
                "ready": rollback_ready,
                "status": "ok",
                "score": 100.0,
                "blockers": [],
                "source": guardrail,
            },
            "auditability_readiness": {
                "ready": auditability_ready,
                "status": "ok",
                "score": 100.0,
                "blockers": [],
                "source": guardrail,
            },
            "supervised_step_planning_readiness": {
                "ready": bool(guardrail.get("supervised_step_planning_readiness", {}).get("ready")),
                "status": _safe_str(guardrail.get("supervised_step_planning_readiness", {}).get("status"), "ok"),
                "score": _safe_float(guardrail.get("supervised_step_planning_readiness", {}).get("score"), 100.0),
                "blockers": list(guardrail.get("supervised_step_planning_readiness", {}).get("blockers") or []),
                "source": guardrail,
            },
            "automation_execution_steps": supervised_plan_steps,
            "blocked_automation_indicators": guardrail.get("blocked_automation_indicators") or {},
            "unresolved_automation_blockers": blockers,
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
            "automation_execution_plan_history": history,
            "automation_execution_plan_history_summary": {
                "history_count": len(history),
                "latest_score": round(plan_score, 2),
            },
            "warnings": [
                "Automation execution plans are dry-run only" if not orchestration_ready else "",
            ],
        }

    def analyze_automation_execution_plan(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "generated_at": snapshot["generated_at"],
                    "automation_execution_plan_id": snapshot["automation_execution_plan_id"],
                    "automation_execution_plan_status": snapshot["automation_execution_plan_status"],
                    "automation_execution_plan_score": snapshot["automation_execution_plan_score"],
                }
            )
            self._write_history(history)
        return snapshot

    def list_automation_execution_plan(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self.analyze_automation_execution_plan(record_history=True)
        history = self._load_history()[-max(1, int(limit)) :]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_automation_execution_plan"] = dict(snapshot)
        payload["automation_execution_plan_history"] = history
        payload["summary_counts"] = {
            "PASS": 1 if snapshot["automation_execution_plan_status"] == "ok" else 0,
            "WARN": 1 if snapshot["automation_execution_plan_status"] == "watch" else 0,
            "FAIL": 1 if snapshot["automation_execution_plan_status"] == "blocked" else 0,
        }
        return payload

    def latest_automation_execution_plan(self) -> Dict[str, Any]:
        return self.analyze_automation_execution_plan(record_history=True)

    def automation_execution_plan_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("automation_execution_plan_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "automation_execution_plan_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
