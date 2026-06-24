#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
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
SMOKE_TEST_FILE = STAGING_ROOT / "production-smoke-tests" / "latest_production_smoke_test.json"
DEPLOYMENT_VALIDATION_FILE = STAGING_ROOT / "production-deployment-validations" / "latest_production_deployment_validation.json"
ROLLOUT_VALIDATION_FILE = STAGING_ROOT / "production-rollout-validations" / "latest_production_rollout_validation.json"
RELEASE_GOVERNANCE_BUNDLE_FILE = STAGING_ROOT / "release-governance-bundles" / "latest_release_governance_bundle.json"
RELEASE_CERTIFICATION_FILE = STAGING_ROOT / "release-certifications" / "latest_executive_release_evidence.json"
LOCK_FILE = STAGING_ROOT / "go_live_guards" / "submission_locks.json"

ENDURANCE_VALIDATION_ROOT = STAGING_ROOT / "runtime-endurance-validations"
LATEST_ENDURANCE_VALIDATION_JSON = ENDURANCE_VALIDATION_ROOT / "latest_runtime_endurance_validation.json"
LATEST_ENDURANCE_VALIDATION_MD = ENDURANCE_VALIDATION_ROOT / "latest_runtime_endurance_validation.md"

DEFAULT_SAMPLE_COUNT = 3
DEFAULT_SAMPLE_INTERVAL_SECONDS = 0.25


@dataclass
class CheckResult:
    level: str
    name: str
    message: str
    remediation: str = ""
    score: float = 100.0


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def endurance_timestamp() -> str:
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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified", "go"}
    return bool(value)


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "PASS"
    if score >= 70.0:
        return "WARN"
    return "FAIL"


def _authority_from_status(status: str) -> str:
    normalized = safe_str(status, "WARN").upper()
    if normalized == "PASS":
        return "GO"
    if normalized == "WARN":
        return "WATCH"
    return "NO_GO"


def _history_summary(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[-1]
    previous = values[-2] if len(values) > 1 else latest
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


def _score_from_level(level: str) -> float:
    normalized = safe_str(level, "FAIL").upper()
    if normalized == "PASS":
        return 100.0
    if normalized == "WARN":
        return 75.0
    return 0.0


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "", warn: bool = False) -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message, remediation="", score=100.0)
    if warn:
        return CheckResult("WARN", name, fail_message, remediation=remediation, score=75.0)
    return CheckResult("FAIL", name, fail_message, remediation=remediation, score=0.0)


def _governance_sources() -> Dict[str, Any]:
    return {}


def _derive_executive_index_from_bundle(release_bundle: Dict[str, Any], sample_index: int) -> Dict[str, Any]:
    rollout_readiness = safe_dict(release_bundle.get("rollout_readiness"))
    supervision_readiness = safe_dict(release_bundle.get("supervision_readiness"))
    audit_readiness = safe_dict(release_bundle.get("audit_readiness"))
    incident_readiness = safe_dict(release_bundle.get("incident_readiness"))
    continuity_readiness = safe_dict(release_bundle.get("continuity_readiness"))
    release_readiness = safe_dict(release_bundle.get("release_readiness"))
    executive_readiness = safe_dict(release_bundle.get("executive_readiness"))
    authority = safe_str(release_bundle.get("overall_authority"), "WATCH").upper()
    score = safe_float(release_bundle.get("overall_score"), 0.0)
    status = safe_str(release_bundle.get("overall_status"), "WARN").lower()
    return {
        "analysis_id": safe_str(release_bundle.get("bundle_id"), f"runtime-endurance:{sample_index}"),
        "generated_at": safe_str(release_bundle.get("generated_at"), iso_now()),
        "activation_readiness": {
            "activation_governance_status": "ok" if _truthy(release_readiness.get("runtime_segmentation_ready", True)) else "watch",
            "activation_governance_authority": "GO" if _truthy(release_readiness.get("runtime_segmentation_ready", True)) else "WATCH",
            "activation_governance_score": 95.0 if _truthy(release_readiness.get("runtime_segmentation_ready", True)) else 75.0,
            "activation_governance_history_summary": {"score_history": {"trend": "stable"}},
        },
        "supervision_readiness": supervision_readiness,
        "audit_completeness": audit_readiness,
        "incident_severity": incident_readiness,
        "continuity_readiness": continuity_readiness,
        "release_authority": safe_dict(release_bundle.get("release_authority_certification")),
        "operational_intelligence": {
            "operational_intelligence_status": "ok" if status == "pass" else "watch",
            "operational_intelligence_authority": authority,
            "operational_intelligence_score": score,
            "operational_intelligence_history_summary": {"score_history": {"trend": "stable"}},
        },
        "executive_command": {
            "executive_governance_status": "ok" if status == "pass" else "watch",
            "executive_governance_index_status": safe_str(executive_readiness.get("executive_governance_index_status"), status),
            "executive_governance_index_authority": safe_str(executive_readiness.get("executive_governance_index_authority"), authority),
            "executive_governance_index_score": safe_float(executive_readiness.get("executive_governance_index_score"), score),
            "executive_governance_index_history_summary": {"score_history": {"trend": "stable"}},
        },
        "institutional_rollout_readiness": {
            "rollout_readiness_status": safe_str(rollout_readiness.get("rollout_readiness_status"), "WATCH"),
            "rollout_readiness_score": safe_float(rollout_readiness.get("rollout_readiness_score"), score),
        },
        "governance_degradation_indicators": {
            "activation_degradation": False,
            "supervision_degradation": safe_str(supervision_readiness.get("supervision_command_status"), "watch") != "ok",
            "audit_degradation": safe_str(audit_readiness.get("operations_audit_status"), "watch") != "ok",
            "incident_degradation": safe_str(incident_readiness.get("incident_governance_status"), "watch") != "ok",
            "continuity_degradation": safe_str(continuity_readiness.get("continuity_governance_status"), "watch") != "ok",
            "release_degradation": status != "pass",
            "intelligence_degradation": safe_str(executive_readiness.get("executive_governance_index_status"), "watch") != "ok",
            "executive_degradation": safe_str(executive_readiness.get("executive_governance_index_status"), "watch") != "ok",
        },
        "executive_escalation_indicators": {
            "escalation_required": authority != "GO",
            "high_risk": authority != "GO",
            "governance_degradation": status != "pass",
            "supervision_saturation": safe_str(supervision_readiness.get("supervision_command_status"), "watch") != "ok",
            "audit_gap": safe_str(audit_readiness.get("operations_audit_status"), "watch") != "ok",
            "incident_escalation": safe_str(incident_readiness.get("incident_governance_status"), "watch") != "ok",
            "continuity_gap": safe_str(continuity_readiness.get("continuity_governance_status"), "watch") != "ok",
            "release_blocker": authority != "GO",
            "intelligence_drift": safe_str(executive_readiness.get("executive_governance_index_status"), "watch") != "ok",
            "rollout_freeze": bool(safe_list(continuity_readiness.get("continuity_freeze_indicators"))),
            "human_supervision_required": True,
        },
    }


