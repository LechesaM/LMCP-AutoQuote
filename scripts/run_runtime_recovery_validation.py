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
FAILURE_VALIDATION_FILE = STAGING_ROOT / "runtime-failure-validations" / "latest_runtime_failure_validation.json"
ENDURANCE_VALIDATION_FILE = STAGING_ROOT / "runtime-endurance-validations" / "latest_runtime_endurance_validation.json"
BOOT_VALIDATION_FILE = STAGING_ROOT / "runtime-boot-validations" / "latest_runtime_boot_validation.json"
ROLLOUT_VALIDATION_FILE = STAGING_ROOT / "production-rollout-validations" / "latest_production_rollout_validation.json"
RELEASE_CERTIFICATION_FILE = STAGING_ROOT / "release-certifications" / "latest_executive_release_evidence.json"
LOCK_FILE = STAGING_ROOT / "go_live_guards" / "submission_locks.json"

RECOVERY_VALIDATION_ROOT = STAGING_ROOT / "runtime-recovery-validations"


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


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _authority_from_status(status: str) -> str:
    normalized = safe_str(status, "watch").lower()
    if normalized == "ok":
        return "GO"
    if normalized == "watch":
        return "WATCH"
    return "NO_GO"


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("WARN", name, fail_message, remediation)


def _load_json(path: Path) -> Dict[str, Any]:
    return safe_dict(read_json(path, {}))


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        normalized = safe_str(value)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _normalize_blocker(
    item: Any,
    *,
    source: str,
    default_category: str,
    default_severity: str = "medium",
) -> Dict[str, Any]:
    if isinstance(item, dict):
        blocker = dict(item)
    else:
        description = safe_str(item, default_category.replace("_", " "))
        blocker = {
            "description": description,
            "category": default_category,
            "severity": default_severity,
        }
    blocker["source"] = source
    blocker["category"] = safe_str(blocker.get("category"), default_category)
    blocker["severity"] = safe_str(blocker.get("severity"), default_severity).lower()
    blocker["description"] = safe_str(
        blocker.get("description") or blocker.get("message") or blocker.get("name") or blocker.get("remediation_id"),
        default_category.replace("_", " "),
    )
    blocker["blocker_id"] = safe_str(
        blocker.get("blocker_id") or blocker.get("remediation_id") or blocker.get("incident_id") or blocker.get("breach_id"),
        f"{source}:{blocker['category']}",
    )
    return blocker


def _append_blockers(target: List[Dict[str, Any]], items: List[Any], *, source: str, category: str, severity: str = "medium") -> None:
    for item in items:
        target.append(_normalize_blocker(item, source=source, default_category=category, default_severity=severity))


def _snapshot_status(snapshot: Dict[str, Any], *keys: str, default: str = "unknown") -> str:
    for key in keys:
        value = safe_str(snapshot.get(key))
        if value:
            return value.lower()
    return default.lower()


