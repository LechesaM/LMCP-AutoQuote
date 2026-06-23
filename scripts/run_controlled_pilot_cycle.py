#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STAGING_ROOT = PROJECT_ROOT / "runtime" / "staging"
GOVERNANCE_EXPORT_ROOT = STAGING_ROOT / "governance-exports"
PILOT_CYCLE_ROOT = STAGING_ROOT / "pilot-cycles"
ACK_FILE = PILOT_CYCLE_ROOT / "operator_acknowledgement.json"
LOCK_FILE = PILOT_CYCLE_ROOT / "pilot_cycle.lock"
LATEST_EXPORT_FILE = GOVERNANCE_EXPORT_ROOT / "latest_pilot_rehearsal_summary.json"
LATEST_EVIDENCE_PACK_FILE = STAGING_ROOT / "evidence-packs" / "latest_pilot_evidence_pack.json"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def cycle_timestamp() -> str:
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


@contextmanager
def cycle_lock() -> Iterable[Path]:
    if LOCK_FILE.exists():
        raise RuntimeError(f"Pilot cycle is already running: {LOCK_FILE}")
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps({"locked_at": iso_now(), "pid": os.getpid()}, indent=2) + "\n", encoding="utf-8")
    try:
        yield LOCK_FILE
    finally:
        try:
            LOCK_FILE.unlink()
        except FileNotFoundError:
            pass


def emit_event(events: List[Dict[str, Any]], name: str, status: str, **details: Any) -> None:
    events.append(
        {
            "timestamp": iso_now(),
            "event": name,
            "status": status,
            "details": details,
        }
    )


def load_latest_export() -> Dict[str, Any]:
    payload = read_json(LATEST_EXPORT_FILE, {})
    return payload if isinstance(payload, dict) else {}


def load_latest_evidence_pack() -> Dict[str, Any]:
    payload = read_json(LATEST_EVIDENCE_PACK_FILE, {})
    return payload if isinstance(payload, dict) else {}


def load_acknowledgement() -> Dict[str, Any]:
    payload = read_json(ACK_FILE, {})
    return payload if isinstance(payload, dict) else {}


