from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PACK_ROOT = PROJECT_ROOT / "runtime" / "staging" / "evidence-packs"
DEFAULT_THRESHOLD = 85.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text if text else default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _load_pack(path: Path) -> Dict[str, Any]:
    payload = _read_json(path, {})
    return payload if isinstance(payload, dict) else {}


def _pack_dirs() -> List[Path]:
    if not EVIDENCE_PACK_ROOT.exists():
        return []
    runs = [
        path
        for path in EVIDENCE_PACK_ROOT.iterdir()
        if path.is_dir() and (path / "pilot_evidence_pack.json").exists()
    ]
    runs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return runs


def _pack_summary(pack: Dict[str, Any], pack_dir: Path) -> Dict[str, Any]:
    readiness = _safe_dict(pack.get("readiness_summary"))
    history = _safe_dict(pack.get("rehearsal_history_summary"))
    trends = _safe_dict(pack.get("PASS/WARN/FAIL trends"))
    counts = _safe_dict(pack.get("summary_counts"))
    return {
        "pack_id": _safe_str(pack.get("pack_id"), pack_dir.name),
        "generated_at": _safe_str(pack.get("generated_at"), _now_iso()),
        "summary_counts": {
            "PASS": _safe_int(counts.get("PASS"), 0),
            "WARN": _safe_int(counts.get("WARN"), 0),
            "FAIL": _safe_int(counts.get("FAIL"), 0),
        },
        "readiness_score": _safe_float(readiness.get("readiness_score"), 0.0),
        "readiness_grade": _safe_str(readiness.get("readiness_grade"), "not_ready"),
        "trend": _safe_str(_safe_dict(readiness.get("trend_summary")).get("trend"), "unknown"),
        "cadence": _safe_dict(readiness.get("cadence")),
        "history_count": _safe_int(history.get("count"), 0),
        "trend_summary": _safe_dict(trends.get("summary")),
        "artifact_paths": _safe_dict(pack.get("artifact_paths")),
        "evidence_sections": {
            "retry_recovery_evidence": _safe_dict(pack.get("retry_recovery_evidence")),
            "rollback_evidence": _safe_dict(pack.get("rollback_evidence")),
            "queue_stability_evidence": _safe_dict(pack.get("queue_stability_evidence")),
            "worker_stability_evidence": _safe_dict(pack.get("worker_stability_evidence")),
            "telemetry_health_evidence": _safe_dict(pack.get("telemetry_health_evidence")),
            "submission_lock_verification": _safe_dict(pack.get("submission_lock_verification")),
            "dry_run_enforcement_verification": _safe_dict(pack.get("dry_run_enforcement_verification")),
            "operator_intervention_summary": _safe_dict(pack.get("operator_intervention_summary")),
        },
    }


def _review_check(label: str, passed: bool, evidence: Dict[str, Any], required: bool = True, failure_note: str = "") -> Dict[str, Any]:
    return {
        "label": label,
        "required": required,
        "status": "PASS" if passed else "FAIL" if required else "WARN",
        "evidence": evidence,
        "note": failure_note if not passed else "",
    }


