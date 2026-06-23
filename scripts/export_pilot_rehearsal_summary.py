#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STAGING_ROOT = PROJECT_ROOT / "runtime" / "staging"
EXPORT_ROOT = STAGING_ROOT / "governance-exports"


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


def status_from_bool(value: bool) -> str:
    return "PASS" if value else "FAIL"


def trend_summary(readiness: Dict[str, Any]) -> Dict[str, Any]:
    trend = safe_dict(readiness.get("trend_summary"))
    cadence = safe_dict(readiness.get("cadence"))
    return {
        "trend": safe_str(trend.get("trend"), "unknown"),
        "delta": safe_float(trend.get("delta"), 0.0),
        "average_score": safe_float(trend.get("average_score"), 0.0),
        "cadence": cadence,
    }


def format_section(title: str, items: List[str]) -> str:
    body = "\n".join(f"- {item}" for item in items)
    return f"## {title}\n{body}\n"


def build_export_payload(service: Any) -> Dict[str, Any]:
    latest_pack = service.latest_pack()
    review = service.governance_review()
    history = service.list_packs(limit=20)

    pack = safe_dict(latest_pack.get("pack"))
    summary = safe_dict(latest_pack.get("summary"))
    readiness = safe_dict(pack.get("readiness_summary"))
    rehearsal_history = safe_dict(pack.get("rehearsal_history_summary"))
    trends = safe_dict(pack.get("PASS/WARN/FAIL trends"))
    evidence_sections = safe_dict(review.get("evidence_sections"))
    no_go_indicators = safe_list(review.get("no_go_indicators"))
    operator_checklist = safe_list(review.get("operator_sign_off_checklist"))
    governance_checklist = safe_list(review.get("governance_review_checklist"))

    submission_lock = safe_dict(review.get("submission_lock_verification"))
    dry_run = safe_dict(evidence_sections.get("dry_run_enforcement_verification"))
    queue = safe_dict(evidence_sections.get("queue_stability_evidence"))
    rollback = safe_dict(evidence_sections.get("rollback_evidence"))
    telemetry = safe_dict(evidence_sections.get("telemetry_health_evidence"))

    readiness_score = safe_float(review.get("readiness_score"), safe_float(summary.get("readiness_score"), 0.0))
    readiness_threshold = safe_float(review.get("readiness_threshold"), safe_float(safe_dict(readiness.get("thresholds")).get("readiness_score"), 85.0))
    readiness_pass = readiness_score >= readiness_threshold
    no_go = bool(no_go_indicators)

    recommendation = "authorise_pilot" if readiness_pass and not no_go else "do_not_authorise"

    operator_sign_off = [
        "Review latest evidence pack and readiness score.",
        "Confirm submission lock verification is PASS.",
        "Confirm dry-run enforcement verification is PASS.",
        "Confirm no-go indicators are absent.",
        "Record operator approval only after manual review of rehearsal evidence.",
    ]

    governance_review_section = [
        f"Pilot authorization status: {safe_str(review.get('pilot_authorization_status'), 'not_authorized')}",
        f"Readiness score: {readiness_score:.2f}",
        f"Threshold: {readiness_threshold:.2f}",
        f"Trend: {safe_str(trend_summary(readiness).get('trend'), 'unknown')} (Δ {safe_float(trend_summary(readiness).get('delta'), 0.0):.2f})",
        f"PASS/WARN/FAIL trend summary: {json.dumps(safe_dict(trends.get('summary')), sort_keys=True)}",
        f"Rehearsal cadence: {json.dumps(trend_summary(readiness).get('cadence', {}), sort_keys=True)}",
        f"NO-GO indicators: {', '.join(no_go_indicators) if no_go_indicators else 'none'}",
    ]

    payload = {
        "export_id": f"{export_timestamp()}-pilot-{uuid.uuid4().hex[:8]}",
        "generated_at": iso_now(),
        "source_runtime": str(STAGING_ROOT / "evidence-packs"),
        "latest_evidence_pack": {
            "pack_id": safe_str(latest_pack.get("pack_id")),
            "generated_at": safe_str(latest_pack.get("generated_at")),
            "summary_counts": safe_dict(summary.get("summary_counts")),
            "readiness_score": safe_float(summary.get("readiness_score"), 0.0),
            "readiness_grade": safe_str(summary.get("readiness_grade"), "not_ready"),
            "trend": safe_str(summary.get("trend"), "unknown"),
            "history_count": safe_int(summary.get("history_count"), 0),
        },
        "rehearsal_history_summary": {
            "count": safe_int(rehearsal_history.get("count"), 0),
            "runs": safe_list(rehearsal_history.get("runs")),
            "trend_summary": safe_dict(rehearsal_history.get("trend_summary")),
            "cadence": safe_dict(rehearsal_history.get("cadence")),
        },
        "readiness_summary": {
            "readiness_score": readiness_score,
            "readiness_grade": safe_str(readiness.get("readiness_grade"), "not_ready"),
            "trend_summary": trend_summary(readiness),
            "metrics": safe_dict(readiness.get("metrics")),
            "thresholds": safe_dict(readiness.get("thresholds")),
            "warning_threshold_indicators": safe_dict(readiness.get("warning_threshold_indicators")),
            "cadence": safe_dict(readiness.get("cadence")),
        },
        "PASS/WARN/FAIL_trends": {
            "summary": safe_dict(trends.get("summary")),
            "latest_run_counts": safe_dict(trends.get("latest_run_counts")),
        },
        "rollback_evidence_summary": rollback,
        "queue_stability_summary": queue,
        "telemetry_health_summary": telemetry,
        "submission_lock_verification": submission_lock,
        "dry_run_enforcement_verification": dry_run,
        "no_go_condition_summary": {
            "status": "PASS" if not no_go else "FAIL",
            "indicators": no_go_indicators,
        },
        "operator_sign_off_section": {
            "items": operator_checklist,
            "guidance": operator_sign_off,
        },
        "governance_review_section": {
            "items": governance_checklist,
            "guidance": governance_review_section,
        },
        "pilot_authorization_recommendation": recommendation,
        "evidence_pack_history": safe_list(history.get("packs")),
    }

    summary_counts = {
        "PASS": 0,
        "WARN": 0,
        "FAIL": 0,
    }
    summary_counts["PASS"] += 1 if readiness_pass else 0
    summary_counts["WARN"] += 1 if not readiness_pass and not no_go else 0
    summary_counts["FAIL"] += 1 if no_go else 0
    summary_counts["PASS"] += 1 if status_from_bool(safe_str(submission_lock.get("status"), "") == "PASS") == "PASS" else 0
    summary_counts["PASS"] += 1 if status_from_bool(safe_str(dry_run.get("status"), "") == "PASS") == "PASS" else 0

    payload["summary_counts"] = summary_counts
    payload["safety_guarantees"] = {
        "live_submissions": False,
        "production_credentials": False,
        "irreversible_operations": False,
        "production_database_access": False,
        "production_queue_access": False,
    }
    return payload


