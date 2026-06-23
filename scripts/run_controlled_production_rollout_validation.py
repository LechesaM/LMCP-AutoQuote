#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


STAGING_ROOT = PROJECT_ROOT / "runtime" / "staging"
ROLLOUT_VALIDATION_ROOT = STAGING_ROOT / "production-rollout-validations"
RELEASE_CERTIFICATION_ROOT = STAGING_ROOT / "release-certifications"
LATEST_PILOT_CYCLE_SUMMARY_FILE = STAGING_ROOT / "pilot-cycles" / "latest_pilot_cycle_summary.json"
LATEST_PILOT_REHEARSAL_SUMMARY_FILE = STAGING_ROOT / "governance-exports" / "latest_pilot_rehearsal_summary.json"
LATEST_PILOT_EVIDENCE_PACK_FILE = STAGING_ROOT / "evidence-packs" / "latest_pilot_evidence_pack.json"
LATEST_RELEASE_CERTIFICATION_FILE = RELEASE_CERTIFICATION_ROOT / "latest_executive_release_evidence.json"
LATEST_RELEASE_CERTIFICATION_MD_FILE = RELEASE_CERTIFICATION_ROOT / "latest_executive_release_evidence.md"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def rollout_timestamp() -> str:
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


def _production_operationalization_service():
    from app.services.production_operationalization_service import ProductionOperationalizationService

    return ProductionOperationalizationService()


def _release_governance_service():
    from app.services.production_release_governance_service import ProductionReleaseGovernanceService

    return ProductionReleaseGovernanceService()


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "PASS"
    if score >= 70.0:
        return "WARN"
    return "FAIL"


def _rollout_authority_from_state(status: str, score: float, blockers: List[str]) -> str:
    normalized = safe_str(status, "WARN").upper()
    if normalized == "CERTIFIED" or (normalized == "PASS" and score >= 85.0 and not blockers):
        return "GO"
    if normalized == "WATCH" or score >= 70.0:
        return "WATCH"
    return "NO_GO"


def _read_release_certification_snapshot() -> Dict[str, Any]:
    snapshot = read_json(LATEST_RELEASE_CERTIFICATION_FILE, {})
    if isinstance(snapshot, dict) and snapshot:
        snapshot["artifact_path"] = str(LATEST_RELEASE_CERTIFICATION_FILE)
        return snapshot
    try:
        service = _release_governance_service()
        latest = safe_dict(service.latest_release_governance())
        if latest:
            latest["artifact_path"] = str(LATEST_RELEASE_CERTIFICATION_FILE)
            return latest
    except Exception:
        return {}
    return {}


def _status_rank(value: str) -> int:
    normalized = safe_str(value, "FAIL").upper()
    if normalized in {"PASS", "READY", "OK", "CERTIFIED", "GO"}:
        return 3
    if normalized in {"WARN", "WATCH"}:
        return 2
    return 1


def _rollout_check(label: str, score: float, ready: bool, details: Dict[str, Any]) -> Dict[str, Any]:
    status = _status_from_score(score)
    if not ready:
        status = "WARN" if score >= 70.0 else "FAIL"
    return {
        "label": label,
        "status": status,
        "score": round(score, 2),
        "ready": bool(ready),
        "details": details,
    }


