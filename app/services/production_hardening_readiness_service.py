from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.backup_restore_governance_service import BackupRestoreGovernanceService
from app.services.compliance_regulatory_governance_service import ComplianceRegulatoryGovernanceService
from app.services.controlled_automation_orchestration_service import ControlledAutomationOrchestrationService
from app.services.data_residency_governance_service import data_residency_governance_service
from app.services.disaster_recovery_governance_service import DisasterRecoveryGovernanceService
from app.services.executive_decision_workspace_service import ExecutiveDecisionWorkspaceService
from app.services.operational_runbook_readiness_service import OperationalRunbookReadinessService
from app.services.production_cutover_readiness_service import ProductionCutoverReadinessService
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.security_hardening_readiness_service import SecurityHardeningReadinessService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "production-hardening-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "production_hardening_readiness_history.json"


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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _unique(values: List[str]) -> List[str]:
    seen: List[str] = []
    for value in values:
        text = _safe_str(value)
        if text and text not in seen:
            seen.append(text)
    return seen


def _component(name: str, payload: Dict[str, Any], ready_key: str = "ready", status_key: Optional[str] = None, score_key: Optional[str] = None, blockers_key: Optional[str] = None) -> Dict[str, Any]:
    ready = bool(payload.get(ready_key))
    status = _safe_str(payload.get(status_key), "ok" if ready else "blocked") if status_key else ("ok" if ready else "blocked")
    score = _safe_float(payload.get(score_key), 100.0 if ready else 0.0) if score_key else (100.0 if ready else 0.0)
    blockers: List[str] = []
    if blockers_key:
        value = payload.get(blockers_key)
        if isinstance(value, list):
            blockers.extend(_safe_str(item) for item in value if _safe_str(item))
    if not ready and not blockers:
        blockers.append(f"{name} not ready")
    return {"ready": ready, "status": status, "score": round(score, 2), "blockers": blockers, "source": payload}


def _synthetic_final_governance_release_readiness(
    cutover: Dict[str, Any],
    runbook: Dict[str, Any],
    security: Dict[str, Any],
    controlled: Dict[str, Any],
) -> Dict[str, Any]:
    ready = all(bool(component.get("ready", False)) for component in (cutover, runbook, security, controlled))
    score = 100.0 if ready else 0.0
    status = "ok" if ready else "blocked"
    blockers: List[str] = []
    for name, component in (
        ("production_cutover_readiness", cutover),
        ("operational_runbook_readiness", runbook),
        ("security_hardening_readiness", security),
        ("controlled_automation_readiness", controlled),
    ):
        if not bool(component.get("ready", False)):
            blockers.append(f"{name} not ready")
        blockers.extend([str(blocker) for blocker in component.get("blockers", []) if str(blocker)])
    blockers = _unique(blockers)
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


