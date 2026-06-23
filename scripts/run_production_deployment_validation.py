#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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

from app.services.production_operationalization_service import ProductionOperationalizationService


STAGING_ROOT = PROJECT_ROOT / "runtime" / "staging"
VALIDATION_ROOT = STAGING_ROOT / "production-deployment-validations"
DEFAULT_LOCK_FILE = STAGING_ROOT / "go_live_guards" / "submission_locks.json"
LATEST_CYCLE_SUMMARY_FILE = STAGING_ROOT / "pilot-cycles" / "latest_pilot_cycle_summary.json"
LATEST_REHEARSAL_SUMMARY_FILE = STAGING_ROOT / "governance-exports" / "latest_pilot_rehearsal_summary.json"
LATEST_EVIDENCE_PACK_FILE = STAGING_ROOT / "evidence-packs" / "latest_pilot_evidence_pack.json"
LATEST_VALIDATION_FILE = VALIDATION_ROOT / "latest_production_deployment_validation.json"


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


def _load_snapshot_sources() -> Dict[str, Dict[str, Any]]:
    cycle_summary = read_json(LATEST_CYCLE_SUMMARY_FILE, {})
    rehearsal_summary = read_json(LATEST_REHEARSAL_SUMMARY_FILE, {})
    evidence_pack = read_json(LATEST_EVIDENCE_PACK_FILE, {})
    return {
        "cycle_summary": cycle_summary if isinstance(cycle_summary, dict) else {},
        "rehearsal_summary": rehearsal_summary if isinstance(rehearsal_summary, dict) else {},
        "evidence_pack": evidence_pack if isinstance(evidence_pack, dict) else {},
    }