def verify_operator_acknowledgement(ack: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    approved_sequence = safe_list(ack.get("approved_rehearsal_sequence"))
    expected_sequence = [
        "operator_review",
        "governance_checkpoint",
        "cadence_verification",
        "readiness_verification",
        "evidence_pack_validation",
    ]
    passed = (
        ack.get("acknowledged") is True
        and safe_str(ack.get("operator_name"))
        and safe_str(ack.get("operator_role"))
        and approved_sequence == expected_sequence
    )
    return passed, {
        "acknowledged": ack.get("acknowledged") is True,
        "operator_name": safe_str(ack.get("operator_name"), "unknown"),
        "operator_role": safe_str(ack.get("operator_role"), "unknown"),
        "approved_rehearsal_sequence": approved_sequence,
        "expected_rehearsal_sequence": expected_sequence,
        "approved_at": safe_str(ack.get("approved_at")),
    }


def verify_governance_export(export: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    readiness = safe_dict(export.get("readiness_summary"))
    no_go = safe_dict(export.get("no_go_condition_summary"))
    lock = safe_dict(export.get("submission_lock_verification"))
    dry_run = safe_dict(export.get("dry_run_enforcement_verification"))
    recommendation = safe_str(export.get("pilot_authorization_recommendation"), "do_not_authorise")
    cadence = safe_dict(readiness.get("cadence"))
    readiness_score = safe_float(readiness.get("readiness_score"), 0.0)
    threshold = safe_float(safe_dict(readiness.get("thresholds")).get("readiness_score"), 85.0)
    passed = (
        readiness_score >= threshold
        and recommendation == "authorise_pilot"
        and safe_str(no_go.get("status"), "FAIL") == "PASS"
        and safe_str(lock.get("status"), "FAIL") == "PASS"
        and safe_str(dry_run.get("status"), "FAIL") == "PASS"
        and safe_int(cadence.get("runs_last_7_days"), 0) > 0
    )
    return passed, {
        "readiness_score": readiness_score,
        "readiness_threshold": threshold,
        "readiness_grade": safe_str(readiness.get("readiness_grade"), "not_ready"),
        "trend": safe_str(safe_dict(readiness.get("trend_summary")).get("trend"), "unknown"),
        "cadence": cadence,
        "pilot_authorization_recommendation": recommendation,
        "no_go_condition_summary": no_go,
        "submission_lock_verification": lock,
        "dry_run_enforcement_verification": dry_run,
    }


def verify_evidence_pack(export: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    pack = load_latest_evidence_pack()
    summary = safe_dict(pack.get("summary")) or safe_dict(pack.get("readiness_summary"))
    trend = safe_str(safe_dict(summary.get("trend_summary")).get("trend"), safe_str(summary.get("trend"), "unknown"))
    if not pack:
        return False, {"exists": False}
    passed = (
        safe_float(summary.get("readiness_score"), 0.0)
        >= safe_float(safe_dict(safe_dict(export.get("readiness_summary")).get("thresholds")).get("readiness_score"), 85.0)
        and trend in {"stable", "improving"}
    )
    return passed, {
        "exists": True,
        "pack_id": safe_str(pack.get("pack_id")),
        "generated_at": safe_str(pack.get("generated_at")),
        "summary_counts": safe_dict(pack.get("summary_counts")),
        "readiness_score": safe_float(summary.get("readiness_score"), 0.0),
        "readiness_grade": safe_str(summary.get("readiness_grade"), "not_ready"),
        "trend": trend,
    }


def build_metrics(export: Dict[str, Any], evidence_pack: Dict[str, Any]) -> Dict[str, Any]:
    readiness = safe_dict(export.get("readiness_summary"))
    cadence = safe_dict(readiness.get("cadence"))
    summary_counts = safe_dict(export.get("summary_counts"))
    evidence_summary = safe_dict(evidence_pack.get("summary_counts")) or safe_dict(evidence_pack.get("summary")) or safe_dict(evidence_pack.get("readiness_summary"))
    return {
        "readiness_score": safe_float(readiness.get("readiness_score"), 0.0),
        "readiness_grade": safe_str(readiness.get("readiness_grade"), "not_ready"),
        "rehearsal_pass_count": safe_int(summary_counts.get("PASS"), 0),
        "rehearsal_warn_count": safe_int(summary_counts.get("WARN"), 0),
        "rehearsal_fail_count": safe_int(summary_counts.get("FAIL"), 0),
        "evidence_pass_count": safe_int(evidence_summary.get("PASS"), 0),
        "evidence_warn_count": safe_int(evidence_summary.get("WARN"), 0),
        "evidence_fail_count": safe_int(evidence_summary.get("FAIL"), 0),
        "rehearsal_runs_last_7_days": safe_int(cadence.get("runs_last_7_days"), 0),
        "rehearsal_average_gap_hours": safe_float(cadence.get("average_gap_hours"), 0.0),
    }


def summary_counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[safe_str(result.get("status"), "WARN")] = counts.get(safe_str(result.get("status"), "WARN"), 0) + 1
    return counts


def render_markdown(payload: Dict[str, Any]) -> str:
    export = safe_dict(payload.get("governance_export"))
    evidence_pack = safe_dict(payload.get("evidence_pack"))
    ack = safe_dict(payload.get("operator_acknowledgement"))
    checks = safe_list(payload.get("checks"))
    counts = safe_dict(payload.get("summary_counts"))
    metrics = safe_dict(payload.get("metrics"))
    no_go = safe_dict(payload.get("no_go_condition_summary"))

    lines = [
        "# Controlled Pilot Cycle Summary",
        "",
        f"- Cycle ID: `{payload['cycle_id']}`",
        f"- Generated At: `{payload['generated_at']}`",
        f"- Status: `{payload['status']}`",
        "",
        "## Readiness",
        f"- Readiness score: `{metrics.get('readiness_score', 0.0):.2f}`",
        f"- Readiness grade: `{metrics.get('readiness_grade', 'not_ready')}`",
        f"- Rehearsal runs (7 days): `{metrics.get('rehearsal_runs_last_7_days', 0)}`",
        f"- Average cadence gap hours: `{metrics.get('rehearsal_average_gap_hours', 0.0):.2f}`",
        "",
        "## Governance Export",
        f"- Export ID: `{safe_str(export.get('export_id'))}`",
        f"- Recommendation: `{safe_str(export.get('pilot_authorization_recommendation'), 'do_not_authorise')}`",
        f"- No-GO: `{safe_str(safe_dict(export.get('no_go_condition_summary')).get('status'), 'FAIL')}`",
        f"- Submission lock: `{safe_str(safe_dict(export.get('submission_lock_verification')).get('status'), 'FAIL')}`",
        f"- Dry-run: `{safe_str(safe_dict(export.get('dry_run_enforcement_verification')).get('status'), 'FAIL')}`",
        "",
        "## Evidence Pack",
        f"- Pack ID: `{safe_str(evidence_pack.get('pack_id'))}`",
        f"- Pack readiness score: `{safe_float(safe_dict(evidence_pack.get('summary')).get('readiness_score') or safe_dict(evidence_pack.get('readiness_summary')).get('readiness_score'), 0.0):.2f}`",
        f"- Pack trend: `{safe_str(safe_dict(safe_dict(evidence_pack.get('summary')).get('trend_summary')).get('trend') or safe_dict(safe_dict(evidence_pack.get('readiness_summary')).get('trend_summary')).get('trend') or safe_dict(evidence_pack.get('summary')).get('trend'), 'unknown')}`",
        "",
        "## Operator Acknowledgement",
        f"- Acknowledged: `{ack.get('acknowledged') is True}`",
        f"- Operator: `{safe_str(ack.get('operator_name'), 'unknown')}`",
        f"- Role: `{safe_str(ack.get('operator_role'), 'unknown')}`",
        f"- Approved rehearsal sequence: `{json.dumps(safe_list(ack.get('approved_rehearsal_sequence')))}`",
        "",
        "## Checks",
    ]
    for check in checks:
        lines.append(
            f"- `{safe_str(check.get('name'))}`: `{safe_str(check.get('status'), 'WARN')}` - {safe_str(check.get('message'))}"
        )
        remediation = safe_str(check.get('remediation'))
        if remediation:
            lines.append(f"  - Remediation: {remediation}")
    lines.extend(
        [
            "",
            "## Summary Counts",
            f"- PASS: `{counts.get('PASS', 0)}`",
            f"- WARN: `{counts.get('WARN', 0)}`",
            f"- FAIL: `{counts.get('FAIL', 0)}`",
            "",
            "## NO-GO Condition Summary",
            f"- Status: `{safe_str(no_go.get('status'), 'FAIL')}`",
            f"- Indicators: `{json.dumps(safe_list(no_go.get('indicators')))}`",
            "",
            "## Safety Notes",
            "- No live portal submissions are enabled.",
            "- No production credentials are used.",
            "- No irreversible operations are performed.",
            "- The cycle uses read-only governance data and staging rehearsal evidence only.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: List[str] | None = None) -> int:
    from app.services.pilot_evidence_pack_service import PilotEvidencePackService

    os.environ.setdefault("LMCP_ENV", "staging")
    os.environ.setdefault("LMCP_PRODUCTION_MODE", "staging")
    os.environ.setdefault("LMCP_ALLOW_FINAL_AUTOMATION", "false")
    os.environ.setdefault("LMCP_ALLOW_DEGRADED_STARTUP", "true")

    PILOT_CYCLE_ROOT.mkdir(parents=True, exist_ok=True)

    export = load_latest_export()
    if not export:
        print("PASS: 0 WARN: 0 FAIL: 1")
        print("No governance export is available.")
        return 1

    ack = load_acknowledgement()
    ack_ok, ack_details = verify_operator_acknowledgement(ack)
    export_ok, export_details = verify_governance_export(export)
    evidence_ok, evidence_details = verify_evidence_pack(export)

    results: List[Dict[str, Any]] = []
    results.append(
        {
            "name": "operator acknowledgment",
            "status": "PASS" if ack_ok else "FAIL",
            "message": "Operator acknowledgment is present and matches the approved rehearsal sequence.",
            "remediation": "Create a valid staging operator acknowledgement artifact in runtime/staging/pilot-cycles/operator_acknowledgement.json.",
        }
    )
    results.append(
        {
            "name": "governance export verification",
            "status": "PASS" if export_ok else "FAIL",
            "message": "Latest governance export satisfies readiness, no-go, submission-lock, and dry-run checks.",
            "remediation": "Regenerate the governance export until readiness, no-go, submission-lock, and dry-run checks all pass.",
        }
    )
    results.append(
        {
            "name": "evidence pack verification",
            "status": "PASS" if evidence_ok else "FAIL",
            "message": "Latest evidence pack is present and aligns with the approved readiness posture.",
            "remediation": "Regenerate the pilot evidence pack so the latest pack is present and ready.",
        }
    )

    export_cadence = safe_dict(safe_dict(export.get("readiness_summary")).get("cadence"))
    cadence_ok = safe_int(export_cadence.get("runs_last_7_days"), 0) > 0
    results.append(
        {
            "name": "rehearsal cadence enforcement",
            "status": "PASS" if cadence_ok else "WARN",
            "message": f"Rehearsal cadence is {safe_int(export_cadence.get('runs_last_7_days'), 0)} run(s) in the last 7 days.",
            "remediation": "Run at least one approved staging rehearsal in the last 7 days.",
        }
    )

    concurrency_limit = max(1, safe_int(os.environ.get("LMCP_PILOT_MAX_CONCURRENCY"), 1))
    results.append(
        {
            "name": "concurrency limit enforcement",
            "status": "PASS" if concurrency_limit == 1 else "WARN",
            "message": f"Pilot concurrency limit is {concurrency_limit}; current cycle executes with a single lock.",
            "remediation": "Set LMCP_PILOT_MAX_CONCURRENCY=1 for controlled pilot execution.",
        }
    )

    if not export_ok:
        no_go = safe_list(safe_dict(export.get("no_go_condition_summary")).get("indicators"))
    else:
        no_go = []

    cycle_id = f"{cycle_timestamp()}-pilot-{uuid.uuid4().hex[:8]}"
    cycle_dir = PILOT_CYCLE_ROOT / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    telemetry_events: List[Dict[str, Any]] = []
    emit_event(telemetry_events, "cycle_started", "PASS", cycle_id=cycle_id)
    emit_event(telemetry_events, "operator_acknowledged", "PASS" if ack_ok else "FAIL", operator=safe_str(ack.get("operator_name")))
    emit_event(telemetry_events, "governance_export_verified", "PASS" if export_ok else "FAIL", export_id=safe_str(export.get("export_id")))
    emit_event(telemetry_events, "evidence_pack_verified", "PASS" if evidence_ok else "FAIL", pack_id=safe_str(safe_dict(load_latest_evidence_pack()).get("pack_id")))
    emit_event(telemetry_events, "rehearsal_cadence_checked", "PASS" if cadence_ok else "WARN", runs_last_7_days=safe_int(export_cadence.get("runs_last_7_days"), 0))
    emit_event(telemetry_events, "concurrency_checked", "PASS" if concurrency_limit == 1 else "WARN", concurrency_limit=concurrency_limit)

    with cycle_lock():
        emit_event(telemetry_events, "cycle_lock_acquired", "PASS", lock_file=str(LOCK_FILE))
        payload = {
            "cycle_id": cycle_id,
            "generated_at": iso_now(),
            "status": "PASS" if all(result["status"] == "PASS" for result in results) else "WARN" if any(result["status"] == "WARN" for result in results) else "FAIL",
            "governance_export": export,
            "evidence_pack": load_latest_evidence_pack(),
            "operator_acknowledgement": ack,
            "checks": results,
            "metrics": build_metrics(export, load_latest_evidence_pack()),
            "summary_counts": summary_counts(results),
            "no_go_condition_summary": {
                "status": "PASS" if not no_go and export_ok else "FAIL",
                "indicators": no_go,
            },
            "operator_acknowledgment_required": True,
            "governance_checkpoint_verified": export_ok and ack_ok,
            "rehearsal_cadence_enforced": cadence_ok,
            "concurrency_limit_enforced": concurrency_limit == 1,
            "telemetry_events": telemetry_events,
            "safety_guarantees": {
                "live_submissions": False,
                "irreversible_operations": False,
                "production_connectivity": False,
                "production_credentials": False,
            },
        }
        payload["summary_counts"] = summary_counts(results)
        payload["status"] = "PASS" if payload["summary_counts"]["FAIL"] == 0 and payload["summary_counts"]["WARN"] == 0 else "WARN" if payload["summary_counts"]["FAIL"] == 0 else "FAIL"
        payload["approved_rehearsal_sequence"] = safe_list(ack.get("approved_rehearsal_sequence"))
        payload["source_paths"] = {
            "governance_export": str(LATEST_EXPORT_FILE),
            "evidence_pack": str(LATEST_EVIDENCE_PACK_FILE),
            "acknowledgement": str(ACK_FILE),
        }

        json_path = cycle_dir / "pilot_cycle_summary.json"
        md_path = cycle_dir / "pilot_cycle_summary.md"
        telemetry_path = cycle_dir / "telemetry.jsonl"
        write_json(json_path, payload)
        md_path.write_text(render_markdown(payload), encoding="utf-8")
        telemetry_path.write_text("\n".join(json.dumps(event, sort_keys=True) for event in telemetry_events) + "\n", encoding="utf-8")
        shutil.copy2(LATEST_EXPORT_FILE, cycle_dir / "latest_governance_export.json")
        shutil.copy2(LATEST_EVIDENCE_PACK_FILE, cycle_dir / "latest_evidence_pack.json")

        latest_cycle_path = PILOT_CYCLE_ROOT / "latest_pilot_cycle_summary.json"
        write_json(latest_cycle_path, payload)
        emit_event(telemetry_events, "cycle_completed", payload["status"], cycle_id=cycle_id)
        telemetry_path.write_text("\n".join(json.dumps(event, sort_keys=True) for event in telemetry_events) + "\n", encoding="utf-8")
        write_json(json_path, payload)
        write_json(latest_cycle_path, payload)

    print(f"Pilot cycle bundle generated: {cycle_dir}")
    print(f"PASS: {payload['summary_counts']['PASS']} WARN: {payload['summary_counts']['WARN']} FAIL: {payload['summary_counts']['FAIL']}")
    print(f"NO-GO status: {payload['no_go_condition_summary']['status']}")
    if payload["summary_counts"]["FAIL"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