class ProductionHardeningReadinessService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.compliance_regulatory_service = ComplianceRegulatoryGovernanceService()
        self.data_residency_service = data_residency_governance_service
        self.disaster_recovery_service = DisasterRecoveryGovernanceService()
        self.backup_restore_service = BackupRestoreGovernanceService()
        self.controlled_automation_service = ControlledAutomationOrchestrationService(runtime_dir=self.runtime_dir)
        self.executive_decision_workspace_service = ExecutiveDecisionWorkspaceService(runtime_dir=self.runtime_dir)
        self.production_cutover_service = ProductionCutoverReadinessService(runtime_dir=self.runtime_dir)
        self.operational_runbook_service = OperationalRunbookReadinessService(runtime_dir=self.runtime_dir)
        self.security_hardening_service = SecurityHardeningReadinessService(runtime_dir=self.runtime_dir)
        self.lifecycle = RfqLifecycleService()

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
        compliance = self.compliance_regulatory_service.latest_compliance_regulatory_governance()
        data_residency = self.data_residency_service.latest()
        disaster_recovery = self.disaster_recovery_service.latest_disaster_recovery_governance()
        backup_restore = self.backup_restore_service.latest_backup_restore_governance()
        controlled = self.controlled_automation_service.latest_controlled_automation_orchestration()
        executive = self.executive_decision_workspace_service.latest_executive_decision_workspace()
        cutover = self.production_cutover_service.latest_production_cutover_readiness()
        runbook = self.operational_runbook_service.latest_operational_runbook_readiness()
        security = self.security_hardening_service.latest_security_hardening_readiness()
        final_release = _synthetic_final_governance_release_readiness(cutover, runbook, security, controlled)

        components = {
            "final_governance_release_readiness": final_release,
            "compliance_regulatory_governance_readiness": compliance,
            "data_residency_sovereignty_governance_readiness": data_residency,
            "disaster_recovery_governance_readiness": disaster_recovery,
            "backup_restore_governance_readiness": backup_restore,
            "controlled_automation_readiness": controlled,
            "executive_decision_workspace_readiness": executive,
            "production_cutover_readiness": cutover,
            "operational_runbook_readiness": runbook,
            "security_hardening_readiness": security,
            "rollback_readiness": cutover.get("release_rollback_readiness") or {},
            "observability_readiness": cutover.get("observability_readiness") or {},
            "incident_response_readiness": cutover.get("incident_response_readiness") or {},
            "dr_failover_readiness": cutover.get("dr_failover_readiness") or {},
            "secrets_access_readiness": cutover.get("secrets_access_readiness") or {},
            "cicd_promotion_readiness": cutover.get("cicd_promotion_readiness") or {},
        }
        component_readiness = {
            key: _component(key, value, blockers_key="unresolved_production_hardening_blockers" if key == "production_cutover_readiness" else None)
            if key == "production_cutover_readiness"
            else {
                "ready": bool(value.get("ready", False) or value.get("status", "").lower() in {"ok", "ready", "pass"}),
                "status": _safe_str(value.get("status"), "ok" if bool(value.get("ready", False)) else "blocked"),
                "score": _safe_float(value.get("score"), 100.0 if bool(value.get("ready", False)) else 0.0),
                "blockers": list(value.get("blockers") or []),
                "source": value,
            }
            for key, value in components.items()
        }
        production_cutover = component_readiness["production_cutover_readiness"]
        operational = component_readiness["operational_runbook_readiness"]
        security_hardening = component_readiness["security_hardening_readiness"]
        rollback_ready = component_readiness["rollback_readiness"]
        observability_ready = component_readiness["observability_readiness"]
        incident_ready = component_readiness["incident_response_readiness"]
        dr_ready = component_readiness["dr_failover_readiness"]
        secrets_ready = component_readiness["secrets_access_readiness"]
        cicd_ready = component_readiness["cicd_promotion_readiness"]

        scores = [value["score"] for value in component_readiness.values()]
        hardening_score = _clamp(mean(scores))
        blockers: List[str] = []
        if not all(value["ready"] for value in component_readiness.values()):
            for name, value in component_readiness.items():
                if not value["ready"]:
                    blockers.append(f"{name}_not_ready")
                blockers.extend([str(item) for item in value["blockers"] if str(item)])
        blockers = _unique(blockers)
        ready = hardening_score >= 80.0 and not blockers
        status = "ok" if ready else "watch" if hardening_score >= 55.0 else "blocked"
        safety_boundaries = {
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
        }
        blocker_indicators = {
            "final_governance_release_blocked": not bool(final_release.get("ready", False)),
            "compliance_regulatory_blocked": not bool(compliance.get("ready", False)),
            "data_residency_blocked": not bool(data_residency.get("ready", False)),
            "disaster_recovery_blocked": not bool(disaster_recovery.get("ready", False)),
            "backup_restore_blocked": not bool(backup_restore.get("ready", False)),
            "controlled_automation_blocked": not bool(controlled.get("ready", False)),
            "executive_workspace_blocked": not bool(executive.get("ready", False)),
            "production_cutover_blocked": not bool(cutover.get("ready", False)),
            "security_hardening_blocked": not bool(security.get("ready", False)),
            "rollback_blocked": not bool(rollback_ready["ready"]),
            "observability_blocked": not bool(observability_ready["ready"]),
            "incident_response_blocked": not bool(incident_ready["ready"]),
            "dr_failover_blocked": not bool(dr_ready["ready"]),
            "secrets_access_blocked": not bool(secrets_ready["ready"]),
            "cicd_promotion_blocked": not bool(cicd_ready["ready"]),
        }
        history = [
            {"event": "production_hardening_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
            {"event": "production_hardening_safety_verified", "status": "passed" if all(safety_boundaries.values()) else "failed", "timestamp": _now_iso()},
        ]
        unresolved_blockers = blockers
        return {
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "production_hardening_readiness_id": f"production-hardening-readiness:{_now_iso()}",
            "production_hardening_readiness_status": status,
            "production_hardening_readiness_score": round(hardening_score, 2),
            "production_hardening_readiness_grade": "ready" if ready else "watch" if status == "watch" else "blocked",
            "ready": ready,
            "status": status,
            "score": round(hardening_score, 2),
            "blockers": unresolved_blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "production_cutover_readiness": cutover,
            "operational_runbook_readiness": runbook,
            "security_hardening_readiness": security,
            "release_rollback_readiness": rollback_ready,
            "observability_readiness": observability_ready,
            "incident_response_readiness": incident_ready,
            "dr_failover_readiness": dr_ready,
            "secrets_access_readiness": secrets_ready,
            "cicd_promotion_readiness": cicd_ready,
            "final_governance_release_readiness": final_release,
            "compliance_regulatory_governance_readiness": compliance,
            "data_residency_sovereignty_governance_readiness": data_residency,
            "disaster_recovery_readiness": disaster_recovery,
            "backup_restore_governance_readiness": backup_restore,
            "controlled_automation_readiness": controlled,
            "executive_decision_workspace_readiness": executive,
            "production_blocker_indicators": blocker_indicators,
            "unresolved_production_hardening_blockers": unresolved_blockers,
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
            "safety_boundaries": safety_boundaries,
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
            "production_hardening_governance_history": history,
            "production_hardening_governance_history_summary": {
                "history_count": len(history),
                "latest_score": round(hardening_score, 2),
            },
            "warnings": blockers,
        }

    def analyze_production_hardening_readiness(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "generated_at": snapshot["generated_at"],
                    "production_hardening_readiness_id": snapshot["production_hardening_readiness_id"],
                    "production_hardening_readiness_status": snapshot["production_hardening_readiness_status"],
                    "production_hardening_readiness_score": snapshot["production_hardening_readiness_score"],
                }
            )
            self._write_history(history)
        return snapshot

    def list_production_hardening_readiness(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self.analyze_production_hardening_readiness(record_history=True)
        history = self._load_history()[-max(1, int(limit)) :]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_production_hardening_readiness"] = dict(snapshot)
        payload["production_hardening_readiness_history"] = history
        payload["summary_counts"] = {
            "PASS": 1 if snapshot["production_hardening_readiness_status"] == "ok" else 0,
            "WARN": 1 if snapshot["production_hardening_readiness_status"] == "watch" else 0,
            "FAIL": 1 if snapshot["production_hardening_readiness_status"] == "blocked" else 0,
        }
        return payload

    def latest_production_hardening_readiness(self) -> Dict[str, Any]:
        return self.analyze_production_hardening_readiness(record_history=True)

    def production_hardening_readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("production_hardening_readiness_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "production_hardening_readiness_history": history,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "production_mode_enabled": False,
            "production_deployment_execution_enabled": False,
            "live_credentials_present": False,
            "live_external_alerting_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_tender_submission_enabled": False,
            "autonomous_supplier_award_enabled": False,
            "procurement_commitment_generation_enabled": False,
            "warnings": latest.get("warnings", []) if history else [],
        }