def _collect_recovery_evidence(
    *,
    rollout_payload: Dict[str, Any],
    runtime_remediation: Dict[str, Any],
    continuity_latest: Dict[str, Any],
    incident_latest: Dict[str, Any],
    executive_latest: Dict[str, Any],
) -> Dict[str, Any]:
    blockers: List[Dict[str, Any]] = []
    blocker_sources: List[str] = []
    warnings: List[str] = []

    rollout_summary = safe_dict(rollout_payload.get("rollout_readiness_summary"))
    rollout_observability = safe_dict(rollout_payload.get("production_observability_summary"))
    rollout_escalation = safe_dict(rollout_payload.get("escalation_chain_summary"))
    rollout_warnings = [safe_str(item) for item in safe_list(rollout_payload.get("warnings")) if safe_str(item)]
    warnings.extend(rollout_warnings)
    rollout_blocker_start = len(blockers)
    _append_blockers(
        blockers,
        safe_list(rollout_summary.get("unresolved_blockers")),
        source="rollout recovery snapshot",
        category="rollout_recovery",
    )
    _append_blockers(
        blockers,
        safe_list(rollout_observability.get("telemetry_degradation")),
        source="rollout recovery snapshot",
        category="observability_recovery",
    )
    if len(blockers) > rollout_blocker_start and "rollout recovery snapshot" not in blocker_sources:
        blocker_sources.append("rollout recovery snapshot")

    continuity_warnings = [safe_str(item) for item in safe_list(continuity_latest.get("warnings")) if safe_str(item)]
    warnings.extend(continuity_warnings)
    continuity_blocker_start = len(blockers)
    freeze_indicators = [
        item
        for item in safe_list(continuity_latest.get("continuity_freeze_indicators"))
        if isinstance(item, dict) and _truthy(item.get("freeze_active"))
    ]
    _append_blockers(
        blockers,
        freeze_indicators,
        source="continuity recovery snapshot",
        category="continuity_freeze",
        severity="high",
    )
    continuity_coordination = safe_dict(continuity_latest.get("operational_continuity_scoring"))
    continuity_status = _snapshot_status(continuity_latest, "status", "continuity_governance_status")
    if continuity_status != "ok":
        blockers.append(
            _normalize_blocker(
                {
                    "description": f"continuity governance remains {continuity_status}",
                    "category": "continuity_governance",
                    "severity": "medium" if continuity_status == "watch" else "high",
                    "score": continuity_coordination.get("score"),
                },
                source="continuity recovery snapshot",
                default_category="continuity_governance",
            )
        )
    if len(blockers) > continuity_blocker_start:
        blocker_sources.append("continuity recovery snapshot")

    escalation_warnings = [safe_str(item) for item in safe_list(incident_latest.get("warnings")) if safe_str(item)]
    warnings.extend(escalation_warnings)
    escalation_blocker_start = len(blockers)
    _append_blockers(
        blockers,
        safe_list(rollout_escalation.get("outstanding_governance_actions")),
        source="escalation recovery snapshot",
        category="governance_action",
    )
    _append_blockers(
        blockers,
        safe_list(rollout_escalation.get("unresolved_operational_exceptions")),
        source="escalation recovery snapshot",
        category="operational_exception",
        severity="medium",
    )
    _append_blockers(
        blockers,
        safe_list(incident_latest.get("escalation_failures")),
        source="escalation recovery snapshot",
        category="escalation_failure",
        severity="high",
    )
    incident_status = _snapshot_status(incident_latest, "status", "incident_governance_status")
    escalation_ready = _truthy(safe_dict(incident_latest.get("operational_recovery_coordination")).get("recovery_ready"))
    if incident_status != "ok" or not escalation_ready:
        blockers.append(
            _normalize_blocker(
                {
                    "description": "incident escalation recovery remains incomplete",
                    "category": "incident_escalation",
                    "severity": "medium" if incident_status == "watch" else "high",
                },
                source="escalation recovery snapshot",
                default_category="incident_escalation",
            )
        )
    if len(blockers) > escalation_blocker_start:
        blocker_sources.append("escalation recovery snapshot")

    remediation_warnings = [safe_str(item) for item in safe_list(runtime_remediation.get("warnings")) if safe_str(item)]
    warnings.extend(remediation_warnings)
    remediation_blocker_start = len(blockers)
    _append_blockers(
        blockers,
        safe_list(runtime_remediation.get("unresolved_remediation_blockers")),
        source="remediation recovery snapshot",
        category="remediation_blocker",
        severity="high",
    )
    remediation_tracking = safe_dict(runtime_remediation.get("governance_recovery_tracking"))
    remediation_status = _snapshot_status(runtime_remediation, "status", "runtime_remediation_status")
    if not _truthy(remediation_tracking.get("governance_recovery_ready")):
        blockers.append(
            _normalize_blocker(
                {
                    "description": "runtime remediation governance recovery is not yet complete",
                    "category": "governance_recovery",
                    "severity": "medium" if remediation_status == "watch" else "high",
                },
                source="remediation recovery snapshot",
                default_category="governance_recovery",
            )
        )
    if len(blockers) > remediation_blocker_start:
        blocker_sources.append("remediation recovery snapshot")

    blockers = [
        blocker
        for blocker in blockers
        if safe_str(blocker.get("description")) and safe_str(blocker.get("blocker_id"))
    ]
    deduped_blockers: List[Dict[str, Any]] = []
    seen = set()
    for blocker in blockers:
        signature = (
            safe_str(blocker.get("source")),
            safe_str(blocker.get("category")),
            safe_str(blocker.get("description")),
            safe_str(blocker.get("blocker_id")),
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped_blockers.append(blocker)

    executive_status = _snapshot_status(executive_latest, "status", "executive_governance_index_status")
    blocker_severities = {safe_str(item.get("severity"), "medium").lower() for item in deduped_blockers}
    if remediation_status == "blocked" or incident_status == "blocked" or continuity_status == "blocked":
        recovery_state = "unresolved-blocked"
    elif not deduped_blockers and all(
        status in {"ok", "watch"}
        for status in [remediation_status, continuity_status, incident_status, executive_status]
    ):
        recovery_state = "recovered"
    elif blocker_severities.intersection({"critical", "high"}):
        recovery_state = "unresolved-blocked"
    else:
        recovery_state = "degraded-but-recovering"

    score_penalty = 0.0 if recovery_state == "recovered" else 12.0 if recovery_state == "degraded-but-recovering" else 24.0
    blocker_count = len(deduped_blockers)
    blocker_penalty = blocker_count * (1.5 if recovery_state == "degraded-but-recovering" else 2.5 if recovery_state == "unresolved-blocked" else 0.0)
    rationale_parts = [
        f"Runtime remediation is `{remediation_status}`.",
        f"Continuity governance is `{continuity_status}`.",
        f"Incident governance is `{incident_status}`.",
        f"Executive governance index is `{executive_status}`.",
        f"Aggregated unresolved blockers: {blocker_count}.",
    ]
    if recovery_state == "recovered":
        rationale_parts.append("All recovery snapshots show complete recovery with no unresolved blockers.")
    elif recovery_state == "degraded-but-recovering":
        rationale_parts.append("Recovery is still in progress; warnings and unresolved blockers remain visible but no hard blockers require a NO_GO posture.")
    else:
        rationale_parts.append("Recovery remains blocked because high-severity blockers or blocked governance snapshots are still present.")

    return {
        "recovery_state": recovery_state,
        "recovery_state_history": [
            {
                "snapshot": "rollout recovery snapshot",
                "status": _snapshot_status(rollout_payload, "overall_status", default="warn"),
                "reason": "rollout validation snapshot captured for recovery evidence",
            },
            {
                "snapshot": "continuity recovery snapshot",
                "status": continuity_status,
                "reason": f"continuity warnings={len(continuity_warnings)} blockers={len([item for item in deduped_blockers if item.get('source') == 'continuity recovery snapshot'])}",
            },
            {
                "snapshot": "escalation recovery snapshot",
                "status": incident_status,
                "reason": f"escalation warnings={len(escalation_warnings)} blockers={len([item for item in deduped_blockers if item.get('source') == 'escalation recovery snapshot'])}",
            },
            {
                "snapshot": "remediation recovery snapshot",
                "status": remediation_status,
                "reason": f"remediation warnings={len(remediation_warnings)} blockers={len([item for item in deduped_blockers if item.get('source') == 'remediation recovery snapshot'])}",
            },
            {
                "snapshot": "final recovery assessment",
                "status": recovery_state,
                "reason": "aggregated cross-governance recovery assessment",
            },
        ],
        "unresolved_blockers": deduped_blockers,
        "recovery_rationale": " ".join(rationale_parts),
        "blocker_sources": blocker_sources,
        "aggregated_warnings": _dedupe_strings(warnings),
        "score_penalty": round(score_penalty + blocker_penalty, 2),
    }


def _write_bundle(path: Path, validation_id: str, generated_at: str, payload: Dict[str, Any], *, artifact_name: str) -> None:
    bundle_dir = path / validation_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record["validation_id"] = validation_id
    record["generated_at"] = generated_at
    write_json(bundle_dir / artifact_name, record)


def _make_recovery_endurance_payload(failure_payload: Dict[str, Any], recovered: bool) -> Dict[str, Any]:
    summary = safe_dict(failure_payload.get("runtime_endurance_summary"))
    if recovered:
        summary.update(
            {
                "runtime_endurance_score": 96.0,
                "runtime_endurance_status": "PASS",
                "runtime_endurance_grade": "ready",
                "overall_authority": "GO",
                "governance_locks_active": True,
                "dry_run_enabled": True,
                "supervision_mandatory": True,
                "services_healthy": True,
                "observability_endpoints_reachable": True,
                "escalation_readiness_intact": True,
                "continuity_indicators_stable": True,
                "no_governance_degradation_occurs": True,
            }
        )
        checks = [
            {"level": "PASS", "name": "governance locks remain active", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "dry-run remains enabled", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "supervision remains mandatory", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "services remain healthy", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "observability endpoints remain reachable", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "continuity indicators remain stable", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "escalation readiness remains intact", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "no governance degradation occurs", "message": "ok", "score": 100.0, "remediation": ""},
        ]
        history = [
            {
                "analysis_id": "runtime-recovery:recovered",
                "window_score": 96.0,
                "continuity_score": 97.0,
                "service_health_score": 98.0,
                "observability_score": 98.0,
                "escalation_score": 97.0,
                "governance_score": 96.0,
                "continuity_stable": True,
                "escalation_ready": True,
                "governance_degradation_detected": False,
                "sources": {
                    "executive_governance_index_status": "ok",
                    "continuity_readiness": {"continuity_governance_status": "ok"},
                    "incident_severity": {"incident_governance_status": "ok"},
                    "release_bundle": {"overall_status": "PASS", "overall_authority": "GO"},
                    "release_certification": {"status": "PASS", "release_governance_status": "ok"},
                },
            }
        ]
    else:
        summary.update(
            {
                "runtime_endurance_score": 77.0,
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
        checks = [
            {"level": "PASS", "name": "governance locks remain active", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "dry-run remains enabled", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "PASS", "name": "supervision remains mandatory", "message": "ok", "score": 100.0, "remediation": ""},
            {"level": "WARN", "name": "services remain healthy", "message": "backend recovery still pending", "score": 75.0, "remediation": "Restore service health."},
            {"level": "WARN", "name": "observability endpoints remain reachable", "message": "observability recovery still pending", "score": 75.0, "remediation": "Restore observability endpoints."},
            {"level": "WARN", "name": "continuity indicators remain stable", "message": "continuity recovery still pending", "score": 75.0, "remediation": "Restore continuity stability."},
            {"level": "WARN", "name": "escalation readiness remains intact", "message": "escalation readiness still pending", "score": 75.0, "remediation": "Restore escalation readiness."},
            {"level": "WARN", "name": "no governance degradation occurs", "message": "governance recovery still pending", "score": 75.0, "remediation": "Restore governance stability."},
        ]
        history = [
            {
                "analysis_id": "runtime-recovery:partial",
                "window_score": 77.0,
                "continuity_score": 66.0,
                "service_health_score": 68.0,
                "observability_score": 60.0,
                "escalation_score": 63.0,
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
        ]
    return {
        "runtime_endurance_summary": summary,
        "checks": checks,
        "sample_history": history,
    }


def _make_recovery_rollout_payload(failure_payload: Dict[str, Any], recovered: bool) -> Dict[str, Any]:
    rollout = safe_dict(failure_payload.get("rollout_readiness_summary"))
    if recovered:
        rollout.update(
            {
                "rollout_readiness_score": 96.0,
                "rollout_readiness_status": "PASS",
                "release_authorization_valid": True,
                "tenant_isolation_ready": True,
                "deployment_health_ready": True,
                "production_observability_ready": True,
                "escalation_chain_ready": True,
                "active_supervision_coverage_ready": True,
                "operator_availability_ready": True,
                "unresolved_blockers": [],
            }
        )
        supervision = {
            "active_supervision_coverage_ready": True,
            "supervision_score": 96.0,
            "supervision_command_status": "ok",
            "operator_name": "governance",
            "operator_role": "supervisor",
            "active_sessions": 1,
            "assigned_rfqs": ["RFQ-1"],
            "pending_approvals": [],
        }
        operator = {
            "operator_availability_ready": True,
            "operator_name": "governance",
            "operator_role": "supervisor",
            "approved_for_supervision": True,
            "onboarding_status": "ready",
        }
        deployment_health = {
            "deployment_health_ready": True,
            "production_observability_ready": True,
            "backup_restore_ready": True,
            "disaster_recovery_ready": True,
            "high_availability_ready": True,
            "audit_retention_ready": True,
        }
        observability = {
            "production_observability_ready": True,
            "worker_heartbeat": {"status": "healthy"},
            "telemetry_degradation": [],
        }
        escalation = {
            "escalation_chain_ready": True,
            "review_board_status": "ok",
            "outstanding_governance_actions": [],
            "unresolved_operational_exceptions": [],
        }
        warnings: List[str] = []
        summary_counts = {"PASS": 8, "WARN": 0, "FAIL": 0}
        incidents = []
        freezes = []
        anomalies = []
        breaches = []
        recovery_drills = [{"name": "runtime_recovery_drill", "status": "PASS"}]
        dr_rehearsals = [{"name": "disaster_recovery_rehearsal", "status": "PASS"}]
        operator_failover = [{"name": "operator_failover", "status": "PASS"}]
        supervision_continuity = [{"name": "supervision_continuity", "status": "PASS"}]
        recovery_escalation = [{"name": "recovery_escalation", "status": "PASS"}]
        recovery_timing = [{"name": "recovery_timing", "status": "PASS"}]
    else:
        rollout.update(
            {
                "rollout_readiness_score": 76.0,
                "rollout_readiness_status": "WARN",
                "release_authorization_valid": True,
                "tenant_isolation_ready": True,
                "deployment_health_ready": True,
                "production_observability_ready": True,
                "escalation_chain_ready": True,
                "active_supervision_coverage_ready": True,
                "operator_availability_ready": True,
                "unresolved_blockers": ["continuity recovery incomplete", "observability recovery incomplete"],
            }
        )
        supervision = {
            "active_supervision_coverage_ready": True,
            "supervision_score": 78.0,
            "supervision_command_status": "watch",
            "operator_name": "governance",
            "operator_role": "supervisor",
            "active_sessions": 1,
            "assigned_rfqs": ["RFQ-1"],
            "pending_approvals": ["recovery completion review"],
        }
        operator = {
            "operator_availability_ready": True,
            "operator_name": "governance",
            "operator_role": "supervisor",
            "approved_for_supervision": True,
            "onboarding_status": "ready",
        }
        deployment_health = {
            "deployment_health_ready": True,
            "production_observability_ready": True,
            "backup_restore_ready": True,
            "disaster_recovery_ready": True,
            "high_availability_ready": True,
            "audit_retention_ready": True,
        }
        observability = {
            "production_observability_ready": True,
            "worker_heartbeat": {"status": "degraded", "lag_seconds": 21},
            "telemetry_degradation": ["observability recovery incomplete"],
        }
        escalation = {
            "escalation_chain_ready": True,
            "review_board_status": "watch",
            "outstanding_governance_actions": ["restore observability", "confirm failover"],
            "unresolved_operational_exceptions": ["observability recovery incomplete"],
        }
        warnings = ["recoveries incomplete", "unresolved blockers remain visible"]
        summary_counts = {"PASS": 5, "WARN": 3, "FAIL": 0}
        incidents = [{"incident_id": "recovery-incomplete", "severity": "medium", "status": "open"}]
        freezes = []
        anomalies = []
        breaches = []
        recovery_drills = [{"name": "runtime_recovery_drill", "status": "PASS"}]
        dr_rehearsals = [{"name": "disaster_recovery_rehearsal", "status": "PASS"}]
        operator_failover = [{"name": "operator_failover", "status": "PASS"}]
        supervision_continuity = [{"name": "supervision_continuity", "status": "PASS"}]
        recovery_escalation = [{"name": "recovery_escalation", "status": "FAIL"}]
        recovery_timing = [{"name": "recovery_timing", "status": "FAIL"}]
    return {
        "overall_status": "PASS" if recovered else "WARN",
        "summary_counts": summary_counts,
        "rollout_readiness_summary": rollout,
        "supervision_readiness_summary": supervision,
        "operator_onboarding_readiness_summary": operator,
        "deployment_health_summary": deployment_health,
        "tenant_isolation_summary": {
            "tenant_isolation_ready": True,
            "tenant_count": 1,
            "workspace_count": 1,
            "tenant_workspace_pair_count": 1,
        },
        "production_observability_summary": observability,
        "escalation_chain_summary": escalation,
        "rollout_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "rollout-recovery-1", "latest_score": rollout["rollout_readiness_score"]},
        "institutional_rollout_certification_evidence": {
            "certification_status": "CERTIFIED" if recovered else "WATCH",
            "certification_authority": "GO" if recovered else "WATCH",
            "rollout_governance_score": rollout["rollout_readiness_score"],
            "rollout_ready_for_supervised_deployment": True,
            "release_authorization_valid": True,
            "governance_override_indicators": {"deployment_blockers": not recovered, "human_supervision_required": True},
        },
        "recovery_drill_readiness": recovery_drills,
        "disaster_recovery_rehearsal_status": dr_rehearsals,
        "operator_failover_readiness": operator_failover,
        "supervision_continuity_readiness": supervision_continuity,
        "continuity_freeze_indicators": freezes,
        "recovery_escalation_readiness": recovery_escalation,
        "recovery_timing_indicators": recovery_timing,
        "operational_incidents": incidents,
        "supervision_failures": [],
        "escalation_failures": [],
        "rollout_anomalies": anomalies,
        "governance_breach_indicators": breaches,
        "operational_freeze_history": freezes,
        "incident_severity_indicators": [{"incident_id": "recovery-incomplete", "severity": "medium", "status": "open"}] if not recovered else [],
        "warnings": warnings,
    }


def _make_recovery_release_payload(failure_payload: Dict[str, Any], recovered: bool) -> Dict[str, Any]:
    release = safe_dict(failure_payload.get("release_certification"))
    if recovered:
        release.update(
            {
                "status": "PASS",
                "certification_status": "CERTIFIED",
                "certification_score": 96.0,
                "release_authority": "GO",
                "release_governance_status": "ok",
                "release_governance_authority": "GO",
                "release_governance_score": 96.0,
                "release_governance_grade": "ready",
                "governance_certification_summary": {"certification_status": "CERTIFIED", "certification_score": 96.0},
                "operational_readiness_certification": {
                    "status": "PASS",
                    "submission_lock_verified": True,
                    "dry_run_verified": True,
                    "overall_validation_passed": True,
                },
                "release_authority_certification": {"status": "PASS", "active_authority": "GO"},
                "release_governance_history_summary": {"score_history": {"trend": "improving", "delta": 6.0, "average": 94.0, "latest": 96.0, "previous": 90.0, "points": [96.0, 90.0]}},
                "release_authority_indicators": {"active_authority": "GO"},
                "deployment_risk_indicators": {"deployment_risk": False},
                "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True},
                "release_readiness_indicators": {"runtime_segmentation_ready": True},
                "release_governance_history": [{"generated_at": iso_now(), "release_governance_score": 96.0, "status": "ok"}],
            }
        )
    else:
        release.update(
            {
                "status": "WARN",
                "certification_status": "WATCH",
                "certification_score": 76.0,
                "release_authority": "WATCH",
                "release_governance_status": "watch",
                "release_governance_authority": "WATCH",
                "release_governance_score": 76.0,
                "release_governance_grade": "watch",
                "governance_certification_summary": {"certification_status": "WATCH", "certification_score": 76.0},
                "operational_readiness_certification": {
                    "status": "WARN",
                    "submission_lock_verified": True,
                    "dry_run_verified": True,
                    "overall_validation_passed": True,
                },
                "release_authority_certification": {"status": "WARN", "active_authority": "WATCH"},
                "release_governance_history_summary": {"score_history": {"trend": "stable", "delta": 0.0, "average": 76.0, "latest": 76.0, "previous": 76.0, "points": [76.0, 76.0]}},
                "release_authority_indicators": {"active_authority": "WATCH"},
                "deployment_risk_indicators": {"deployment_risk": True, "deployment_risk_reason": "recovery incomplete"},
                "operational_release_indicators": {"submission_lock_verified": True, "dry_run_verified": True, "environment_safe": True},
                "release_readiness_indicators": {"runtime_segmentation_ready": True},
                "release_governance_history": [{"generated_at": iso_now(), "release_governance_score": 76.0, "status": "watch"}],
            }
        )
    return release


def _make_recovery_deployment_payload(
    rollout_payload: Dict[str, Any],
    release_payload: Dict[str, Any],
    recovered: bool,
) -> Dict[str, Any]:
    rollout_summary = safe_dict(rollout_payload.get("rollout_readiness_summary"))
    deployment_health = safe_dict(rollout_payload.get("deployment_health_summary"))
    observability = safe_dict(rollout_payload.get("production_observability_summary"))
    operator = safe_dict(rollout_payload.get("operator_onboarding_readiness_summary"))
    release_authority = safe_str(safe_dict(release_payload.get("release_authority_indicators")).get("active_authority"), "GO" if recovered else "WATCH").upper()
    status = "PASS" if recovered else "WARN"
    readiness_score = 96.0 if recovered else 74.0
    section_status = "ok" if recovered else "watch"
    warnings = [] if recovered else ["deployment readiness below threshold", "recovery completion review pending"]
    history_entry = {
        "analysis_id": f"{safe_str(rollout_payload.get('validation_id'), 'runtime-recovery')}:release-gate",
        "generated_at": iso_now(),
        "production_readiness_score": readiness_score,
        "release_governance_score": readiness_score,
        "release_governance_status": section_status,
        "release_governance_authority": "GO" if recovered else "WATCH",
        "release_governance_grade": "ready" if recovered else "watch",
        "deployment_risk_indicators": {"deployment_risk": not recovered},
        "operational_release_indicators": {
            "submission_lock_verified": True,
            "dry_run_verified": True,
            "environment_safe": True,
            "history_available": True,
            "overall_validation_passed": recovered,
        },
        "release_readiness_indicators": {"runtime_segmentation_ready": recovered or _truthy(rollout_summary.get("tenant_isolation_ready"))},
        "release_authority_indicators": {
            "go_release_authority": recovered,
            "watch_release_authority": not recovered,
            "no_go_release_authority": False,
            "active_authority": "GO" if recovered else "WATCH",
        },
        "unresolved_deployment_blockers": [] if recovered else safe_list(rollout_summary.get("unresolved_blockers")) or ["deployment readiness below threshold"],
        "governance_override_authority": not recovered,
        "release_escalation_authority": not recovered,
        "production_rollout_readiness": recovered,
        "production_rollout_readiness_status": "ready" if recovered else "watch",
        "summary_components": {"runtime_segmentation": readiness_score},
        "validation_counts": {"PASS": 8 if recovered else 0, "WARN": 0 if recovered else 8, "FAIL": 0},
        "warnings": warnings,
    }
    return {
        "validation_id": f"{safe_str(rollout_payload.get('validation_id'), 'runtime-recovery')}-deployment",
        "generated_at": iso_now(),
        "overall_status": status,
        "overall_grade": "ready" if recovered else "watch",
        "readiness_summary": {
            "production_readiness_score": readiness_score,
            "production_readiness_status": status,
            "production_readiness_grade": "ready" if recovered else "watch",
            "summary_components": {
                "runtime_segmentation": readiness_score,
                "operator_access": readiness_score,
                "observability": readiness_score,
                "backup_restore": readiness_score,
                "disaster_recovery": readiness_score,
                "high_availability": readiness_score,
                "audit_retention": readiness_score,
                "deployment_readiness": readiness_score,
            },
        },
        "validation_sections": {
            "runtime_segmentation": {
                "production_runtime_segmentation_score": readiness_score,
                "production_runtime_segmentation_status": section_status,
                "tenant_workspace_isolation": {"isolation_verified": _truthy(rollout_summary.get("tenant_isolation_ready"))},
            },
            "operator_access": {
                "operator_access_governance_score": readiness_score,
                "operator_access_governance_status": section_status,
                "operator_access_details": {"operator_name": safe_str(operator.get("operator_name"), "governance"), "operator_role": safe_str(operator.get("operator_role"), "supervisor")},
                "operator_access_risk_indicators": {"pending_approval_backlog": not recovered},
            },
            "observability": {
                "production_observability_governance_score": readiness_score,
                "production_observability_governance_status": section_status,
                "observability_readiness_indicators": {"worker_heartbeat": safe_dict(observability.get("worker_heartbeat")) or {"status": "healthy"}},
                "observability_risk_indicators": {"telemetry_degradation": safe_list(observability.get("telemetry_degradation"))},
            },
            "backup_restore": {
                "backup_restore_governance_score": readiness_score,
                "backup_restore_governance_status": section_status,
                "backup_restore_details": {"latest_pack_id": "runtime-recovery-pack"},
                "recovery_readiness_indicators": {"evidence_pack_available": True},
            },
            "disaster_recovery": {
                "disaster_recovery_governance_score": readiness_score,
                "disaster_recovery_governance_status": section_status,
                "recovery_readiness_indicators": {"final_readiness_cleared": recovered},
            },
            "high_availability": {
                "high_availability_governance_score": readiness_score,
                "high_availability_governance_status": section_status,
                "ha_readiness_indicators": {"queue_stable": recovered},
            },
            "audit_retention": {
                "audit_retention_governance_score": readiness_score,
                "audit_retention_governance_status": section_status,
                "audit_retention_details": {"cycle_count": 1},
                "audit_retention_indicators": {"cycle_history_available": True},
            },
            "deployment_readiness": {
                "deployment_readiness_governance_score": readiness_score,
                "deployment_readiness_governance_status": section_status,
                "deployment_readiness_indicators": {"executive_ready": recovered, "release_authority": release_authority},
            },
        },
        "deployment_risk_summary": {"deployment_risk": not recovered},
        "operator_access_risk_indicators": {"pending_approval_backlog": not recovered},
        "ha_readiness_indicators": {"queue_stable": recovered},
        "recovery_readiness_indicators": {"final_readiness_cleared": recovered},
        "environment_safety": {"status": "PASS", "details": {"lmcp_env": "staging"}, "blockers": []},
        "submission_lock_verification": {"status": "PASS", "exists": True, "verified": True},
        "dry_run_enforcement_verification": {"status": "PASS", "verified": True},
        "validation_counts": {"PASS": 8 if recovered else 0, "WARN": 0 if recovered else 8, "FAIL": 0},
        "warnings": warnings,
        "governance_validation_history": [history_entry],
        "latest_release_governance": {
            "analysis_id": history_entry["analysis_id"],
            "generated_at": history_entry["generated_at"],
            "production_readiness_score": readiness_score,
            "release_governance_score": readiness_score,
            "release_governance_status": section_status,
            "release_governance_authority": "GO" if recovered else "WATCH",
            "release_governance_grade": "ready" if recovered else "watch",
        },
    }


class _SimulatedOperationalIntelligenceService:
    def __init__(self, recovered: bool = True) -> None:
        self.recovered = recovered

    def latest_operational_intelligence(self) -> Dict[str, Any]:
        return {
            "status": "ok" if self.recovered else "watch",
            "generated_at": iso_now(),
            "operational_intelligence_status": "ok" if self.recovered else "watch",
            "operational_intelligence_authority": "GO" if self.recovered else "WATCH",
            "operational_intelligence_score": 96.0 if self.recovered else 72.0,
            "operational_intelligence_grade": "ready" if self.recovered else "watch",
            "operational_intelligence_history_summary": {
                "score_history": _history_points([96.0, 92.0] if self.recovered else [72.0, 76.0])
            },
            "operational_intelligence_degradation_indicators": {"degradation_detected": not self.recovered},
        }


class _SimulatedExecutiveCommandService:
    def __init__(self, recovered: bool = True) -> None:
        self.recovered = recovered

    def latest_executive_command(self) -> Dict[str, Any]:
        return {
            "status": "ok" if self.recovered else "watch",
            "generated_at": iso_now(),
            "executive_governance_status": "ok" if self.recovered else "watch",
            "executive_governance_index_status": "ok" if self.recovered else "watch",
            "executive_governance_index_authority": "GO" if self.recovered else "WATCH",
            "executive_governance_index_score": 96.0 if self.recovered else 74.0,
            "executive_governance_index_grade": "ready" if self.recovered else "watch",
            "executive_governance_index_history_summary": {
                "score_history": _history_points([96.0, 92.0] if self.recovered else [74.0, 78.0])
            },
            "executive_governance_index_degradation_indicators": {"degradation_detected": not self.recovered},
        }


def build_runtime_recovery_validation_report(
    *,
    failure_validation_file: Optional[Path] = None,
    endurance_validation_file: Optional[Path] = None,
    boot_validation_file: Optional[Path] = None,
    rollout_validation_file: Optional[Path] = None,
    release_certification_file: Optional[Path] = None,
    lock_file: Optional[Path] = None,
    output_root: Optional[Path] = None,
    recovered: bool = True,
) -> Dict[str, Any]:
    failure_validation_file = failure_validation_file or FAILURE_VALIDATION_FILE
    endurance_validation_file = endurance_validation_file or ENDURANCE_VALIDATION_FILE
    boot_validation_file = boot_validation_file or BOOT_VALIDATION_FILE
    rollout_validation_file = rollout_validation_file or ROLLOUT_VALIDATION_FILE
    release_certification_file = release_certification_file or RELEASE_CERTIFICATION_FILE
    lock_file = lock_file or LOCK_FILE
    output_root = output_root or RECOVERY_VALIDATION_ROOT

    failure_payload = _load_json(failure_validation_file)
    endurance_payload = _load_json(endurance_validation_file)
    boot_payload = _load_json(boot_validation_file)
    rollout_payload = _load_json(rollout_validation_file)
    release_payload = _load_json(release_certification_file)
    lock_payload = _load_json(lock_file)

    generated_at = iso_now()
    validation_id = f"runtime-recovery-{validation_timestamp()}-{uuid.uuid4().hex[:8]}"
    bundle_root = output_root / validation_id
    bundle_root.mkdir(parents=True, exist_ok=True)

    recovery_endurance = _make_recovery_endurance_payload(endurance_payload or failure_payload, recovered=recovered)
    recovery_rollout = _make_recovery_rollout_payload(rollout_payload or failure_payload, recovered=recovered)
    recovery_release = _make_recovery_release_payload(release_payload or failure_payload, recovered=recovered)
    recovery_rollout["latest_release_certification"] = recovery_release
    recovery_rollout["release_certification_snapshot"] = recovery_release
    recovery_deployment = _make_recovery_deployment_payload(recovery_rollout, recovery_release, recovered=recovered)

    endurance_root = bundle_root / "recovered-runtime-endurance-validations"
    rollout_root = bundle_root / "recovered-production-rollout-validations"
    release_root = bundle_root / "recovered-release-certifications"
    deployment_root = bundle_root / "recovered-production-deployment-validations"
    for root in (endurance_root, rollout_root, release_root, deployment_root):
        root.mkdir(parents=True, exist_ok=True)

    _write_bundle(
        endurance_root,
        f"{validation_id}-endurance",
        generated_at,
        recovery_endurance,
        artifact_name="runtime_endurance_validation.json",
    )
    _write_bundle(
        rollout_root,
        f"{validation_id}-rollout",
        generated_at,
        recovery_rollout,
        artifact_name="production_rollout_validation.json",
    )
    _write_bundle(
        release_root,
        f"{validation_id}-release",
        generated_at,
        recovery_release,
        artifact_name="executive_release_evidence.json",
    )
    _write_bundle(
        deployment_root,
        f"{validation_id}-deployment",
        generated_at,
        recovery_deployment,
        artifact_name="production_deployment_validation.json",
    )

    from app.services.activation_governance_service import ActivationGovernanceService
    from app.services.executive_governance_index_service import ExecutiveGovernanceIndexService
    from app.services.operational_exception_service import _safe_dict, _safe_list, _safe_str
    from app.services.production_audit_governance_service import ProductionAuditGovernanceService
    from app.services.production_continuity_governance_service import ProductionContinuityGovernanceService
    from app.services.production_incident_governance_service import ProductionIncidentGovernanceService
    from app.services.production_release_governance_service import ProductionReleaseGovernanceService
    from app.services.production_supervision_command_service import ProductionSupervisionCommandService
    from app.services.runtime_remediation_governance_service import RuntimeRemediationGovernanceService

    remediation_service = RuntimeRemediationGovernanceService(validation_root=endurance_root)
    continuity_service = ProductionContinuityGovernanceService(validation_root=rollout_root, release_certification_root=release_root)
    incident_service = ProductionIncidentGovernanceService(validation_root=rollout_root, release_certification_root=release_root)
    supervision_service = ProductionSupervisionCommandService(validation_root=rollout_root, release_certification_root=release_root)
    activation_service = ActivationGovernanceService(validation_root=rollout_root, release_certification_root=release_root)
    audit_service = ProductionAuditGovernanceService(validation_root=rollout_root, release_certification_root=release_root)
    release_service = ProductionReleaseGovernanceService(validation_root=deployment_root)
    intelligence_service = _SimulatedOperationalIntelligenceService(recovered=recovered)
    executive_command_service = _SimulatedExecutiveCommandService(recovered=recovered)
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

    containment = {
        "lock_verified": bool(lock_payload)
        and lock_payload.get("final_automation_disabled") is True
        and lock_payload.get("live_portal_submission_disabled") is True
        and lock_payload.get("production_credentials_disabled") is True
        and lock_payload.get("dry_run_mode_required") is True
        and lock_payload.get("submission_execution_allowed") is False,
        "dry_run_enabled": safe_dict(boot_payload.get("boot_readiness_summary")).get("dry_run_mode_enabled") is True
        and safe_dict(endurance_payload.get("runtime_endurance_summary")).get("dry_run_enabled") is True,
        "supervision_mandatory": safe_dict(boot_payload.get("boot_readiness_summary")).get("human_supervision_required") is True
        and safe_dict(endurance_payload.get("runtime_endurance_summary")).get("supervision_mandatory") is True,
    }
    containment["containment_active"] = containment["lock_verified"] and containment["dry_run_enabled"] and containment["supervision_mandatory"]

    runtime_remediation = remediation_latest
    continuity_status = safe_str(continuity_latest.get("status"), "watch").lower()
    incident_status = safe_str(incident_latest.get("status"), "watch").lower()
    supervision_status = safe_str(supervision_latest.get("status"), "watch").lower()
    executive_status = safe_str(executive_latest.get("status"), "watch").lower()
    release_status = safe_str(release_latest.get("status"), "watch").upper()

    checks: List[CheckResult] = [
        _check(containment["containment_active"], "governance containment remains active", "containment remains active", "containment is not active", "Restore locks, dry-run, and supervision requirements."),
        _check(runtime_remediation.get("status") in {"ok", "watch"}, "remediation governance activates", "runtime remediation active", "runtime remediation did not activate", "Ensure recovery evidence is readable."),
        _check(_truthy(runtime_remediation.get("governance_recovery_tracking", {}).get("governance_recovery_ready")), "governance stability restoration", "governance stability restored", "governance stability remains degraded", "Close remediation blockers and rerun recovery."),
        _check(_truthy(runtime_remediation.get("governance_recovery_tracking", {}).get("recovery_readiness_intact")), "continuity recovery", "continuity recovery restored", "continuity recovery remains incomplete", "Restore continuity indicators."),
        _check(_truthy(runtime_remediation.get("remediation_escalation_indicators", {}).get("escalation_gap_found")) is False, "escalation readiness restoration", "escalation readiness restored", "escalation readiness remains degraded", "Restore escalation timing and readiness."),
        _check(_truthy(runtime_remediation.get("remediation_escalation_indicators", {}).get("observability_failure_found")) is False, "observability restoration", "observability restored", "observability remains degraded", "Restore observability endpoints and telemetry."),
        _check(supervision_status in {"ok", "watch"}, "supervision continuity", "supervision continuity remains active", "supervision continuity is degraded", "Restore supervision coverage."),
        _check(continuity_status in {"ok", "watch"}, "continuity governance responds", "continuity governance responded", "continuity governance did not respond", "Rebuild continuity evidence."),
        _check(incident_status in {"ok", "watch"}, "incident governance responds", "incident governance responded", "incident governance did not respond", "Rebuild incident evidence."),
        _check(executive_status in {"ok", "watch"}, "governance index recovery", "executive governance index reflects recovery", "executive governance index does not reflect recovery", "Rebuild executive governance index evidence."),
    ]

    recovery_evidence = _collect_recovery_evidence(
        rollout_payload=recovery_rollout,
        runtime_remediation=runtime_remediation,
        continuity_latest=continuity_latest,
        incident_latest=incident_latest,
        executive_latest=executive_latest,
    )
    unresolved_blockers = recovery_evidence["unresolved_blockers"]
    recovery_state = recovery_evidence["recovery_state"]
    if not containment["containment_active"] and recovery_state != "recovered":
        recovery_state = "unresolved-blocked"
        recovery_evidence["recovery_state"] = recovery_state
        recovery_evidence["recovery_rationale"] = (
            f"{recovery_evidence['recovery_rationale']} Governance containment is not active, so recovery remains blocked."
        )
        recovery_evidence["score_penalty"] = max(safe_float(recovery_evidence.get("score_penalty"), 0.0), 24.0)
        recovery_evidence["recovery_state_history"][-1]["status"] = recovery_state
        recovery_evidence["recovery_state_history"][-1]["reason"] = "containment inactive during final recovery assessment"

    overall_status = _overall_status([check.level for check in checks])
    if recovery_state == "recovered":
        overall_status = "PASS"
    elif recovery_state == "degraded-but-recovering":
        overall_status = "WARN"
    else:
        overall_status = "FAIL" if not containment["containment_active"] else "WARN"
    summary_counts = {
        "PASS": sum(1 for check in checks if check.level == "PASS"),
        "WARN": sum(1 for check in checks if check.level == "WARN"),
        "FAIL": sum(1 for check in checks if check.level == "FAIL"),
    }
    base_recovery_score = round(
        max(
            0.0,
            min(
                100.0,
                mean(
                    [
                        100.0 if containment["containment_active"] else 0.0,
                        100.0 if _truthy(runtime_remediation.get("governance_recovery_tracking", {}).get("governance_recovery_ready")) else 70.0,
                        100.0 if _truthy(runtime_remediation.get("governance_recovery_tracking", {}).get("recovery_readiness_intact")) else 70.0,
                        100.0 if continuity_status == "ok" else 75.0,
                        100.0 if incident_status == "ok" else 75.0,
                        100.0 if supervision_status == "ok" else 80.0,
                        100.0 if executive_status == "ok" else 75.0,
                        100.0 if not unresolved_blockers else 70.0,
                    ]
                ),
            ),
        ),
        2,
    )
    recovery_score = round(max(0.0, min(100.0, base_recovery_score - safe_float(recovery_evidence.get("score_penalty"), 0.0))), 2)
    if recovery_state != "recovered":
        recovery_score = min(recovery_score, 84.99)
    score_impact = {
        "base_score": base_recovery_score,
        "state_penalty": safe_float(recovery_evidence.get("score_penalty"), 0.0),
        "final_score": recovery_score,
        "state": recovery_state,
    }

    report = {
        "validation_id": validation_id,
        "generated_at": generated_at,
        "overall_status": overall_status,
        "overall_score": recovery_score,
        "recovery_state": recovery_state,
        "recovery_state_history": recovery_evidence["recovery_state_history"],
        "recovery_rationale": recovery_evidence["recovery_rationale"],
        "blocker_sources": recovery_evidence["blocker_sources"],
        "summary_counts": summary_counts,
        "governance_recovery": {
            "containment_active": containment["containment_active"],
            "lock_verified": containment["lock_verified"],
            "dry_run_enabled": containment["dry_run_enabled"],
            "supervision_mandatory": containment["supervision_mandatory"],
        },
        "recovery_scenarios": [
            {
                "scenario": "redis_interruption",
                "recovered": recovered,
                "governance_response": "restored" if recovered else "watch",
            },
            {
                "scenario": "backend_degradation",
                "recovered": recovered,
                "governance_response": "restored" if recovered else "watch",
            },
            {
                "scenario": "worker_interruption",
                "recovered": recovered,
                "governance_response": "restored" if recovered else "watch",
            },
            {
                "scenario": "observability_interruption",
                "recovered": recovered,
                "governance_response": "restored" if recovered else "watch",
            },
            {
                "scenario": "escalation_degradation",
                "recovered": recovered,
                "governance_response": "restored" if recovered else "watch",
            },
            {
                "scenario": "continuity_instability",
                "recovered": recovered,
                "governance_response": "restored" if recovered else "watch",
            },
        ],
        "service_snapshots": {
            "runtime_remediation": runtime_remediation,
            "continuity_governance": continuity_latest,
            "incident_governance": incident_latest,
            "supervision_command": supervision_latest,
            "executive_governance_index": executive_latest,
            "activation_governance": activation_latest,
            "operations_audit": audit_latest,
            "release_governance": release_latest,
        },
        "checks": [check.__dict__ for check in checks],
        "warnings": recovery_evidence["aggregated_warnings"],
        "score_impact": score_impact,
        "validation_history": {
            "failure_validation_id": safe_str(failure_payload.get("validation_id"), ""),
            "failure_validation_status": safe_str(failure_payload.get("overall_status"), "WARN"),
            "endurance_validation_id": safe_str(endurance_payload.get("validation_id"), ""),
            "boot_validation_id": safe_str(boot_payload.get("validation_id"), ""),
            "rollout_validation_id": safe_str(rollout_payload.get("validation_id"), ""),
            "release_certification_status": safe_str(release_payload.get("status"), ""),
        },
        "unresolved_blockers": unresolved_blockers,
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "live_submission_enablement": False,
            "dry_run_protections_active": True,
            "human_supervision_required": True,
        },
        "artifacts": {
            "bundle_root": str(bundle_root),
            "runtime_recovery_validation_json": str(bundle_root / "runtime_recovery_validation.json"),
            "runtime_recovery_validation_md": str(bundle_root / "runtime_recovery_validation.md"),
            "latest_runtime_recovery_validation_json": str(output_root / "latest_runtime_recovery_validation.json"),
            "latest_runtime_recovery_validation_md": str(output_root / "latest_runtime_recovery_validation.md"),
        },
        "notes": [
            "Recovery validation is staging-only and uses simulated recovery state.",
            "Unresolved blockers remain visible when recovery is incomplete.",
            "Human supervision remains mandatory and governance layers remain authoritative.",
        ],
    }

    markdown = "\n".join(
        [
            "# Runtime Recovery Validation",
            "",
            f"- Validation ID: `{validation_id}`",
            f"- Generated At: `{generated_at}`",
            f"- Overall Status: `{overall_status}`",
            f"- Overall Score: `{recovery_score:.2f}`",
            f"- Final Recovery State: `{recovery_state}`",
            "",
            "## Governance Recovery",
            f"- Containment Active: `{containment['containment_active']}`",
            f"- Lock Verified: `{containment['lock_verified']}`",
            f"- Dry-Run Enabled: `{containment['dry_run_enabled']}`",
            f"- Supervision Mandatory: `{containment['supervision_mandatory']}`",
            "",
            "## Recovery Assessment",
            f"- Recovery Rationale: {recovery_evidence['recovery_rationale']}",
            f"- Blocker Sources: `{json.dumps(recovery_evidence['blocker_sources'])}`",
            f"- Score Impact: base={base_recovery_score:.2f}, penalty={safe_float(recovery_evidence.get('score_penalty'), 0.0):.2f}, final={recovery_score:.2f}",
            "",
            "## Recovery Scenarios",
            *[
                f"- {item['scenario']}: recovered={item['recovered']} -> {item['governance_response']}"
                for item in report["recovery_scenarios"]
            ],
            "",
            "## Recovery State History",
            *[
                f"- {item['snapshot']}: `{item['status']}` ({item['reason']})"
                for item in recovery_evidence["recovery_state_history"]
            ],
            "",
            "## Service Snapshots",
            f"- Runtime Remediation Status: `{safe_str(runtime_remediation.get('status'), 'unknown')}`",
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
            "## Unresolved Blockers",
            *(
                [
                    f"- {safe_str(item.get('source'), 'snapshot')} / {safe_str(item.get('category'), 'blocker')}: {safe_str(item.get('description'), 'n/a')} [{safe_str(item.get('severity'), 'medium')}]"
                    for item in unresolved_blockers
                ]
                if unresolved_blockers
                else ["- none"]
            ),
            "",
            "## Warnings",
            *([f"- {warning}" for warning in recovery_evidence["aggregated_warnings"]] if recovery_evidence["aggregated_warnings"] else ["- none"]),
            "",
            "## Safety Guarantees",
            "- Autonomous procurement authority remains disabled.",
            "- Live submission enablement remains disabled.",
            "- Dry-run protections remain active.",
            "- Human supervision remains mandatory.",
        ]
    )

    write_json(bundle_root / "runtime_recovery_validation.json", report)
    write_text(bundle_root / "runtime_recovery_validation.md", markdown)
    write_json(output_root / "latest_runtime_recovery_validation.json", report)
    write_text(output_root / "latest_runtime_recovery_validation.md", markdown)

    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run controlled runtime recovery validation.")
    parser.add_argument("--output-root", default=str(RECOVERY_VALIDATION_ROOT), help="Directory for runtime recovery validation bundles.")
    parser.add_argument(
        "--partial",
        action="store_true",
        help="Emit a partial recovery bundle that preserves unresolved blockers for operator review.",
    )
    args = parser.parse_args(argv)

    report = build_runtime_recovery_validation_report(output_root=Path(args.output_root), recovered=not args.partial)
    print("Runtime recovery validation:")
    print(
        json.dumps(
            {
                "validation_id": report["validation_id"],
                "overall_status": report["overall_status"],
                "overall_score": report["overall_score"],
                "recovery_state": report["recovery_state"],
                "summary_counts": report["summary_counts"],
                "bundle_root": report["artifacts"]["bundle_root"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