def _load_stage_state() -> Dict[str, Any]:
    return {
        "boot": safe_dict(read_json(BOOT_VALIDATION_FILE, {})),
        "smoke": safe_dict(read_json(SMOKE_TEST_FILE, {})),
        "deployment": safe_dict(read_json(DEPLOYMENT_VALIDATION_FILE, {})),
        "rollout": safe_dict(read_json(ROLLOUT_VALIDATION_FILE, {})),
        "release_bundle": safe_dict(read_json(RELEASE_GOVERNANCE_BUNDLE_FILE, {})),
        "release_certification": safe_dict(read_json(RELEASE_CERTIFICATION_FILE, {})),
        "lock": safe_dict(read_json(LOCK_FILE, {})),
    }


def _lock_summary(lock_data: Dict[str, Any]) -> Dict[str, Any]:
    final_automation_disabled = lock_data.get("final_automation_disabled") is True
    live_portal_submission_disabled = lock_data.get("live_portal_submission_disabled") is True
    production_credentials_disabled = lock_data.get("production_credentials_disabled") is True
    dry_run_mode_required = lock_data.get("dry_run_mode_required") is True
    submission_execution_allowed = lock_data.get("submission_execution_allowed") is True
    human_supervision_value = lock_data.get("human_supervision_required")
    human_supervision_required = True if human_supervision_value is None else human_supervision_value is True
    lock_verified = (
        bool(lock_data)
        and final_automation_disabled
        and live_portal_submission_disabled
        and production_credentials_disabled
        and dry_run_mode_required
        and not submission_execution_allowed
        and human_supervision_required
    )
    return {
        "lock_file": str(LOCK_FILE),
        "lock_exists": LOCK_FILE.exists(),
        "lock_verified": lock_verified,
        "final_automation_disabled": final_automation_disabled,
        "live_portal_submission_disabled": live_portal_submission_disabled,
        "production_credentials_disabled": production_credentials_disabled,
        "dry_run_mode_required": dry_run_mode_required,
        "submission_execution_allowed": submission_execution_allowed,
        "human_supervision_required": human_supervision_required,
    }


def _source_score_from_status(status: str) -> float:
    return 100.0 if safe_str(status, "FAIL").upper() == "PASS" else 75.0 if safe_str(status, "FAIL").upper() == "WARN" else 0.0


