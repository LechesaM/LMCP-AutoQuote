from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_VALIDATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "production-deployment-validations"
LATEST_VALIDATION_FILE = PRODUCTION_VALIDATION_ROOT / "latest_production_deployment_validation.json"
SECTION_STATUS_KEYS = {
    "runtime_segmentation": ("production_runtime_segmentation_status", "status"),
    "operator_access": ("operator_access_governance_status", "status"),
    "observability": ("production_observability_governance_status", "status"),
    "backup_restore": ("backup_restore_governance_status", "status"),
    "disaster_recovery": ("disaster_recovery_governance_status", "status"),
    "high_availability": ("high_availability_governance_status", "status"),
    "audit_retention": ("audit_retention_governance_status", "status"),
    "deployment_readiness": ("deployment_readiness_governance_status", "status"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _authority_from_status(status: str) -> str:
    normalized = _safe_str(status, "watch").lower()
    if normalized == "ok":
        return "GO"
    if normalized == "watch":
        return "WATCH"
    return "NO_GO"


def _normalize_section_status(value: Any) -> str:
    normalized = _safe_str(value, "FAIL").upper()
    if normalized in {"OK", "PASS", "READY"}:
        return "PASS"
    if normalized in {"WATCH", "WARN"}:
        return "WARN"
    if normalized in {"BLOCKED", "FAIL", "NO_GO"}:
        return "FAIL"
    return "FAIL"


def _trend_from_delta(delta: float) -> str:
    if delta > 2.0:
        return "improving"
    if delta < -2.0:
        return "declining"
    return "stable"


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    return {
        "trend": _trend_from_delta(delta),
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


class ProductionReleaseGovernanceService:
    def __init__(self, validation_root: Optional[Path] = None) -> None:
        self.validation_root = validation_root or PRODUCTION_VALIDATION_ROOT

    def _bundle_files(self) -> List[Path]:
        if not self.validation_root.exists():
            return []
        bundles = [
            path / "production_deployment_validation.json"
            for path in self.validation_root.iterdir()
            if path.is_dir() and (path / "production_deployment_validation.json").exists()
        ]
        bundles.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return bundles

    def _load_payloads(self, limit: int = 20) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        for bundle_path in self._bundle_files()[: max(1, int(limit))]:
            payload = _read_json(bundle_path, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(bundle_path)
                payloads.append(payload)
        if not payloads and LATEST_VALIDATION_FILE.exists():
            payload = _read_json(LATEST_VALIDATION_FILE, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(LATEST_VALIDATION_FILE)
                payloads.append(payload)
        return payloads

    def _section_status(self, sections: Dict[str, Any], key: str) -> str:
        section = _safe_dict(sections.get(key))
        for field in SECTION_STATUS_KEYS.get(key, ("status",)):
            status = _safe_str(section.get(field), "")
            if status:
                return _normalize_section_status(status)
        return "FAIL"

    def _extract_blockers(self, payload: Dict[str, Any]) -> List[str]:
        blockers: List[str] = []
        env = _safe_dict(payload.get("environment_safety"))
        lock = _safe_dict(payload.get("submission_lock_verification"))
        dry_run = _safe_dict(payload.get("dry_run_enforcement_verification"))
        risk = _safe_dict(payload.get("deployment_risk_summary"))
        sections = _safe_dict(payload.get("validation_sections"))
        warnings = _safe_list(payload.get("warnings"))

        blockers.extend(_safe_list(env.get("blockers")))
        if not _safe_str(lock.get("status"), "FAIL") == "PASS":
            blockers.append("submission lock not verified")
        if not _safe_str(dry_run.get("status"), "PASS") == "PASS":
            blockers.append("dry-run enforcement not verified")
        if _safe_str(payload.get("overall_status"), "FAIL") == "FAIL":
            blockers.append("overall production validation failed")
        if risk.get("deployment_risk"):
            blockers.append("deployment risk elevated")
        for key in ("runtime_segmentation", "operator_access", "observability", "backup_restore", "disaster_recovery", "high_availability", "audit_retention", "deployment_readiness"):
            if self._section_status(sections, key) == "FAIL":
                blockers.append(f"{key.replace('_', ' ')} blocked")
        blockers.extend(warnings)
        cleaned: List[str] = []
        for blocker in blockers:
            text = _safe_str(blocker)
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _release_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        readiness = _safe_dict(payload.get("readiness_summary"))
        sections = _safe_dict(payload.get("validation_sections"))
        validation_counts = _safe_dict(payload.get("validation_counts"))
        blockers = self._extract_blockers(payload)
        score = _safe_float(readiness.get("production_readiness_score"), 0.0)
        overall_status = _safe_str(payload.get("overall_status"), "FAIL").upper()
        authority = "GO" if overall_status == "PASS" and score >= 85.0 and not blockers else "WATCH" if overall_status == "WARN" or score >= 70.0 else "NO_GO"
        release_status = _status_from_score(score)
        if blockers and authority == "GO":
            authority = "WATCH"
            release_status = "watch"
        deployment_risk_indicators = {
            "deployment_risk": bool(_safe_dict(payload.get("deployment_risk_summary")).get("deployment_risk")) or authority == "NO_GO",
            "runtime_segmentation_risk": self._section_status(sections, "runtime_segmentation") == "FAIL",
            "operator_access_risk": self._section_status(sections, "operator_access") != "PASS" or bool(_safe_dict(payload.get("operator_access_risk_indicators")).get("operator_access_risk")),
            "observability_risk": self._section_status(sections, "observability") != "PASS",
            "backup_restore_risk": self._section_status(sections, "backup_restore") != "PASS",
            "disaster_recovery_risk": self._section_status(sections, "disaster_recovery") != "PASS",
            "high_availability_risk": self._section_status(sections, "high_availability") != "PASS",
            "audit_retention_risk": self._section_status(sections, "audit_retention") != "PASS",
        }
        operational_release_indicators = {
            "submission_lock_verified": _safe_str(_safe_dict(payload.get("submission_lock_verification")).get("status"), "FAIL") == "PASS",
            "dry_run_verified": _safe_str(_safe_dict(payload.get("dry_run_enforcement_verification")).get("status"), "FAIL") == "PASS",
            "environment_safe": _safe_str(_safe_dict(payload.get("environment_safety")).get("status"), "FAIL") == "PASS",
            "history_available": True,
            "overall_validation_passed": overall_status == "PASS",
        }
        release_readiness_indicators = {
            "runtime_segmentation_ready": self._section_status(sections, "runtime_segmentation") == "PASS",
            "operator_access_ready": self._section_status(sections, "operator_access") == "PASS",
            "observability_ready": self._section_status(sections, "observability") == "PASS",
            "backup_restore_ready": self._section_status(sections, "backup_restore") == "PASS",
            "disaster_recovery_ready": self._section_status(sections, "disaster_recovery") == "PASS",
            "high_availability_ready": self._section_status(sections, "high_availability") == "PASS",
            "audit_retention_ready": self._section_status(sections, "audit_retention") == "PASS",
            "deployment_governance_ready": self._section_status(sections, "deployment_readiness") == "PASS",
            "submission_lock_ready": operational_release_indicators["submission_lock_verified"],
            "dry_run_ready": operational_release_indicators["dry_run_verified"],
        }
        release_authority_indicators = {
            "go_release_authority": authority == "GO",
            "watch_release_authority": authority == "WATCH",
            "no_go_release_authority": authority == "NO_GO",
            "active_authority": authority,
        }
        release_governance_score = round(mean([
            score,
            100.0 if operational_release_indicators["submission_lock_verified"] else 0.0,
            100.0 if operational_release_indicators["dry_run_verified"] else 0.0,
            100.0 if operational_release_indicators["environment_safe"] else 0.0,
        ]), 2)
        if authority == "NO_GO":
            release_governance_status = "blocked"
        elif authority == "WATCH":
            release_governance_status = "watch"
        else:
            release_governance_status = "ok"
        release_governance_grade = "ready" if authority == "GO" else "watch" if authority == "WATCH" else "blocked"
        history = _safe_list(payload.get("governance_validation_history"))
        entry = {
            "analysis_id": f"{_safe_str(payload.get('validation_id'), 'validation')}:release-gate",
            "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
            "validation_id": _safe_str(payload.get("validation_id"), ""),
            "production_readiness_score": score,
            "release_governance_score": release_governance_score,
            "release_governance_status": release_governance_status,
            "release_governance_authority": authority,
            "release_governance_grade": release_governance_grade,
            "production_rollout_readiness": authority == "GO",
            "production_rollout_readiness_status": release_governance_grade,
            "deployment_risk_indicators": deployment_risk_indicators,
            "operational_release_indicators": operational_release_indicators,
            "release_readiness_indicators": release_readiness_indicators,
            "release_authority_indicators": release_authority_indicators,
            "unresolved_deployment_blockers": blockers,
            "governance_override_authority": authority in {"WATCH", "NO_GO"},
            "release_escalation_authority": authority != "GO",
            "release_governance_history": history[: max(1, len(history))],
            "validation_counts": validation_counts,
            "summary_components": _safe_dict(payload.get("readiness_summary")).get("summary_components", {}),
            "warnings": blockers,
        }
        return entry

    def list_release_governance(self, limit: int = 20) -> Dict[str, Any]:
        payloads = self._load_payloads(limit=limit)
        if not payloads:
            return {"status": "not_found", "message": "No production deployment validation history has been recorded yet.", "release_governance": {}}
        entries = [self._release_entry(payload) for payload in payloads]
        latest = entries[0]
        history_scores = [entry["release_governance_score"] for entry in entries]
        overall_score = latest["release_governance_score"]
        release_status = latest["release_governance_status"]
        if release_status == "ok":
            warnings: List[str] = []
        else:
            warnings = _safe_list(latest.get("warnings"))
        if latest["release_governance_authority"] == "NO_GO" and "release gate blocked" not in warnings:
            warnings.append("release gate blocked")
        return {
            "status": release_status,
            "generated_at": _now_iso(),
            "analysis_id": latest["analysis_id"],
            "release_governance_status": release_status,
            "release_governance_authority": latest["release_governance_authority"],
            "release_governance_score": overall_score,
            "release_governance_grade": latest["release_governance_grade"],
            "production_rollout_readiness": latest["production_rollout_readiness"],
            "production_rollout_readiness_status": latest["production_rollout_readiness_status"],
            "deployment_risk_indicators": latest["deployment_risk_indicators"],
            "operational_release_indicators": latest["operational_release_indicators"],
            "release_readiness_indicators": latest["release_readiness_indicators"],
            "release_authority_indicators": latest["release_authority_indicators"],
            "unresolved_deployment_blockers": latest["unresolved_deployment_blockers"],
            "governance_override_authority": latest["governance_override_authority"],
            "release_escalation_authority": latest["release_escalation_authority"],
            "release_governance_history": entries,
            "latest_release_governance": latest,
            "release_governance_history_summary": {
                "analysis_count": len(entries),
                "latest_analysis_id": latest["analysis_id"],
                "latest_score": overall_score,
                "score_history": _history_points(history_scores),
            },
            "summary_components": latest.get("summary_components", {}),
            "warnings": warnings,
        }

    def latest_release_governance(self) -> Dict[str, Any]:
        response = self.list_release_governance(limit=20)
        if response.get("status") == "not_found":
            return {"status": "not_found", "message": "No production release governance history has been recorded yet.", "release_governance": {}}
        return {
            "status": response.get("status", "ok"),
            "release_governance_status": response.get("release_governance_status", "watch"),
            "release_governance_authority": response.get("release_governance_authority", "WATCH"),
            "release_governance_grade": response.get("release_governance_grade", "blocked"),
            "release_governance_score": response.get("release_governance_score", 0.0),
            "latest_release_governance": response.get("latest_release_governance", {}),
            "release_governance_history": response.get("release_governance_history", []),
            "release_governance_history_summary": response.get("release_governance_history_summary", {}),
            "deployment_risk_indicators": response.get("deployment_risk_indicators", {}),
            "operational_release_indicators": response.get("operational_release_indicators", {}),
            "release_readiness_indicators": response.get("release_readiness_indicators", {}),
            "release_authority_indicators": response.get("release_authority_indicators", {}),
            "unresolved_deployment_blockers": response.get("unresolved_deployment_blockers", []),
            "governance_override_authority": response.get("governance_override_authority", False),
            "release_escalation_authority": response.get("release_escalation_authority", False),
            "production_rollout_readiness": response.get("production_rollout_readiness", False),
            "production_rollout_readiness_status": response.get("production_rollout_readiness_status", "blocked"),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }

    def release_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_release_governance(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("release_governance_history", [])),
            "release_governance_history": response.get("release_governance_history", []),
            "release_governance_history_summary": response.get("release_governance_history_summary", {}),
            "deployment_risk_indicators": response.get("deployment_risk_indicators", {}),
            "operational_release_indicators": response.get("operational_release_indicators", {}),
            "release_readiness_indicators": response.get("release_readiness_indicators", {}),
            "release_authority_indicators": response.get("release_authority_indicators", {}),
            "unresolved_deployment_blockers": response.get("unresolved_deployment_blockers", []),
            "governance_override_authority": response.get("governance_override_authority", False),
            "release_escalation_authority": response.get("release_escalation_authority", False),
            "production_rollout_readiness": response.get("production_rollout_readiness", False),
            "production_rollout_readiness_status": response.get("production_rollout_readiness_status", "blocked"),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }
