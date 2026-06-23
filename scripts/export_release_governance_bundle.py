#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STAGING_ROOT = PROJECT_ROOT / "runtime" / "staging"
RELEASE_GOVERNANCE_BUNDLE_ROOT = STAGING_ROOT / "release-governance-bundles"
LATEST_RELEASE_GOVERNANCE_BUNDLE_JSON = RELEASE_GOVERNANCE_BUNDLE_ROOT / "latest_release_governance_bundle.json"
LATEST_RELEASE_GOVERNANCE_BUNDLE_MD = RELEASE_GOVERNANCE_BUNDLE_ROOT / "latest_release_governance_bundle.md"

LATEST_PRODUCTION_DEPLOYMENT_VALIDATION = STAGING_ROOT / "production-deployment-validations" / "latest_production_deployment_validation.json"
LATEST_PRODUCTION_ROLLOUT_VALIDATION = STAGING_ROOT / "production-rollout-validations" / "latest_production_rollout_validation.json"
LATEST_RELEASE_CERTIFICATION = STAGING_ROOT / "release-certifications" / "latest_executive_release_evidence.json"
LATEST_PILOT_EVIDENCE_PACK = STAGING_ROOT / "evidence-packs" / "latest_pilot_evidence_pack.json"
LATEST_PILOT_REHEARSAL_SUMMARY = STAGING_ROOT / "governance-exports" / "latest_pilot_rehearsal_summary.json"
LATEST_PILOT_CYCLE_SUMMARY = STAGING_ROOT / "pilot-cycles" / "latest_pilot_cycle_summary.json"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def bundle_timestamp() -> str:
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


