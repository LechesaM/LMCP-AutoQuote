#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STAGING_ROOT = PROJECT_ROOT / "runtime" / "staging"
RELEASE_CERTIFICATION_ROOT = STAGING_ROOT / "release-certifications"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def export_timestamp() -> str:
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


def trend_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    trend = safe_dict(payload.get("trend_summary"))
    cadence = safe_dict(payload.get("cadence"))
    return {
        "trend": safe_str(trend.get("trend"), "unknown"),
        "delta": safe_float(trend.get("delta"), 0.0),
        "average_score": safe_float(trend.get("average_score"), 0.0),
        "cadence": cadence,
    }


def format_section(title: str, items: List[str]) -> str:
    return "\n".join([f"## {title}"] + [f"- {item}" for item in items]) + "\n"


def _release_service():
    from app.services.production_release_governance_service import ProductionReleaseGovernanceService

    return ProductionReleaseGovernanceService()


def build_release_evidence_payload(service: Any) -> Dict[str, Any]:
    latest = safe_dict(service.latest_release_governance())
    history = safe_dict(service.release_governance_history(limit=20))

    release_history = safe_list(latest.get("release_governance_history"))
    latest_entry = safe_dict(latest.get("latest_release_governance"))
    readiness = {
        "production_readiness_score": safe_float(latest.get("production_readiness_score"), 0.0),
        "production_readiness_status": safe_str(latest.get("release_governance_status"), "watch"),
        "production_readiness_grade": safe_str(latest.get("release_governance_grade"), "blocked"),
        "trend_summary": {
            "trend": safe_str(safe_dict(latest_entry).get("production_readiness_score"), "unknown"),
            "delta": safe_float(safe_dict(safe_dict(latest.get("release_governance_history_summary")).get("score_history")).get("delta"), 0.0),
            "average_score": safe_float(safe_dict(safe_dict(latest.get("release_governance_history_summary")).get("score_history")).get("average"), 0.0),
            "cadence": safe_dict(safe_dict(safe_dict(latest.get("release_governance_history_summary")).get("score_history")).get("cadence")),
        },
        "thresholds": {
            "production_readiness_score": 85.0,
        },
        "release_governance_history_summary": safe_dict(latest.get("release_governance_history_summary")),
    }

    release_authority = safe_dict(latest.get("release_authority_indicators"))
    operational_release = safe_dict(latest.get("operational_release_indicators"))
    readiness_indicators = safe_dict(latest.get("release_readiness_indicators"))
    deployment_risk = safe_dict(latest.get("deployment_risk_indicators"))
    blockers = safe_list(latest.get("unresolved_deployment_blockers"))
    warnings = safe_list(latest.get("warnings"))

    release_governance_score = safe_float(latest.get("release_governance_score"), 0.0)
    release_authority_state = safe_str(latest.get("release_governance_authority"), "WATCH")
    certification_status = "CERTIFIED" if release_authority_state == "GO" and not blockers else "WATCH" if release_authority_state == "WATCH" else "NO_GO"

    executive_rollout_summary = {
        "status": certification_status,
        "release_authority": release_authority_state,
        "release_governance_score": release_governance_score,
        "production_rollout_readiness": bool(latest.get("production_rollout_readiness")),
        "production_rollout_readiness_status": safe_str(latest.get("production_rollout_readiness_status"), "blocked"),
        "unresolved_deployment_blockers": blockers,
        "warnings": warnings,
    }

    governance_certification_summary = {
        "certification_status": certification_status,
        "certification_score": release_governance_score,
        "certified_go_governance": release_authority_state == "GO" and not blockers,
        "certified_watch_governance": release_authority_state == "WATCH",
        "certified_no_go_governance": release_authority_state == "NO_GO",
    }

    deployment_readiness_certification = {
        "status": certification_status,
        "ready_for_deployment": release_authority_state == "GO" and not blockers,
        "deployment_risk_indicators": deployment_risk,
        "release_readiness_indicators": readiness_indicators,
    }

    operational_readiness_certification = {
        "status": certification_status,
        "submission_lock_verified": bool(operational_release.get("submission_lock_verified")),
        "dry_run_verified": bool(operational_release.get("dry_run_verified")),
        "environment_safe": bool(operational_release.get("environment_safe")),
        "overall_validation_passed": bool(operational_release.get("overall_validation_passed")),
    }

    release_authority_certification = {
        "status": certification_status,
        "go_release_authority": bool(release_authority.get("go_release_authority")),
        "watch_release_authority": bool(release_authority.get("watch_release_authority")),
        "no_go_release_authority": bool(release_authority.get("no_go_release_authority")),
        "active_authority": safe_str(release_authority.get("active_authority"), release_authority_state),
    }

    deployment_risk_summary = {
        "deployment_risk": bool(deployment_risk.get("deployment_risk")),
        "runtime_segmentation_risk": bool(deployment_risk.get("runtime_segmentation_risk")),
        "operator_access_risk": bool(deployment_risk.get("operator_access_risk")),
        "observability_risk": bool(deployment_risk.get("observability_risk")),
        "backup_restore_risk": bool(deployment_risk.get("backup_restore_risk")),
        "disaster_recovery_risk": bool(deployment_risk.get("disaster_recovery_risk")),
        "high_availability_risk": bool(deployment_risk.get("high_availability_risk")),
        "audit_retention_risk": bool(deployment_risk.get("audit_retention_risk")),
    }

    institutional_sign_off_summary = {
        "operator_sign_off_status": "PENDING",
        "governance_review_status": "COMPLETE" if certification_status != "NO_GO" else "ESCALATE",
        "rollout_authorization": "APPROVED" if certification_status == "CERTIFIED" else "HELD",
        "rollout_recommendation": "approve_release" if certification_status == "CERTIFIED" else "hold_release",
        "sign_off_history": safe_list(history.get("release_governance_history")),
    }

    payload = {
        "export_id": f"{export_timestamp()}-release-{uuid.uuid4().hex[:8]}",
        "generated_at": iso_now(),
        "source_runtime": str(STAGING_ROOT / "production-deployment-validations"),
        "latest_release_validation": {
            "validation_id": safe_str(latest.get("validation_id")),
            "generated_at": safe_str(latest.get("generated_at")),
            "summary_counts": safe_dict(latest.get("validation_counts")),
            "readiness_score": release_governance_score,
            "release_governance_status": safe_str(latest.get("release_governance_status"), "watch"),
            "release_governance_authority": release_authority_state,
            "production_rollout_readiness": bool(latest.get("production_rollout_readiness")),
            "production_rollout_readiness_status": safe_str(latest.get("production_rollout_readiness_status"), "blocked"),
        },
        "executive_rollout_summary": executive_rollout_summary,
        "governance_certification_summary": governance_certification_summary,
        "deployment_readiness_certification": deployment_readiness_certification,
        "operational_readiness_certification": operational_readiness_certification,
        "release_authority_certification": release_authority_certification,
        "deployment_risk_summary": deployment_risk_summary,
        "institutional_sign_off_summary": institutional_sign_off_summary,
        "release_governance_history": safe_list(latest.get("release_governance_history")),
        "release_governance_history_summary": safe_dict(latest.get("release_governance_history_summary")),
        "readiness_summary": readiness,
        "summary_counts": {
            "PASS": 0 if certification_status == "NO_GO" else 1,
            "WARN": 1 if certification_status == "WATCH" else 0,
            "FAIL": 1 if certification_status == "NO_GO" else 0,
        },
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

    return payload


def markdown_summary(payload: Dict[str, Any]) -> str:
    rollout = safe_dict(payload.get("executive_rollout_summary"))
    certification = safe_dict(payload.get("governance_certification_summary"))
    readiness = safe_dict(payload.get("readiness_summary"))
    operational = safe_dict(payload.get("operational_readiness_certification"))
    authority = safe_dict(payload.get("release_authority_certification"))
    risk = safe_dict(payload.get("deployment_risk_summary"))
    signoff = safe_dict(payload.get("institutional_sign_off_summary"))

    lines = [
        "# Executive Release Evidence",
        "",
        f"- Export ID: `{safe_str(payload.get('export_id'))}`",
        f"- Generated At: `{safe_str(payload.get('generated_at'))}`",
        f"- Source Runtime: `{safe_str(payload.get('source_runtime'))}`",
        "",
        format_section(
            "Executive Rollout Summary",
            [
                f"Status: `{safe_str(rollout.get('status'), 'WATCH')}`",
                f"Release authority: `{safe_str(rollout.get('release_authority'), 'WATCH')}`",
                f"Release governance score: `{safe_float(rollout.get('release_governance_score'), 0.0):.2f}`",
                f"Readiness: `{safe_str(rollout.get('production_rollout_readiness_status'), 'blocked')}`",
                f"Blockers: `{json.dumps(safe_list(rollout.get('unresolved_deployment_blockers')), sort_keys=True)}`",
            ],
        ),
        format_section(
            "Governance Certification Summary",
            [
                f"Certification status: `{safe_str(certification.get('certification_status'), 'WATCH')}`",
                f"Certification score: `{safe_float(certification.get('certification_score'), 0.0):.2f}`",
                f"GO certified: `{str(bool(certification.get('certified_go_governance'))).lower()}`",
                f"WATCH certified: `{str(bool(certification.get('certified_watch_governance'))).lower()}`",
                f"NO-GO certified: `{str(bool(certification.get('certified_no_go_governance'))).lower()}`",
            ],
        ),
        format_section(
            "Deployment / Operational Readiness",
            [
                f"Deployment ready: `{str(bool(deployment_bool(payload, 'deployment_readiness_certification', 'ready_for_deployment'))).lower()}`",
                f"Submission lock verified: `{str(bool(operational.get('submission_lock_verified'))).lower()}`",
                f"Dry-run verified: `{str(bool(operational.get('dry_run_verified'))).lower()}`",
                f"Environment safe: `{str(bool(operational.get('environment_safe'))).lower()}`",
                f"Overall validation passed: `{str(bool(operational.get('overall_validation_passed'))).lower()}`",
            ],
        ),
        format_section(
            "Release Authority Certification",
            [
                f"GO authority: `{str(bool(authority.get('go_release_authority'))).lower()}`",
                f"WATCH authority: `{str(bool(authority.get('watch_release_authority'))).lower()}`",
                f"NO-GO authority: `{str(bool(authority.get('no_go_release_authority'))).lower()}`",
                f"Active authority: `{safe_str(authority.get('active_authority'), 'WATCH')}`",
            ],
        ),
        format_section(
            "Deployment Risk Summary",
            [
                f"Risk summary: `{json.dumps(risk, sort_keys=True)}`",
            ],
        ),
        format_section(
            "Institutional Sign-Off Summary",
            [
                f"Operator sign-off status: `{safe_str(signoff.get('operator_sign_off_status'), 'PENDING')}`",
                f"Governance review status: `{safe_str(signoff.get('governance_review_status'), 'ESCALATE')}`",
                f"Rollout authorization: `{safe_str(signoff.get('rollout_authorization'), 'HELD')}`",
                f"Rollout recommendation: `{safe_str(signoff.get('rollout_recommendation'), 'hold_release')}`",
            ],
        ),
        format_section(
            "Readiness Summary",
            [
                f"Score: `{safe_float(readiness.get('readiness_score'), 0.0):.2f}`",
                f"Grade: `{safe_str(readiness.get('readiness_grade'), 'not_ready')}`",
                f"Trend: `{safe_str(safe_dict(readiness.get('trend_summary')).get('trend'), 'unknown')}`",
                f"Delta: `{safe_float(safe_dict(readiness.get('trend_summary')).get('delta'), 0.0):.2f}`",
                f"Cadence: `{json.dumps(safe_dict(readiness.get('thresholds')), sort_keys=True)}`",
            ],
        ),
        "## Safety Notes",
        "- Read-only evidence exporter.",
        "- No autonomous procurement authority.",
        "- No irreversible actions are performed.",
        "- No production submission enablement or production connectivity is required.",
        "- Governance layers remain authoritative and human supervision remains mandatory.",
        "- Dry-run protections remain active.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def deployment_bool(payload: Dict[str, Any], section: str, key: str) -> bool:
    section_payload = safe_dict(payload.get(section))
    return bool(section_payload.get(key))


def build_release_evidence_export(*, service: Optional[Any] = None, output_root: Optional[Path] = None) -> Dict[str, Any]:
    service = service or _release_service()
    output_root = output_root or RELEASE_CERTIFICATION_ROOT
    output_root.mkdir(parents=True, exist_ok=True)
    payload = build_release_evidence_payload(service)
    export_id = safe_str(payload.get("export_id"))
    export_dir = output_root / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    payload["artifact_paths"] = {
        "json": str(export_dir / "executive_release_evidence.json"),
        "markdown": str(export_dir / "executive_release_evidence.md"),
        "latest_json": str(output_root / "latest_executive_release_evidence.json"),
        "latest_markdown": str(output_root / "latest_executive_release_evidence.md"),
    }
    payload["release_certification_artifacts"] = payload["artifact_paths"]

    json_path = export_dir / "executive_release_evidence.json"
    md_path = export_dir / "executive_release_evidence.md"
    write_json(json_path, payload)
    write_text(md_path, markdown_summary(payload))
    write_json(output_root / "latest_executive_release_evidence.json", payload)
    write_text(output_root / "latest_executive_release_evidence.md", markdown_summary(payload))
    return payload


def _print_summary(payload: Dict[str, Any]) -> None:
    rollout = safe_dict(payload.get("executive_rollout_summary"))
    certification = safe_dict(payload.get("governance_certification_summary"))
    print(f"Export generated: {payload.get('artifact_paths', {}).get('json', '')}")
    print(f"Release authority: {safe_str(rollout.get('release_authority'), 'WATCH')}")
    print(f"Certification status: {safe_str(certification.get('certification_status'), 'WATCH')}")
    print(f"Release governance score: {safe_float(rollout.get('release_governance_score'), 0.0):.2f}")
    print(f"Rollout readiness: {str(bool(rollout.get('production_rollout_readiness'))).lower()}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export executive release evidence from staged production deployment validation artifacts.")
    parser.add_argument("--output-root", type=Path, default=RELEASE_CERTIFICATION_ROOT, help="Where to write the evidence bundle.")
    parser.add_argument("--json", action="store_true", help="Print the full evidence payload as JSON.")
    args = parser.parse_args(argv)

    payload = build_release_evidence_export(output_root=args.output_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0 if safe_dict(payload.get("governance_certification_summary")).get("certification_status") == "CERTIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