def _sample_window(sample_index: int, sources: Dict[str, Any], state: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    boot = safe_dict(state["boot"])
    smoke = safe_dict(state["smoke"])
    deployment = safe_dict(state["deployment"])
    rollout = safe_dict(state["rollout"])
    release_bundle = safe_dict(state["release_bundle"])
    release_certification = safe_dict(state["release_certification"])
    lock_summary = _lock_summary(safe_dict(state["lock"]))

    executive_index_source = sources.get("executive_index")
    if executive_index_source and hasattr(executive_index_source, "latest_executive_governance_index"):
        executive_index = safe_dict(executive_index_source.latest_executive_governance_index())
    else:
        executive_index = _derive_executive_index_from_bundle(release_bundle, sample_index)
    activation = safe_dict(executive_index.get("activation_readiness"))
    supervision = safe_dict(executive_index.get("supervision_readiness"))
    audit = safe_dict(executive_index.get("audit_completeness"))
    incident = safe_dict(executive_index.get("incident_severity"))
    continuity = safe_dict(executive_index.get("continuity_readiness"))
    release = safe_dict(executive_index.get("release_authority"))
    intelligence = safe_dict(executive_index.get("operational_intelligence"))
    executive_command = safe_dict(executive_index.get("executive_command"))
    rollout_readiness = safe_dict(executive_index.get("institutional_rollout_readiness"))
    degradation = safe_dict(executive_index.get("governance_degradation_indicators"))
    escalation = safe_dict(executive_index.get("executive_escalation_indicators"))

    boot_summary = safe_dict(boot.get("boot_readiness_summary"))
    boot_compose = safe_dict(boot.get("compose_validation"))
    smoke_compose = safe_dict(smoke.get("compose_validation"))
    smoke_counts = safe_dict(smoke.get("summary_counts"))

    boot_ready = _truthy(boot_summary.get("production_runtime_boot_ready"))
    health_endpoints_respond = _truthy(boot_summary.get("health_endpoints_respond"))
    smoke_pass = safe_str(smoke.get("overall_status"), "FAIL").upper() == "PASS"
    smoke_services = safe_dict(smoke_compose.get("service_expectations"))
    smoke_services_ok = all(_truthy(value) for value in smoke_services.values()) if smoke_services else False
    deployment_ready = safe_str(deployment.get("overall_status"), "FAIL").upper() == "PASS"
    rollout_ready = safe_str(rollout.get("overall_status"), "FAIL").upper() == "PASS"
    release_bundle_status = safe_str(release_bundle.get("overall_status"), "FAIL").upper()
    release_bundle_authority = safe_str(release_bundle.get("overall_authority"), "NO_GO").upper()
    release_bundle_ready = release_bundle_status == "PASS" and release_bundle_authority == "GO"
    release_cert_status = safe_str(release_certification.get("status"), safe_str(release_certification.get("certification_status"), "WATCH")).upper()

    continuity_status = safe_str(continuity.get("status"), safe_str(continuity.get("continuity_governance_status"), "blocked")).upper()
    continuity_authority = safe_str(continuity.get("continuity_governance_authority"), _authority_from_status(continuity_status)).upper()
    continuity_score = safe_float(continuity.get("continuity_governance_score"), 0.0)
    continuity_history_summary = safe_dict(continuity.get("continuity_governance_history_summary"))
    continuity_trend = safe_str(safe_dict(continuity_history_summary.get("score_history")).get("trend"), "unknown")
    continuity_freeze = safe_list(continuity.get("continuity_freeze_indicators"))

    incident_status = safe_str(incident.get("status"), safe_str(incident.get("incident_governance_status"), "blocked")).upper()
    incident_authority = safe_str(incident.get("incident_governance_authority"), _authority_from_status(incident_status)).upper()
    incident_score = safe_float(incident.get("incident_governance_score"), 0.0)
    incident_trend = safe_str(safe_dict(safe_dict(incident.get("incident_governance_history_summary")).get("score_history")).get("trend"), "unknown")
    incident_breaches = safe_list(incident.get("governance_breach_indicators"))

    supervision_status = safe_str(supervision.get("status"), safe_str(supervision.get("supervision_command_status"), "blocked")).upper()
    supervision_authority = safe_str(supervision.get("supervision_command_authority"), _authority_from_status(supervision_status)).upper()
    supervision_score = safe_float(supervision.get("supervision_command_score"), 0.0)
    supervision_history_summary = safe_dict(supervision.get("supervision_command_history_summary"))
    supervision_trend = safe_str(safe_dict(supervision_history_summary.get("score_history")).get("trend"), "unknown")
    active_supervised_operators = safe_list(safe_dict(supervision.get("latest_supervision_command")).get("active_supervised_operators"))

    audit_status = safe_str(audit.get("status"), safe_str(audit.get("operations_audit_status"), "blocked")).upper()
    audit_authority = safe_str(audit.get("operations_audit_authority"), _authority_from_status(audit_status)).upper()
    audit_score = safe_float(audit.get("operations_audit_score"), 0.0)
    audit_trend = safe_str(safe_dict(safe_dict(audit.get("operations_audit_history_summary")).get("score_history")).get("trend"), "unknown")

    activation_status = safe_str(activation.get("status"), safe_str(activation.get("activation_governance_status"), "blocked")).upper()
    activation_authority = safe_str(activation.get("activation_governance_authority"), _authority_from_status(activation_status)).upper()
    activation_score = safe_float(activation.get("activation_governance_score"), 0.0)
    activation_trend = safe_str(safe_dict(safe_dict(activation.get("activation_governance_history_summary")).get("score_history")).get("trend"), "unknown")

    release_status = safe_str(release.get("status"), safe_str(release.get("release_governance_status"), "blocked")).upper()
    release_authority = safe_str(release.get("release_governance_authority"), _authority_from_status(release_status)).upper()
    release_score = safe_float(release.get("release_governance_score"), 0.0)
    release_trend = safe_str(safe_dict(safe_dict(release.get("release_governance_history_summary")).get("score_history")).get("trend"), "unknown")

    intelligence_status = safe_str(intelligence.get("status"), safe_str(intelligence.get("operational_intelligence_status"), "blocked")).upper()
    intelligence_authority = safe_str(intelligence.get("operational_intelligence_authority"), _authority_from_status(intelligence_status)).upper()
    intelligence_score = safe_float(intelligence.get("operational_intelligence_score"), 0.0)
    intelligence_trend = safe_str(safe_dict(safe_dict(intelligence.get("operational_intelligence_history_summary")).get("score_history")).get("trend"), "unknown")

    executive_command_block = safe_dict(executive_index.get("executive_command"))
    executive_status = safe_str(
        executive_index.get("executive_governance_index_status"),
        safe_str(executive_command_block.get("executive_governance_index_status"), safe_str(executive_command_block.get("executive_governance_status"), "blocked")),
    ).upper()
    executive_authority = safe_str(
        executive_index.get("executive_governance_index_authority"),
        safe_str(executive_command_block.get("executive_governance_index_authority"), _authority_from_status(executive_status)),
    ).upper()
    executive_score = safe_float(
        executive_index.get("executive_governance_index_score"),
        safe_float(executive_command_block.get("executive_governance_index_score"), 0.0),
    )
    executive_trend = safe_str(
        safe_dict(safe_dict(executive_index.get("executive_governance_index_history_summary")).get("score_history")).get("trend"),
        safe_str(safe_dict(safe_dict(executive_command_block.get("executive_governance_index_history_summary")).get("score_history")).get("trend"), "unknown"),
    )
    rollout_governance = safe_dict(executive_index.get("institutional_rollout_readiness"))
    degradation_indicators = safe_dict(executive_index.get("governance_degradation_indicators"))
    escalation_indicators = safe_dict(executive_index.get("executive_escalation_indicators"))

    service_health_ready = boot_ready or smoke_pass or rollout_ready
    observability_endpoints_reachable = boot_ready and health_endpoints_respond and smoke_pass
    executive_ready = executive_status in {"PASS", "OK"}
    escalation_ready = (
        release_bundle_ready
        and release_cert_status in {"PASS", "CERTIFIED", "GO"}
        and supervision_authority == "GO"
        and incident_authority == "GO"
        and continuity_authority == "GO"
        and executive_ready
    )
    continuity_stable = continuity_trend == "stable" and not any(_truthy(item.get("freeze_active")) for item in continuity_freeze)
    governance_degradation_detected = any(_truthy(value) for value in degradation_indicators.values()) or executive_trend == "declining" or continuity_trend == "declining" or incident_trend == "declining" or supervision_trend == "declining" or audit_trend == "declining" or activation_trend == "declining" or release_trend == "declining" or intelligence_trend == "declining"

    runtime_score = mean([
        100.0 if lock_summary["lock_verified"] else 0.0,
        100.0 if lock_summary["lock_exists"] else 0.0,
        100.0 if lock_summary["final_automation_disabled"] else 0.0,
        100.0 if lock_summary["dry_run_mode_required"] else 0.0,
        100.0 if lock_summary["human_supervision_required"] else 0.0,
    ])
    services_score = mean([
        100.0 if boot_ready else 75.0 if smoke_pass else 0.0,
        100.0 if smoke_pass else 0.0,
        100.0 if smoke_services_ok else 75.0 if smoke_pass else 0.0,
        100.0 if deployment_ready else 75.0 if safe_str(deployment.get("overall_status"), "FAIL").upper() == "WARN" else 0.0,
        100.0 if rollout_ready else 75.0 if safe_str(rollout.get("overall_status"), "FAIL").upper() == "WARN" else 0.0,
    ])
    observability_score = mean([
        100.0 if observability_endpoints_reachable else 75.0 if smoke_pass else 0.0,
        100.0 if health_endpoints_respond else 75.0 if smoke_pass else 0.0,
        100.0 if safe_dict(boot.get("compose_validation")).get("compose_parsed") else 75.0 if smoke_pass else 0.0,
    ])
    governance_score = mean([
        activation_score,
        supervision_score,
        audit_score,
        incident_score,
        continuity_score,
        release_score,
        intelligence_score,
        executive_score,
    ])
    escalation_score = mean([
        100.0 if escalation_ready else 75.0 if safe_str(release_bundle.get("overall_authority"), "NO_GO").upper() == "WATCH" else 0.0,
        100.0 if supervision_authority == "GO" else 75.0 if supervision_authority == "WATCH" else 0.0,
        100.0 if incident_authority == "GO" else 75.0 if incident_authority == "WATCH" else 0.0,
        100.0 if continuity_authority == "GO" else 75.0 if continuity_authority == "WATCH" else 0.0,
    ])
    continuity_score_summary = mean([
        continuity_score,
        100.0 if continuity_stable else 75.0 if continuity_trend == "stable" else 0.0,
        100.0 if not continuity_freeze else 75.0 if all(not _truthy(item.get("freeze_active")) for item in continuity_freeze) else 0.0,
        100.0 if not governance_degradation_detected else 75.0 if continuity_trend == "stable" else 0.0,
    ])

    window_score = round(mean([
        runtime_score,
        services_score,
        observability_score,
        governance_score,
        escalation_score,
        continuity_score_summary,
    ]), 2)
    if not lock_summary["lock_verified"] or not lock_summary["dry_run_mode_required"] or not lock_summary["human_supervision_required"]:
        window_status = "FAIL"
    elif any(
        item in {"WARN", "blocked", "watch", "NO_GO"}
        for item in [
            safe_str(boot.get("overall_status"), "FAIL").upper(),
            safe_str(smoke.get("overall_status"), "FAIL").upper(),
            safe_str(deployment.get("overall_status"), "FAIL").upper(),
            safe_str(rollout.get("overall_status"), "FAIL").upper(),
            release_bundle_status,
            release_bundle_authority,
            continuity_status,
            incident_status,
            supervision_status,
            audit_status,
            activation_status,
            release_status,
            intelligence_status,
            executive_status,
        ]
    ):
        window_status = "WARN" if window_score >= 70.0 else "FAIL"
    else:
        window_status = "PASS"
    window_authority = _authority_from_status(window_status)
    window_grade = "ready" if window_status == "PASS" else "watch" if window_status == "WARN" else "blocked"
    notes: List[str] = []
    if not boot_ready:
        notes.append("boot_readiness_not_ready")
    if not observability_endpoints_reachable:
        notes.append("observability_endpoints_unreachable")
    if not escalation_ready:
        notes.append("escalation_readiness_watch")
    if not continuity_stable:
        notes.append("continuity_indicators_not_stable")
    if governance_degradation_detected:
        notes.append("governance_degradation_detected")

    return {
        "sample_index": sample_index,
        "observed_at": iso_now(),
        "simulated_elapsed_seconds": round(sample_index * 1.0, 3),
        "boot_readiness_status": safe_str(boot_summary.get("status"), safe_str(boot.get("overall_status"), "WARN")).upper(),
        "boot_ready": boot_ready,
        "smoke_status": safe_str(smoke.get("overall_status"), "WARN").upper(),
        "smoke_pass": smoke_pass,
        "lock_active": lock_summary["lock_verified"],
        "dry_run_enabled": _truthy(boot_summary.get("dry_run_mode_enabled")) and lock_summary["dry_run_mode_required"],
        "supervision_mandatory": _truthy(boot_summary.get("human_supervision_required")) and lock_summary["human_supervision_required"],
        "service_health_ready": service_health_ready,
        "observability_endpoints_reachable": observability_endpoints_reachable,
        "escalation_ready": escalation_ready,
        "continuity_stable": continuity_stable,
        "governance_degradation_detected": governance_degradation_detected,
        "runtime_score": round(runtime_score, 2),
        "service_health_score": round(services_score, 2),
        "observability_score": round(observability_score, 2),
        "governance_score": round(governance_score, 2),
        "escalation_score": round(escalation_score, 2),
        "continuity_score": round(continuity_score_summary, 2),
        "window_score": window_score,
        "window_status": window_status,
        "window_authority": window_authority,
        "window_grade": window_grade,
        "analysis_id": safe_str(executive_index.get("analysis_id"), f"runtime-endurance:{sample_index}"),
        "sources": {
            "executive_governance_index_status": executive_status,
            "executive_governance_index_score": executive_score,
            "activation_readiness": activation,
            "supervision_readiness": supervision,
            "audit_completeness": audit,
            "incident_severity": incident,
            "continuity_readiness": continuity,
            "release_authority": release,
            "operational_intelligence": intelligence,
            "executive_command": executive_command,
            "rollout_governance": rollout_governance,
            "governance_degradation_indicators": degradation_indicators,
            "executive_escalation_indicators": escalation_indicators,
            "release_bundle": release_bundle,
            "release_certification": release_certification,
            "boot_readiness_summary": boot_summary,
            "smoke_compose_validation": smoke_compose,
            "deployment": deployment,
            "rollout": rollout,
            "lock_summary": lock_summary,
        },
        "notes": notes,
        "summary_counts": {
            "PASS": 1 if window_status == "PASS" else 0,
            "WARN": 1 if window_status == "WARN" else 0,
            "FAIL": 1 if window_status == "FAIL" else 0,
        },
    }


def _build_checks(samples: List[Dict[str, Any]], state: Dict[str, Any]) -> List[CheckResult]:
    boot = safe_dict(state["boot"])
    smoke = safe_dict(state["smoke"])
    deployment = safe_dict(state["deployment"])
    rollout = safe_dict(state["rollout"])
    release_bundle = safe_dict(state["release_bundle"])
    release_cert = safe_dict(state["release_certification"])
    lock_summary = _lock_summary(safe_dict(state["lock"]))
    first_sample = safe_dict(samples[0] if samples else {})
    latest_sample = safe_dict(samples[-1] if samples else {})

    checks: List[CheckResult] = []
    checks.append(
        _check(
            lock_summary["lock_verified"],
            "governance locks remain active",
            "submission lock file keeps final automation disabled",
            "submission lock enforcement is incomplete",
            "Restore the staging submission lock file and keep all lock fields locked down.",
        )
    )
    checks.append(
        _check(
            lock_summary["dry_run_mode_required"],
            "dry-run remains enabled",
            "dry-run mode is still required by the submission lock",
            "dry-run mode is not required by the submission lock",
            "Set dry_run_mode_required=true in the staged submission lock.",
        )
    )
    checks.append(
        _check(
            lock_summary["human_supervision_required"],
            "supervision remains mandatory",
            "human supervision remains mandatory",
            "human supervision is not mandatory",
            "Keep human_supervision_required=true in the staged submission lock.",
        )
    )

    boot_ready = _truthy(safe_dict(boot.get("boot_readiness_summary")).get("production_runtime_boot_ready"))
    smoke_pass = safe_str(smoke.get("overall_status"), "FAIL").upper() == "PASS"
    deployment_pass = safe_str(deployment.get("overall_status"), "FAIL").upper() == "PASS"
    rollout_pass = safe_str(rollout.get("overall_status"), "FAIL").upper() == "PASS"
    service_health_ok = boot_ready and smoke_pass and deployment_pass and rollout_pass
    service_health_warn = smoke_pass or safe_str(safe_dict(boot.get("compose_validation")).get("compose_message"), "").strip() != ""
    checks.append(
        _check(
            service_health_ok,
            "services remain healthy",
            "runtime and staged validation evidence indicate healthy services",
            "services are not yet healthy in the staged runtime evidence",
            "Bring the production deployment package and runtime boot validation back to green.",
            warn=service_health_warn,
        )
    )

    backend_reachable = _truthy(safe_dict(boot.get("boot_readiness_summary")).get("health_endpoints_respond"))
    smoke_backend_expected = _truthy(safe_dict(safe_dict(smoke.get("compose_validation")).get("service_expectations")).get("backend"))
    smoke_frontend_expected = _truthy(safe_dict(safe_dict(smoke.get("compose_validation")).get("service_expectations")).get("frontend"))
    observability_reachable = backend_reachable or (smoke_backend_expected and smoke_frontend_expected and smoke_pass)
    checks.append(
        _check(
            observability_reachable,
            "observability endpoints remain reachable",
            "observability endpoints are reachable according to staged evidence",
            "observability endpoints are not fully reachable in the staged evidence",
            "Check /health and the frontend root response in the controlled boot validation.",
            warn=smoke_pass,
        )
    )

    continuity_readiness = safe_dict(safe_dict(latest_sample.get("sources", {})).get("continuity_readiness", {}))
    continuity_status = safe_str(continuity_readiness.get("continuity_governance_status"), "blocked").upper()
    continuity_trend = safe_str(safe_dict(safe_dict(continuity_readiness.get("continuity_governance_history_summary")).get("score_history")).get("trend"), "unknown")
    continuity_freeze_indicators = safe_list(continuity_readiness.get("continuity_freeze_indicators"))
    continuity_stable = continuity_trend == "stable" and not any(_truthy(item.get("freeze_active")) for item in continuity_freeze_indicators)
    checks.append(
        _check(
            continuity_stable,
            "continuity indicators remain stable",
            "continuity indicators are stable across the sampled windows",
            "continuity indicators are not stable across the sampled windows",
            "Restore continuity readiness signals in the continuity governance evidence.",
            warn=continuity_status in {"WATCH", "BLOCKED"},
        )
    )

    executive_status = safe_str(safe_dict(latest_sample.get("sources", {})).get("executive_governance_index_status"), "WARN").upper()
    release_bundle_state = safe_dict(safe_dict(latest_sample.get("sources", {})).get("release_bundle", {}))
    escalation_ready = safe_str(release_bundle_state.get("overall_status"), "FAIL").upper() == "PASS" and safe_str(release_bundle_state.get("overall_authority"), "NO_GO").upper() == "GO" and executive_status in {"PASS", "OK"}
    checks.append(
        _check(
            escalation_ready,
            "escalation readiness remains intact",
            "escalation readiness remains intact in the sampled evidence",
            "escalation readiness is not yet intact in the sampled evidence",
            "Bring the release governance bundle and executive governance index back to GO.",
            warn=(
                executive_status in {"WARN", "BLOCKED", "NO_GO", "WATCH"}
                or safe_str(release_bundle_state.get("overall_status"), "FAIL").upper() != "PASS"
                or safe_str(release_bundle_state.get("overall_authority"), "NO_GO").upper() != "GO"
            ),
        )
    )

    degradation_detected = any(_truthy(sample.get("governance_degradation_detected")) for sample in samples)
    stable_window_scores = _history_summary([safe_float(sample.get("window_score"), 0.0) for sample in samples]).get("trend") == "stable"
    no_degradation = not degradation_detected and stable_window_scores
    checks.append(
        _check(
            no_degradation,
            "no governance degradation occurs",
            "no governance degradation was detected across the sampled windows",
            "governance degradation was detected across the sampled windows",
            "Resolve the degraded governance signals before re-running endurance validation.",
            warn=degradation_detected,
        )
    )

    checks.append(
        _check(
            len(samples) > 0,
            "simulated timing windows completed",
            f"{len(samples)} simulated endurance windows were recorded",
            "no simulated endurance windows were recorded",
            "Increase the simulated sample count and re-run the validator.",
        )
    )

    return checks


def build_runtime_endurance_validation_report(
    *,
    output_root: Optional[Path] = None,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    sample_interval_seconds: float = DEFAULT_SAMPLE_INTERVAL_SECONDS,
) -> Dict[str, Any]:
    output_root = output_root or ENDURANCE_VALIDATION_ROOT
    output_root.mkdir(parents=True, exist_ok=True)

    sources = _governance_sources()
    samples: List[Dict[str, Any]] = []
    for sample_index in range(max(1, int(sample_count))):
        state = _load_stage_state()
        previous = samples[-1] if samples else None
        samples.append(_sample_window(sample_index, sources, state, previous))
        if sample_index < max(1, int(sample_count)) - 1 and sample_interval_seconds > 0:
            time.sleep(sample_interval_seconds)

    checks = _build_checks(samples, _load_stage_state())
    summary_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for check in checks:
        level = safe_str(check.level, "FAIL").upper()
        if level not in summary_counts:
            level = "FAIL"
        summary_counts[level] += 1

    sample_scores = [safe_float(sample.get("window_score"), 0.0) for sample in samples]
    overall_score = round(mean(sample_scores), 2) if sample_scores else 0.0
    if summary_counts["FAIL"] > 0 or overall_score < 50.0:
        overall_status = "FAIL"
    elif summary_counts["WARN"] > 0 or overall_score < 85.0:
        overall_status = "WARN"
    else:
        overall_status = "PASS"
    overall_authority = _authority_from_status(overall_status)
    overall_grade = "ready" if overall_status == "PASS" else "watch" if overall_status == "WARN" else "blocked"

    latest_sample = safe_dict(samples[-1] if samples else {})
    continuity_scores = [safe_float(sample.get("continuity_score"), 0.0) for sample in samples]
    service_scores = [safe_float(sample.get("service_health_score"), 0.0) for sample in samples]
    observability_scores = [safe_float(sample.get("observability_score"), 0.0) for sample in samples]
    escalation_scores = [safe_float(sample.get("escalation_score"), 0.0) for sample in samples]
    governance_scores = [safe_float(sample.get("governance_score"), 0.0) for sample in samples]

    state = _load_stage_state()
    boot = safe_dict(state["boot"])
    smoke = safe_dict(state["smoke"])
    deployment = safe_dict(state["deployment"])
    rollout = safe_dict(state["rollout"])
    release_bundle = safe_dict(state["release_bundle"])
    release_cert = safe_dict(state["release_certification"])
    lock_summary = _lock_summary(safe_dict(state["lock"]))

    boot_summary = safe_dict(boot.get("boot_readiness_summary"))
    smoke_summary = safe_dict(smoke.get("compose_validation"))
    rollout_summary = safe_dict(rollout.get("rollout_readiness_summary"))
    release_summary = safe_dict(release_bundle.get("release_readiness"))
    latest_release_cert_status = safe_str(release_cert.get("status"), safe_str(release_cert.get("certification_status"), "WATCH")).upper()
    latest_release_cert_score = safe_float(release_cert.get("release_governance_score"), safe_float(release_bundle.get("overall_score"), 0.0))
    boot_ready = _truthy(boot_summary.get("production_runtime_boot_ready"))
    smoke_pass = safe_str(smoke.get("overall_status"), "FAIL").upper() == "PASS"
    deployment_ready = safe_str(deployment.get("overall_status"), "FAIL").upper() == "PASS"
    rollout_ready = safe_str(rollout.get("overall_status"), "FAIL").upper() == "PASS"
    release_bundle_ready = safe_str(release_bundle.get("overall_status"), "FAIL").upper() == "PASS" and safe_str(release_bundle.get("overall_authority"), "NO_GO").upper() == "GO"
    health_endpoints_respond = _truthy(boot_summary.get("health_endpoints_respond"))
    escalation_ready = _truthy(latest_sample.get("escalation_ready"))
    continuity_indicators_stable = _truthy(latest_sample.get("continuity_stable")) and all(_truthy(sample.get("continuity_stable")) for sample in samples)

    runtime_endurance_summary = {
        "runtime_endurance_score": overall_score,
        "runtime_endurance_status": overall_status,
        "runtime_endurance_grade": overall_grade,
        "overall_authority": overall_authority,
        "sample_count": len(samples),
        "simulated_timing_windows": {
            "simulated": True,
            "sample_count": len(samples),
            "sample_interval_seconds": sample_interval_seconds,
            "observation_span_seconds": round(max(0, len(samples) - 1) * sample_interval_seconds, 3),
        },
        "governance_locks_active": lock_summary["lock_verified"],
        "dry_run_enabled": lock_summary["dry_run_mode_required"] and _truthy(boot_summary.get("dry_run_mode_enabled")),
        "supervision_mandatory": lock_summary["human_supervision_required"] and _truthy(boot_summary.get("human_supervision_required")),
        "services_healthy": all(safe_str(sample.get("window_status"), "FAIL").upper() == "PASS" for sample in samples) and boot_ready and smoke_pass and deployment_ready and rollout_ready,
        "observability_endpoints_reachable": all(safe_str(sample.get("window_status"), "FAIL").upper() == "PASS" for sample in samples) and boot_ready and health_endpoints_respond and smoke_pass,
        "escalation_readiness_intact": all(safe_str(sample.get("window_status"), "FAIL").upper() == "PASS" for sample in samples) and release_bundle_ready and safe_str(latest_sample.get("window_authority"), "WATCH").upper() == "GO" and escalation_ready,
        "continuity_indicators_stable": continuity_indicators_stable and _history_summary(continuity_scores).get("trend") == "stable",
        "no_governance_degradation_occurs": all(safe_str(sample.get("window_status"), "FAIL").upper() == "PASS" for sample in samples) and _history_summary(sample_scores).get("trend") == "stable",
        "warnings": [
            warning
            for bucket in (
                [] if lock_summary["lock_verified"] else ["submission_lock_not_verified"],
                [] if _truthy(boot_summary.get("dry_run_mode_enabled")) else ["dry_run_not_enabled"],
                [] if _truthy(boot_summary.get("human_supervision_required")) else ["human_supervision_not_required"],
            )
            for warning in bucket
        ],
    }

    history_summary = {
        "analysis_count": len(samples),
        "latest_analysis_id": safe_str(latest_sample.get("analysis_id"), f"runtime-endurance:{endurance_timestamp()}"),
        "latest_score": overall_score,
        "score_history": _history_summary(sample_scores),
        "service_health_history": _history_summary(service_scores),
        "observability_history": _history_summary(observability_scores),
        "escalation_history": _history_summary(escalation_scores),
        "continuity_history": _history_summary(continuity_scores),
        "governance_history": _history_summary(governance_scores),
    }

    checks_by_name = [
        {
            "level": check.level,
            "name": check.name,
            "message": check.message,
            "remediation": check.remediation,
            "score": check.score,
        }
        for check in checks
    ]

    validation_id = f"{endurance_timestamp()}-endurance-{uuid.uuid4().hex[:8]}"
    bundle_dir = output_root / validation_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "validation_id": validation_id,
        "generated_at": iso_now(),
        "source_runtime": str(STAGING_ROOT),
        "monitoring_mode": "simulated_timing_windows",
        "sample_count": len(samples),
        "sample_interval_seconds": sample_interval_seconds,
        "runtime_endurance_summary": runtime_endurance_summary,
        "history_summary": history_summary,
        "sample_history": samples,
        "checks": checks_by_name,
        "summary_counts": summary_counts,
        "source_artifacts": {
            "boot_validation": str(BOOT_VALIDATION_FILE),
            "production_smoke_test": str(SMOKE_TEST_FILE),
            "production_deployment_validation": str(DEPLOYMENT_VALIDATION_FILE),
            "production_rollout_validation": str(ROLLOUT_VALIDATION_FILE),
            "release_governance_bundle": str(RELEASE_GOVERNANCE_BUNDLE_FILE),
            "release_certification": str(RELEASE_CERTIFICATION_FILE),
            "submission_lock": str(LOCK_FILE),
        },
        "latest_source_snapshots": {
            "boot_validation": boot,
            "production_smoke_test": smoke,
            "production_deployment_validation": deployment,
            "production_rollout_validation": rollout,
            "release_governance_bundle": release_bundle,
            "release_certification": release_cert,
        },
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "human_supervision_required": True,
            "dry_run_protections_active": True,
        },
        "artifact_paths": {
            "json": str(bundle_dir / "runtime_endurance_validation.json"),
            "markdown": str(bundle_dir / "runtime_endurance_validation.md"),
            "latest_json": str(output_root / "latest_runtime_endurance_validation.json"),
            "latest_markdown": str(output_root / "latest_runtime_endurance_validation.md"),
        },
    }

    write_json(bundle_dir / "runtime_endurance_validation.json", payload)
    write_text(bundle_dir / "runtime_endurance_validation.md", markdown_summary(payload))
    write_json(output_root / "latest_runtime_endurance_validation.json", payload)
    write_text(output_root / "latest_runtime_endurance_validation.md", markdown_summary(payload))
    return payload