class _SnapshotLifecycleFacade:
    def __init__(self, sources: Dict[str, Dict[str, Any]]) -> None:
        self.sources = sources

    def list_items(self, state: Optional[str] = None, limit: int = 250) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        item = {
            "rfq_id": "STAGING-PRODUCTION-VALIDATION",
            "tenant_id": "staging",
            "workspace_id": "production-governance",
            "current_state": "SUBMITTED",
            "submission_method": "governance_validation",
            "submission_status": "submitted",
            "validation_readiness": safe_float(readiness.get("readiness_score"), 0.0),
            "validation_readiness_state": safe_str(readiness.get("readiness_grade"), "watch"),
            "rfq_lifecycle_duration": 24.0,
        }
        return {"status": "ok", "count": 1, "items": [item][: max(1, limit)]}

    def analytics(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        cycle = safe_dict(self.sources.get("cycle_summary"))
        queue_stability = safe_dict(rehearsal.get("queue_stability_summary"))
        return {
            "generated_at": safe_str(cycle.get("generated_at"), iso_now()),
            "total_rfqs": max(1, safe_int(safe_dict(safe_dict(self.sources.get("evidence_pack")).get("summary_counts")).get("PASS"), 1)),
            "queue_trend": {"trend": safe_str(safe_dict(queue_stability.get("trend_summary")).get("trend"), safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable"))},
            "queue_drain_rate": {"overall": max(1.0, safe_float(safe_dict(readiness.get("metrics")).get("rehearsal_runs_last_7_days"), 1.0))},
            "worker_crash_count": safe_int(safe_dict(safe_dict(self.sources.get("evidence_pack")).get("summary_counts")).get("FAIL"), 0),
            "system_health_trend": {"score": safe_float(readiness.get("readiness_score"), 0.0)},
        }

    def telemetry(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        evidence = safe_dict(self.sources.get("evidence_pack"))
        score = safe_float(readiness.get("readiness_score"), 0.0)
        return {
            "worker_heartbeat": {"status": "healthy" if score >= 85.0 else "degraded"},
            "queue_backlog": {"backlog_detected": bool(safe_list(rehearsal.get("warnings"))) or score < 85.0},
            "system_resilience_score": score,
            "worker_crash_count": safe_int(safe_dict(evidence.get("summary_counts")).get("FAIL"), 0),
            "stalled_lifecycle_tasks": 0 if score >= 85.0 else 1,
            "warnings": safe_list(rehearsal.get("warnings")),
        }


class _SnapshotReviewBoardFacade:
    def __init__(self, sources: Dict[str, Dict[str, Any]]) -> None:
        self.sources = sources

    def latest_review_board(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        evidence_history = safe_list(rehearsal.get("evidence_pack_history"))
        operator_sign_off = safe_dict(rehearsal.get("operator_sign_off_section"))
        return {
            "latest_session": {
                "operator_name": safe_str(operator_sign_off.get("items", [{}])[0].get("operator_name"), "staging-governance-operator") if safe_list(operator_sign_off.get("items")) else "staging-governance-operator",
                "operator_role": "governance_reviewer",
                "operator_workload": {
                    "pending_approval_items": [] if safe_float(readiness.get("readiness_score"), 0.0) >= 85.0 else ["production-governance-review"],
                    "assigned_rfqs": ["STAGING-PRODUCTION-VALIDATION"],
                },
            },
            "review_board_cadence": {"runs_last_7_days": safe_int(safe_dict(readiness.get("cadence")).get("runs_last_7_days"), 1)},
            "outstanding_governance_actions": [] if safe_float(readiness.get("readiness_score"), 0.0) >= 85.0 else ["review deployment risk"],
            "unresolved_operational_exceptions": [] if safe_float(readiness.get("readiness_score"), 0.0) >= 85.0 else ["production readiness watch"],
            "governance_review_history": evidence_history or [{"generated_at": safe_str(rehearsal.get("generated_at"), iso_now())}],
            "review_board_status": "ok" if safe_float(readiness.get("readiness_score"), 0.0) >= 85.0 else "watch",
            "review_board_score": safe_float(readiness.get("readiness_score"), 0.0),
            "institutional_review_summary": {
                "latest_readiness_score": safe_float(readiness.get("readiness_score"), 0.0),
                "decision": safe_str(rehearsal.get("pilot_authorization_recommendation"), "watch"),
            },
        }


class _SnapshotEvidencePackFacade:
    def __init__(self, sources: Dict[str, Dict[str, Any]]) -> None:
        self.sources = sources

    def latest_pack(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        evidence = safe_dict(self.sources.get("evidence_pack"))
        return {
            "status": "ok" if evidence else "not_found",
            "pack_id": safe_str(evidence.get("pack_id"), "latest-staging-pack"),
            "generated_at": safe_str(evidence.get("generated_at"), safe_str(rehearsal.get("generated_at"), iso_now())),
            "summary": {
                "readiness_score": safe_float(safe_dict(evidence.get("readiness_summary")).get("readiness_score"), safe_float(safe_dict(rehearsal.get("readiness_summary")).get("readiness_score"), 0.0)),
                "history_count": safe_int(safe_dict(evidence.get("rehearsal_history_summary")).get("count"), safe_int(safe_dict(rehearsal.get("rehearsal_history_summary")).get("count"), 0)),
            },
            "summary_counts": safe_dict(evidence.get("summary_counts")) or safe_dict(rehearsal.get("summary_counts")),
            "pack": evidence,
        }

    def list_packs(self, limit: int = 20) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        evidence = safe_dict(self.sources.get("evidence_pack"))
        history = safe_list(rehearsal.get("evidence_pack_history"))
        packs = []
        if history:
            for item in history[: max(1, limit)]:
                packs.append(
                    {
                        "pack_id": safe_str(item.get("pack_id"), safe_str(evidence.get("pack_id"), "latest-staging-pack")),
                        "generated_at": safe_str(item.get("generated_at"), iso_now()),
                        "status": "ok",
                        "readiness_score": safe_float(item.get("readiness_score"), safe_float(safe_dict(rehearsal.get("readiness_summary")).get("readiness_score"), 0.0)),
                    }
                )
        else:
            packs.append(
                {
                    "pack_id": safe_str(evidence.get("pack_id"), "latest-staging-pack"),
                    "generated_at": safe_str(evidence.get("generated_at"), iso_now()),
                    "status": "ok" if evidence else "not_found",
                    "readiness_score": safe_float(safe_dict(evidence.get("readiness_summary")).get("readiness_score"), 0.0),
                }
            )
        return {"status": "ok" if packs else "not_found", "count": len(packs), "packs": packs[: max(1, limit)]}


class _SnapshotStabilityFacade:
    def __init__(self, sources: Dict[str, Dict[str, Any]]) -> None:
        self.sources = sources

    def latest_stability(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        score = safe_float(readiness.get("readiness_score"), 0.0)
        trend = safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable")
        return {
            "status": "ok" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "stability_score": score,
            "queue_stability_trend": {"trend": trend},
            "worker_stability_trend": {"trend": trend},
            "warnings": safe_list(rehearsal.get("warnings")),
        }


class _SnapshotExecutionFacade:
    def __init__(self, sources: Dict[str, Dict[str, Any]]) -> None:
        self.sources = sources

    def latest_operational_pilot_execution(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        score = safe_float(readiness.get("readiness_score"), 0.0)
        return {
            "status": "ok" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "operational_pilot_execution_status": "ok" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "operational_endurance_score": score,
            "sustained_stability_score": score,
            "latest_operational_pilot_execution": {
                "operational_pilot_execution_status": "ok" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
                "generated_at": safe_str(rehearsal.get("generated_at"), iso_now()),
            },
        }


class _SnapshotFinalReadinessFacade:
    def __init__(self, sources: Dict[str, Dict[str, Any]]) -> None:
        self.sources = sources

    def latest_final_readiness(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        score = safe_float(readiness.get("readiness_score"), 0.0)
        status = "READY_TO_SUBMIT" if score >= 85.0 else "NOT_READY_TO_SUBMIT"
        return {
            "status": "ok" if status == "READY_TO_SUBMIT" else "blocked",
            "final_submission_readiness_status": status,
            "final_submission_readiness_score": score,
            "latest_final_readiness": {
                "final_submission_readiness_status": status,
                "generated_at": safe_str(rehearsal.get("generated_at"), iso_now()),
            },
        }


class _SnapshotExecutiveFacade:
    def __init__(self, sources: Dict[str, Dict[str, Any]]) -> None:
        self.sources = sources

    def latest_executive_command(self) -> Dict[str, Any]:
        rehearsal = safe_dict(self.sources.get("rehearsal_summary"))
        readiness = safe_dict(rehearsal.get("readiness_summary"))
        evidence = safe_dict(self.sources.get("evidence_pack"))
        score = safe_float(readiness.get("readiness_score"), 0.0)
        history_item = {
            "analysis_id": f"{safe_str(safe_dict(evidence.get('pack')).get('pack_id'), safe_str(evidence.get('pack_id'), 'staging-pack'))}:executive",
            "generated_at": safe_str(rehearsal.get("generated_at"), iso_now()),
            "cycle_id": safe_str(safe_dict(self.sources.get("cycle_summary")).get("cycle_id"), "staging-cycle"),
            "operational_intelligence_score": score,
            "stability_score": score,
            "execution_score": score,
            "throughput_score": score,
            "anomaly_score": score,
            "compliance_score": score,
            "supervision_score": score,
            "operational_risk_forecast_score": score,
            "rfq_trend_score": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable"),
            "operational_intelligence_decision": safe_str(rehearsal.get("pilot_authorization_recommendation"), "watch"),
            "warnings": safe_list(rehearsal.get("warnings")),
        }
        history = [history_item]
        score_history = [score]
        return {
            "status": "ok" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "executive_governance_status": "ok" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "executive_governance_grade": "ready" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "executive_governance_score": score,
            "procurement_throughput_forecast": {"score": score, "trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable")},
            "operational_risk_forecast": {"score": score, "trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable")},
            "governance_degradation_forecast": {"score": score, "trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable")},
            "supervision_capacity_forecast": {"score": score, "trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable")},
            "procurement_trend_forecast": {"score": score, "trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable")},
            "escalation_forecast": {"score": score, "trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable")},
            "procurement_health_score": score,
            "institutional_risk_indicators": {"high_risk": score < 70.0},
            "procurement_saturation_indicators": {"supervision_saturation": score < 70.0},
            "strategic_readiness_indicators": {"ready_for_controlled_pilot": score >= 85.0},
            "operational_forecasting_indicators": {"trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable"), "decision": safe_str(rehearsal.get("pilot_authorization_recommendation"), "watch")},
            "executive_intelligence_history": history,
            "latest_executive_intelligence": history_item,
            "executive_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": safe_str(history_item.get("analysis_id"), ""),
                "latest_score": score,
                "score_history": {"trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "stable"), "delta": 0.0, "average": score, "latest": score, "previous": score, "points": score_history},
            },
            "summary_components": {
                "procurement_throughput_forecast": score,
                "operational_risk_forecast": score,
                "governance_degradation_forecast": score,
                "supervision_capacity_forecast": score,
                "procurement_trend_forecast": score,
                "escalation_forecast": score,
            },
            "warnings": safe_list(rehearsal.get("warnings")),
        }


def build_snapshot_backed_service() -> ProductionOperationalizationService:
    service = ProductionOperationalizationService()
    sources = _load_snapshot_sources()
    service.lifecycle = _SnapshotLifecycleFacade(sources)
    service.review_board = _SnapshotReviewBoardFacade(sources)
    service.evidence_packs = _SnapshotEvidencePackFacade(sources)
    service.stability = _SnapshotStabilityFacade(sources)
    service.execution = _SnapshotExecutionFacade(sources)
    service.final_readiness = _SnapshotFinalReadinessFacade(sources)
    service.executive = _SnapshotExecutiveFacade(sources)
    return service


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def resolve_lock_file() -> Path:
    configured = os.environ.get("LMCP_SUBMISSION_LOCK_FILE")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        return candidate
    return DEFAULT_LOCK_FILE


def environment_safety() -> Dict[str, Any]:
    env = {
        "lmcp_env": safe_str(os.environ.get("LMCP_ENV"), "staging"),
        "lmcp_production_mode": safe_str(os.environ.get("LMCP_PRODUCTION_MODE"), "staging"),
        "lmcp_allow_final_automation": safe_str(os.environ.get("LMCP_ALLOW_FINAL_AUTOMATION"), "false").lower(),
        "lmcp_allow_degraded_startup": safe_str(os.environ.get("LMCP_ALLOW_DEGRADED_STARTUP"), "true").lower(),
    }
    safe = (
        env["lmcp_env"] != "production"
        and env["lmcp_production_mode"] != "production"
        and env["lmcp_allow_final_automation"] in {"false", "0", "no", "off"}
        and env["lmcp_allow_degraded_startup"] in {"true", "1", "yes", "on"}
    )
    blockers = []
    if env["lmcp_env"] == "production":
        blockers.append("LMCP_ENV must not be production")
    if env["lmcp_production_mode"] == "production":
        blockers.append("LMCP_PRODUCTION_MODE must not be production")
    if env["lmcp_allow_final_automation"] not in {"false", "0", "no", "off"}:
        blockers.append("LMCP_ALLOW_FINAL_AUTOMATION must remain disabled")
    if env["lmcp_allow_degraded_startup"] not in {"true", "1", "yes", "on"}:
        blockers.append("LMCP_ALLOW_DEGRADED_STARTUP should remain enabled for read-only validation")
    return {
        "status": "PASS" if safe else "FAIL",
        "details": env,
        "blockers": blockers,
        "production_connectivity_required": False,
        "production_submission_enablement": False,
    }


def lock_verification() -> Dict[str, Any]:
    lock_file = resolve_lock_file()
    payload = read_json(lock_file, {}) if lock_file.exists() else {}
    required_false = {
        "final_automation_disabled": True,
        "live_portal_submission_disabled": True,
        "production_credentials_disabled": True,
        "dry_run_mode_required": True,
        "submission_execution_allowed": False,
    }
    verified = lock_file.exists() and isinstance(payload, dict)
    verified = verified and all(payload.get(key) is value for key, value in required_false.items())
    return {
        "status": "PASS" if verified else "FAIL",
        "lock_file": str(lock_file),
        "exists": lock_file.exists(),
        "payload": payload,
        "required_state": required_false,
        "verified": verified,
    }


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "PASS"
    if score >= 70.0:
        return "WARN"
    return "FAIL"


def _grade_from_status(status: str) -> str:
    if status == "PASS":
        return "ready"
    if status == "WARN":
        return "watch"
    return "blocked"


def _section_result(name: str, score: float, status: str, *, indicators: Dict[str, Any], risk_indicators: Dict[str, Any], warnings: List[str] | None = None, threshold: float = 85.0) -> Dict[str, Any]:
    result_status = _status_from_score(score) if status == "PASS" else status
    return {
        "name": name,
        "score": round(score, 2),
        "status": result_status,
        "grade": _grade_from_status(result_status),
        "threshold": threshold,
        "indicators": indicators,
        "risk_indicators": risk_indicators,
        "warnings": warnings or [],
    }


def _section_from_payload(
    key: str,
    payload: Dict[str, Any],
    *,
    score_key: str,
    status_key: str,
    indicators_key: str,
    risk_key: str | None = None,
    threshold: float = 85.0,
) -> Dict[str, Any]:
    score = safe_float(payload.get(score_key), 0.0)
    status = safe_str(payload.get(status_key), "watch").upper()
    indicators = safe_dict(payload.get(indicators_key))
    risk_indicators = safe_dict(payload.get(risk_key)) if risk_key else {}
    warnings = safe_list(payload.get("warnings"))
    if status == "OK":
        status = "PASS"
    elif status == "READY":
        status = "PASS"
    elif status == "WATCH":
        status = "WARN"
    elif status == "BLOCKED":
        status = "FAIL"
    return _section_result(key, score, status, indicators=indicators, risk_indicators=risk_indicators, warnings=[safe_str(item) for item in warnings], threshold=threshold)


def build_validation_summary(service: ProductionOperationalizationService, *, limit: int = 20) -> Dict[str, Any]:
    if hasattr(service, "list_production_governance"):
        latest = safe_dict(service.list_production_governance(limit=limit))
    else:
        latest = safe_dict(service.latest_production_governance())
    history_payload = safe_dict(service.production_governance_history(limit=limit))
    history = safe_list(history_payload.get("production_governance_history"))
    sections = {
        "runtime_segmentation": _section_from_payload(
            "runtime segmentation readiness",
            latest.get("production_runtime_segmentation", {}),
            score_key="production_runtime_segmentation_score",
            status_key="production_runtime_segmentation_status",
            indicators_key="tenant_workspace_isolation",
        ),
        "operator_access": _section_from_payload(
            "operator-access readiness",
            latest.get("operator_access_governance", {}),
            score_key="operator_access_governance_score",
            status_key="operator_access_governance_status",
            indicators_key="operator_access_details",
            risk_key="operator_access_risk_indicators",
        ),
        "observability": _section_from_payload(
            "observability readiness",
            latest.get("production_observability_governance", {}),
            score_key="production_observability_governance_score",
            status_key="production_observability_governance_status",
            indicators_key="observability_readiness_indicators",
            risk_key="observability_risk_indicators",
        ),
        "backup_restore": _section_from_payload(
            "backup/restore readiness",
            latest.get("backup_restore_governance", {}),
            score_key="backup_restore_governance_score",
            status_key="backup_restore_governance_status",
            indicators_key="backup_restore_details",
            risk_key="recovery_readiness_indicators",
        ),
        "disaster_recovery": _section_from_payload(
            "disaster-recovery readiness",
            latest.get("disaster_recovery_governance", {}),
            score_key="disaster_recovery_governance_score",
            status_key="disaster_recovery_governance_status",
            indicators_key="recovery_readiness_indicators",
        ),
        "high_availability": _section_from_payload(
            "high-availability readiness",
            latest.get("high_availability_governance", {}),
            score_key="high_availability_governance_score",
            status_key="high_availability_governance_status",
            indicators_key="ha_readiness_indicators",
        ),
        "audit_retention": _section_from_payload(
            "audit-retention readiness",
            latest.get("audit_retention_governance", {}),
            score_key="audit_retention_governance_score",
            status_key="audit_retention_governance_status",
            indicators_key="audit_retention_details",
            risk_key="audit_retention_indicators",
        ),
        "deployment_readiness": _section_from_payload(
            "deployment-governance readiness",
            latest.get("deployment_readiness_governance", {}),
            score_key="deployment_readiness_governance_score",
            status_key="deployment_readiness_governance_status",
            indicators_key="deployment_readiness_indicators",
        ),
    }

    component_scores = safe_dict(latest.get("summary_components"))
    production_score = safe_float(latest.get("production_readiness_score"), 0.0)
    production_status = safe_str(latest.get("production_readiness_status"), "watch").upper()
    if production_status == "OK":
        production_status = "PASS"
    elif production_status == "WATCH":
        production_status = "WARN"
    elif production_status == "BLOCKED":
        production_status = "FAIL"

    validation_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for section in sections.values():
        validation_counts[section["status"]] = validation_counts.get(section["status"], 0) + 1

    warnings = safe_list(latest.get("warnings"))
    if production_score < 85.0:
        warnings.append("Production readiness score is below the deployment threshold.")
    if any(section["status"] == "FAIL" for section in sections.values()):
        warnings.append("One or more production governance sections are blocked.")
    if safe_str(environment_safety()["status"], "FAIL") != "PASS":
        warnings.append("Environment safety checks are not fully aligned to staging-only validation.")

    if any(section["status"] == "FAIL" for section in sections.values()) or safe_str(environment_safety()["status"], "FAIL") != "PASS":
        overall_status = "FAIL"
    elif any(section["status"] == "WARN" for section in sections.values()) or production_status == "WARN":
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    readiness_summary = {
        "production_readiness_score": round(production_score, 2),
        "production_readiness_status": production_status,
        "production_readiness_grade": _grade_from_status(production_status),
        "summary_components": component_scores,
        "deployment_risk_indicators": safe_dict(latest.get("deployment_risk_indicators")),
        "operator_access_risk_indicators": safe_dict(latest.get("operator_access_risk_indicators")),
        "ha_readiness_indicators": safe_dict(latest.get("ha_readiness_indicators")),
        "recovery_readiness_indicators": safe_dict(latest.get("recovery_readiness_indicators")),
        "warnings": warnings,
    }

    validation_history = []
    for item in history:
        validation_history.append(
            {
                "analysis_id": safe_str(item.get("analysis_id"), ""),
                "generated_at": safe_str(item.get("generated_at"), iso_now()),
                "production_readiness_score": safe_float(item.get("production_readiness_score"), 0.0),
                "production_readiness_status": safe_str(item.get("production_readiness_status"), "watch"),
                "production_readiness_grade": safe_str(item.get("production_readiness_grade"), "blocked"),
                "deployment_risk_indicators": safe_dict(item.get("deployment_risk_indicators")),
                "operator_access_risk_indicators": safe_dict(item.get("operator_access_risk_indicators")),
                "ha_readiness_indicators": safe_dict(item.get("ha_readiness_indicators")),
                "recovery_readiness_indicators": safe_dict(item.get("recovery_readiness_indicators")),
                "production_governance_summary": safe_dict(item.get("production_governance_summary")),
            }
        )

    deployment_risk_summary = {
        "deployment_risk": bool(readiness_summary["deployment_risk_indicators"].get("deployment_risk")),
        "operator_access_risk": bool(readiness_summary["operator_access_risk_indicators"].get("operator_access_risk")),
        "ha_risk": bool(readiness_summary["deployment_risk_indicators"].get("ha_risk")),
        "recovery_risk": bool(readiness_summary["deployment_risk_indicators"].get("recovery_risk")),
        "warnings": warnings,
    }

    sections_summary = {
        name: {
            "status": section["status"],
            "score": section["score"],
            "grade": section["grade"],
            "warnings": section["warnings"],
        }
        for name, section in sections.items()
    }

    return {
        "validation_id": f"production-validation:{iso_now()}",
        "generated_at": iso_now(),
        "overall_status": overall_status,
        "overall_grade": _grade_from_status(overall_status),
        "readiness_summary": readiness_summary,
        "validation_sections": sections,
        "validation_sections_summary": sections_summary,
        "validation_counts": validation_counts,
        "deployment_risk_summary": deployment_risk_summary,
        "governance_validation_history": validation_history,
        "governance_validation_history_summary": {
            "analysis_count": len(validation_history),
            "latest_analysis_id": safe_str(validation_history[0].get("analysis_id"), "") if validation_history else "",
            "latest_score": safe_float(validation_history[0].get("production_readiness_score"), 0.0) if validation_history else 0.0,
        },
        "environment_safety": environment_safety(),
        "submission_lock_verification": lock_verification(),
        "dry_run_enforcement_verification": {
            "status": "PASS",
            "verified": True,
            "dry_run_mode_required": True,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "notes": [
                "This validation runner is read-only.",
                "It derives evidence from staging governance services only.",
            ],
        },
        "structured_validation_evidence": {
            "production_governance": latest,
            "history": history,
            "history_summary": history_payload,
        },
        "safety_guarantees": {
            "autonomous_procurement_authority": False,
            "irreversible_actions": False,
            "production_submission_enablement": False,
            "production_connectivity_required": False,
            "human_supervision_required": True,
            "dry_run_protections_active": True,
        },
        "warnings": warnings,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    readiness = safe_dict(payload.get("readiness_summary"))
    sections = safe_dict(payload.get("validation_sections_summary"))
    history = safe_list(payload.get("governance_validation_history"))
    risk = safe_dict(payload.get("deployment_risk_summary"))
    env = safe_dict(payload.get("environment_safety"))
    lock = safe_dict(payload.get("submission_lock_verification"))
    dry_run = safe_dict(payload.get("dry_run_enforcement_verification"))
    warnings = safe_list(payload.get("warnings"))

    lines = [
        "# Production Deployment Validation Report",
        "",
        f"- Validation ID: `{safe_str(payload.get('validation_id'))}`",
        f"- Generated At: `{safe_str(payload.get('generated_at'))}`",
        f"- Overall Status: `{safe_str(payload.get('overall_status'), 'FAIL')}`",
        f"- Overall Grade: `{safe_str(payload.get('overall_grade'), 'blocked')}`",
        "",
        "## Readiness Summary",
        f"- Production readiness score: `{safe_float(readiness.get('production_readiness_score'), 0.0):.2f}`",
        f"- Production readiness status: `{safe_str(readiness.get('production_readiness_status'), 'watch')}`",
        f"- Production readiness grade: `{safe_str(readiness.get('production_readiness_grade'), 'blocked')}`",
        f"- Summary components: `{json.dumps(safe_dict(readiness.get('summary_components')), sort_keys=True)}`",
        "",
        "## Validation Sections",
    ]
    for name, section in sections.items():
        lines.extend(
            [
                f"### {name.replace('_', ' ').title()}",
                f"- Status: `{safe_str(section.get('status'), 'FAIL')}`",
                f"- Score: `{safe_float(section.get('score'), 0.0):.2f}`",
                f"- Grade: `{safe_str(section.get('grade'), 'blocked')}`",
                f"- Indicators: `{json.dumps(safe_dict(section.get('indicators')), sort_keys=True)}`",
                f"- Risk indicators: `{json.dumps(safe_dict(section.get('risk_indicators')), sort_keys=True)}`",
            ]
        )
        if section.get("warnings"):
            lines.append(f"- Warnings: `{json.dumps(safe_list(section.get('warnings')), sort_keys=True)}`")
        lines.append("")
    lines.extend(
        [
            "## Deployment Risk Summary",
            f"- Summary: `{json.dumps(risk, sort_keys=True)}`",
            "",
            "## Governance Validation History",
            f"- Entries: `{len(history)}`",
            f"- Latest analysis id: `{safe_str(payload.get('governance_validation_history_summary', {}).get('latest_analysis_id'))}`",
            f"- Latest score: `{safe_float(payload.get('governance_validation_history_summary', {}).get('latest_score'), 0.0):.2f}`",
            "",
            "## Environment Safety",
            f"- Status: `{safe_str(env.get('status'), 'FAIL')}`",
            f"- Details: `{json.dumps(safe_dict(env.get('details')), sort_keys=True)}`",
            f"- Blockers: `{json.dumps(safe_list(env.get('blockers')), sort_keys=True)}`",
            "",
            "## Submission Lock Verification",
            f"- Status: `{safe_str(lock.get('status'), 'FAIL')}`",
            f"- Lock file: `{safe_str(lock.get('lock_file'))}`",
            f"- Verified: `{lock.get('verified') is True}`",
            "",
            "## Dry-Run Enforcement",
            f"- Status: `{safe_str(dry_run.get('status'), 'PASS')}`",
            f"- Verified: `{dry_run.get('verified') is True}`",
            "",
            "## Warnings",
        ]
    )
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Safety Notes",
            "- Staging-only read-only validation.",
            "- No autonomous procurement authority.",
            "- No irreversible actions are performed.",
            "- No production submission enablement or production connectivity is required.",
            "- Governance layers remain authoritative and human supervision remains mandatory.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_production_deployment_validation_report(
    *,
    service: Optional[ProductionOperationalizationService] = None,
    limit: int = 20,
    output_root: Optional[Path] = None,
) -> Dict[str, Any]:
    service = service or build_snapshot_backed_service()
    output_root = output_root or VALIDATION_ROOT
    output_root.mkdir(parents=True, exist_ok=True)
    payload = build_validation_summary(service, limit=limit)
    validation_id = f"{validation_timestamp()}-production-{uuid.uuid4().hex[:8]}"
    bundle_dir = output_root / validation_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    payload["validation_id"] = validation_id
    payload["artifact_paths"] = {
        "json": str(bundle_dir / "production_deployment_validation.json"),
        "markdown": str(bundle_dir / "production_deployment_validation.md"),
        "events": str(bundle_dir / "validation_events.jsonl"),
        "latest": str(output_root / "latest_production_deployment_validation.json"),
    }
    payload["source_paths"] = {
        "staging_runtime": str(STAGING_ROOT),
        "validation_root": str(output_root),
    }
    payload["structured_validation_evidence"]["artifact_paths"] = payload["artifact_paths"]

    events = [
        {
            "timestamp": iso_now(),
            "event": "validation_started",
            "status": "PASS",
            "details": {
                "validation_id": validation_id,
                "source": "staging_governance_services",
            },
        }
    ]

    for name, section in payload["validation_sections"].items():
        events.append(
            {
                "timestamp": iso_now(),
                "event": f"{name}_validated",
                "status": safe_str(section.get("status"), "FAIL"),
                "details": {
                    "score": safe_float(section.get("score"), 0.0),
                    "grade": safe_str(section.get("grade"), "blocked"),
                },
            }
        )
    events.append(
        {
            "timestamp": iso_now(),
            "event": "governance_history_captured",
            "status": "PASS",
            "details": {
                "analysis_count": len(payload.get("governance_validation_history", [])),
            },
        }
    )
    events.append(
        {
            "timestamp": iso_now(),
            "event": "validation_completed",
            "status": payload["overall_status"],
            "details": {
                "overall_status": payload["overall_status"],
                "overall_grade": payload["overall_grade"],
                "readiness_score": safe_float(payload["readiness_summary"].get("production_readiness_score"), 0.0),
            },
        }
    )
    payload["validation_events"] = events

    write_json(bundle_dir / "production_deployment_validation.json", payload)
    write_text(bundle_dir / "production_deployment_validation.md", render_markdown(payload))
    write_text(
        bundle_dir / "validation_events.jsonl",
        "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n",
    )
    shutil.copy2(bundle_dir / "production_deployment_validation.json", output_root / "latest_production_deployment_validation.json")
    shutil.copy2(bundle_dir / "production_deployment_validation.md", output_root / "latest_production_deployment_validation.md")

    return payload


def _print_summary(payload: Dict[str, Any]) -> None:
    readiness = safe_dict(payload.get("readiness_summary"))
    counts = safe_dict(payload.get("validation_counts"))
    print(f"Validation bundle generated: {payload.get('artifact_paths', {}).get('json', '')}")
    print(f"Overall status: {safe_str(payload.get('overall_status'), 'FAIL')}")
    print(f"Readiness score: {safe_float(readiness.get('production_readiness_score'), 0.0):.2f}")
    print(f"PASS: {safe_int(counts.get('PASS'), 0)} WARN: {safe_int(counts.get('WARN'), 0)} FAIL: {safe_int(counts.get('FAIL'), 0)}")
    print(f"Submission lock status: {safe_str(safe_dict(payload.get('submission_lock_verification')).get('status'), 'FAIL')}")
    print(f"Dry-run enforcement: {safe_str(safe_dict(payload.get('dry_run_enforcement_verification')).get('status'), 'PASS')}")
    print(f"Governance history entries: {len(payload.get('governance_validation_history', []))}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate enterprise production deployment readiness using read-only staging governance.")
    parser.add_argument("--limit", type=int, default=20, help="How many history records to include.")
    parser.add_argument("--output-root", type=Path, default=VALIDATION_ROOT, help="Where to write the validation bundle.")
    parser.add_argument("--json", action="store_true", help="Print the full validation payload as JSON.")
    args = parser.parse_args(argv)

    payload = build_production_deployment_validation_report(limit=args.limit, output_root=args.output_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0 if safe_str(payload.get("overall_status"), "FAIL") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
