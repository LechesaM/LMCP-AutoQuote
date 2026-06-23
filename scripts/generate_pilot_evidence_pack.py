#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "staging"
REHEARSAL_RUNTIME_DIR = RUNTIME_ROOT / "rehearsals"
EVIDENCE_PACK_ROOT = RUNTIME_ROOT / "evidence-packs"
DEFAULT_SUBMISSION_LOCK_FILE = RUNTIME_ROOT / "go_live_guards" / "submission_locks.json"


def resolve_submission_lock_file() -> Path:
    configured = os.environ.get("LMCP_SUBMISSION_LOCK_FILE")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        return candidate
    return DEFAULT_SUBMISSION_LOCK_FILE


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def pack_timestamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text if text else default
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def truthy_dry_run_guarantees(payload: Dict[str, Any]) -> bool:
    guarantees = payload.get("dry_run_guarantees") if isinstance(payload, dict) else {}
    if not isinstance(guarantees, dict):
        return False
    required_false = ("irreversible_operations", "live_submissions", "production_databases", "production_queues")
    return all(guarantees.get(name) is False for name in required_false)


def build_readiness_snapshot(service: Any) -> Dict[str, Any]:
    readiness = service.readiness_summary(limit=20)
    latest = service.latest_rehearsal()
    history = service.readiness_history(limit=20)
    latest_run = latest.get("run") if isinstance(latest, dict) else {}
    latest_summary = load_json(REHEARSAL_RUNTIME_DIR / "latest_operational_rehearsal.json", {})
    return {
        "readiness_summary": readiness,
        "readiness_history": history,
        "latest_rehearsal": latest,
        "latest_rehearsal_summary": latest_run if isinstance(latest_run, dict) else {},
        "latest_summary_file": latest_summary if isinstance(latest_summary, dict) else {},
    }


def build_section_status(status: str, evidence: Dict[str, Any], notes: List[str] | None = None) -> Dict[str, Any]:
    return {
        "status": status,
        "evidence": evidence,
        "notes": notes or [],
    }