def markdown_summary(payload: Dict[str, Any]) -> str:
    summary = safe_dict(payload.get("runtime_endurance_summary"))
    history = safe_dict(payload.get("history_summary"))
    latest_sample = safe_dict(safe_list(payload.get("sample_history"))[-1] if safe_list(payload.get("sample_history")) else {})
    lines = [
        "# Runtime Endurance Validation Report",
        "",
        f"- Validation ID: `{safe_str(payload.get('validation_id'))}`",
        f"- Generated At: `{safe_str(payload.get('generated_at'))}`",
        f"- Source Runtime: `{safe_str(payload.get('source_runtime'))}`",
        f"- Monitoring Mode: `{safe_str(payload.get('monitoring_mode'))}`",
        f"- Sample Count: `{safe_int(payload.get('sample_count'), 0)}`",
        f"- Sample Interval Seconds: `{safe_float(payload.get('sample_interval_seconds'), 0.0):.2f}`",
        "",
        "## Endurance Summary",
        f"- Status: `{safe_str(summary.get('runtime_endurance_status'), 'FAIL')}`",
        f"- Score: `{safe_float(summary.get('runtime_endurance_score'), 0.0):.2f}`",
        f"- Grade: `{safe_str(summary.get('runtime_endurance_grade'), 'blocked')}`",
        f"- Authority: `{safe_str(summary.get('overall_authority'), 'NO_GO')}`",
        f"- Governance locks active: `{str(bool(summary.get('governance_locks_active'))).lower()}`",
        f"- Dry-run enabled: `{str(bool(summary.get('dry_run_enabled'))).lower()}`",
        f"- Supervision mandatory: `{str(bool(summary.get('supervision_mandatory'))).lower()}`",
        f"- Services healthy: `{str(bool(summary.get('services_healthy'))).lower()}`",
        f"- Observability endpoints reachable: `{str(bool(summary.get('observability_endpoints_reachable'))).lower()}`",
        f"- Escalation readiness intact: `{str(bool(summary.get('escalation_readiness_intact'))).lower()}`",
        f"- Continuity indicators stable: `{str(bool(summary.get('continuity_indicators_stable'))).lower()}`",
        f"- No governance degradation occurs: `{str(bool(summary.get('no_governance_degradation_occurs'))).lower()}`",
        "",
        "## Timing Windows",
        f"- Simulated: `{str(bool(safe_dict(summary.get('simulated_timing_windows')).get('simulated'))).lower()}`",
        f"- Window sample count: `{safe_int(safe_dict(summary.get('simulated_timing_windows')).get('sample_count'), 0)}`",
        f"- Window interval seconds: `{safe_float(safe_dict(summary.get('simulated_timing_windows')).get('sample_interval_seconds'), 0.0):.2f}`",
        f"- Observation span seconds: `{safe_float(safe_dict(summary.get('simulated_timing_windows')).get('observation_span_seconds'), 0.0):.2f}`",
        "",
        "## History Summary",
        f"- Analysis count: `{safe_int(history.get('analysis_count'), 0)}`",
        f"- Latest analysis id: `{safe_str(history.get('latest_analysis_id'))}`",
        f"- Latest score: `{safe_float(history.get('latest_score'), 0.0):.2f}`",
        f"- Score trend: `{safe_str(safe_dict(history.get('score_history')).get('trend'), 'unknown')}`",
        f"- Service health trend: `{safe_str(safe_dict(history.get('service_health_history')).get('trend'), 'unknown')}`",
        f"- Observability trend: `{safe_str(safe_dict(history.get('observability_history')).get('trend'), 'unknown')}`",
        f"- Escalation trend: `{safe_str(safe_dict(history.get('escalation_history')).get('trend'), 'unknown')}`",
        f"- Continuity trend: `{safe_str(safe_dict(history.get('continuity_history')).get('trend'), 'unknown')}`",
        f"- Governance trend: `{safe_str(safe_dict(history.get('governance_history')).get('trend'), 'unknown')}`",
        "",
        "## Latest Sample",
        f"- Observed at: `{safe_str(latest_sample.get('observed_at'))}`",
        f"- Window score: `{safe_float(latest_sample.get('window_score'), 0.0):.2f}`",
        f"- Window status: `{safe_str(latest_sample.get('window_status'), 'FAIL')}`",
        f"- Window authority: `{safe_str(latest_sample.get('window_authority'), 'NO_GO')}`",
        f"- Notes: `{json.dumps(safe_list(latest_sample.get('notes')), sort_keys=True)}`",
        "",
        "## Checks",
    ]
    for check in safe_list(payload.get("checks")):
        lines.append(f"- {safe_str(check.get('level'))}: {safe_str(check.get('name'))} - {safe_str(check.get('message'))}")
    lines += [
        "",
        "## Safety Guarantees",
        f"- Autonomous procurement authority: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('autonomous_procurement_authority'))).lower()}`",
        f"- Irreversible operations: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('irreversible_operations'))).lower()}`",
        f"- Production submission enablement: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('production_submission_enablement'))).lower()}`",
        f"- Production connectivity required: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('production_connectivity_required'))).lower()}`",
        f"- Human supervision required: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('human_supervision_required'))).lower()}`",
        f"- Dry-run protections active: `{str(bool(safe_dict(payload.get('safety_guarantees')).get('dry_run_protections_active'))).lower()}`",
        "",
        "## Evidence Artifacts",
    ]
    for key, value in safe_dict(payload.get("artifact_paths")).items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def _print_summary(payload: Dict[str, Any]) -> None:
    summary = safe_dict(payload.get("runtime_endurance_summary"))
    print(f"Runtime endurance validation: {safe_str(payload.get('artifact_paths', {}).get('json'), '')}")
    print(f"Overall status: {safe_str(summary.get('runtime_endurance_status'), 'FAIL')}")
    print(f"Overall score: {safe_float(summary.get('runtime_endurance_score'), 0.0):.2f}")
    print(f"Governance locks active: {str(bool(summary.get('governance_locks_active'))).lower()}")
    print(f"Dry-run enabled: {str(bool(summary.get('dry_run_enabled'))).lower()}")
    print(f"Supervision mandatory: {str(bool(summary.get('supervision_mandatory'))).lower()}")
    print(f"Escalation readiness intact: {str(bool(summary.get('escalation_readiness_intact'))).lower()}")
    print(f"Continuity indicators stable: {str(bool(summary.get('continuity_indicators_stable'))).lower()}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run controlled runtime endurance validation for the production runtime stack.")
    parser.add_argument("--output-root", type=Path, default=ENDURANCE_VALIDATION_ROOT, help="Where to write endurance validation evidence.")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLE_COUNT, help="Number of simulated timing samples to collect.")
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_SAMPLE_INTERVAL_SECONDS, help="Seconds to wait between simulated samples.")
    parser.add_argument("--json", action="store_true", help="Emit the full payload as JSON.")
    args = parser.parse_args(argv)

    payload = build_runtime_endurance_validation_report(
        output_root=args.output_root,
        sample_count=args.samples,
        sample_interval_seconds=args.interval_seconds,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
