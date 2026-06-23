from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROLLOUT_VALIDATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "production-rollout-validations"
LATEST_ROLLOUT_VALIDATION_FILE = ROLLOUT_VALIDATION_ROOT / "latest_production_rollout_validation.json"
RELEASE_CERTIFICATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "release-certifications"
LATEST_RELEASE_CERTIFICATION_FILE = RELEASE_CERTIFICATION_ROOT / "latest_executive_release_evidence.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


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


def _bool_score(value: Any) -> float:
    return 100.0 if bool(value) else 0.0


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified"}
    return bool(value)


def _records_all_pass(records: List[Any]) -> bool:
    if not records:
        return False
    for record in records:
        if isinstance(record, dict):
            status = _safe_str(record.get("status"), "").upper()
            if status and status != "PASS":
                return False
            if "ready" in record and not _truthy(record.get("ready")):
                return False
            if "status" not in record and "ready" not in record and not any(_truthy(value) for value in record.values()):
                return False
        elif not _truthy(record):
            return False
    return True


class ProductionContinuityGovernanceService:
    def __init__(
        self,
        validation_root: Optional[Path] = None,
        release_certification_root: Optional[Path] = None,
    ) -> None:
        self.validation_root = validation_root or ROLLOUT_VALIDATION_ROOT
        self.release_certification_root = release_certification_root or RELEASE_CERTIFICATION_ROOT

    def _bundle_files(self) -> List[Path]:
        if not self.validation_root.exists():
            return []
        bundles = [
            path / "production_rollout_validation.json"
            for path in self.validation_root.iterdir()
            if path.is_dir() and (path / "production_rollout_validation.json").exists()
        ]
        bundles.sort(
            key=lambda path: (
                _parse_iso((_read_json(path, {}) or {}).get("generated_at")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                path.name,
            ),
            reverse=True,
        )
        return bundles

    def _load_rollout_payloads(self, limit: int = 20) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        for bundle_path in self._bundle_files()[: max(1, int(limit))]:
            payload = _read_json(bundle_path, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(bundle_path)
                payloads.append(payload)
        if not payloads and LATEST_ROLLOUT_VALIDATION_FILE.exists():
            payload = _read_json(LATEST_ROLLOUT_VALIDATION_FILE, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(LATEST_ROLLOUT_VALIDATION_FILE)
                payloads.append(payload)
        return payloads

    def _release_bundle_files(self) -> List[Path]:
        if not self.release_certification_root.exists():
            return []
        bundles = [
            path / "executive_release_evidence.json"
            for path in self.release_certification_root.iterdir()
            if path.is_dir() and (path / "executive_release_evidence.json").exists()
        ]
        bundles.sort(
            key=lambda path: (
                _parse_iso((_read_json(path, {}) or {}).get("generated_at")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                path.name,
            ),
            reverse=True,
        )
        return bundles

    def _latest_rollout_payload(self) -> Dict[str, Any]:
        payloads = self._load_rollout_payloads(limit=1)
        return payloads[0] if payloads else {}

    def _latest_release_certification(self) -> Dict[str, Any]:
        if LATEST_RELEASE_CERTIFICATION_FILE.exists():
            payload = _read_json(LATEST_RELEASE_CERTIFICATION_FILE, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(LATEST_RELEASE_CERTIFICATION_FILE)
                return payload
        release_bundles = self._release_bundle_files()
        if release_bundles:
            payload = _read_json(release_bundles[0], {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(release_bundles[0])
                return payload
        payload = self._latest_rollout_payload()
        return _safe_dict(payload.get("release_certification_snapshot")) or _safe_dict(payload.get("latest_release_certification"))

    def _history_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rollout_readiness = _safe_dict(payload.get("rollout_readiness_summary"))
        tenant = _safe_dict(payload.get("tenant_isolation_summary"))
        operator = _safe_dict(payload.get("operator_onboarding_readiness_summary"))
        supervision = _safe_dict(payload.get("supervision_readiness_summary"))
        deployment_health = _safe_dict(payload.get("deployment_health_summary"))
        observability = _safe_dict(payload.get("production_observability_summary"))
        escalation = _safe_dict(payload.get("escalation_chain_summary"))
        institutional = _safe_dict(payload.get("institutional_rollout_certification_evidence"))
        latest_release = _safe_dict(payload.get("latest_release_certification"))
        release_snapshot = _safe_dict(payload.get("release_certification_snapshot"))
        release_certification = self._latest_release_certification()

        warnings = [warning for warning in _safe_list(payload.get("warnings")) if _safe_str(warning)]
        readiness_score = _safe_float(rollout_readiness.get("rollout_readiness_score"), 0.0)
        recovery_drills = _safe_list(payload.get("recovery_drill_readiness"))
        dr_rehearsals = _safe_list(payload.get("disaster_recovery_rehearsal_status"))
        operator_failover = _safe_list(payload.get("operator_failover_readiness"))
        supervision_continuity = _safe_list(payload.get("supervision_continuity_readiness"))
        continuity_freeze = _safe_list(payload.get("continuity_freeze_indicators"))
        freeze_history = _safe_list(payload.get("operational_freeze_history"))
        recovery_escalation = _safe_list(payload.get("recovery_escalation_readiness"))
        recovery_timing = _safe_list(payload.get("recovery_timing_indicators"))
        continuity_ready = all(
            [
                _truthy(rollout_readiness.get("tenant_isolation_ready")),
                _truthy(rollout_readiness.get("operator_availability_ready")),
                _truthy(rollout_readiness.get("active_supervision_coverage_ready")),
                _truthy(rollout_readiness.get("deployment_health_ready")),
                _truthy(rollout_readiness.get("production_observability_ready")),
                _truthy(rollout_readiness.get("release_authorization_valid")),
                _truthy(rollout_readiness.get("escalation_chain_ready")),
                _truthy(deployment_health.get("deployment_health_ready")),
                _truthy(observability.get("production_observability_ready")),
            ]
        )
        continuity_indicator_score = mean([
            100.0 if _records_all_pass(recovery_drills) else 0.0,
            100.0 if _records_all_pass(dr_rehearsals) else 0.0,
            100.0 if _records_all_pass(operator_failover) else 0.0,
            100.0 if _records_all_pass(supervision_continuity) else 0.0,
            100.0 if not continuity_freeze else 0.0,
            100.0 if _records_all_pass(recovery_escalation) else 0.0,
            100.0 if _records_all_pass(recovery_timing) else 0.0,
            100.0 if continuity_ready else 0.0,
        ])
        continuity_score = round((readiness_score * 0.75) + (continuity_indicator_score * 0.25), 2)
        continuity_status = _status_from_score(continuity_score)
        if continuity_freeze and any(_truthy(item.get("freeze_active")) for item in continuity_freeze):
            continuity_status = "watch" if continuity_status == "ok" else continuity_status
        continuity_authority = _authority_from_status(continuity_status)
        continuity_grade = "ready" if continuity_status == "ok" else "watch" if continuity_status == "watch" else "blocked"

        audit_retention_indicators = {
            "rollout_validation_retained": bool(self._bundle_files()),
            "latest_rollout_validation_retained": LATEST_ROLLOUT_VALIDATION_FILE.exists(),
            "release_certification_retained": bool(self._release_bundle_files()) or LATEST_RELEASE_CERTIFICATION_FILE.exists(),
            "latest_release_certification_retained": LATEST_RELEASE_CERTIFICATION_FILE.exists(),
            "institutional_continuity_history_retained": bool(recovery_drills or dr_rehearsals or operator_failover or supervision_continuity or continuity_freeze or recovery_escalation or recovery_timing),
            "retention_compliant": bool(self._bundle_files()) and (bool(self._release_bundle_files()) or LATEST_RELEASE_CERTIFICATION_FILE.exists()),
        }
        audit_completeness_indicators = {
            "recovery_drill_readiness_recorded": bool(recovery_drills),
            "dr_rehearsal_status_recorded": bool(dr_rehearsals),
            "operator_failover_readiness_recorded": bool(operator_failover),
            "supervision_continuity_readiness_recorded": bool(supervision_continuity),
            "continuity_freeze_indicators_recorded": bool(continuity_freeze),
            "recovery_escalation_readiness_recorded": bool(recovery_escalation),
            "recovery_timing_indicators_recorded": bool(recovery_timing),
            "operational_continuity_scoring_recorded": True,
            "continuity_governance_history_recorded": True,
        }
        continuity_history = [
            {
                "audit_type": "continuity_governance",
                "analysis_id": _safe_str(payload.get("validation_id"), "rollout"),
                "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                "continuity_score": round(continuity_score, 2),
                "continuity_status": continuity_status,
                "continuity_authority": continuity_authority,
                "continuity_grade": continuity_grade,
                "recovery_drill_count": len(recovery_drills),
                "dr_rehearsal_count": len(dr_rehearsals),
                "operator_failover_count": len(operator_failover),
                "supervision_continuity_count": len(supervision_continuity),
                "continuity_freeze_count": len(continuity_freeze),
            }
        ]

        history_payload = {
            "analysis_id": f"{_safe_str(payload.get('validation_id'), 'rollout')}:continuity-governance",
            "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
            "status": continuity_status,
            "continuity_governance_status": continuity_status,
            "continuity_governance_authority": continuity_authority,
            "continuity_governance_score": round(continuity_score, 2),
            "continuity_governance_grade": continuity_grade,
            "recovery_drill_readiness": recovery_drills,
            "disaster_recovery_rehearsal_status": dr_rehearsals,
            "operator_failover_readiness": operator_failover,
            "supervision_continuity_readiness": supervision_continuity,
            "continuity_freeze_indicators": continuity_freeze,
            "recovery_escalation_readiness": recovery_escalation,
            "recovery_timing_indicators": recovery_timing,
            "operational_continuity_scoring": {
                "score": round(continuity_score, 2),
                "status": continuity_status,
                "grade": continuity_grade,
                "indicator_score": round(continuity_indicator_score, 2),
            },
            "continuity_governance_history": continuity_history,
            "audit_retention_indicators": audit_retention_indicators,
            "audit_completeness_indicators": audit_completeness_indicators,
            "rollout_readiness_summary": {
                "rollout_readiness_score": readiness_score,
                "rollout_readiness_status": _safe_str(rollout_readiness.get("rollout_readiness_status"), "watch"),
                "rollout_readiness_grade": _safe_str(rollout_readiness.get("rollout_readiness_grade"), "watch"),
            },
            "latest_rollout_validation": payload,
            "latest_release_certification": latest_release,
            "release_certification_snapshot": release_snapshot or release_certification,
            "summary_counts": _safe_dict(payload.get("summary_counts")),
            "warnings": warnings
            + ([] if not continuity_freeze else ["Continuity freeze indicators are active."])
            + ([] if not recovery_drills else ["Recovery drill readiness recorded."])
            + ([] if not dr_rehearsals else ["Disaster recovery rehearsal status recorded."]),
        }
        return history_payload

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for payload in self._load_rollout_payloads(limit=limit):
            entry = self._history_entry(payload)
            entries.append(
                {
                    "analysis_id": entry["analysis_id"],
                    "generated_at": entry["generated_at"],
                    "continuity_governance_status": entry["continuity_governance_status"],
                    "continuity_governance_authority": entry["continuity_governance_authority"],
                    "continuity_governance_score": entry["continuity_governance_score"],
                    "continuity_governance_grade": entry["continuity_governance_grade"],
                    "audit_retention_indicators": entry["audit_retention_indicators"],
                    "audit_completeness_indicators": entry["audit_completeness_indicators"],
                    "operational_continuity_scoring": entry["operational_continuity_scoring"],
                    "summary_counts": entry["summary_counts"],
                }
            )
        return entries

    def list_continuity_governance(self, limit: int = 20) -> Dict[str, Any]:
        history = self._history(limit=limit)
        latest_payload = self._latest_rollout_payload()
        latest = self._history_entry(latest_payload) if latest_payload else self._history_entry({})
        scores = [float(item.get("continuity_governance_score", 0.0)) for item in history] or [latest["continuity_governance_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["continuity_governance_score"],
            "score_history": _history_points(scores),
        }
        return {
            "status": latest["status"],
            "continuity_governance_status": latest["continuity_governance_status"],
            "continuity_governance_authority": latest["continuity_governance_authority"],
            "continuity_governance_score": latest["continuity_governance_score"],
            "continuity_governance_grade": latest["continuity_governance_grade"],
            **latest,
            "latest_continuity_governance": latest,
            "continuity_governance_history": history[: max(1, int(limit))],
            "continuity_governance_history_summary": summary,
            "summary_counts": latest.get("summary_counts", {}),
            "warnings": latest.get("warnings", []),
        }

    def latest_continuity_governance(self) -> Dict[str, Any]:
        return self.list_continuity_governance(limit=1)

    def continuity_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_continuity_governance(limit=limit)
        history = latest["continuity_governance_history"]
        return {
            "status": latest["status"],
            "continuity_governance_status": latest["continuity_governance_status"],
            "continuity_governance_authority": latest["continuity_governance_authority"],
            "continuity_governance_score": latest["continuity_governance_score"],
            "continuity_governance_grade": latest["continuity_governance_grade"],
            "count": len(history),
            "continuity_governance_history": history,
            "continuity_governance_history_summary": latest["continuity_governance_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
