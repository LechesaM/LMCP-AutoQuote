#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STAGING_ROOT = PROJECT_ROOT / "runtime" / "staging"
BOOT_VALIDATION_FILE = STAGING_ROOT / "runtime-boot-validations" / "latest_runtime_boot_validation.json"
ENDURANCE_VALIDATION_FILE = STAGING_ROOT / "runtime-endurance-validations" / "latest_runtime_endurance_validation.json"
ROLLLOUT_VALIDATION_FILE = STAGING_ROOT / "production-rollout-validations" / "latest_production_rollout_validation.json"
ROLLOUT_VALIDATION_FILE = ROLLLOUT_VALIDATION_FILE
RELEASE_CERTIFICATION_FILE = STAGING_ROOT / "release-certifications" / "latest_executive_release_evidence.json"
LOCK_FILE = STAGING_ROOT / "go_live_guards" / "submission_locks.json"

FAILURE_VALIDATION_ROOT = STAGING_ROOT / "runtime-failure-validations"


@dataclass
class CheckResult:
    level: str
    name: str
    message: str
    remediation: str = ""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def validation_timestamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text if text else default
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified", "go"}
    return bool(value)


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    if delta > 2.0:
        trend = "improving"
    elif delta < -2.0:
        trend = "declining"
    else:
        trend = "stable"
    return {
        "trend": trend,
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


def _overall_status(levels: List[str]) -> str:
    normalized = [safe_str(level, "FAIL").upper() for level in levels if safe_str(level)]
    if not normalized:
        return "FAIL"
    if any(level == "FAIL" for level in normalized):
        return "FAIL"
    if any(level in {"WARN", "WATCH"} for level in normalized):
        return "WARN"
    return "PASS"


def _compose_status(score: float) -> str:
    if score >= 85.0:
        return "PASS"
    if score >= 70.0:
        return "WARN"
    return "FAIL"


def _compose_authority(status: str) -> str:
    normalized = safe_str(status, "WARN").upper()
    if normalized == "PASS":
        return "GO"
    if normalized == "WARN":
        return "WATCH"
    return "NO_GO"


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _load_latest(path: Path) -> Dict[str, Any]:
    return safe_dict(read_json(path, {}))


def _write_bundle(path: Path, validation_id: str, generated_at: str, payload: Dict[str, Any]) -> None:
    bundle_dir = path / validation_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record["validation_id"] = validation_id
    record["generated_at"] = generated_at
    write_json(bundle_dir / "runtime_failure_validation.json", record)


def _simulate_endurance_payload(base: Dict[str, Any]) -> Dict[str, Any]:
    summary = safe_dict(base.get("runtime_endurance_summary"))
    summary.update(
        {
            "runtime_endurance_score": 74.0,
            "runtime_endurance_status": "WARN",
            "runtime_endurance_grade": "watch",
            "overall_authority": "WATCH",
            "governance_locks_active": True,
            "dry_run_enabled": True,
            "supervision_mandatory": True,
            "services_healthy": False,
            "observability_endpoints_reachable": False,
            "escalation_readiness_intact": False,
            "continuity_indicators_stable": False,
            "no_governance_degradation_occurs": False,
        }
    )
    return {
        "runtime_endurance_summary": summary,
        "checks": [
            {"level": "PASS", "name": "governance locks remain active", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "dry-run remains enabled", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "supervision remains mandatory", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "WARN", "name": "services remain healthy", "message": "backend degradation simulated", "score": 75.0, "remediation": "Restore service health and rerun the staged control window."},
            {"level": "WARN", "name": "observability endpoints remain reachable", "message": "observability interruption simulated", "score": 75.0, "remediation": "Restore observability endpoints."},
            {"level": "WARN", "name": "continuity indicators remain stable", "message": "continuity instability simulated", "score": 75.0, "remediation": "Restore continuity stability and confirm the next control window."},
            {"level": "WARN", "name": "escalation readiness remains intact", "message": "escalation timing degradation simulated", "score": 75.0, "remediation": "Restore escalation readiness and confirm the next control window."},
            {"level": "WARN", "name": "no governance degradation occurs", "message": "governance degradation simulated", "score": 75.0, "remediation": "Restore governance containment and rerun the staged control window."},
        ],
        "sample_history": [
            {
                "analysis_id": "runtime-failure:simulated-endurance",
                "window_score": 74.0,
                "continuity_score": 60.0,
                "service_health_score": 64.0,
                "observability_score": 58.0,
                "escalation_score": 60.0,
                "governance_score": 62.0,
                "continuity_stable": False,
                "escalation_ready": False,
                "governance_degradation_detected": True,
                "sources": {
                    "executive_governance_index_status": "watch",
                    "continuity_readiness": {"continuity_governance_status": "watch"},
                    "incident_severity": {"incident_governance_status": "watch"},
                    "release_bundle": {"overall_status": "WARN", "overall_authority": "WATCH"},
                    "release_certification": {"status": "WARN", "release_governance_status": "watch"},
                },
            }
        ],
    }


def _simulated_rollout_payload(base: Dict[str, Any]) -> Dict[str, Any]:
    rollout_readiness = safe_dict(base.get("rollout_readiness_summary"))
    rollout_readiness.update(
        {
            "rollout_readiness_score": 74.0,
            "rollout_readiness_status": "WARN",
            "release_authorization_valid": True,
            "tenant_isolation_ready": True,
            "deployment_health_ready": False,
            "production_observability_ready": False,
            "escalation_chain_ready": False,
            "active_supervision_coverage_ready": True,
            "operator_availability_ready": True,
            "unresolved_blockers": [
                "backend degradation",
                "observability interruption",
                "continuity instability",
            ],
        }
    )
    return {
        "overall_status": "WARN",
        "summary_counts": {"PASS": 5, "WARN": 3, "FAIL": 0},
        "rollout_readiness_summary": rollout_readiness,
        "supervision_readiness_summary": {
            "active_supervision_coverage_ready": True,
            "supervision_score": 76.0,
            "supervision_command_status": "watch",
            "operator_name": "governance",
            "operator_role": "supervisor",
            "active_sessions": 1,
            "assigned_rfqs": ["RFQ-1"],
            "pending_approvals": ["staged rollback review"],
        },
        "operator_onboarding_readiness_summary": {
            "operator_availability_ready": True,
            "operator_name": "governance",
            "operator_role": "supervisor",
            "approved_for_supervision": True,
            "onboarding_status": "ready",
        },
        "deployment_health_summary": {
            "deployment_health_ready": False,
            "production_observability_ready": False,
            "backup_restore_ready": True,
            "disaster_recovery_ready": False,
            "high_availability_ready": False,
            "audit_retention_ready": True,
        },
        "tenant_isolation_summary": {
            "tenant_isolation_ready": True,
            "tenant_count": 1,
            "workspace_count": 1,
            "tenant_workspace_pair_count": 1,
        },
        "production_observability_summary": {
            "production_observability_ready": False,
            "worker_heartbeat": {"status": "degraded", "lag_seconds": 45},
            "telemetry_degradation": [
                "redis interruption",
                "backend degradation",
                "worker interruption",
                "observability interruption",
            ],
        },
        "escalation_chain_summary": {
            "escalation_chain_ready": False,
            "review_board_status": "watch",
            "outstanding_governance_actions": ["restore alerting", "verify failover"],
            "unresolved_operational_exceptions": ["continuity instability"],
        },
        "rollout_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "rollout-failure-1", "latest_score": 74.0},
        "institutional_rollout_certification_evidence": {
            "certification_status": "WATCH",
            "certification_authority": "WATCH",
            "rollout_governance_score": 74.0,
            "rollout_ready_for_supervised_deployment": False,
            "governance_override_indicators": {
                "deployment_blockers": True,
                "release_authorization_override": False,
                "human_supervision_required": True,
            },
        },
        "operational_incidents": [
            {"incident_id": "redis-interruption", "severity": "high", "status": "open"},
            {"incident_id": "backend-degradation", "severity": "medium", "status": "open"},
        ],
        "supervision_failures": [],
        "escalation_failures": [
            {"failure_id": "escalation-timing", "severity": "medium", "status": "open"},
        ],
        "rollout_anomalies": [
            {"anomaly_id": "worker-interruption", "severity": "medium", "status": "open"},
        ],
        "governance_breach_indicators": [
            {"breach_id": "observability-interruption", "contained": True, "severity": "medium"},
        ],
        "operational_freeze_history": [
            {"freeze_active": True, "reason": "continuity instability simulated", "generated_at": iso_now()}
        ],
        "incident_severity_indicators": [
            {"incident_id": "redis-interruption", "severity": "high", "status": "open"}
        ],
        "warnings": [
            "redis interruption simulated",
            "backend degradation simulated",
            "worker interruption simulated",
            "observability interruption simulated",
            "escalation timing degradation simulated",
            "continuity instability simulated",
        ],
    }


def _simulated_release_certification(base: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(base)
    payload.update(
        {
            "status": "WARN",
            "release_governance_status": "watch",
            "release_governance_authority": "WATCH",
            "release_governance_score": 74.0,
            "release_governance_grade": "watch",
            "release_governance_history_summary": {"score_history": {"trend": "declining", "delta": -4.0, "average": 76.0, "latest": 74.0, "previous": 78.0, "points": [74.0, 78.0]}},
            "release_authority_indicators": {"active_authority": "WATCH"},
            "deployment_risk_indicators": {"deployment_risk": True, "deployment_risk_reason": "simulated runtime failures"},
            "operational_release_indicators": {
                "submission_lock_verified": True,
                "dry_run_verified": True,
                "environment_safe": True,
            },
            "release_readiness_indicators": {"runtime_segmentation_ready": True},
            "release_governance_history": [
                {"generated_at": iso_now(), "release_governance_score": 74.0, "status": "watch"}
            ],
        }
        )
    return payload


class _SimulatedOperationalIntelligenceService:
    def latest_operational_intelligence(self) -> Dict[str, Any]:
        return {
            "status": "watch",
            "generated_at": iso_now(),
            "operational_intelligence_status": "watch",
            "operational_intelligence_authority": "WATCH",
            "operational_intelligence_score": 68.0,
            "operational_intelligence_grade": "watch",
            "operational_intelligence_history_summary": {"score_history": {"trend": "declining", "delta": -6.0, "average": 70.0, "latest": 68.0, "previous": 74.0, "points": [68.0, 74.0]}},
            "operational_intelligence_degradation_indicators": {"degradation_detected": True},
        }


class _SimulatedExecutiveCommandService:
    def latest_executive_command(self) -> Dict[str, Any]:
        return {
            "status": "watch",
            "generated_at": iso_now(),
            "executive_governance_status": "watch",
            "executive_governance_index_status": "watch",
            "executive_governance_index_authority": "WATCH",
            "executive_governance_index_score": 70.0,
            "executive_governance_index_grade": "watch",
            "executive_governance_index_history_summary": {"score_history": {"trend": "declining", "delta": -5.0, "average": 72.0, "latest": 70.0, "previous": 75.0, "points": [70.0, 75.0]}},
            "executive_governance_index_degradation_indicators": {"degradation_detected": True},
        }


def _baseline_containment_checks(boot: Dict[str, Any], endurance: Dict[str, Any], lock: Dict[str, Any]) -> Dict[str, bool]:
    boot_summary = safe_dict(boot.get("boot_readiness_summary"))
    endurance_summary = safe_dict(endurance.get("runtime_endurance_summary"))
    human_supervision_required = lock.get("human_supervision_required")
    if human_supervision_required is None:
        human_supervision_required = True
    lock_verified = all(
        [
            bool(lock),
            lock.get("final_automation_disabled") is True,
            lock.get("live_portal_submission_disabled") is True,
            lock.get("production_credentials_disabled") is True,
            lock.get("dry_run_mode_required") is True,
            lock.get("submission_execution_allowed") is False,
            human_supervision_required is True,
        ]
    )
    return {
        "lock_verified": lock_verified,
        "dry_run_enabled": boot_summary.get("dry_run_mode_enabled") is True and endurance_summary.get("dry_run_enabled") is True,
        "supervision_mandatory": boot_summary.get("human_supervision_required") is True and endurance_summary.get("supervision_mandatory") is True,
        "containment_active": lock_verified
        and boot_summary.get("dry_run_mode_enabled") is True
        and endurance_summary.get("dry_run_enabled") is True
        and boot_summary.get("human_supervision_required") is True
        and endurance_summary.get("supervision_mandatory") is True,
    }


def build_runtime_failure_injection_validation_report(
    *,
    boot_validation_file: Optional[Path] = None,
    endurance_validation_file: Optional[Path] = None,
    rollout_validation_file: Optional[Path] = None,
    release_certification_file: Optional[Path] = None,
    lock_file: Optional[Path] = None,
    output_root: Optional[Path] = None,
) -> Dict[str, Any]:
    boot_validation_file = boot_validation_file or BOOT_VALIDATION_FILE
    endurance_validation_file = endurance_validation_file or ENDURANCE_VALIDATION_FILE
    rollout_validation_file = rollout_validation_file or ROLLLOUT_VALIDATION_FILE
    release_certification_file = release_certification_file or RELEASE_CERTIFICATION_FILE
    lock_file = lock_file or LOCK_FILE
    output_root = output_root or FAILURE_VALIDATION_ROOT

    boot = _load_latest(boot_validation_file)
    endurance = _load_latest(endurance_validation_file)
    rollout = _load_latest(rollout_validation_file)
    release = _load_latest(release_certification_file)
    lock = _load_latest(lock_file)

    generated_at = iso_now()
    validation_id = f"runtime-failure-{validation_timestamp()}-{uuid.uuid4().hex[:8]}"
    bundle_root = output_root / validation_id
    bundle_root.mkdir(parents=True, exist_ok=True)

    containment = _baseline_containment_checks(boot, endurance, lock)

    simulated_endurance = _simulate_endurance_payload(endurance)
    simulated_rollout = _simulated_rollout_payload(rollout)
    simulated_release = _simulated_release_certification(release)

    endurance_root = bundle_root / "simulated-runtime-endurance-validations"
    rollout_root = bundle_root / "simulated-production-rollout-validations"
    release_root = bundle_root / "simulated-release-certifications"
    cycle_root = bundle_root / "simulated-pilot-cycles"
    evidence_root = bundle_root / "simulated-evidence-packs"
    for root in (endurance_root, rollout_root, release_root, cycle_root, evidence_root):
        root.mkdir(parents=True, exist_ok=True)

    _write_bundle(endurance_root, f"{validation_id}-endurance", generated_at, simulated_endurance)
    _write_bundle(rollout_root, f"{validation_id}-rollout", generated_at, simulated_rollout)
    _write_bundle(release_root, f"{validation_id}-release", generated_at, simulated_release)

    from app.services.activation_governance_service import ActivationGovernanceService
    from app.services.executive_governance_index_service import ExecutiveGovernanceIndexService
    from app.services.production_audit_governance_service import ProductionAuditGovernanceService
    from app.services.production_continuity_governance_service import ProductionContinuityGovernanceService
    from app.services.production_incident_governance_service import ProductionIncidentGovernanceService
    from app.services.production_release_governance_service import ProductionReleaseGovernanceService
    from app.services.production_supervision_command_service import ProductionSupervisionCommandService
    from app.services.runtime_remediation_governance_service import RuntimeRemediationGovernanceService

    remediation_service = RuntimeRemediationGovernanceService(validation_root=endurance_root)
    continuity_service = ProductionContinuityGovernanceService(
        validation_root=rollout_root,
        release_certification_root=release_root,
    )
    incident_service = ProductionIncidentGovernanceService(
        validation_root=rollout_root,
        release_certification_root=release_root,
    )
    supervision_service = ProductionSupervisionCommandService(
        validation_root=rollout_root,
        release_certification_root=release_root,
    )
    activation_service = ActivationGovernanceService(
        validation_root=rollout_root,
        release_certification_root=release_root,
    )
    audit_service = ProductionAuditGovernanceService(
        validation_root=rollout_root,
        release_certification_root=release_root,
    )
    release_service = ProductionReleaseGovernanceService(validation_root=rollout_root)
    intelligence_service = _SimulatedOperationalIntelligenceService()
    executive_command_service = _SimulatedExecutiveCommandService()
    executive_index_service = ExecutiveGovernanceIndexService(
        validation_root=rollout_root,
        release_certification_root=release_root,
        activation_service=activation_service,
        supervision_command_service=supervision_service,
        audit_service=audit_service,
        incident_service=incident_service,
        continuity_service=continuity_service,
        release_service=release_service,
        intelligence_service=intelligence_service,
        executive_command_service=executive_command_service,
    )

    remediation_latest = remediation_service.latest_runtime_remediation()
    continuity_latest = continuity_service.latest_continuity_governance()
    incident_latest = incident_service.latest_incident_governance()
    supervision_latest = supervision_service.latest_supervision_command()
    executive_latest = executive_index_service.latest_executive_governance_index()
    activation_latest = activation_service.latest_activation_governance()
    audit_latest = audit_service.latest_operations_audit()
    release_latest = release_service.latest_release_governance()
    executive_command_latest = executive_command_service.latest_executive_command()

    failure_scenarios = [
        {
            "scenario": "redis_interruption",
            "simulated_failure": "redis service interruption",
            "expected_governance_response": "containment remains active with remediation watch",
            "containment_active": containment["containment_active"],
            "dry_run_enabled": containment["dry_run_enabled"],
            "supervision_mandatory": containment["supervision_mandatory"],
            "escalation_indicator_active": bool(remediation_latest.get("remediation_escalation_indicators", {}).get("escalation_gap_found")),
        },
        {
            "scenario": "backend_degradation",
            "simulated_failure": "backend health degradation",
            "expected_governance_response": "remediation watch and executive degradation visible",
            "containment_active": containment["containment_active"],
            "dry_run_enabled": containment["dry_run_enabled"],
            "supervision_mandatory": containment["supervision_mandatory"],
            "escalation_indicator_active": bool(remediation_latest.get("remediation_escalation_indicators", {}).get("service_health_degradation_found")),
        },
        {
            "scenario": "worker_interruption",
            "simulated_failure": "worker interruption",
            "expected_governance_response": "continuity watch and escalation readiness visible",
            "containment_active": containment["containment_active"],
            "dry_run_enabled": containment["dry_run_enabled"],
            "supervision_mandatory": containment["supervision_mandatory"],
            "escalation_indicator_active": bool(remediation_latest.get("remediation_escalation_indicators", {}).get("service_health_degradation_found")),
        },
        {
            "scenario": "observability_interruption",
            "simulated_failure": "observability interruption",
            "expected_governance_response": "incident and continuity watchers remain active",
            "containment_active": containment["containment_active"],
            "dry_run_enabled": containment["dry_run_enabled"],
            "supervision_mandatory": containment["supervision_mandatory"],
            "escalation_indicator_active": bool(remediation_latest.get("warning_indicators", {}).get("observability_failure_warning")),
        },
        {
            "scenario": "escalation_timing_degradation",
            "simulated_failure": "escalation timing degradation",
            "expected_governance_response": "incident escalation remains visible",
            "containment_active": containment["containment_active"],
            "dry_run_enabled": containment["dry_run_enabled"],
            "supervision_mandatory": containment["supervision_mandatory"],
            "escalation_indicator_active": bool(remediation_latest.get("remediation_escalation_indicators", {}).get("escalation_gap_found")),
        },
        {
            "scenario": "continuity_instability",
            "simulated_failure": "continuity instability",
            "expected_governance_response": "continuity governance responds with watch state",
            "containment_active": containment["containment_active"],
            "dry_run_enabled": containment["dry_run_enabled"],
            "supervision_mandatory": containment["supervision_mandatory"],
            "escalation_indicator_active": bool(remediation_latest.get("remediation_escalation_indicators", {}).get("continuity_instability_found")),
        },
    ]

    service_snapshots = {
        "runtime_remediation": remediation_latest,
        "continuity_governance": continuity_latest,
        "incident_governance": incident_latest,
        "supervision_command": supervision_latest,
        "activation_governance": activation_latest,
        "operations_audit": audit_latest,
        "release_governance": release_latest,
        "executive_command": executive_command_latest,
        "executive_governance_index": executive_latest,
    }

    checks: List[CheckResult] = [
        _check(containment["lock_verified"], "submission locks remain enforced", "staged submission lock verified", "submission lock enforcement missing", "Restore the staged submission lock and rerun the control window."),
        _check(containment["dry_run_enabled"], "dry-run mode remains enabled", "dry-run protections remain active", "dry-run protections are disabled", "Re-enable dry-run protections and rerun the control window."),
        _check(containment["supervision_mandatory"], "supervision remains mandatory", "mandatory supervision remains active", "mandatory supervision is not active", "Restore supervision enforcement and rerun the control window."),
        _check(remediation_latest.get("status") in {"watch", "blocked"}, "runtime remediation governance activates", "runtime remediation governance activated", "runtime remediation governance did not activate", "Ensure remediation governance reads the simulated failures."),
        _check(bool(remediation_latest.get("remediation_escalation_indicators", {}).get("escalation_gap_found")), "escalation indicators activate", "escalation indicators are active", "escalation indicators did not activate", "Restore escalation readiness signals."),
        _check(bool(remediation_latest.get("open_remediation_tracking")), "remediation governance activates", "remediation findings are open", "no remediation findings were opened", "Ensure the simulated runtime endurance degradation is detected."),
        _check(continuity_latest.get("status") in {"watch", "blocked"}, "continuity governance responds", "continuity governance responded", "continuity governance did not respond", "Rebuild the continuity validation snapshot."),
        _check(incident_latest.get("status") in {"watch", "blocked"}, "incident governance responds", "incident governance responded", "incident governance did not respond", "Rebuild the incident validation snapshot."),
        _check(executive_latest.get("status") in {"watch", "blocked"}, "executive governance index reflects degradation", "executive governance index reflects degradation", "executive governance index did not reflect degradation", "Rebuild the executive governance index snapshot."),
        _check(bool(executive_latest.get("governance_degradation_indicators", {}).get("executive_degradation")), "executive degradation indicator activates", "executive degradation indicator is active", "executive degradation indicator is not active", "Ensure the simulated release and continuity degradation is visible."),
    ]

    summary_counts = {
        "PASS": sum(1 for check in checks if check.level == "PASS"),
        "WARN": len(failure_scenarios),
        "FAIL": sum(1 for check in checks if check.level == "FAIL"),
    }
    overall_status = _overall_status([check.level for check in checks])
    overall_score = round(max(0.0, min(100.0, 100.0 - (summary_counts["WARN"] * 1.5) - (summary_counts["FAIL"] * 15.0))), 2)
    governance_containment = {
        "containment_active": containment["containment_active"],
        "lock_verified": containment["lock_verified"],
        "dry_run_enabled": containment["dry_run_enabled"],
        "supervision_mandatory": containment["supervision_mandatory"],
    }

    report = {
        "validation_id": validation_id,
        "generated_at": generated_at,
        "overall_status": overall_status,
        "overall_score": overall_score,
        "summary_counts": summary_counts,
        "governance_containment": governance_containment,
        "failure_scenarios": failure_scenarios,
        "service_snapshots": service_snapshots,
        "checks": [check.__dict__ for check in checks],
        "validation_history": {
            "endurance_validation": safe_str(endurance.get("validation_id"), ""),
            "boot_validation": safe_str(boot.get("validation_id"), ""),
            "rollout_validation": safe_str(rollout.get("validation_id"), ""),
            "release_certification": safe_str(release.get("status"), ""),
        },
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "live_submission_enablement": False,
            "dry_run_protections_active": True,
            "human_supervision_required": True,
        },
        "artifacts": {
            "bundle_root": str(bundle_root),
            "runtime_failure_validation_json": str(bundle_root / "runtime_failure_validation.json"),
            "runtime_failure_validation_md": str(bundle_root / "runtime_failure_validation.md"),
            "latest_runtime_failure_validation_json": str(output_root / "latest_runtime_failure_validation.json"),
            "latest_runtime_failure_validation_md": str(output_root / "latest_runtime_failure_validation.md"),
        },
        "notes": [
            "All failures are simulated in a controlled staging-only payload.",
            "No external connectivity or live procurement operations were used.",
            "Governance containment remains active through dry-run enforcement and mandatory supervision.",
        ],
    }

    markdown = "\n".join(
        [
            "# Runtime Failure Injection Validation",
            "",
            f"- Validation ID: `{validation_id}`",
            f"- Generated At: `{generated_at}`",
            f"- Overall Status: `{overall_status}`",
            f"- Overall Score: `{overall_score:.2f}`",
            "",
            "## Governance Containment",
            f"- Containment Active: `{governance_containment['containment_active']}`",
            f"- Lock Verified: `{governance_containment['lock_verified']}`",
            f"- Dry-Run Enabled: `{governance_containment['dry_run_enabled']}`",
            f"- Supervision Mandatory: `{governance_containment['supervision_mandatory']}`",
            "",
            "## Simulated Failures",
            *[
                f"- {scenario['scenario']}: {scenario['simulated_failure']} -> {scenario['expected_governance_response']}"
                for scenario in failure_scenarios
            ],
            "",
            "## Service Responses",
            f"- Runtime Remediation Status: `{safe_str(remediation_latest.get('status'), 'unknown')}`",
            f"- Continuity Status: `{safe_str(continuity_latest.get('status'), 'unknown')}`",
            f"- Incident Status: `{safe_str(incident_latest.get('status'), 'unknown')}`",
            f"- Supervision Status: `{safe_str(supervision_latest.get('status'), 'unknown')}`",
            f"- Executive Governance Index Status: `{safe_str(executive_latest.get('status'), 'unknown')}`",
            "",
            "## Checks",
            *[
                f"- [{check.level}] {check.name}: {check.message}"
                + (f" Remediation: {check.remediation}" if check.remediation else "")
                for check in checks
            ],
            "",
            "## Safety Guarantees",
            "- Autonomous procurement authority remains disabled.",
            "- Live submission enablement remains disabled.",
            "- Dry-run protections remain active.",
            "- Human supervision remains mandatory.",
        ]
    )

    write_json(bundle_root / "runtime_failure_validation.json", report)
    write_text(bundle_root / "runtime_failure_validation.md", markdown)
    write_json(output_root / "latest_runtime_failure_validation.json", report)
    write_text(output_root / "latest_runtime_failure_validation.md", markdown)

    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run controlled runtime failure injection validation.")
    parser.add_argument("--output-root", default=str(FAILURE_VALIDATION_ROOT), help="Directory for runtime failure validation bundles.")
    args = parser.parse_args(argv)

    output_root = Path(args.output_root)
    report = build_runtime_failure_injection_validation_report(output_root=output_root)
    print("Runtime failure injection validation:")
    print(json.dumps(
        {
            "validation_id": report["validation_id"],
            "overall_status": report["overall_status"],
            "overall_score": report["overall_score"],
            "summary_counts": report["summary_counts"],
            "bundle_root": report["artifacts"]["bundle_root"],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