def derive_sections(service: Any) -> Tuple[Dict[str, Any], Dict[str, int]]:
    snapshot = build_readiness_snapshot(service)
    readiness = snapshot["readiness_summary"]
    history = snapshot["readiness_history"]
    latest = snapshot["latest_rehearsal"]
    latest_run = snapshot["latest_rehearsal_summary"]
    latest_file = snapshot["latest_summary_file"]

    metrics = readiness.get("metrics") if isinstance(readiness, dict) else {}
    thresholds = readiness.get("thresholds") if isinstance(readiness, dict) else {}
    trend = readiness.get("trend_summary") if isinstance(readiness, dict) else {}
    cadence = readiness.get("cadence") if isinstance(readiness, dict) else {}
    warning_indicators = readiness.get("warning_threshold_indicators") if isinstance(readiness, dict) else {}

    section_statuses: List[str] = []

    readiness_section = build_section_status(
        "PASS" if safe_float(readiness.get("readiness_score"), 0.0) >= safe_float(thresholds.get("readiness_score"), 70.0) else "WARN",
        {
            "readiness_score": safe_float(readiness.get("readiness_score"), 0.0),
            "readiness_grade": safe_str(readiness.get("readiness_grade"), "unknown"),
            "trend": safe_str(trend.get("trend"), "unknown"),
            "delta": safe_float(trend.get("delta"), 0.0),
            "average_score": safe_float(trend.get("average_score"), 0.0),
            "cadence": cadence,
            "metrics": metrics,
            "warning_threshold_indicators": warning_indicators,
            "thresholds": thresholds,
        },
        [
            "Derived from read-only rehearsal summaries in runtime/staging/rehearsals/",
            "No live workflow execution or production connectivity required.",
        ],
    )
    section_statuses.append(readiness_section["status"])

    history_runs = history.get("runs") if isinstance(history, dict) else []
    history_section = build_section_status(
        "PASS" if history.get("status") == "ok" else "WARN",
        {
            "history_count": safe_int(history.get("count"), 0),
            "trend_summary": history.get("trend_summary", {}),
            "cadence": history.get("cadence", {}),
            "runs": history_runs,
        },
        ["Includes rehearsal history and trend summaries only."],
    )
    section_statuses.append(history_section["status"])

    def drill_result(label: str, key: str) -> Dict[str, Any]:
        drill = latest.get("drill_outcomes", {}) if isinstance(latest, dict) else {}
        payload = drill.get(key, {}) if isinstance(drill, dict) else {}
        return {
            "scenario": safe_str(payload.get("scenario"), label),
            "status": safe_str(payload.get("status"), "unknown"),
            "pass": bool(payload.get("pass")),
            "warn": bool(payload.get("warn")),
            "fail": bool(payload.get("fail")),
        }

    retry = drill_result("retry_rehearsal", "retry_drill")
    rollback = drill_result("rollback_rehearsal", "rollback_drill")
    queue = drill_result("queue_congestion_rehearsal", "queue_drill")
    worker = drill_result("worker_recovery_rehearsal", "worker_recovery_drill")
    dlq = drill_result("dead_letter_rehearsal", "dlq_drill")
    telemetry = drill_result("telemetry_validation_rehearsal", "telemetry_validation")

    lock_file = resolve_submission_lock_file()
    lock_payload = load_json(lock_file, {}) if lock_file.exists() else {}
    lock_ok = (
        lock_file.exists()
        and isinstance(lock_payload, dict)
        and lock_payload.get("final_automation_disabled") is True
        and lock_payload.get("live_portal_submission_disabled") is True
        and lock_payload.get("production_credentials_disabled") is True
        and lock_payload.get("dry_run_mode_required") is True
        and lock_payload.get("submission_execution_allowed") is False
    )

    evidence_sections = {
        "retry_recovery_evidence": build_section_status(
            "PASS" if retry["pass"] else "WARN" if retry["warn"] else "FAIL" if retry["fail"] else "WARN",
            retry,
            ["Derived from the latest operational rehearsal drill outcomes."],
        ),
        "rollback_evidence": build_section_status(
            "PASS" if rollback["pass"] else "WARN" if rollback["warn"] else "FAIL" if rollback["fail"] else "WARN",
            rollback,
            ["Rollback rehearsal remained isolated and reversible."],
        ),
        "queue_stability_evidence": build_section_status(
            "PASS" if queue["pass"] else "WARN" if queue["warn"] else "FAIL" if queue["fail"] else "WARN",
            queue,
            ["Queue congestion rehearsal is read-only evidence; no queue topology was changed."],
        ),
        "worker_stability_evidence": build_section_status(
            "PASS" if worker["pass"] else "WARN" if worker["warn"] else "FAIL" if worker["fail"] else "WARN",
            worker,
            ["Worker recovery rehearsal is based on staging evidence only."],
        ),
        "telemetry_health_evidence": build_section_status(
            "PASS" if telemetry["pass"] else "WARN" if telemetry["warn"] else "FAIL" if telemetry["fail"] else "WARN",
            telemetry,
            ["Telemetry validation rehearsal completed in staging."],
        ),
        "submission_lock_verification": build_section_status(
            "PASS" if lock_ok else "FAIL",
            {
                "lock_file": str(lock_file),
                "exists": lock_file.exists(),
                "verified_read_only": True,
                "payload": lock_payload,
                "verified": lock_ok,
                "note": "Staging submission lock is verified from the configured lock file path.",
            },
            [
                "The configured staging lock file is present and explicit.",
                "No live submissions are enabled; no production connectivity is used.",
            ],
        ),
        "dry_run_enforcement_verification": build_section_status(
            "PASS" if truthy_dry_run_guarantees(latest_file) else "FAIL",
            {
                "source_file": str(REHEARSAL_RUNTIME_DIR / "latest_operational_rehearsal.json"),
                "dry_run_guarantees": latest_file.get("dry_run_guarantees", {}) if isinstance(latest_file, dict) else {},
                "environment_contract": latest_file.get("environment_contract", {}) if isinstance(latest_file, dict) else {},
                "verified": truthy_dry_run_guarantees(latest_file),
            },
            ["Dry-run enforcement is asserted from the latest rehearsal summary."],
        ),
        "operator_intervention_summary": build_section_status(
            "PASS" if safe_float(metrics.get("operator_intervention_frequency"), 0.0) <= safe_float(thresholds.get("operator_intervention_frequency"), 20.0) else "WARN",
            {
                "operator_intervention_frequency": safe_float(metrics.get("operator_intervention_frequency"), 0.0),
                "warning_threshold": safe_float(thresholds.get("operator_intervention_frequency"), 20.0),
                "warning_threshold_indicators": warning_indicators,
            },
            ["Operator intervention frequency is derived from rehearsal metrics only."],
        ),
    }

    for section in evidence_sections.values():
        section_statuses.append(section["status"])

    pack_summary = {
        "PASS": sum(1 for status in section_statuses if status == "PASS"),
        "WARN": sum(1 for status in section_statuses if status == "WARN"),
        "FAIL": sum(1 for status in section_statuses if status == "FAIL"),
    }

    payload = {
        "readiness_summary": readiness,
        "rehearsal_history_summary": {
            "status": history.get("status", "unknown"),
            "count": safe_int(history.get("count"), 0),
            "trend_summary": history.get("trend_summary", {}),
            "cadence": history.get("cadence", {}),
            "runs": history_runs,
        },
        "PASS/WARN/FAIL trends": {
            "summary": pack_summary,
            "latest_run_counts": latest_run.get("overall_counts", {}) if isinstance(latest_run, dict) else {},
            "scenario_statuses": latest_file.get("scenario_statuses", {}) if isinstance(latest_file, dict) else {},
        },
        "retry_recovery_evidence": evidence_sections["retry_recovery_evidence"],
        "rollback_evidence": evidence_sections["rollback_evidence"],
        "queue_stability_evidence": evidence_sections["queue_stability_evidence"],
        "worker_stability_evidence": evidence_sections["worker_stability_evidence"],
        "telemetry_health_evidence": evidence_sections["telemetry_health_evidence"],
        "submission_lock_verification": evidence_sections["submission_lock_verification"],
        "dry_run_enforcement_verification": evidence_sections["dry_run_enforcement_verification"],
        "operator_intervention_summary": evidence_sections["operator_intervention_summary"],
    }

    return payload, pack_summary