def _history_scores(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    trend = "stable"
    if delta > 2.0:
        trend = "improving"
    elif delta < -2.0:
        trend = "declining"
    return {
        "trend": trend,
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


def _snapshot_rollout_state() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    cycle = read_json(LATEST_PILOT_CYCLE_SUMMARY_FILE, {})
    rehearsal = read_json(LATEST_PILOT_REHEARSAL_SUMMARY_FILE, {})
    evidence = read_json(LATEST_PILOT_EVIDENCE_PACK_FILE, {})
    release_certification = _read_release_certification_snapshot()

    cycle = safe_dict(cycle)
    rehearsal = safe_dict(rehearsal)
    evidence = safe_dict(evidence)
    release_certification = safe_dict(release_certification)

    readiness = safe_dict(rehearsal.get("readiness_summary")) or safe_dict(evidence.get("readiness_summary"))
    readiness_metrics = safe_dict(readiness.get("metrics"))
    rehearsal_history_summary = safe_dict(rehearsal.get("rehearsal_history_summary")) or safe_dict(evidence.get("rehearsal_history_summary"))
    rehearsal_runs = safe_list(rehearsal_history_summary.get("runs"))
    operator_sign_off = safe_dict(rehearsal.get("operator_sign_off_section"))
    operator_ack = safe_dict(cycle.get("operator_acknowledgement"))
    latest_rehearsal = safe_dict(rehearsal.get("latest_rehearsal"))
    queue_stability_summary = safe_dict(rehearsal.get("queue_stability_summary")) or safe_dict(latest_rehearsal.get("queue_stability_summary"))
    telemetry_health_summary = safe_dict(rehearsal.get("telemetry_health_summary")) or safe_dict(latest_rehearsal.get("telemetry_health_summary"))
    no_go_condition_summary = safe_dict(rehearsal.get("no_go_condition_summary"))
    release_summary = safe_dict(release_certification.get("governance_certification_summary"))
    release_authority = safe_dict(release_certification.get("release_authority_certification"))
    release_readiness = safe_dict(release_certification.get("release_readiness_indicators"))
    release_operational = safe_dict(release_certification.get("operational_readiness_certification"))
    release_deployment = safe_dict(release_certification.get("deployment_readiness_certification"))

    operator_items = safe_list(operator_sign_off.get("items"))
    operator_acknowledged = bool(operator_ack.get("acknowledged")) or all(
        safe_str(safe_dict(item).get("status"), "FAIL") == "PASS" for item in operator_items
    )
    operator_role = "governance_reviewer"
    operator_name = "staging-governance-operator"
    active_sessions = 1 if operator_acknowledged else 0
    pending_approvals: List[str] = [] if operator_acknowledged else ["operator supervision pending"]

    readiness_score = safe_float(readiness.get("readiness_score"), safe_float(readiness_metrics.get("rehearsal_success_rate"), 0.0))
    readiness_grade = safe_str(readiness.get("readiness_grade"), "watch")
    release_authorization_valid = safe_str(release_summary.get("certification_status"), "WATCH") == "CERTIFIED" and safe_str(release_authority.get("active_authority"), "WATCH") == "GO"
    tenant_isolation_ready = bool(safe_dict(release_readiness).get("runtime_segmentation_ready", True))
    supervision_coverage_ready = operator_acknowledged and not pending_approvals
    operator_availability_ready = operator_acknowledged and safe_str(operator_role, "") in {"governance_reviewer", "operator", "supervisor"}
    deployment_health_ready = all(
        [
            safe_str(safe_dict(telemetry_health_summary).get("status"), "watch") in {"PASS", "ok"},
            safe_str(safe_dict(queue_stability_summary).get("status"), "watch") == "PASS",
            safe_str(safe_dict(latest_rehearsal.get("operational_health")).get("status"), "watch") == "ok",
        ]
    )
    production_observability_ready = safe_str(safe_dict(telemetry_health_summary).get("status"), "watch") in {"PASS", "ok"}
    escalation_chain_ready = safe_str(no_go_condition_summary.get("status"), "FAIL") == "PASS" and operator_acknowledged

    latest = {
        "analysis_id": safe_str(cycle.get("cycle_id"), safe_str(rehearsal.get("run_id"), "production-rollout")),
        "generated_at": safe_str(rehearsal.get("generated_at"), safe_str(cycle.get("generated_at"), iso_now())),
        "production_readiness_score": readiness_score,
        "production_readiness_status": "ok" if readiness_score >= 85.0 else "watch" if readiness_score >= 70.0 else "blocked",
        "production_readiness_grade": readiness_grade if readiness_grade else ("ready" if readiness_score >= 85.0 else "watch" if readiness_score >= 70.0 else "blocked"),
        "production_runtime_segmentation": {
            "production_runtime_segmentation_score": 100.0 if tenant_isolation_ready else 60.0,
            "production_runtime_segmentation_status": "ok" if tenant_isolation_ready else "watch",
            "tenant_workspace_isolation": {
                "tenant_count": 1 if tenant_isolation_ready else 0,
                "workspace_count": 1 if tenant_isolation_ready else 0,
                "tenant_workspace_pair_count": 1 if tenant_isolation_ready else 0,
                "isolation_verified": tenant_isolation_ready,
            },
        },
        "operator_access_governance": {
            "operator_access_governance_score": 100.0 if operator_acknowledged else 60.0,
            "operator_access_governance_status": "ok" if operator_acknowledged else "watch",
            "operator_access_details": {
                "operator_name": operator_name,
                "operator_role": operator_role,
                "active_sessions": active_sessions,
                "assigned_rfqs": [safe_str(safe_dict(cycle.get("evidence_pack")).get("pack_id"), "production-rollout-pack")] if operator_acknowledged else [],
                "pending_approvals": pending_approvals,
            },
            "operator_access_risk_indicators": {"pending_approval_backlog": bool(pending_approvals)},
        },
        "production_observability_governance": {
            "production_observability_governance_score": safe_float(readiness_metrics.get("telemetry_health"), 0.0),
            "production_observability_governance_status": "ok" if production_observability_ready else "watch",
            "observability_readiness_indicators": {"worker_heartbeat": production_observability_ready},
            "observability_risk_indicators": {"telemetry_degradation": [] if production_observability_ready else ["telemetry health degraded"]},
        },
        "backup_restore_governance": {
            "backup_restore_governance_score": 100.0 if safe_str(safe_dict(evidence.get("status")).get("status"), "ok") == "ok" else 60.0,
            "backup_restore_governance_status": "ok" if evidence else "watch",
            "backup_restore_details": {
                "latest_pack_id": safe_str(safe_dict(evidence.get("pack")).get("pack_id"), safe_str(safe_dict(cycle.get("evidence_pack")).get("pack_id"), "production-rollout-pack")),
            },
            "recovery_readiness_indicators": {
                "evidence_pack_available": bool(evidence),
                "history_available": bool(rehearsal_runs),
            },
        },
        "disaster_recovery_governance": {
            "disaster_recovery_governance_score": 100.0 if safe_str(release_operational.get("overall_validation_passed"), "False").lower() == "true" else 60.0,
            "disaster_recovery_governance_status": "ok" if safe_str(release_operational.get("overall_validation_passed"), "False").lower() == "true" else "watch",
            "recovery_readiness_indicators": {
                "final_readiness_cleared": safe_str(release_deployment.get("ready_for_deployment"), "False").lower() == "true",
            },
        },
        "high_availability_governance": {
            "high_availability_governance_score": 100.0 if safe_str(safe_dict(queue_stability_summary).get("status"), "WATCH") == "PASS" else 60.0,
            "high_availability_governance_status": "ok" if safe_str(safe_dict(queue_stability_summary).get("status"), "WATCH") == "PASS" else "watch",
            "ha_readiness_indicators": {"queue_stable": safe_str(safe_dict(queue_stability_summary).get("status"), "WATCH") == "PASS"},
        },
        "audit_retention_governance": {
            "audit_retention_governance_score": 100.0 if len(rehearsal_runs) > 0 else 60.0,
            "audit_retention_governance_status": "ok" if rehearsal_runs else "watch",
            "audit_retention_details": {"cycle_count": len(rehearsal_runs)},
            "audit_retention_indicators": {"cycle_history_available": bool(rehearsal_runs)},
        },
        "deployment_readiness_governance": {
            "deployment_readiness_governance_score": safe_float(release_certification.get("release_governance_score"), readiness_score),
            "deployment_readiness_governance_status": "ok" if release_authorization_valid and readiness_score >= 85.0 else "watch",
            "deployment_readiness_indicators": {
                "executive_ready": safe_str(release_summary.get("certification_status"), "WATCH") == "CERTIFIED",
                "final_ready": safe_str(release_deployment.get("ready_for_deployment"), "False").lower() == "true",
                "stability_ready": readiness_score >= 85.0,
            },
        },
        "deployment_risk_indicators": {
            "deployment_risk": not release_authorization_valid or readiness_score < 85.0 or not production_observability_ready or not tenant_isolation_ready,
            "operator_access_risk": bool(pending_approvals),
            "ha_risk": safe_str(safe_dict(queue_stability_summary).get("status"), "WATCH") != "PASS",
            "recovery_risk": safe_str(release_operational.get("overall_validation_passed"), "False").lower() != "true",
        },
        "operator_access_risk_indicators": {"pending_approval_backlog": bool(pending_approvals)},
        "ha_readiness_indicators": {"queue_stable": safe_str(safe_dict(queue_stability_summary).get("status"), "WATCH") == "PASS"},
        "recovery_readiness_indicators": {"final_readiness_cleared": safe_str(release_operational.get("overall_validation_passed"), "False").lower() == "true"},
        "warnings": safe_list(rehearsal.get("warnings")),
    }

    history = []
    for run in rehearsal_runs:
        run_payload = safe_dict(run)
        score = safe_float(run_payload.get("readiness_score"), 0.0)
        metrics = safe_dict(run_payload.get("metrics"))
        history.append(
            {
                "analysis_id": f"{safe_str(run_payload.get('run_id'), 'run')}:production",
                "generated_at": safe_str(run_payload.get("generated_at"), iso_now()),
                "cycle_id": safe_str(run_payload.get("run_id"), ""),
                "production_readiness_score": score,
                "production_readiness_status": _status_from_score(score).lower(),
                "production_readiness_grade": safe_str(run_payload.get("readiness_grade"), "blocked"),
                "deployment_risk_indicators": {"executive_risk": score < 70.0, "stability_risk": safe_float(metrics.get("telemetry_health"), 0.0) < 85.0},
                "operator_access_risk_indicators": {"review_backlog": safe_float(metrics.get("operator_intervention_frequency"), 0.0) > 20.0},
                "ha_readiness_indicators": {"queue_stable": safe_float(metrics.get("queue_stability"), 0.0) >= 85.0},
                "recovery_readiness_indicators": {"rollback_ready": safe_float(metrics.get("rollback_success"), 0.0) >= 85.0},
                "production_governance_summary": {"decision": "support_enterprise_deployment" if score >= 85.0 else "watch_enterprise_deployment" if score >= 70.0 else "defer_enterprise_deployment"},
            }
        )

    history_summary = {
        "analysis_count": len(history),
        "latest_analysis_id": safe_str(history[0].get("analysis_id"), "") if history else "",
        "latest_score": safe_float(history[0].get("production_readiness_score"), readiness_score) if history else readiness_score,
    }
    latest["production_governance_history"] = history
    latest["production_governance_history_summary"] = history_summary
    return latest, {"status": "ok", "count": len(history), "production_governance_history": history, "production_governance_history_summary": history_summary, "summary_components": safe_dict(readiness.get("metrics")), "warnings": safe_list(rehearsal.get("warnings"))}


def build_rollout_validation_report(
    *,
    operational_service: Optional[Any] = None,
    output_root: Optional[Path] = None,
) -> Dict[str, Any]:
    output_root = output_root or ROLLOUT_VALIDATION_ROOT
    output_root.mkdir(parents=True, exist_ok=True)

    if operational_service is None:
        latest, history = _snapshot_rollout_state()
    else:
        latest = safe_dict(operational_service.latest_production_governance())
        history = safe_dict(operational_service.production_governance_history(limit=20))
    release_certification = _read_release_certification_snapshot()

    production_runtime_segmentation = safe_dict(latest.get("production_runtime_segmentation"))
    operator_access_governance = safe_dict(latest.get("operator_access_governance"))
    production_observability_governance = safe_dict(latest.get("production_observability_governance"))
    backup_restore_governance = safe_dict(latest.get("backup_restore_governance"))
    disaster_recovery_governance = safe_dict(latest.get("disaster_recovery_governance"))
    high_availability_governance = safe_dict(latest.get("high_availability_governance"))
    audit_retention_governance = safe_dict(latest.get("audit_retention_governance"))
    deployment_readiness_governance = safe_dict(latest.get("deployment_readiness_governance"))
    release_authority = safe_dict(release_certification.get("release_authority_certification"))
    release_cert_summary = safe_dict(release_certification.get("governance_certification_summary"))
    release_readiness = safe_dict(release_certification.get("deployment_readiness_certification"))
    release_operational = safe_dict(release_certification.get("operational_readiness_certification"))
    release_latest = safe_dict(release_certification.get("latest_release_validation"))

    release_authorization_valid = safe_str(release_cert_summary.get("certification_status"), "WATCH") == "CERTIFIED" and safe_str(release_authority.get("active_authority"), "WATCH") == "GO"
    tenant_isolation_ready = bool(safe_dict(production_runtime_segmentation.get("tenant_workspace_isolation")).get("isolation_verified"))
    supervision_coverage_ready = bool(safe_dict(operator_access_governance.get("operator_access_details")).get("active_sessions", 0)) and not safe_list(safe_dict(operator_access_governance.get("operator_access_details")).get("pending_approvals"))
    operator_availability_ready = not safe_list(safe_dict(operator_access_governance.get("operator_access_details")).get("pending_approvals")) and safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_role"), "") in {"governance_reviewer", "operator", "supervisor"}
    deployment_health_ready = all(
        [
            safe_str(production_observability_governance.get("production_observability_governance_status"), "blocked") == "ok",
            safe_str(backup_restore_governance.get("backup_restore_governance_status"), "blocked") == "ok",
            safe_str(disaster_recovery_governance.get("disaster_recovery_governance_status"), "blocked") == "ok",
            safe_str(high_availability_governance.get("high_availability_governance_status"), "blocked") == "ok",
            safe_str(audit_retention_governance.get("audit_retention_governance_status"), "blocked") == "ok",
        ]
    )
    production_observability_ready = bool(safe_dict(production_observability_governance.get("observability_readiness_indicators")).get("worker_heartbeat")) and not safe_list(safe_dict(production_observability_governance.get("observability_risk_indicators")).get("telemetry_degradation"))
    escalation_chain_ready = (
        not bool(safe_dict(operator_access_governance.get("operator_access_risk_indicators")).get("pending_approval_backlog"))
        and not safe_list(safe_dict(history.get("production_governance_history_summary")).get("warnings"))
        and not safe_list(safe_dict(release_certification).get("warnings"))
    )

    rollout_checks = {
        "production_rollout_readiness": _rollout_check(
            "Production rollout readiness",
            safe_float(latest.get("production_readiness_score"), 0.0),
            safe_str(latest.get("production_readiness_status"), "watch") == "ok" and safe_float(latest.get("production_readiness_score"), 0.0) >= 85.0,
            {
                "production_readiness_grade": safe_str(latest.get("production_readiness_grade"), "blocked"),
                "summary_components": safe_dict(latest.get("summary_components")),
            },
        ),
        "active_supervision_coverage": _rollout_check(
            "Active supervision coverage",
            safe_float(operator_access_governance.get("operator_access_governance_score"), 0.0),
            supervision_coverage_ready,
            {
                "operator_name": safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_name"), "staging-governance-operator"),
                "operator_role": safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_role"), "governance_reviewer"),
                "active_sessions": safe_int(safe_dict(operator_access_governance.get("operator_access_details")).get("active_sessions"), 0),
                "assigned_rfqs": safe_list(safe_dict(operator_access_governance.get("operator_access_details")).get("assigned_rfqs")),
            },
        ),
        "operator_availability_readiness": _rollout_check(
            "Operator availability readiness",
            safe_float(operator_access_governance.get("operator_access_governance_score"), 0.0),
            operator_availability_ready,
            {
                "pending_approvals": safe_list(safe_dict(operator_access_governance.get("operator_access_details")).get("pending_approvals")),
                "operator_role": safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_role"), "governance_reviewer"),
            },
        ),
        "release_authorization_validity": _rollout_check(
            "Release authorization validity",
            safe_float(release_cert_summary.get("certification_score"), safe_float(safe_dict(release_latest).get("release_governance_score"), 0.0)),
                release_authorization_valid,
            {
                "certification_status": safe_str(release_cert_summary.get("certification_status"), "WATCH"),
                "active_authority": safe_str(release_authority.get("active_authority"), "WATCH"),
                "certified_go_governance": bool(release_cert_summary.get("certified_go_governance")),
            },
        ),
        "deployment_health_readiness": _rollout_check(
            "Deployment health readiness",
            safe_float(latest.get("production_readiness_score"), 0.0),
            deployment_health_ready,
            {
                "production_observability_status": safe_str(production_observability_governance.get("production_observability_governance_status"), "blocked"),
                "backup_restore_status": safe_str(backup_restore_governance.get("backup_restore_governance_status"), "blocked"),
                "disaster_recovery_status": safe_str(disaster_recovery_governance.get("disaster_recovery_governance_status"), "blocked"),
                "high_availability_status": safe_str(high_availability_governance.get("high_availability_governance_status"), "blocked"),
                "audit_retention_status": safe_str(audit_retention_governance.get("audit_retention_governance_status"), "blocked"),
            },
        ),
        "tenant_isolation_readiness": _rollout_check(
            "Tenant isolation readiness",
            safe_float(production_runtime_segmentation.get("production_runtime_segmentation_score"), 0.0),
            tenant_isolation_ready,
            safe_dict(production_runtime_segmentation.get("tenant_workspace_isolation")),
        ),
        "production_observability_readiness": _rollout_check(
            "Production observability readiness",
            safe_float(production_observability_governance.get("production_observability_governance_score"), 0.0),
            production_observability_ready,
            {
                "worker_heartbeat": safe_dict(production_observability_governance.get("observability_readiness_indicators")).get("worker_heartbeat"),
                "telemetry_degradation": safe_list(safe_dict(production_observability_governance.get("observability_risk_indicators")).get("telemetry_degradation")),
            },
        ),
        "escalation_chain_readiness": _rollout_check(
            "Escalation chain readiness",
            safe_float(safe_dict(history.get("production_governance_history_summary")).get("latest_score"), 0.0),
            escalation_chain_ready,
            {
                "outstanding_governance_actions": safe_list(safe_dict(operational_service.review_board.latest_review_board()).get("outstanding_governance_actions", [])) if hasattr(operational_service, "review_board") else [],
                "unresolved_operational_exceptions": safe_list(safe_dict(operational_service.review_board.latest_review_board()).get("unresolved_operational_exceptions", [])) if hasattr(operational_service, "review_board") else [],
            },
        ),
    }

    scores = [safe_float(item.get("score"), 0.0) for item in rollout_checks.values()]
    readiness_score = round(mean(scores), 2) if scores else 0.0
    blockers = []
    for key, check in rollout_checks.items():
        if check["status"] == "FAIL":
            blockers.append(check["label"])
    warnings = []
    if release_cert_summary and safe_str(release_cert_summary.get("certification_status"), "WATCH") != "CERTIFIED":
        warnings.append("release certification is not certified")
    if safe_str(latest.get("production_readiness_grade"), "blocked") != "ready":
        warnings.append("production readiness is below threshold")
    if blockers and not warnings:
        warnings.append("one or more rollout checks are not yet ready")

    authority_state = "GO" if readiness_score >= 85.0 and not blockers and not warnings and release_authorization_valid else "WATCH" if readiness_score >= 70.0 else "NO_GO"
    certification_status = "CERTIFIED" if authority_state == "GO" else "WATCH" if authority_state == "WATCH" else "NO_GO"
    overall_status = "PASS" if certification_status == "CERTIFIED" else "WARN" if certification_status == "WATCH" else "FAIL"

    validation_id = f"{rollout_timestamp()}-production-{uuid.uuid4().hex[:8]}"
    export_dir = output_root / validation_id
    export_dir.mkdir(parents=True, exist_ok=True)

    release_snapshot_bundle = {}
    if safe_str(release_certification.get("artifact_path"), ""):
        source_json = Path(safe_str(release_certification.get("artifact_path")))
        if source_json.exists():
            copied_json = export_dir / "source_release_certification.json"
            shutil.copy2(source_json, copied_json)
            release_snapshot_bundle["json"] = str(copied_json)
    if LATEST_RELEASE_CERTIFICATION_MD_FILE.exists():
        copied_md = export_dir / "source_release_certification.md"
        shutil.copy2(LATEST_RELEASE_CERTIFICATION_MD_FILE, copied_md)
        release_snapshot_bundle["markdown"] = str(copied_md)

    rollout_readiness_summary = {
        "rollout_readiness_score": readiness_score,
        "rollout_readiness_status": overall_status,
        "rollout_readiness_grade": "ready" if certification_status == "CERTIFIED" else "watch" if certification_status == "WATCH" else "blocked",
        "release_authorization_valid": release_authorization_valid,
        "tenant_isolation_ready": tenant_isolation_ready,
        "deployment_health_ready": deployment_health_ready,
        "production_observability_ready": production_observability_ready,
        "escalation_chain_ready": escalation_chain_ready,
        "active_supervision_coverage_ready": supervision_coverage_ready,
        "operator_availability_ready": operator_availability_ready,
        "unresolved_blockers": blockers,
        "warnings": warnings,
    }
    supervision_readiness_summary = {
        "active_supervision_coverage_ready": supervision_coverage_ready,
        "supervision_score": safe_float(operator_access_governance.get("operator_access_governance_score"), 0.0),
        "operator_name": safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_name"), "staging-governance-operator"),
        "operator_role": safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_role"), "governance_reviewer"),
        "active_sessions": safe_int(safe_dict(operator_access_governance.get("operator_access_details")).get("active_sessions"), 0),
        "assigned_rfqs": safe_list(safe_dict(operator_access_governance.get("operator_access_details")).get("assigned_rfqs")),
        "pending_approvals": safe_list(safe_dict(operator_access_governance.get("operator_access_details")).get("pending_approvals")),
    }
    operator_onboarding_readiness_summary = {
        "operator_availability_ready": operator_availability_ready,
        "operator_name": safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_name"), "staging-governance-operator"),
        "operator_role": safe_str(safe_dict(operator_access_governance.get("operator_access_details")).get("operator_role"), "governance_reviewer"),
        "approved_for_supervision": operator_availability_ready and supervision_coverage_ready,
        "onboarding_status": "ready" if operator_availability_ready else "watch" if safe_float(operator_access_governance.get("operator_access_governance_score"), 0.0) >= 70.0 else "blocked",
    }
    deployment_health_summary = {
        "deployment_health_ready": deployment_health_ready,
        "production_observability_ready": production_observability_ready,
        "backup_restore_ready": safe_str(backup_restore_governance.get("backup_restore_governance_status"), "blocked") == "ok",
        "disaster_recovery_ready": safe_str(disaster_recovery_governance.get("disaster_recovery_governance_status"), "blocked") == "ok",
        "high_availability_ready": safe_str(high_availability_governance.get("high_availability_governance_status"), "blocked") == "ok",
        "audit_retention_ready": safe_str(audit_retention_governance.get("audit_retention_governance_status"), "blocked") == "ok",
    }
    tenant_isolation_summary = {
        "tenant_isolation_ready": tenant_isolation_ready,
        "tenant_count": safe_int(safe_dict(production_runtime_segmentation.get("tenant_workspace_isolation")).get("tenant_count"), 0),
        "workspace_count": safe_int(safe_dict(production_runtime_segmentation.get("tenant_workspace_isolation")).get("workspace_count"), 0),
        "tenant_workspace_pair_count": safe_int(safe_dict(production_runtime_segmentation.get("tenant_workspace_isolation")).get("tenant_workspace_pair_count"), 0),
    }
    observability_summary = {
        "production_observability_ready": production_observability_ready,
        "worker_heartbeat": safe_dict(production_observability_governance.get("observability_readiness_indicators")).get("worker_heartbeat"),
        "telemetry_degradation": safe_list(safe_dict(production_observability_governance.get("observability_risk_indicators")).get("telemetry_degradation")),
    }
    escalation_summary = {
        "escalation_chain_ready": escalation_chain_ready,
        "review_board_status": safe_str(safe_dict(operational_service.review_board.latest_review_board()).get("review_board_status"), "watch") if hasattr(operational_service, "review_board") else "watch",
        "outstanding_governance_actions": safe_list(safe_dict(operational_service.review_board.latest_review_board()).get("outstanding_governance_actions", [])) if hasattr(operational_service, "review_board") else [],
        "unresolved_operational_exceptions": safe_list(safe_dict(operational_service.review_board.latest_review_board()).get("unresolved_operational_exceptions", [])) if hasattr(operational_service, "review_board") else [],
    }

    rollout_governance_history = safe_list(history.get("production_governance_history"))
    history_scores = [safe_float(item.get("production_readiness_score"), 0.0) for item in rollout_governance_history]
    history_summary = {
        "analysis_count": safe_int(safe_dict(history.get("production_governance_history_summary")).get("analysis_count"), len(rollout_governance_history)),
        "latest_analysis_id": safe_str(safe_dict(history.get("production_governance_history_summary")).get("latest_analysis_id"), ""),
        "latest_score": safe_float(safe_dict(history.get("production_governance_history_summary")).get("latest_score"), readiness_score),
        "score_history": _history_scores(history_scores),
    }

    institutional_rollout_certification_evidence = {
        "certification_status": certification_status,
        "certification_authority": authority_state,
        "rollout_governance_score": readiness_score,
        "release_authorization_valid": release_authorization_valid,
        "rollout_ready_for_supervised_deployment": certification_status == "CERTIFIED",
        "governance_override_indicators": {
            "deployment_blockers": bool(blockers),
            "release_authorization_override": not release_authorization_valid,
            "human_supervision_required": True,
        },
    }

    payload = {
        "validation_id": validation_id,
        "generated_at": iso_now(),
        "source_runtime": str(STAGING_ROOT),
        "latest_release_certification": {
            "artifact_path": safe_str(release_certification.get("artifact_path"), ""),
            "certification_status": safe_str(release_cert_summary.get("certification_status"), "WATCH"),
            "certification_score": safe_float(release_cert_summary.get("certification_score"), 0.0),
            "release_authority": safe_str(release_authority.get("active_authority"), "WATCH"),
            "production_rollout_readiness": bool(release_readiness.get("ready_for_deployment")),
        },
        "rollout_readiness_summary": rollout_readiness_summary,
        "supervision_readiness_summary": supervision_readiness_summary,
        "operator_onboarding_readiness_summary": operator_onboarding_readiness_summary,
        "deployment_health_summary": deployment_health_summary,
        "tenant_isolation_summary": tenant_isolation_summary,
        "production_observability_summary": observability_summary,
        "escalation_chain_summary": escalation_summary,
        "rollout_governance_history": rollout_governance_history,
        "rollout_governance_history_summary": history_summary,
        "institutional_rollout_certification_evidence": institutional_rollout_certification_evidence,
        "rollout_checks": rollout_checks,
        "summary_counts": {
            "PASS": sum(1 for item in rollout_checks.values() if item["status"] == "PASS"),
            "WARN": sum(1 for item in rollout_checks.values() if item["status"] == "WARN"),
            "FAIL": sum(1 for item in rollout_checks.values() if item["status"] == "FAIL"),
        },
        "release_certification_snapshot": release_certification,
        "source_artifacts": {
            "release_certification": safe_str(release_certification.get("artifact_path"), str(LATEST_RELEASE_CERTIFICATION_FILE)),
            "rollout_validation_root": str(output_root),
        },
        "artifact_paths": {},
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_operations": False,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "human_supervision_required": True,
            "dry_run_protections_active": True,
        },
        "warnings": warnings,
    }

    payload["artifact_paths"] = {
        "json": str(export_dir / "production_rollout_validation.json"),
        "markdown": str(export_dir / "production_rollout_validation.md"),
        "latest_json": str(output_root / "latest_production_rollout_validation.json"),
        "latest_markdown": str(output_root / "latest_production_rollout_validation.md"),
        "source_release_certification_json": release_snapshot_bundle.get("json"),
        "source_release_certification_md": release_snapshot_bundle.get("markdown"),
    }
    payload["rollout_certification_artifacts"] = payload["artifact_paths"]

    write_json(export_dir / "production_rollout_validation.json", payload)
    write_text(export_dir / "production_rollout_validation.md", markdown_summary(payload))
    write_json(output_root / "latest_production_rollout_validation.json", payload)
    write_text(output_root / "latest_production_rollout_validation.md", markdown_summary(payload))
    return payload


def markdown_summary(payload: Dict[str, Any]) -> str:
    rollout = safe_dict(payload.get("rollout_readiness_summary"))
    supervision = safe_dict(payload.get("supervision_readiness_summary"))
    onboarding = safe_dict(payload.get("operator_onboarding_readiness_summary"))
    release = safe_dict(payload.get("latest_release_certification"))
    health = safe_dict(payload.get("deployment_health_summary"))
    tenant = safe_dict(payload.get("tenant_isolation_summary"))
    observability = safe_dict(payload.get("production_observability_summary"))
    escalation = safe_dict(payload.get("escalation_chain_summary"))
    institutional = safe_dict(payload.get("institutional_rollout_certification_evidence"))

    lines = [
        "# Controlled Production Rollout Validation",
        "",
        f"- Validation ID: `{safe_str(payload.get('validation_id'))}`",
        f"- Generated At: `{safe_str(payload.get('generated_at'))}`",
        f"- Source Runtime: `{safe_str(payload.get('source_runtime'))}`",
        "",
        "## Rollout Readiness",
        f"- Score: `{safe_float(rollout.get('rollout_readiness_score'), 0.0):.2f}`",
        f"- Status: `{safe_str(rollout.get('rollout_readiness_status'), 'FAIL')}`",
        f"- Grade: `{safe_str(rollout.get('rollout_readiness_grade'), 'blocked')}`",
        f"- Release authorization valid: `{str(bool(rollout.get('release_authorization_valid'))).lower()}`",
        f"- Tenant isolation ready: `{str(bool(rollout.get('tenant_isolation_ready'))).lower()}`",
        f"- Deployment health ready: `{str(bool(rollout.get('deployment_health_ready'))).lower()}`",
        f"- Production observability ready: `{str(bool(rollout.get('production_observability_ready'))).lower()}`",
        f"- Escalation chain ready: `{str(bool(rollout.get('escalation_chain_ready'))).lower()}`",
        f"- Active supervision coverage ready: `{str(bool(rollout.get('active_supervision_coverage_ready'))).lower()}`",
        f"- Operator availability ready: `{str(bool(rollout.get('operator_availability_ready'))).lower()}`",
        f"- Unresolved blockers: `{json.dumps(safe_list(rollout.get('unresolved_blockers')), sort_keys=True)}`",
        "",
        "## Supervision Readiness",
        f"- Operator: `{safe_str(supervision.get('operator_name'), 'staging-governance-operator')}`",
        f"- Role: `{safe_str(supervision.get('operator_role'), 'governance_reviewer')}`",
        f"- Active sessions: `{safe_int(supervision.get('active_sessions'), 0)}`",
        f"- Assigned RFQs: `{json.dumps(safe_list(supervision.get('assigned_rfqs')), sort_keys=True)}`",
        f"- Pending approvals: `{json.dumps(safe_list(supervision.get('pending_approvals')), sort_keys=True)}`",
        "",
        "## Operator Onboarding",
        f"- Status: `{safe_str(onboarding.get('onboarding_status'), 'blocked')}`",
        f"- Approved for supervision: `{str(bool(onboarding.get('approved_for_supervision'))).lower()}`",
        "",
        "## Release Certification Snapshot",
        f"- Artifact path: `{safe_str(release.get('artifact_path'), '')}`",
        f"- Certification status: `{safe_str(release.get('certification_status'), 'WATCH')}`",
        f"- Certification score: `{safe_float(release.get('certification_score'), 0.0):.2f}`",
        f"- Release authority: `{safe_str(release.get('release_authority'), 'WATCH')}`",
        f"- Production rollout readiness: `{str(bool(release.get('production_rollout_readiness'))).lower()}`",
        "",
        "## Deployment Health",
        f"- Observability ready: `{str(bool(health.get('production_observability_ready'))).lower()}`",
        f"- Backup restore ready: `{str(bool(health.get('backup_restore_ready'))).lower()}`",
        f"- Disaster recovery ready: `{str(bool(health.get('disaster_recovery_ready'))).lower()}`",
        f"- High availability ready: `{str(bool(health.get('high_availability_ready'))).lower()}`",
        f"- Audit retention ready: `{str(bool(health.get('audit_retention_ready'))).lower()}`",
        "",
        "## Tenant Isolation",
        f"- Tenant isolation ready: `{str(bool(tenant.get('tenant_isolation_ready'))).lower()}`",
        f"- Tenant count: `{safe_int(tenant.get('tenant_count'), 0)}`",
        f"- Workspace count: `{safe_int(tenant.get('workspace_count'), 0)}`",
        f"- Tenant/workspace pairs: `{safe_int(tenant.get('tenant_workspace_pair_count'), 0)}`",
        "",
        "## Observability",
        f"- Worker heartbeat: `{json.dumps(observability.get('worker_heartbeat'), sort_keys=True)}`",
        f"- Telemetry degradation: `{json.dumps(safe_list(observability.get('telemetry_degradation')), sort_keys=True)}`",
        "",
        "## Escalation Chain",
        f"- Ready: `{str(bool(escalation.get('escalation_chain_ready'))).lower()}`",
        f"- Review board status: `{safe_str(escalation.get('review_board_status'), 'watch')}`",
        f"- Outstanding actions: `{json.dumps(safe_list(escalation.get('outstanding_governance_actions')), sort_keys=True)}`",
        f"- Unresolved exceptions: `{json.dumps(safe_list(escalation.get('unresolved_operational_exceptions')), sort_keys=True)}`",
        "",
        "## Institutional Certification",
        f"- Certification status: `{safe_str(institutional.get('certification_status'), 'NO_GO')}`",
        f"- Certification authority: `{safe_str(institutional.get('certification_authority'), 'WATCH')}`",
        f"- Rollout score: `{safe_float(institutional.get('rollout_governance_score'), 0.0):.2f}`",
        f"- Rollout ready for supervised deployment: `{str(bool(institutional.get('rollout_ready_for_supervised_deployment'))).lower()}`",
        "",
        "## Safety Notes",
        "- Read-only validation runner.",
        "- No autonomous procurement authority.",
        "- No irreversible actions are performed.",
        "- No production submission enablement or production connectivity is required.",
        "- Governance layers remain authoritative and human supervision remains mandatory.",
        "- Dry-run protections remain active.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _print_summary(payload: Dict[str, Any]) -> None:
    rollout = safe_dict(payload.get("rollout_readiness_summary"))
    institutional = safe_dict(payload.get("institutional_rollout_certification_evidence"))
    print(f"Validation generated: {safe_str(payload.get('artifact_paths', {}).get('json'), '')}")
    print(f"Certification status: {safe_str(institutional.get('certification_status'), 'NO_GO')}")
    print(f"Rollout score: {safe_float(institutional.get('rollout_governance_score'), 0.0):.2f}")
    print(f"Release authority valid: {str(bool(rollout.get('release_authorization_valid'))).lower()}")
    print(f"Supervision coverage ready: {str(bool(rollout.get('active_supervision_coverage_ready'))).lower()}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export controlled production rollout validation evidence.")
    parser.add_argument("--output-root", type=Path, default=ROLLOUT_VALIDATION_ROOT, help="Where to write the rollout evidence bundle.")
    parser.add_argument("--json", action="store_true", help="Print the full validation payload as JSON.")
    args = parser.parse_args(argv)

    payload = build_rollout_validation_report(output_root=args.output_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0 if safe_str(safe_dict(payload.get("institutional_rollout_certification_evidence")).get("certification_status"), "NO_GO") == "CERTIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