def markdown_summary(payload: Dict[str, Any]) -> str:
    readiness = safe_dict(payload.get("readiness_summary"))
    rehearsal = safe_dict(payload.get("rehearsal_history_summary"))
    trends = safe_dict(payload.get("PASS/WARN/FAIL_trends"))
    lock = safe_dict(payload.get("submission_lock_verification"))
    dry_run = safe_dict(payload.get("dry_run_enforcement_verification"))
    no_go = safe_dict(payload.get("no_go_condition_summary"))
    recommendation = safe_str(payload.get("pilot_authorization_recommendation"), "do_not_authorise")

    lines = [
        "# Pilot Rehearsal Summary Export",
        "",
        f"- Export ID: `{payload['export_id']}`",
        f"- Generated At: `{payload['generated_at']}`",
        f"- Recommendation: `{recommendation}`",
        "",
        format_section(
            "Readiness Score Summary",
            [
                f"Score: `{safe_float(readiness.get('readiness_score'), 0.0):.2f}`",
                f"Grade: `{safe_str(readiness.get('readiness_grade'), 'not_ready')}`",
                f"Trend: `{safe_str(safe_dict(readiness.get('trend_summary')).get('trend'), 'unknown')}`",
                f"Delta: `{safe_float(safe_dict(readiness.get('trend_summary')).get('delta'), 0.0):.2f}`",
                f"Thresholds: `{json.dumps(safe_dict(readiness.get('thresholds')), sort_keys=True)}`",
            ],
        ),
        format_section(
            "PASS/WARN/FAIL Trends",
            [
                f"Summary: `{json.dumps(safe_dict(trends.get('summary')), sort_keys=True)}`",
                f"Latest Run Counts: `{json.dumps(safe_dict(trends.get('latest_run_counts')), sort_keys=True)}`",
                f"Rehearsal Runs: `{safe_int(rehearsal.get('count'), 0)}`",
            ],
        ),
        format_section(
            "Rehearsal Cadence Summary",
            [
                f"Runs in history: `{safe_int(rehearsal.get('count'), 0)}`",
                f"Cadence: `{json.dumps(safe_dict(rehearsal.get('cadence')), sort_keys=True)}`",
                f"Trend summary: `{json.dumps(safe_dict(rehearsal.get('trend_summary')), sort_keys=True)}`",
            ],
        ),
        format_section(
            "Rollback / Queue / Telemetry",
            [
                f"Rollback evidence: `{json.dumps(safe_dict(payload.get('rollback_evidence_summary')), sort_keys=True)}`",
                f"Queue stability: `{json.dumps(safe_dict(payload.get('queue_stability_summary')), sort_keys=True)}`",
                f"Telemetry health: `{json.dumps(safe_dict(payload.get('telemetry_health_summary')), sort_keys=True)}`",
            ],
        ),
        format_section(
            "Submission Lock Verification",
            [
                f"Status: `{safe_str(lock.get('status'), 'unknown')}`",
                f"Evidence: `{json.dumps(safe_dict(lock.get('evidence')), sort_keys=True)}`",
            ],
        ),
        format_section(
            "Dry-Run Enforcement Verification",
            [
                f"Status: `{safe_str(dry_run.get('status'), 'unknown')}`",
                f"Evidence: `{json.dumps(safe_dict(dry_run.get('evidence')), sort_keys=True)}`",
            ],
        ),
        format_section(
            "NO-GO Condition Summary",
            [
                f"Status: `{safe_str(no_go.get('status'), 'unknown')}`",
                f"Indicators: `{json.dumps(safe_list(no_go.get('indicators')), ensure_ascii=False)}`",
            ],
        ),
        format_section(
            "Operator Sign-Off",
            [f"{idx + 1}. {item}" for idx, item in enumerate(safe_list(safe_dict(payload.get('operator_sign_off_section')).get('guidance')))],
        ),
        format_section(
            "Governance Review",
            [f"{idx + 1}. {item}" for idx, item in enumerate(safe_list(safe_dict(payload.get('governance_review_section')).get('guidance')))],
        ),
        format_section(
            "Pilot Authorization Recommendation",
            [
                f"Recommendation: `{recommendation}`",
                "This export is read-only, staging-only, and does not enable live submission controls.",
            ],
        ),
        format_section(
            "Safety Notes",
            [
                "No production credentials are included.",
                "No irreversible actions are enabled.",
                "No live submissions are triggered by this export.",
            ],
        ),
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    from app.services.pilot_evidence_pack_service import PilotEvidencePackService

    service = PilotEvidencePackService()
    payload = build_export_payload(service)
    export_id = safe_str(payload.get("export_id"), f"{export_timestamp()}-pilot-{uuid.uuid4().hex[:8]}")
    export_dir = EXPORT_ROOT / export_id
    export_dir.mkdir(parents=True, exist_ok=True)

    json_path = export_dir / "pilot_rehearsal_summary.json"
    md_path = export_dir / "pilot_rehearsal_summary.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown_summary(payload), encoding="utf-8")

    latest_path = EXPORT_ROOT / "latest_pilot_rehearsal_summary.json"
    latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Pilot rehearsal summary export generated: {export_dir}")
    print(f"Readiness score: {safe_float(safe_dict(payload.get('readiness_summary')).get('readiness_score'), 0.0):.2f}")
    print(f"Summary counts: {payload.get('summary_counts')}")
    print(f"NO-GO status: {safe_str(safe_dict(payload.get('no_go_condition_summary')).get('status'), 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
