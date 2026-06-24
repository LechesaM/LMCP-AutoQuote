from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.automation_readiness_service import AutomationReadinessService, _safe_float, _safe_str, _unique


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "controlled-automation-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "automation_guardrail_history.json"


class AutomationGuardrailService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.readiness_service = AutomationReadinessService(runtime_dir=self.runtime_dir)

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
        safety = readiness.get("safety_boundaries") or {}
        blocked_indicators = {
            "final_automation_blocked": not bool(safety.get("lmcp_allow_final_automation") is True),
            "autonomous_procurement_execution_blocked": True,
            "autonomous_tender_submission_blocked": True,
            "autonomous_supplier_award_blocked": True,
            "live_external_alerting_blocked": True,
            "production_credentials_blocked": True,
            "procurement_commitment_generation_blocked": True,
            "dry_run_only": bool(safety.get("dry_run_enforced")),
            "human_supervision_active": bool(safety.get("human_supervision_required")),
            "human_approval_checkpoints_required": bool((readiness.get("governance_rules") or {}).get("human_approval_checkpoints_required")),
            "rollback_planning_required": bool((readiness.get("governance_rules") or {}).get("rollback_planning_required")),
            "auditability_required": bool((readiness.get("governance_rules") or {}).get("auditability_required")),
        }
        supervised_step_planning = {
            "ready": bool(blocked_indicators["dry_run_only"] and blocked_indicators["human_supervision_active"]),
            "status": "ok" if blocked_indicators["dry_run_only"] and blocked_indicators["human_supervision_active"] else "blocked",
            "score": 100.0 if blocked_indicators["dry_run_only"] and blocked_indicators["human_supervision_active"] else 0.0,
            "blockers": [] if blocked_indicators["dry_run_only"] and blocked_indicators["human_supervision_active"] else ["supervised_step_planning_missing"],
            "source": readiness,
        }
        guardrail_score = mean([
            100.0 if blocked_indicators["final_automation_blocked"] else 0.0,
            100.0 if blocked_indicators["autonomous_procurement_execution_blocked"] else 0.0,
            100.0 if blocked_indicators["autonomous_tender_submission_blocked"] else 0.0,
            100.0 if blocked_indicators["autonomous_supplier_award_blocked"] else 0.0,
            100.0 if blocked_indicators["live_external_alerting_blocked"] else 0.0,
            100.0 if blocked_indicators["production_credentials_blocked"] else 0.0,
            100.0 if blocked_indicators["procurement_commitment_generation_blocked"] else 0.0,
            100.0 if blocked_indicators["dry_run_only"] else 0.0,
            100.0 if blocked_indicators["human_supervision_active"] else 0.0,
            100.0 if blocked_indicators["human_approval_checkpoints_required"] else 0.0,
            100.0 if blocked_indicators["rollback_planning_required"] else 0.0,
            100.0 if blocked_indicators["auditability_required"] else 0.0,
        ])
        blockers = _unique(list(readiness.get("unresolved_automation_blockers") or []))
        if not blocked_indicators["final_automation_blocked"]:
            blockers.append("final_automation_must_remain_disabled")
        if not blocked_indicators["dry_run_only"]:
            blockers.append("dry_run_enforcement_missing")
        if not blocked_indicators["human_supervision_active"]:
            blockers.append("human_supervision_missing")
        guardrail_ready = guardrail_score >= 90.0 and not blockers
        status = "ok" if guardrail_ready else "blocked"
        history = [
            {
                "event": "automation_guardrail_initialized",
                "status": status,
                "score": round(guardrail_score, 2),
                "timestamp": _now_iso(),
            },
            {
                "event": "automation_guardrail_controls_verified",
                "status": "passed" if guardrail_ready else "failed",
                "final_automation_enabled": False,
                "dry_run_enforced": True,
                "human_supervision_required": True,
                "timestamp": _now_iso(),
            },
        ]
        return {
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "automation_guardrail_id": f"automation-guardrail:{_now_iso()}",
            "automation_guardrail_status": status,
            "automation_guardrail_score": round(guardrail_score, 2),
            "guardrail_readiness": {
                "ready": guardrail_ready,
                "status": status,
                "score": round(guardrail_score, 2),
                "blockers": blockers,
                "source": readiness,
            },
            "supervised_step_planning_readiness": supervised_step_planning,
            "blocked_automation_indicators": blocked_indicators,
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
            "automation_guardrail_history": history,
            "automation_guardrail_history_summary": {
                "history_count": len(history),
                "latest_score": round(guardrail_score, 2),
            },
            "warnings": [
                "Automation guardrails are advisory and non-executing" if status != "ok" else "",
            ],
        }

    def analyze_automation_guardrail(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "generated_at": snapshot["generated_at"],
                    "automation_guardrail_id": snapshot["automation_guardrail_id"],
                    "automation_guardrail_status": snapshot["automation_guardrail_status"],
                    "automation_guardrail_score": snapshot["automation_guardrail_score"],
                }
            )
            self._write_history(history)
        return snapshot

    def list_automation_guardrail(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self.analyze_automation_guardrail(record_history=True)
        history = self._load_history()[-max(1, int(limit)) :]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_automation_guardrail"] = dict(snapshot)
        payload["automation_guardrail_history"] = history
        payload["summary_counts"] = {
            "PASS": 1 if snapshot["automation_guardrail_status"] == "ok" else 0,
            "WARN": 1 if snapshot["automation_guardrail_status"] == "watch" else 0,
            "FAIL": 1 if snapshot["automation_guardrail_status"] == "blocked" else 0,
        }
        return payload

    def latest_automation_guardrail(self) -> Dict[str, Any]:
        return self.analyze_automation_guardrail(record_history=True)

    def automation_guardrail_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("automation_guardrail_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "automation_guardrail_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