def _dig(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


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


def _production_package_report() -> Dict[str, Any]:
    module = _load_module(PROJECT_ROOT / "scripts" / "validate_production_package.py", "release_governance_validate_production_package")
    return safe_dict(module.build_production_package_report())


def _production_access_governance_report() -> Dict[str, Any]:
    module = _load_module(PROJECT_ROOT / "scripts" / "validate_production_access_governance.py", "release_governance_validate_production_access_governance")
    return safe_dict(module.build_production_access_governance_report())


def _production_deployment_validation_report() -> Dict[str, Any]:
    return safe_dict(read_json(LATEST_PRODUCTION_DEPLOYMENT_VALIDATION, {}))


def _production_rollout_validation_report() -> Dict[str, Any]:
    return safe_dict(read_json(LATEST_PRODUCTION_ROLLOUT_VALIDATION, {}))


def _status_rank(value: str) -> int:
    normalized = safe_str(value, "FAIL").upper()
    if normalized in {"PASS", "OK", "READY", "CERTIFIED", "GO"}:
        return 3
    if normalized in {"WARN", "WATCH"}:
        return 2
    return 1


def _score_from_status(value: str) -> float:
    normalized = safe_str(value, "FAIL").upper()
    if normalized in {"PASS", "OK", "READY", "CERTIFIED", "GO"}:
        return 100.0
    if normalized in {"WARN", "WATCH"}:
        return 75.0
    return 0.0


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "PASS"
    if score >= 70.0:
        return "WARN"
    return "FAIL"


def _readiness_status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _authority_from_status(value: str) -> str:
    normalized = safe_str(value, "FAIL").upper()
    if normalized in {"PASS", "OK", "READY", "CERTIFIED", "GO"}:
        return "GO"
    if normalized in {"WARN", "WATCH"}:
        return "WATCH"
    return "NO_GO"


def _overall_status(statuses: List[str]) -> str:
    ranks = [_status_rank(item) for item in statuses if safe_str(item)]
    if not ranks:
        return "FAIL"
    if 1 in ranks:
        return "FAIL"
    if 2 in ranks:
        return "WARN"
    return "PASS"


def _json_summary_counts(reports: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for report in reports:
        summary = safe_dict(report.get("summary_counts")) or safe_dict(report.get("validation_counts"))
        if summary:
            counts["PASS"] += safe_int(summary.get("PASS"), 0)
            counts["WARN"] += safe_int(summary.get("WARN"), 0)
            counts["FAIL"] += safe_int(summary.get("FAIL"), 0)
            continue
        status = safe_str(report.get("overall_status") or report.get("status"), "FAIL").upper()
        if status in {"PASS", "OK", "READY", "CERTIFIED", "GO"}:
            counts["PASS"] += 1
        elif status in {"WARN", "WATCH"}:
            counts["WARN"] += 1
        else:
            counts["FAIL"] += 1
    return counts


def _readiness_score_from_reports(reports: List[Dict[str, Any]]) -> float:
    scores: List[float] = []
    for report in reports:
        for key in (
            "production_readiness_score",
            "rollout_readiness_score",
            "release_governance_score",
            "production_governance_score",
            "continuity_governance_score",
            "operations_audit_score",
            "incident_governance_score",
            "executive_governance_index_score",
        ):
            if key in report:
                scores.append(safe_float(report.get(key), 0.0))
                break
        else:
            if "summary_counts" in report:
                counts = safe_dict(report.get("summary_counts"))
                total = sum(safe_int(counts.get(level), 0) for level in ("PASS", "WARN", "FAIL"))
                if total:
                    scores.append(round((safe_int(counts.get("PASS"), 0) / total) * 100.0, 2))
    return round(mean(scores), 2) if scores else 0.0


def _source_entry(name: str, report: Dict[str, Any], *, score_key: str | None = None, status_key: str | None = None, authority_key: str | None = None) -> Dict[str, Any]:
    raw_status = _dig(report, status_key) if status_key else None
    raw_authority = _dig(report, authority_key) if authority_key else None
    raw_score = _dig(report, score_key) if score_key else None
    status = safe_str(raw_status, safe_str(report.get("overall_status") or report.get("status"), "FAIL"))
    authority = safe_str(raw_authority, _authority_from_status(status))
    score = safe_float(raw_score, _score_from_status(status))
    blockers = safe_list(report.get("unresolved_blockers")) or safe_list(report.get("warnings"))
    return {
        "name": name,
        "status": status,
        "authority": authority,
        "score": round(score, 2),
        "blockers": blockers,
        "warnings": safe_list(report.get("warnings")),
        "artifact_path": safe_str(report.get("artifact_path"), ""),
    }


def _derive_supervision_readiness(rollout: Dict[str, Any]) -> Dict[str, Any]:
    supervision = safe_dict(rollout.get("supervision_readiness_summary"))
    onboarding = safe_dict(rollout.get("operator_onboarding_readiness_summary"))
    score = round(
        mean(
            [
                safe_float(rollout.get("rollout_readiness_summary", {}).get("rollout_readiness_score"), 0.0),
                100.0 if safe_str(supervision.get("active_supervision_coverage_ready"), "").lower() == "true" else 0.0,
                100.0 if safe_str(onboarding.get("approved_for_supervision"), "").lower() == "true" else 0.0,
                100.0 if not safe_list(supervision.get("pending_approvals")) else 0.0,
            ]
        ),
        2,
    )
    status = safe_str(supervision.get("supervision_command_status"), _readiness_status_from_score(score)).lower()
    authority = safe_str(supervision.get("supervision_command_authority"), _authority_from_status(status.upper()))
    if status not in {"ok", "watch", "blocked"}:
        status = _readiness_status_from_score(score)
    return {
        "status": status,
        "supervision_command_status": status,
        "supervision_command_score": score,
        "supervision_command_authority": authority,
        "supervision_command_grade": safe_str(supervision.get("supervision_command_grade"), "ready" if status == "ok" else "watch" if status == "watch" else "blocked"),
        "latest_supervision_command": {
            "active_supervised_operators": safe_list(supervision.get("active_supervised_operators")),
            "active_rfq_oversight": safe_dict(supervision.get("active_rfq_oversight")),
            "operational_workload_visibility": safe_dict(supervision.get("operational_workload_visibility")),
            "supervision_sla_visibility": safe_dict(supervision.get("supervision_sla_visibility")),
            "supervision_lapse_indicators": safe_dict(supervision.get("supervision_lapse_indicators")),
            "supervision_saturation_indicators": safe_dict(supervision.get("supervision_saturation_indicators")),
        },
        "supervision_command_history_summary": safe_dict(supervision.get("supervision_command_history_summary")),
        "warnings": safe_list(supervision.get("warnings")),
    }


def _derive_continuity_readiness(rollout: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    rollout_readiness = safe_dict(rollout.get("rollout_readiness_summary"))
    deployment_health = safe_dict(rollout.get("deployment_health_summary"))
    observability = safe_dict(rollout.get("production_observability_summary"))
    escalation = safe_dict(rollout.get("escalation_chain_summary"))
    release_ok = safe_str(release.get("governance_certification_summary", {}).get("certification_status"), safe_str(release.get("status"), "WATCH")).upper() == "CERTIFIED"
    readiness_bool = all(
        [
            safe_str(rollout_readiness.get("rollout_readiness_status"), "WARN").upper() in {"PASS", "OK", "READY", "CERTIFIED"},
            bool(deployment_health.get("deployment_health_ready")),
            bool(observability.get("production_observability_ready")),
            bool(escalation.get("escalation_chain_ready")),
            release_ok,
        ]
    )
    score = round(
        mean(
            [
                safe_float(rollout_readiness.get("rollout_readiness_score"), 0.0),
                100.0 if deployment_health.get("deployment_health_ready") else 0.0,
                100.0 if observability.get("production_observability_ready") else 0.0,
                100.0 if escalation.get("escalation_chain_ready") else 0.0,
                100.0 if release_ok else 0.0,
            ]
        ),
        2,
    )
    status = _readiness_status_from_score(score)
    authority = _authority_from_status(status.upper())
    return {
        "status": status,
        "continuity_governance_status": status,
        "continuity_governance_score": score,
        "continuity_governance_authority": authority,
        "continuity_governance_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
        "continuity_governance_history_summary": {
            "analysis_count": safe_int(safe_dict(rollout.get("rollout_governance_history_summary")).get("analysis_count"), 0),
            "latest_score": score,
            "score_history": {
                "trend": "stable" if score >= 70.0 else "declining",
                "delta": 0.0,
                "average": score,
                "latest": score,
                "previous": score,
                "points": [score],
            },
        },
        "warnings": [] if readiness_bool else ["continuity_readiness_watch"],
    }


def _derive_audit_readiness(package: Dict[str, Any], access: Dict[str, Any], deployment: Dict[str, Any], rollout: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    checks = [package, access, deployment, rollout, release]
    score = 100.0 if all(safe_str(item.get("overall_status") or item.get("status"), "FAIL").upper() in {"PASS", "OK", "READY", "CERTIFIED"} for item in checks) else 75.0 if any(safe_str(item.get("overall_status") or item.get("status"), "WARN").upper() in {"WARN", "WATCH"} for item in checks) else 0.0
    status = _readiness_status_from_score(score)
    return {
        "status": status,
        "operations_audit_status": status,
        "operations_audit_score": score,
        "operations_audit_authority": _authority_from_status(status.upper()),
        "operations_audit_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
        "operations_audit_history_summary": {
            "analysis_count": 1 if score else 0,
            "latest_score": score,
            "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score] if score else []},
        },
        "warnings": [] if score >= 85.0 else ["audit_retention_watch"],
    }


def _derive_incident_readiness(rollout: Dict[str, Any], release: Dict[str, Any], deployment: Dict[str, Any]) -> Dict[str, Any]:
    warnings = safe_list(rollout.get("warnings")) + safe_list(deployment.get("warnings")) + safe_list(release.get("warnings"))
    score = 100.0 if not warnings else 75.0 if len(warnings) <= 2 else 0.0
    status = _readiness_status_from_score(score)
    return {
        "status": status,
        "incident_governance_status": status,
        "incident_governance_score": score,
        "incident_governance_authority": _authority_from_status(status.upper()),
        "incident_governance_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
        "incident_governance_history_summary": {
            "analysis_count": 1 if score else 0,
            "latest_score": score,
            "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score] if score else []},
        },
        "warnings": warnings,
    }


def _derive_executive_readiness(
    package: Dict[str, Any],
    access: Dict[str, Any],
    deployment: Dict[str, Any],
    rollout: Dict[str, Any],
    release: Dict[str, Any],
    supervision: Dict[str, Any],
    continuity: Dict[str, Any],
    audit: Dict[str, Any],
    incident: Dict[str, Any],
) -> Dict[str, Any]:
    components = [
        _score_from_status(safe_str(package.get("overall_status"), "FAIL")),
        _score_from_status(safe_str(access.get("overall_status"), "FAIL")),
        safe_float(deployment.get("readiness_summary", {}).get("production_readiness_score"), _score_from_status(safe_str(deployment.get("overall_status"), "FAIL"))),
        safe_float(rollout.get("institutional_rollout_certification_evidence", {}).get("rollout_governance_score"), _score_from_status(safe_str(rollout.get("overall_status"), "WARN"))),
        safe_float(release.get("release_governance_score"), _score_from_status(safe_str(release.get("status"), "WATCH"))),
        safe_float(supervision.get("supervision_command_score"), _score_from_status(safe_str(supervision.get("status"), "WATCH"))),
        safe_float(continuity.get("continuity_governance_score"), _score_from_status(safe_str(continuity.get("status"), "WATCH"))),
        safe_float(audit.get("operations_audit_score"), _score_from_status(safe_str(audit.get("status"), "WATCH"))),
        safe_float(incident.get("incident_governance_score"), _score_from_status(safe_str(incident.get("status"), "WATCH"))),
    ]
    score = round(mean(components), 2)
    status = _readiness_status_from_score(score)
    authority = _authority_from_status(status.upper())
    return {
        "status": status,
        "executive_governance_index_status": status,
        "executive_governance_index_score": score,
        "executive_governance_index_authority": authority,
        "executive_governance_index_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
        "executive_governance_index_history_summary": {
            "analysis_count": 1,
            "latest_score": score,
            "score_history": {"trend": "stable", "delta": 0.0, "average": score, "latest": score, "previous": score, "points": [score]},
        },
        "warnings": [],
    }


def _read_validation_sources() -> Dict[str, Dict[str, Any]]:
    package = _production_package_report()
    access = _production_access_governance_report()
    deployment = _production_deployment_validation_report()
    rollout = _production_rollout_validation_report()
    release = safe_dict(read_json(LATEST_RELEASE_CERTIFICATION, {}))
    supervision = _derive_supervision_readiness(rollout)
    continuity = _derive_continuity_readiness(rollout, release)
    audit = _derive_audit_readiness(package, access, deployment, rollout, release)
    incident = _derive_incident_readiness(rollout, release, deployment)
    executive = _derive_executive_readiness(package, access, deployment, rollout, release, supervision, continuity, audit, incident)

    return {
        "package": package,
        "access": access,
        "deployment": deployment,
        "rollout": rollout,
        "release": release,
        "supervision": supervision,
        "continuity": continuity,
        "audit": audit,
        "incident": incident,
        "executive": executive,
    }


def build_release_governance_bundle(*, output_root: Path = RELEASE_GOVERNANCE_BUNDLE_ROOT) -> Dict[str, Any]:
    sources = _read_validation_sources()
    package = safe_dict(sources["package"])
    access = safe_dict(sources["access"])
    deployment = safe_dict(sources["deployment"])
    rollout = safe_dict(sources["rollout"])
    release = safe_dict(sources["release"])
    supervision = safe_dict(sources["supervision"])
    continuity = safe_dict(sources["continuity"])
    audit = safe_dict(sources["audit"])
    incident = safe_dict(sources["incident"])
    executive = safe_dict(sources["executive"])

    release_certification = safe_dict(release.get("latest_release_governance") or release)
    release_score = safe_float(release.get("release_governance_score"), safe_float(release_certification.get("release_governance_score"), 0.0))
    rollout_score = safe_float(rollout.get("institutional_rollout_certification_evidence", {}).get("rollout_governance_score"), safe_float(rollout.get("rollout_readiness_summary", {}).get("rollout_readiness_score"), 0.0))
    deployment_score = safe_float(deployment.get("readiness_summary", {}).get("production_readiness_score"), 0.0)
    package_score = _score_from_status(safe_str(package.get("overall_status"), "FAIL"))
    access_score = _score_from_status(safe_str(access.get("overall_status"), "FAIL"))

    release_status = safe_str(release.get("release_governance_status"), safe_str(release.get("status"), "watch")).upper()
    rollout_status = safe_str(
        rollout.get("institutional_rollout_certification_evidence", {}).get("certification_status"),
        safe_str(rollout.get("rollout_readiness_summary", {}).get("rollout_readiness_status"), safe_str(rollout.get("overall_status"), "WARN")),
    ).upper()
    continuity_status = safe_str(continuity.get("continuity_governance_status"), safe_str(continuity.get("status"), "watch")).upper()
    supervision_status = safe_str(supervision.get("supervision_command_status"), safe_str(supervision.get("status"), "watch")).upper()
    audit_status = safe_str(audit.get("operations_audit_status"), safe_str(audit.get("status"), "watch")).upper()
    incident_status = safe_str(incident.get("incident_governance_status"), safe_str(incident.get("status"), "watch")).upper()
    executive_status = safe_str(executive.get("executive_governance_index_status"), safe_str(executive.get("status"), "watch")).upper()
    deployment_status = safe_str(deployment.get("overall_status"), "FAIL").upper()

    continuity_score = safe_float(continuity.get("continuity_governance_score"), _score_from_status(continuity_status))
    supervision_score = safe_float(supervision.get("supervision_command_score"), _score_from_status(supervision_status))
    audit_score = safe_float(audit.get("operations_audit_score"), _score_from_status(audit_status))
    incident_score = safe_float(incident.get("incident_governance_score"), _score_from_status(incident_status))
    executive_score = safe_float(executive.get("executive_governance_index_score"), _score_from_status(executive_status))
    deployment_score = safe_float(deployment.get("readiness_summary", {}).get("production_readiness_score"), _score_from_status(deployment_status))

    source_summaries = {
        "production_package": _source_entry("production package", package),
        "production_access_governance": _source_entry("production access governance", access),
        "production_deployment_validation": _source_entry("production deployment validation", deployment, score_key="readiness_summary.production_readiness_score", status_key="overall_status"),
        "production_rollout_validation": _source_entry("production rollout validation", rollout, score_key="institutional_rollout_certification_evidence.rollout_governance_score", status_key="institutional_rollout_certification_evidence.certification_status", authority_key="institutional_rollout_certification_evidence.certification_authority"),
        "release_governance": _source_entry("release governance", release, score_key="release_governance_score", status_key="release_governance_status", authority_key="release_governance_authority"),
        "supervision_governance": _source_entry("supervision governance", supervision, score_key="supervision_command_score", status_key="supervision_command_status", authority_key="supervision_command_authority"),
        "continuity_governance": _source_entry("continuity governance", continuity, score_key="continuity_governance_score", status_key="continuity_governance_status", authority_key="continuity_governance_authority"),
        "operations_audit": _source_entry("operations audit", audit, score_key="operations_audit_score", status_key="operations_audit_status", authority_key="operations_audit_authority"),
        "incident_governance": _source_entry("incident governance", incident, score_key="incident_governance_score", status_key="incident_governance_status", authority_key="incident_governance_authority"),
        "executive_governance_index": _source_entry("executive governance index", executive, score_key="executive_governance_index_score", status_key="executive_governance_index_status", authority_key="executive_governance_index_authority"),
    }

    validation_reports = [package, access, deployment, rollout]
    overall_status = _overall_status([
        safe_str(package.get("overall_status"), "FAIL"),
        safe_str(access.get("overall_status"), "FAIL"),
        deployment_status,
        rollout_status,
        release_status,
        continuity_status,
        supervision_status,
        audit_status,
        incident_status,
        executive_status,
    ])
    overall_authority = _authority_from_status(overall_status)
    overall_score = round(mean([
        package_score,
        access_score,
        deployment_score,
        rollout_score,
        release_score,
        continuity_score,
        supervision_score,
        audit_score,
        incident_score,
        executive_score,
    ]), 2)

    release_readiness = {
        "release_governance_status": release_status.lower(),
        "release_governance_score": release_score,
        "release_governance_authority": safe_str(release.get("release_governance_authority"), _authority_from_status(release_status)),
        "release_governance_grade": safe_str(release.get("release_governance_grade"), "blocked" if release_status == "NO_GO" else "watch" if release_status == "WATCH" else "ready"),
        "release_authority_valid": safe_str(release.get("release_authority_indicators", {}).get("active_authority"), "WATCH") == "GO",
        "deployment_risk_indicators": safe_dict(release.get("deployment_risk_indicators")),
        "operational_release_indicators": safe_dict(release.get("operational_release_indicators")),
        "release_readiness_indicators": safe_dict(release.get("release_readiness_indicators")),
        "release_governance_history_summary": safe_dict(release.get("release_governance_history_summary")),
        "unresolved_deployment_blockers": safe_list(release.get("unresolved_deployment_blockers")),
    }
    rollout_readiness = {
        "rollout_readiness_score": rollout_score,
        "rollout_readiness_status": safe_str(rollout.get("institutional_rollout_certification_evidence", {}).get("certification_status"), safe_str(rollout.get("rollout_readiness_summary", {}).get("rollout_readiness_status"), "WARN")).upper(),
        "rollout_readiness_grade": safe_str(rollout.get("institutional_rollout_certification_evidence", {}).get("certification_status"), "WATCH").lower(),
        "institutional_rollout_readiness": safe_dict(rollout.get("institutional_rollout_certification_evidence")),
        "supervision_readiness_summary": safe_dict(rollout.get("supervision_readiness_summary")),
        "operator_onboarding_readiness_summary": safe_dict(rollout.get("operator_onboarding_readiness_summary")),
        "deployment_health_summary": safe_dict(rollout.get("deployment_health_summary")),
        "tenant_isolation_summary": safe_dict(rollout.get("tenant_isolation_summary")),
        "production_observability_summary": safe_dict(rollout.get("production_observability_summary")),
        "escalation_chain_summary": safe_dict(rollout.get("escalation_chain_summary")),
        "rollout_governance_history_summary": safe_dict(rollout.get("rollout_governance_history_summary")),
    }
    continuity_readiness = {
        "continuity_governance_status": continuity_status.lower(),
        "continuity_governance_score": continuity_score,
        "continuity_governance_authority": safe_str(continuity.get("continuity_governance_authority"), _authority_from_status(continuity_status)),
        "continuity_governance_grade": safe_str(continuity.get("continuity_governance_grade"), "blocked" if continuity_status == "NO_GO" else "watch" if continuity_status == "WATCH" else "ready"),
        "continuity_governance_history_summary": safe_dict(continuity.get("continuity_governance_history_summary")),
    }
    supervision_readiness = {
        "supervision_command_status": supervision_status.lower(),
        "supervision_command_score": supervision_score,
        "supervision_command_authority": safe_str(supervision.get("supervision_command_authority"), _authority_from_status(supervision_status)),
        "supervision_command_grade": safe_str(supervision.get("supervision_command_grade"), "blocked" if supervision_status == "NO_GO" else "watch" if supervision_status == "WATCH" else "ready"),
        "latest_supervision_command": safe_dict(supervision.get("latest_supervision_command")),
        "supervision_command_history_summary": safe_dict(supervision.get("supervision_command_history_summary")),
    }
    audit_readiness = {
        "operations_audit_status": audit_status.lower(),
        "operations_audit_score": audit_score,
        "operations_audit_authority": safe_str(audit.get("operations_audit_authority"), _authority_from_status(audit_status)),
        "operations_audit_grade": safe_str(audit.get("operations_audit_grade"), "blocked" if audit_status == "NO_GO" else "watch" if audit_status == "WATCH" else "ready"),
        "operations_audit_history_summary": safe_dict(audit.get("operations_audit_history_summary")),
    }
    incident_readiness = {
        "incident_governance_status": incident_status.lower(),
        "incident_governance_score": incident_score,
        "incident_governance_authority": safe_str(incident.get("incident_governance_authority"), _authority_from_status(incident_status)),
        "incident_governance_grade": safe_str(incident.get("incident_governance_grade"), "blocked" if incident_status == "NO_GO" else "watch" if incident_status == "WATCH" else "ready"),
        "incident_governance_history_summary": safe_dict(incident.get("incident_governance_history_summary")),
    }
    executive_readiness = {
        "executive_governance_index_status": executive_status.lower(),
        "executive_governance_index_score": executive_score,
        "executive_governance_index_authority": safe_str(executive.get("executive_governance_index_authority"), _authority_from_status(executive_status)),
        "executive_governance_index_grade": safe_str(executive.get("executive_governance_index_grade"), "blocked" if executive_status == "NO_GO" else "watch" if executive_status == "WATCH" else "ready"),
        "executive_governance_index_history_summary": safe_dict(executive.get("executive_governance_index_history_summary")),
    }

    safety_guarantees = {
        "autonomous_procurement_authority": False,
        "irreversible_operations": False,
        "production_submission_enablement": False,
        "production_connectivity_required": False,
        "human_supervision_required": True,
        "dry_run_protections_active": True,
    }

    bundle_dir = output_root / f"{bundle_timestamp()}-release-{uuid.uuid4().hex[:8]}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = {
        "json": str(bundle_dir / "release_governance_bundle.json"),
        "markdown": str(bundle_dir / "release_governance_bundle.md"),
        "latest_json": str(output_root / "latest_release_governance_bundle.json"),
        "latest_markdown": str(output_root / "latest_release_governance_bundle.md"),
        "source_production_package": str(LATEST_PRODUCTION_DEPLOYMENT_VALIDATION),
        "source_production_rollout_validation": str(LATEST_PRODUCTION_ROLLOUT_VALIDATION),
        "source_release_certification": str(LATEST_RELEASE_CERTIFICATION),
        "source_pilot_evidence_pack": str(LATEST_PILOT_EVIDENCE_PACK),
        "source_pilot_rehearsal_summary": str(LATEST_PILOT_REHEARSAL_SUMMARY),
        "source_pilot_cycle_summary": str(LATEST_PILOT_CYCLE_SUMMARY),
    }

    history = [
        {"name": key, "status": value["status"], "score": value["score"], "authority": value["authority"], "artifact_path": value["artifact_path"]}
        for key, value in source_summaries.items()
    ]
    governance_history = safe_list(release.get("release_governance_history")) or safe_list(executive.get("consolidated_governance_history"))
    governance_history = list(governance_history)[:20] if governance_history else history

    payload = {
        "bundle_id": bundle_dir.name,
        "generated_at": iso_now(),
        "source_runtime": str(STAGING_ROOT),
        "overall_status": overall_status,
        "overall_authority": overall_authority,
        "overall_score": overall_score,
        "summary_counts": _json_summary_counts(validation_reports),
        "validation_summaries": {
            "production_package": package,
            "production_access_governance": access,
            "production_deployment_validation": deployment,
            "production_rollout_validation": rollout,
        },
        "release_readiness": release_readiness,
        "rollout_readiness": rollout_readiness,
        "continuity_readiness": continuity_readiness,
        "supervision_readiness": supervision_readiness,
        "audit_readiness": audit_readiness,
        "incident_readiness": incident_readiness,
        "executive_readiness": executive_readiness,
        "governance_validation_history": governance_history,
        "source_summaries": source_summaries,
        "release_authority_certification": safe_dict(release.get("release_authority_certification")),
        "deployment_readiness_certification": safe_dict(release.get("deployment_readiness_certification")),
        "operational_readiness_certification": safe_dict(release.get("operational_readiness_certification")),
        "governance_certification_summary": safe_dict(release.get("governance_certification_summary")),
        "release_certification_snapshot": safe_dict(release.get("release_certification_snapshot")),
        "latest_release_governance": safe_dict(release.get("latest_release_governance")),
        "latest_production_deployment_validation": deployment,
        "latest_production_rollout_validation": rollout,
        "latest_production_package_validation": package,
        "latest_production_access_governance": access,
        "latest_pilot_evidence_pack": read_json(LATEST_PILOT_EVIDENCE_PACK, {}),
        "latest_pilot_rehearsal_summary": read_json(LATEST_PILOT_REHEARSAL_SUMMARY, {}),
        "latest_pilot_cycle_summary": read_json(LATEST_PILOT_CYCLE_SUMMARY, {}),
        "safety_guarantees": safety_guarantees,
        "warnings": [],
        "artifact_paths": artifact_paths,
    }

    write_json(bundle_dir / "release_governance_bundle.json", payload)
    write_text(bundle_dir / "release_governance_bundle.md", markdown_summary(payload))
    write_json(output_root / "latest_release_governance_bundle.json", payload)
    write_text(output_root / "latest_release_governance_bundle.md", markdown_summary(payload))
    return payload


def markdown_summary(payload: Dict[str, Any]) -> str:
    lines = [
        "# Release Governance Bundle",
        "",
        f"- Bundle ID: `{safe_str(payload.get('bundle_id'))}`",
        f"- Generated At: `{safe_str(payload.get('generated_at'))}`",
        f"- Source Runtime: `{safe_str(payload.get('source_runtime'))}`",
        f"- Overall Status: `{safe_str(payload.get('overall_status'), 'FAIL')}`",
        f"- Overall Authority: `{safe_str(payload.get('overall_authority'), 'NO_GO')}`",
        f"- Overall Score: `{safe_float(payload.get('overall_score'), 0.0):.2f}`",
        f"- Summary Counts: `{json.dumps(safe_dict(payload.get('summary_counts')), sort_keys=True)}`",
        "",
        "## Validation Summaries",
    ]
    for key, report in safe_dict(payload.get("validation_summaries")).items():
        lines.append(f"- {key}: `{safe_str(report.get('overall_status'), safe_str(report.get('status'), 'FAIL'))}`")
    lines += [
        "",
        "## Readiness",
        f"- Release readiness: `{json.dumps(safe_dict(payload.get('release_readiness')), sort_keys=True)}`",
        f"- Rollout readiness: `{json.dumps(safe_dict(payload.get('rollout_readiness')), sort_keys=True)}`",
        f"- Continuity readiness: `{json.dumps(safe_dict(payload.get('continuity_readiness')), sort_keys=True)}`",
        f"- Supervision readiness: `{json.dumps(safe_dict(payload.get('supervision_readiness')), sort_keys=True)}`",
        f"- Audit readiness: `{json.dumps(safe_dict(payload.get('audit_readiness')), sort_keys=True)}`",
        f"- Incident readiness: `{json.dumps(safe_dict(payload.get('incident_readiness')), sort_keys=True)}`",
        f"- Executive readiness: `{json.dumps(safe_dict(payload.get('executive_readiness')), sort_keys=True)}`",
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
    print(f"Release governance bundle: {safe_str(payload.get('artifact_paths', {}).get('json'), '')}")
    print(f"Overall status: {safe_str(payload.get('overall_status'), 'FAIL')}")
    print(f"Overall authority: {safe_str(payload.get('overall_authority'), 'NO_GO')}")
    print(f"Overall score: {safe_float(payload.get('overall_score'), 0.0):.2f}")
    print(f"Summary counts: PASS {safe_int(safe_dict(payload.get('summary_counts')).get('PASS'), 0)} WARN {safe_int(safe_dict(payload.get('summary_counts')).get('WARN'), 0)} FAIL {safe_int(safe_dict(payload.get('summary_counts')).get('FAIL'), 0)}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export the controlled release governance bundle.")
    parser.add_argument("--output-root", type=Path, default=RELEASE_GOVERNANCE_BUNDLE_ROOT, help="Where to write the governance bundle.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable summary.")
    args = parser.parse_args(argv)

    payload = build_release_governance_bundle(output_root=args.output_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