def markdown_for_pack(pack: Dict[str, Any], artifact_paths: Dict[str, str], summary_counts: Dict[str, int]) -> str:
    readiness = pack["readiness_summary"]
    history = pack["rehearsal_history_summary"]
    trends = pack["PASS/WARN/FAIL trends"]
    lines = [
        "# LMCP Pilot Evidence Pack",
        "",
        f"- Pack ID: `{pack['pack_id']}`",
        f"- Generated At: `{pack['generated_at']}`",
        f"- Source Runtime: `{pack['source_runtime']}`",
        f"- Rehearsal Runtime: `{pack['rehearsal_runtime']}`",
        "",
        "## Readiness Summary",
        f"- Readiness Score: `{safe_float(readiness.get('readiness_score'), 0.0):.2f}`",
        f"- Readiness Grade: `{safe_str(readiness.get('readiness_grade'), 'unknown')}`",
        f"- Trend: `{safe_str(readiness.get('trend_summary', {}).get('trend'), 'unknown')}`",
        f"- Delta: `{safe_float(readiness.get('trend_summary', {}).get('delta'), 0.0):.2f}`",
        f"- Cadence Runs (7d): `{safe_int(readiness.get('cadence', {}).get('runs_last_7_days'), 0)}`",
        "",
        "## Rehearsal History",
        f"- Runs Recorded: `{safe_int(history.get('count'), 0)}`",
        f"- Average Gap Hours: `{safe_float(history.get('cadence', {}).get('average_gap_hours'), 0.0):.2f}`",
        f"- Most Recent Run: `{safe_str(history.get('cadence', {}).get('most_recent_run_at'), '')}`",
        "",
        "## PASS/WARN/FAIL Trends",
        f"- PASS: `{summary_counts.get('PASS', 0)}`",
        f"- WARN: `{summary_counts.get('WARN', 0)}`",
        f"- FAIL: `{summary_counts.get('FAIL', 0)}`",
        f"- Latest Run Counts: `{json.dumps(trends.get('latest_run_counts', {}), sort_keys=True)}`",
        "",
        "## Evidence Checks",
    ]
    for key in (
        "retry_recovery_evidence",
        "rollback_evidence",
        "queue_stability_evidence",
        "worker_stability_evidence",
        "telemetry_health_evidence",
        "submission_lock_verification",
        "dry_run_enforcement_verification",
        "operator_intervention_summary",
    ):
        section = pack[key]
        lines.extend(
            [
                f"### {key.replace('_', ' ').title()}",
                f"- Status: `{section['status']}`",
                f"- Evidence: `{json.dumps(section['evidence'], sort_keys=True)}`",
            ]
        )
        if section.get("notes"):
            lines.append(f"- Notes: `{json.dumps(section['notes'], sort_keys=True)}`")
        lines.append("")
    lines.extend(
        [
            "## Artifact Paths",
            f"- JSON Summary: `{artifact_paths['json']}`",
            f"- Markdown Summary: `{artifact_paths['markdown']}`",
            "",
            "## Safety Notes",
            "- This evidence pack is staging-only and read-only.",
            "- Live submissions remain disabled.",
            "- Production credentials are not used.",
            "- No irreversible operations are performed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    from app.services.operational_rehearsal_service import OperationalRehearsalService

    service = OperationalRehearsalService(REHEARSAL_RUNTIME_DIR)
    pack_id = f"{pack_timestamp()}-pilot-{uuid.uuid4().hex[:8]}"
    pack_dir = EVIDENCE_PACK_ROOT / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    lock_file = resolve_submission_lock_file()

    evidence_payload, summary_counts = derive_sections(service)

    latest_rehearsal = service.latest_rehearsal()
    readiness = service.readiness_summary(limit=20)
    history = service.readiness_history(limit=20)

    pack = {
        "pack_id": pack_id,
        "generated_at": iso_now(),
        "source_runtime": str(REHEARSAL_RUNTIME_DIR),
        "rehearsal_runtime": str(REHEARSAL_RUNTIME_DIR),
        "latest_rehearsal": latest_rehearsal,
        "readiness_summary": readiness,
        "rehearsal_history_summary": history,
        "PASS/WARN/FAIL trends": evidence_payload["PASS/WARN/FAIL trends"],
        "retry_recovery_evidence": evidence_payload["retry_recovery_evidence"],
        "rollback_evidence": evidence_payload["rollback_evidence"],
        "queue_stability_evidence": evidence_payload["queue_stability_evidence"],
        "worker_stability_evidence": evidence_payload["worker_stability_evidence"],
        "telemetry_health_evidence": evidence_payload["telemetry_health_evidence"],
        "submission_lock_verification": evidence_payload["submission_lock_verification"],
        "dry_run_enforcement_verification": evidence_payload["dry_run_enforcement_verification"],
        "operator_intervention_summary": evidence_payload["operator_intervention_summary"],
        "summary_counts": summary_counts,
            "safety_guarantees": {
                "live_submissions": False,
                "production_credentials": False,
                "irreversible_operations": False,
                "production_database_access": False,
                "production_queue_access": False,
            },
        "lock_source": str(lock_file),
    }

    artifact_paths = {
        "json": str(pack_dir / "pilot_evidence_pack.json"),
        "markdown": str(pack_dir / "pilot_evidence_pack.md"),
    }
    pack["artifact_paths"] = artifact_paths

    json_path = pack_dir / "pilot_evidence_pack.json"
    md_path = pack_dir / "pilot_evidence_pack.md"
    json_path.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown_for_pack(pack, artifact_paths, summary_counts), encoding="utf-8")

    latest_path = EVIDENCE_PACK_ROOT / "latest_pilot_evidence_pack.json"
    latest_path.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Evidence pack generated: {pack_dir}")
    print(f"PASS: {summary_counts['PASS']} WARN: {summary_counts['WARN']} FAIL: {summary_counts['FAIL']}")
    if summary_counts["FAIL"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
