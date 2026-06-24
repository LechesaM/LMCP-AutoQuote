from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_runbook_readiness_service import OperationalRunbookReadinessService
from app.services.security_hardening_readiness_service import SecurityHardeningReadinessService
from app.services.controlled_automation_orchestration_service import ControlledAutomationOrchestrationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "production-hardening-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "production_cutover_readiness_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _synthetic_final_governance_release_readiness(
    runbook: Dict[str, Any],
    security: Dict[str, Any],
    controlled: Dict[str, Any],
) -> Dict[str, Any]:
    ready = all(
        bool(component.get("ready", False))
        for component in (runbook, security, controlled)
    )
    score = 100.0 if ready else 0.0
    status = "ok" if ready else "blocked"
    blockers: List[str] = []
    for name, component in (
        ("operational_runbook_readiness", runbook),
        ("security_hardening_readiness", security),
        ("controlled_automation_readiness", controlled),
    ):
        if not bool(component.get("ready", False)):
            blockers.append(f"{name} not ready")
        blockers.extend([str(blocker) for blocker in component.get("blockers", []) if str(blocker)])
    blockers = list(dict.fromkeys(blockers))
    now = _now_iso()
    return {
        "generated_at": now,
        "environment": "staging",
        "governance_mode": "read_only",
        "final_governance_release_readiness_id": f"final-governance-release-readiness:{now}",
        "final_governance_release_readiness_status": status,
        "final_governance_release_readiness_score": score,
        "final_governance_release_readiness_grade": "ready" if ready else "blocked",
        "ready": ready,
        "status": status,
        "score": score,
        "blockers": blockers,
        "cicd_governance_readiness": controlled,
        "safety_boundaries": {
            "read_only": True,
            "staging_only": True,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "final_automation_disabled": True,
            "no_live_credentials": True,
            "no_live_external_alerting": True,
            "no_production_data_movement": True,
        },
    }


class ProductionCutoverReadinessService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.operational_runbook_service = OperationalRunbookReadinessService(runtime_dir=self.runtime_dir)
        self.security_hardening_service = SecurityHardeningReadinessService(runtime_dir=self.runtime_dir)
        self.controlled_automation_service = ControlledAutomationOrchestrationService(runtime_dir=self.runtime_dir)

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
        runbook = self.operational_runbook_service.latest_operational_runbook_readiness()
        security = self.security_hardening_service.latest_security_hardening_readiness()
        controlled = self.controlled_automation_service.latest_controlled_automation_orchestration()
        final_release = _synthetic_final_governance_release_readiness(runbook, security, controlled)

        components = {
            "final_governance_release_readiness": final_release,
            "operational_runbook_readiness": runbook,
            "security_hardening_readiness": security,
            "controlled_automation_readiness": controlled,
            "rollback_readiness": runbook.get("release_rollback_readiness") or {},
            "observability_readiness": runbook.get("observability_readiness") or {},
            "incident_response_readiness": runbook.get("incident_response_readiness") or {},
            "dr_failover_readiness": runbook.get("dr_failover_readiness") or {},
            "secrets_access_readiness": security.get("secrets_access_readiness") or {},
            "cicd_promotion_readiness": final_release.get("cicd_governance_readiness") or {},
        }
        ready = all(bool(component.get("ready", False)) for component in components.values())
        score = mean([100.0 if bool(component.get("ready", False)) else 0.0 for component in components.values()])
        blockers: List[str] = []
        for name, component in components.items():
            if not bool(component.get("ready", False)):
                blockers.append(f"{name}_not_ready")
            blockers.extend([str(blocker) for blocker in component.get("blockers", []) if str(blocker)])
        blockers = list(dict.fromkeys(blockers))
        snapshot = {
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "production_cutover_readiness_id": f"production-cutover-readiness:{_now_iso()}",
            "production_cutover_readiness_status": "ok" if ready else "blocked",
            "production_cutover_readiness_score": round(score, 2),
            "production_cutover_readiness_grade": "ready" if ready else "blocked",
            "ready": ready,
            "status": "ok" if ready else "blocked",
            "score": round(score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "NO_GO",
            "production_cutover_readiness": {"ready": ready, "status": "ok" if ready else "blocked", "score": round(score, 2), "blockers": blockers},
            "operational_runbook_readiness": runbook,
            "security_hardening_readiness": security,
            "release_rollback_readiness": components["rollback_readiness"],
            "observability_readiness": components["observability_readiness"],
            "incident_response_readiness": components["incident_response_readiness"],
            "dr_failover_readiness": components["dr_failover_readiness"],
            "secrets_access_readiness": components["secrets_access_readiness"],
            "cicd_promotion_readiness": components["cicd_promotion_readiness"],
            "production_blocker_indicators": {
                "final_governance_blocked": not bool(final_release.get("ready")),
                "dry_run_enforced": bool(final_release.get("safety_boundaries", {}).get("dry_run_enforced", True)),
                "human_supervision_required": bool(final_release.get("safety_boundaries", {}).get("human_supervision_required", True)),
                "controlled_automation_blocked": not bool(controlled.get("ready", False)),
                "security_hardening_blocked": not bool(security.get("ready", False)),
                "rollback_blocked": not bool(runbook.get("release_rollback_readiness", {}).get("ready", False)),
            },
            "unresolved_production_hardening_blockers": blockers,
            "production_mode_enabled": False,
            "production_deployment_execution_enabled": False,
            "live_credentials_present": False,
            "live_external_alerting_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_tender_submission_enabled": False,
            "autonomous_supplier_award_enabled": False,
            "procurement_commitment_generation_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "production_cutover_human_approval_required": True,
            "rollback_planning_required": True,
            "security_review_required": True,
            "governance_rules": {
                "advisory_only": True,
                "read_only": True,
                "staging_only": True,
                "dry_run_enforced": True,
                "human_supervision_required": True,
                "production_cutover_human_approval_required": True,
                "rollback_planning_required": True,
                "security_review_required": True,
                "production_mode_enabled": False,
                "production_deployment_execution_enabled": False,
                "live_credentials_present": False,
                "live_external_alerting_enabled": False,
                "autonomous_procurement_execution_enabled": False,
                "autonomous_tender_submission_enabled": False,
                "autonomous_supplier_award_enabled": False,
                "procurement_commitment_generation_enabled": False,
            },
            "production_hardening_governance_history": [
                {"event": "production_hardening_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "cutover_and_security_boundaries_verified", "status": "passed" if ready else "failed", "timestamp": _now_iso()},
            ],
            "warnings": blockers,
        }
        return snapshot

    def latest_production_cutover_readiness(self) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = self._load_history()
        history.append(
            {
                "generated_at": snapshot["generated_at"],
                "production_cutover_readiness_id": snapshot["production_cutover_readiness_id"],
                "production_cutover_readiness_status": snapshot["production_cutover_readiness_status"],
                "production_cutover_readiness_score": snapshot["production_cutover_readiness_score"],
            }
        )
        self._write_history(history)
        return snapshot

    def list_production_cutover_readiness(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self.latest_production_cutover_readiness()
        history = self._load_history()[-max(1, int(limit)) :]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_production_cutover_readiness"] = dict(snapshot)
        payload["production_cutover_readiness_history"] = history
        return payload

    def production_cutover_readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("production_cutover_readiness_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "production_cutover_readiness_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