class PilotEvidencePackService:
    def _latest_pack_dir(self) -> Optional[Path]:
        packs = _pack_dirs()
        return packs[0] if packs else None

    def list_packs(self, limit: int = 20) -> Dict[str, Any]:
        packs = [_pack_summary(_load_pack(path / "pilot_evidence_pack.json"), path) for path in _pack_dirs()[: max(1, int(limit))]]
        latest = packs[0] if packs else {}
        return {
            "status": "ok",
            "count": len(packs),
            "packs": packs,
            "latest_pack_id": _safe_str(latest.get("pack_id")),
            "latest_generated_at": _safe_str(latest.get("generated_at")),
        }

    def latest_pack(self) -> Dict[str, Any]:
        latest_dir = self._latest_pack_dir()
        if latest_dir is None:
            return {
                "status": "not_found",
                "message": "No pilot evidence packs have been generated yet.",
                "pack": {},
                "pilot_authorization_status": "pending_review",
                "no_go_indicators": ["No pilot evidence pack is available."],
                "operator_sign_off_checklist": [],
                "governance_review_checklist": [],
            }
        pack = _load_pack(latest_dir / "pilot_evidence_pack.json")
        summary = _pack_summary(pack, latest_dir)
        return {
            "status": "ok",
            "pack": pack,
            "summary": summary,
            "pack_id": summary.get("pack_id", latest_dir.name),
            "generated_at": summary.get("generated_at", _now_iso()),
        }

    def get_pack(self, pack_id: str) -> Dict[str, Any]:
        target = EVIDENCE_PACK_ROOT / str(pack_id)
        pack_file = target / "pilot_evidence_pack.json"
        if not pack_file.exists():
            return {
                "status": "not_found",
                "pack_id": pack_id,
                "message": "Pilot evidence pack not found.",
            }
        pack = _load_pack(pack_file)
        return {
            "status": "ok",
            "pack": pack,
            "summary": _pack_summary(pack, target),
            "pack_id": _safe_str(pack.get("pack_id"), pack_id),
            "generated_at": _safe_str(pack.get("generated_at"), _now_iso()),
        }

    def governance_review(self) -> Dict[str, Any]:
        latest = self.latest_pack()
        if latest.get("status") != "ok":
            return latest

        pack = _safe_dict(latest.get("pack"))
        summary = _safe_dict(latest.get("summary"))
        readiness = _safe_dict(pack.get("readiness_summary"))
        history = _safe_dict(pack.get("rehearsal_history_summary"))
        trends = _safe_dict(pack.get("PASS/WARN/FAIL trends"))
        sections = _safe_dict(pack)
        evidence_sections = {
            "rollback_evidence": _safe_dict(sections.get("rollback_evidence")),
            "queue_stability_evidence": _safe_dict(sections.get("queue_stability_evidence")),
            "telemetry_health_evidence": _safe_dict(sections.get("telemetry_health_evidence")),
            "submission_lock_verification": _safe_dict(sections.get("submission_lock_verification")),
            "dry_run_enforcement_verification": _safe_dict(sections.get("dry_run_enforcement_verification")),
            "operator_intervention_summary": _safe_dict(sections.get("operator_intervention_summary")),
        }

        readiness_score = _safe_float(readiness.get("readiness_score"), 0.0)
        readiness_threshold = _safe_float(_safe_dict(readiness.get("thresholds")).get("readiness_score"), DEFAULT_THRESHOLD)
        checklist = [
            _review_check("Evidence pack available", True, {"pack_id": summary.get("pack_id")}),
            _review_check("Readiness score meets threshold", readiness_score >= readiness_threshold, {"readiness_score": readiness_score, "threshold": readiness_threshold}),
            _review_check("PASS/WARN/FAIL history available", _safe_int(history.get("count"), 0) > 0, {"history_count": _safe_int(history.get("count"), 0)}),
            _review_check("Rollback evidence present", _safe_str(_safe_dict(evidence_sections["rollback_evidence"]).get("status"), "") == "PASS", evidence_sections["rollback_evidence"]),
            _review_check("Queue stability evidence present", _safe_str(_safe_dict(evidence_sections["queue_stability_evidence"]).get("status"), "") == "PASS", evidence_sections["queue_stability_evidence"]),
            _review_check("Telemetry health evidence present", _safe_str(_safe_dict(evidence_sections["telemetry_health_evidence"]).get("status"), "") == "PASS", evidence_sections["telemetry_health_evidence"]),
            _review_check("Submission lock verified", _safe_str(_safe_dict(evidence_sections["submission_lock_verification"]).get("status"), "") == "PASS", evidence_sections["submission_lock_verification"]),
            _review_check("Dry-run enforcement verified", _safe_str(_safe_dict(evidence_sections["dry_run_enforcement_verification"]).get("status"), "") == "PASS", evidence_sections["dry_run_enforcement_verification"]),
        ]

        no_go_indicators = [
            item["label"]
            for item in checklist
            if item["required"] and item["status"] != "PASS"
        ]
        operator_sign_off_checklist = [
            {
                "item": "Confirm latest evidence pack reviewed",
                "required": True,
                "status": "PASS",
            },
            {
                "item": "Confirm dry-run protections remain active",
                "required": True,
                "status": "PASS" if _safe_dict(evidence_sections["dry_run_enforcement_verification"]).get("status") == "PASS" else "FAIL",
            },
            {
                "item": "Confirm submission locks remain enforced",
                "required": True,
                "status": "PASS" if _safe_dict(evidence_sections["submission_lock_verification"]).get("status") == "PASS" else "FAIL",
            },
        ]
        governance_review_checklist = [
            {
                "item": "Review readiness score and trend",
                "status": "PASS" if readiness_score >= readiness_threshold else "FAIL",
            },
            {
                "item": "Review rehearsal cadence",
                "status": "PASS" if _safe_int(_safe_dict(readiness.get("cadence")).get("runs_last_7_days"), 0) > 0 else "WARN",
            },
            {
                "item": "Review rollback, queue, telemetry and submission-lock evidence",
                "status": "PASS" if not no_go_indicators else "WARN",
            },
        ]
        pilot_authorization_status = "authorized" if not no_go_indicators and readiness_score >= readiness_threshold else "not_authorized"
        warning_banners = []
        if pilot_authorization_status != "authorized":
            warning_banners.append("Pilot authorization is not granted. Review the NO-GO indicators before proceeding.")

        return {
            "status": "ok",
            "generated_at": _now_iso(),
            "latest_evidence_pack": latest,
            "readiness_score": readiness_score,
            "readiness_grade": _safe_str(readiness.get("readiness_grade"), "not_ready"),
            "PASS/WARN/FAIL_history": {
                "trend_summary": _safe_dict(readiness.get("trend_summary")),
                "cadence": _safe_dict(readiness.get("cadence")),
                "history": _safe_list(history.get("runs")),
                "trends": _safe_dict(trends.get("summary")),
            },
            "rehearsal_cadence": _safe_dict(readiness.get("cadence")),
            "rollback_evidence": evidence_sections["rollback_evidence"],
            "queue_stability_evidence": evidence_sections["queue_stability_evidence"],
            "telemetry_health_evidence": evidence_sections["telemetry_health_evidence"],
            "submission_lock_verification": evidence_sections["submission_lock_verification"],
            "operator_sign_off_checklist": operator_sign_off_checklist,
            "governance_review_checklist": governance_review_checklist,
            "pilot_authorization_status": pilot_authorization_status,
            "no_go_indicators": no_go_indicators,
            "staging_warning_banners": warning_banners,
            "evidence_summary": summary,
            "evidence_sections": evidence_sections,
            "readiness_threshold": readiness_threshold,
        }
