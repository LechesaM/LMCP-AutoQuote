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


class ProductionSupervisionCommandService:
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
        latest_file = self.release_certification_root / "latest_executive_release_evidence.json"
        if latest_file.exists():
            payload = _read_json(latest_file, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(latest_file)
                return payload
        release_bundles = self._release_bundle_files()
        if release_bundles:
            payload = _read_json(release_bundles[0], {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(release_bundles[0])
                return payload
        payload = self._latest_rollout_payload()
        return _safe_dict(payload.get("release_certification_snapshot")) or _safe_dict(payload.get("latest_release_certification"))

    def _entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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
        active_sessions = _safe_int(supervision.get("active_sessions"), 0)
        assigned_rfqs = _safe_list(supervision.get("assigned_rfqs"))
        pending_approvals = _safe_list(supervision.get("pending_approvals"))
        operator_name = _safe_str(operator.get("operator_name"), "staging-governance-operator")
        operator_role = _safe_str(operator.get("operator_role"), "governance_reviewer")
        operator_ready = _truthy(operator.get("approved_for_supervision")) and _truthy(operator.get("operator_availability_ready"))
        supervision_ready = _truthy(supervision.get("active_supervision_coverage_ready"))
        deployment_ready = _truthy(deployment_health.get("deployment_health_ready"))
        observability_ready = _truthy(observability.get("production_observability_ready"))
        escalation_ready = _truthy(escalation.get("escalation_chain_ready"))
        release_valid = _truthy(institutional.get("release_authorization_valid"))
        rollout_ready = _truthy(institutional.get("rollout_ready_for_supervised_deployment"))
        release_ready = _truthy(_safe_dict(release_certification.get("operational_readiness_certification")).get("overall_validation_passed", False))
        release_authority = _safe_str(latest_release.get("release_authority"), _safe_str(_safe_dict(release_certification.get("release_authority_certification")).get("active_authority"), "WATCH")).upper()
        release_certification_status = _safe_str(latest_release.get("certification_status"), _safe_str(_safe_dict(release_certification.get("governance_certification_summary")).get("certification_status"), "WATCH")).upper()
        release_governance_score = _safe_float(latest_release.get("certification_score"), _safe_float(_safe_dict(release_certification.get("governance_certification_summary")).get("certification_score"), 0.0))

        workload_items = len(assigned_rfqs) + len(pending_approvals)
        saturation_active = active_sessions > 1 or workload_items > 2
        freeze_active = not (operator_ready and supervision_ready and deployment_ready and observability_ready and escalation_ready and release_valid and release_ready and rollout_ready)
        lapse_active = not operator_ready or not supervision_ready or active_sessions == 0 or not escalation_ready

        command_score = round(
            mean(
                [
                    readiness_score,
                    _bool_score(operator_ready),
                    _bool_score(supervision_ready),
                    _bool_score(deployment_ready),
                    _bool_score(observability_ready),
                    _bool_score(escalation_ready),
                    _bool_score(release_valid),
                    _bool_score(release_ready),
                    _bool_score(rollout_ready),
                    _bool_score(not saturation_active),
                ]
            ),
            2,
        )
        if freeze_active or command_score < 70.0 or readiness_score < 70.0:
            status = "blocked"
        elif command_score < 85.0 or warnings:
            status = "watch"
        else:
            status = "ok"
        authority = _authority_from_status(status)
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"

        active_supervised_operators = [
            {
                "operator_name": operator_name,
                "operator_role": operator_role,
                "approved_for_supervision": bool(operator.get("approved_for_supervision")),
                "operator_availability_ready": bool(operator.get("operator_availability_ready")),
                "active_sessions": active_sessions,
            }
        ]
        active_rfq_oversight = {
            "assigned_rfqs": assigned_rfqs,
            "assigned_rfq_count": len(assigned_rfqs),
            "pending_approvals": pending_approvals,
            "pending_approval_count": len(pending_approvals),
            "active_session_count": active_sessions,
        }
        operational_workload_visibility = {
            "workload_items": workload_items,
            "workload_pressure": "high" if workload_items > 2 else "moderate" if workload_items > 0 else "low",
            "assigned_rfq_count": len(assigned_rfqs),
            "pending_approval_count": len(pending_approvals),
            "active_session_count": active_sessions,
        }
        supervision_sla_visibility = {
            "sla_ready": not lapse_active and not saturation_active and release_valid and release_ready,
            "sla_status": "PASS" if not lapse_active and not saturation_active and release_valid and release_ready else "WARN" if release_valid else "FAIL",
            "coverage_ready": supervision_ready,
            "review_board_status": _safe_str(escalation.get("review_board_status"), "watch"),
        }
        supervision_lapse_indicators = {
            "operator_certification_lapse": not operator_ready,
            "coverage_lapse": not supervision_ready,
            "active_session_lapse": active_sessions == 0,
            "escalation_lapse": not escalation_ready,
            "release_authorization_lapse": not release_valid,
        }
        operational_freeze_indicators = {
            "freeze_active": freeze_active,
            "operator_freeze": not operator_ready,
            "supervision_freeze": not supervision_ready,
            "deployment_freeze": not deployment_ready,
            "observability_freeze": not observability_ready,
            "escalation_freeze": not escalation_ready,
            "rollout_freeze": not rollout_ready,
            "release_freeze": not release_valid or not release_ready,
            "warning_freeze": bool(warnings),
        }
        supervision_coverage_indicators = {
            "supervision_coverage_ready": supervision_ready,
            "active_supervision_coverage_ready": supervision_ready,
            "coverage_score": _safe_float(supervision.get("supervision_score"), _bool_score(supervision_ready)),
            "coverage_active_sessions": active_sessions,
            "coverage_assigned_rfqs": assigned_rfqs,
            "coverage_pending_approvals": pending_approvals,
        }

        history = _safe_list(payload.get("rollout_governance_history"))
        history_summary = _safe_dict(payload.get("rollout_governance_history_summary"))
        history_scores = [entry.get("supervision_score", _safe_float(entry.get("production_readiness_score"), 0.0)) for entry in history if isinstance(entry, dict)]

        return {
            "analysis_id": f"{_safe_str(payload.get('validation_id'), 'rollout')}:supervision-command",
            "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
            "validation_id": _safe_str(payload.get("validation_id"), ""),
            "cycle_id": _safe_str(payload.get("validation_id"), "").replace("production-", ""),
            "status": status,
            "supervision_command_status": status,
            "supervision_command_authority": authority,
            "supervision_command_score": command_score,
            "supervision_command_grade": grade,
            "production_rollout_readiness": status == "ok" and rollout_ready,
            "production_rollout_readiness_status": "ready" if status == "ok" and rollout_ready else "watch" if status == "watch" else "blocked",
            "active_supervised_operators": active_supervised_operators,
            "supervision_coverage": supervision_coverage_indicators,
            "active_rfq_oversight": active_rfq_oversight,
            "escalation_command_visibility": {
                "escalation_ready": escalation_ready,
                "review_board_status": _safe_str(escalation.get("review_board_status"), "watch"),
                "outstanding_governance_actions": _safe_list(escalation.get("outstanding_governance_actions")),
                "unresolved_operational_exceptions": _safe_list(escalation.get("unresolved_operational_exceptions")),
            },
            "supervision_saturation": {
                "supervision_saturation_active": saturation_active,
                "active_sessions_over_threshold": active_sessions > 1,
                "assigned_rfqs_over_threshold": len(assigned_rfqs) > 2,
                "pending_approvals_over_threshold": len(pending_approvals) > 0,
                "workload_items": workload_items,
            },
            "supervision_lapse_indicators": supervision_lapse_indicators,
            "operational_workload_visibility": operational_workload_visibility,
            "supervision_sla_visibility": supervision_sla_visibility,
            "operational_freeze_indicators": operational_freeze_indicators,
            "supervision_governance_history": history,
            "supervision_governance_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": _safe_str(history[0].get("analysis_id"), "") if history else "",
                "latest_score": command_score,
                "score_history": _history_points([command_score] + [score for score in history_scores if isinstance(score, (int, float))]),
            },
            "latest_rollout_validation": _safe_dict(payload),
            "latest_release_certification": _safe_dict(release_certification),
            "release_certification_snapshot": _safe_dict(release_snapshot),
            "summary_counts": _safe_dict(payload.get("summary_counts")),
            "warnings": warnings
            + (["supervision_saturation_active"] if saturation_active else [])
            + (["supervision_lapse_active"] if lapse_active else [])
            + (["operational_freeze_active"] if freeze_active else []),
            "release_governance_score": release_governance_score,
            "release_authority": release_authority,
            "release_certification_status": release_certification_status,
            "operator_name": operator_name,
            "operator_role": operator_role,
            "deployment_health_summary": deployment_health,
            "production_observability_summary": observability,
            "institutional_rollout_certification_evidence": institutional,
            "rollout_readiness_summary": rollout_readiness,
            "operator_onboarding_readiness_summary": _safe_dict(payload.get("operator_onboarding_readiness_summary")),
        }

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [self._entry(payload) for payload in self._load_rollout_payloads(limit=limit)]

    def list_supervision_command(self, limit: int = 20) -> Dict[str, Any]:
        history = self._history(limit=limit)
        if not history:
            return {
                "status": "not_found",
                "message": "No production supervision command evidence has been recorded yet.",
                "supervision_governance_history": [],
            }
        latest = history[0]
        scores = [entry.get("supervision_command_score", 0.0) for entry in history if isinstance(entry, dict)]
        return {
            "status": latest.get("status", "watch"),
            "generated_at": latest.get("generated_at", _now_iso()),
            "latest_supervision_command": latest,
            "supervision_command_status": latest.get("supervision_command_status", "watch"),
            "supervision_command_authority": latest.get("supervision_command_authority", "WATCH"),
            "supervision_command_score": latest.get("supervision_command_score", 0.0),
            "supervision_command_grade": latest.get("supervision_command_grade", "watch"),
            "production_rollout_readiness": latest.get("production_rollout_readiness", False),
            "production_rollout_readiness_status": latest.get("production_rollout_readiness_status", "watch"),
            "active_supervised_operators": latest.get("active_supervised_operators", []),
            "supervision_coverage": latest.get("supervision_coverage", {}),
            "active_rfq_oversight": latest.get("active_rfq_oversight", {}),
            "escalation_command_visibility": latest.get("escalation_command_visibility", {}),
            "supervision_saturation": latest.get("supervision_saturation", {}),
            "supervision_lapse_indicators": latest.get("supervision_lapse_indicators", {}),
            "operational_workload_visibility": latest.get("operational_workload_visibility", {}),
            "supervision_sla_visibility": latest.get("supervision_sla_visibility", {}),
            "operational_freeze_indicators": latest.get("operational_freeze_indicators", {}),
            "supervision_governance_history": history,
            "supervision_governance_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": _safe_str(latest.get("analysis_id"), ""),
                "latest_score": latest.get("supervision_command_score", 0.0),
                "score_history": _history_points(scores),
            },
            "latest_rollout_validation": latest.get("latest_rollout_validation", {}),
            "latest_release_certification": latest.get("latest_release_certification", {}),
            "release_certification_snapshot": latest.get("release_certification_snapshot", {}),
            "deployment_health_summary": latest.get("deployment_health_summary", {}),
            "production_observability_summary": latest.get("production_observability_summary", {}),
            "institutional_rollout_certification_evidence": latest.get("institutional_rollout_certification_evidence", {}),
            "rollout_readiness_summary": latest.get("rollout_readiness_summary", {}),
            "operator_onboarding_readiness_summary": latest.get("operator_onboarding_readiness_summary", {}),
            "summary_counts": latest.get("summary_counts", {}),
            "warnings": latest.get("warnings", []),
        }

    def latest_supervision_command(self) -> Dict[str, Any]:
        response = self.list_supervision_command(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No production supervision command evidence has been recorded yet.",
                "supervision_command": {},
            }
        return response

    def supervision_command_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_supervision_command(limit=limit)
        return {
            "status": response.get("status", "watch"),
            "count": len(response.get("supervision_governance_history", [])),
            "supervision_governance_history": response.get("supervision_governance_history", []),
            "supervision_governance_history_summary": response.get("supervision_governance_history_summary", {}),
            "production_rollout_readiness": response.get("production_rollout_readiness", False),
            "production_rollout_readiness_status": response.get("production_rollout_readiness_status", "watch"),
            "supervision_saturation": response.get("supervision_saturation", {}),
            "supervision_lapse_indicators": response.get("supervision_lapse_indicators", {}),
            "operational_freeze_indicators": response.get("operational_freeze_indicators", {}),
            "warnings": response.get("warnings", []),
        }
