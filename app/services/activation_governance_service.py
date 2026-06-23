from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
import json

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


def _bool_status(value: Any) -> str:
    return "PASS" if bool(value) else "FAIL"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified"}
    return bool(value)


class ActivationGovernanceService:
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

    def _rollout_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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
        summary_counts = _safe_dict(payload.get("summary_counts"))
        warnings = [warning for warning in _safe_list(payload.get("warnings")) if _safe_str(warning)]
        rollout_history = _safe_list(payload.get("rollout_governance_history"))
        rollout_history_summary = _safe_dict(payload.get("rollout_governance_history_summary"))

        tenant_ready = _truthy(tenant.get("tenant_isolation_ready"))
        operator_ready = _truthy(operator.get("approved_for_supervision")) and _truthy(operator.get("operator_availability_ready"))
        supervision_ready = _truthy(supervision.get("active_supervision_coverage_ready"))
        deployment_ready = _truthy(deployment_health.get("deployment_health_ready"))
        observability_ready = _truthy(observability.get("production_observability_ready"))
        escalation_ready = _truthy(escalation.get("escalation_chain_ready"))
        release_valid = _truthy(institutional.get("release_authorization_valid"))
        rollout_ready = _truthy(institutional.get("rollout_ready_for_supervised_deployment"))
        release_ready = _truthy(_safe_dict(release_certification.get("operational_readiness_certification")).get("overall_validation_passed", False))

        assigned_rfqs = _safe_list(supervision.get("assigned_rfqs"))
        pending_approvals = _safe_list(supervision.get("pending_approvals"))
        active_sessions = _safe_int(supervision.get("active_sessions"), 0)
        tenant_workspace_pairs = _safe_int(tenant.get("tenant_workspace_pair_count"), 0)
        tenant_count = _safe_int(tenant.get("tenant_count"), 0)
        workspace_count = _safe_int(tenant.get("workspace_count"), 0)
        readiness_score = _safe_float(rollout_readiness.get("rollout_readiness_score"), 0.0)
        release_authority = _safe_str(latest_release.get("release_authority"), _safe_str(_safe_dict(release_certification.get("release_authority_certification")).get("active_authority"), "WATCH")).upper()
        release_certification_status = _safe_str(latest_release.get("certification_status"), _safe_str(_safe_dict(release_certification.get("governance_certification_summary")).get("certification_status"), "WATCH")).upper()

        staged_rollout_segmentation = {
            "staged_rollout_segmentation_status": "PASS" if tenant_ready else "FAIL",
            "staged_rollout_segmentation_ready": tenant_ready and tenant_workspace_pairs > 0,
            "tenant_count": tenant_count,
            "workspace_count": workspace_count,
            "tenant_workspace_pair_count": tenant_workspace_pairs,
            "tenant_workspace_isolation": _safe_dict(tenant.get("tenant_workspace_isolation")),
        }

        tenant_activation_readiness = {
            "tenant_activation_ready": tenant_ready,
            "tenant_activation_score": _bool_score(tenant_ready),
            "tenant_activation_status": _bool_status(tenant_ready),
            "tenant_count": tenant_count,
            "workspace_count": workspace_count,
            "tenant_workspace_pair_count": tenant_workspace_pairs,
            "tenant_isolation_ready": tenant_ready,
        }

        operator_certification_readiness = {
            "operator_certification_ready": operator_ready,
            "operator_certification_score": _bool_score(operator_ready),
            "operator_certification_status": _bool_status(operator_ready),
            "operator_name": _safe_str(operator.get("operator_name"), "staging-governance-operator"),
            "operator_role": _safe_str(operator.get("operator_role"), "governance_reviewer"),
            "approved_for_supervision": bool(operator.get("approved_for_supervision")),
            "operator_availability_ready": bool(operator.get("operator_availability_ready")),
            "onboarding_status": _safe_str(operator.get("onboarding_status"), "watch"),
        }

        supervision_assignment_readiness = {
            "supervision_assignment_ready": supervision_ready,
            "supervision_assignment_score": _bool_score(supervision_ready),
            "supervision_assignment_status": _bool_status(supervision_ready),
            "active_sessions": active_sessions,
            "assigned_rfqs": assigned_rfqs,
            "pending_approvals": pending_approvals,
            "supervision_score": _safe_float(supervision.get("supervision_score"), 0.0),
        }

        throughput_expansion_ready = readiness_score >= 85.0 and deployment_ready and observability_ready and release_valid and release_ready and rollout_ready
        throughput_expansion_readiness = {
            "throughput_expansion_ready": throughput_expansion_ready,
            "throughput_expansion_score": round(
                mean(
                    [
                        readiness_score,
                        _bool_score(deployment_ready),
                        _bool_score(observability_ready),
                        _bool_score(release_valid),
                        _bool_score(release_ready),
                        _bool_score(rollout_ready),
                    ]
                ),
                2,
            ),
            "throughput_expansion_status": "PASS" if throughput_expansion_ready else "WARN" if readiness_score >= 70.0 else "FAIL",
            "throughput_expansion_grade": "ready" if throughput_expansion_ready else "watch" if readiness_score >= 70.0 else "blocked",
            "release_authorization_valid": release_valid,
            "release_authority": release_authority,
            "release_certification_status": release_certification_status,
            "deployment_health_ready": deployment_ready,
            "production_observability_ready": observability_ready,
        }

        escalation_chain_ready = bool(escalation.get("escalation_chain_ready"))
        escalation_readiness = {
            "escalation_ready": escalation_chain_ready and release_valid,
            "escalation_readiness_score": round(mean([_bool_score(escalation_chain_ready), _bool_score(release_valid)]), 2),
            "escalation_readiness_status": "PASS" if escalation_chain_ready and release_valid else "WARN" if escalation_chain_ready else "FAIL",
            "escalation_chain_ready": escalation_chain_ready,
            "review_board_status": _safe_str(escalation.get("review_board_status"), "watch"),
            "outstanding_governance_actions": _safe_list(escalation.get("outstanding_governance_actions")),
            "unresolved_operational_exceptions": _safe_list(escalation.get("unresolved_operational_exceptions")),
        }

        operator_saturation_indicators = {
            "operator_saturation_active": active_sessions > 1 or len(assigned_rfqs) > 2 or len(pending_approvals) > 0,
            "active_sessions_over_threshold": active_sessions > 1,
            "assigned_rfqs_over_threshold": len(assigned_rfqs) > 2,
            "pending_approvals_over_threshold": len(pending_approvals) > 0,
            "operator_load": len(assigned_rfqs) + len(pending_approvals),
        }

        supervision_coverage_indicators = {
            "active_supervision_coverage_ready": supervision_ready,
            "supervision_coverage_score": _safe_float(supervision.get("supervision_score"), _bool_score(supervision_ready)),
            "coverage_active_sessions": active_sessions,
            "coverage_assigned_rfqs": assigned_rfqs,
            "coverage_pending_approvals": pending_approvals,
            "operator_availability_ready": operator_ready,
        }

        freeze_indicators = {
            "freeze_active": not (
                tenant_ready
                and operator_ready
                and supervision_ready
                and deployment_ready
                and observability_ready
                and escalation_chain_ready
                and release_valid
                and release_ready
            )
            or bool(warnings),
            "tenant_activation_freeze": not tenant_ready,
            "operator_certification_freeze": not operator_ready,
            "supervision_assignment_freeze": not supervision_ready,
            "throughput_expansion_freeze": not throughput_expansion_ready,
            "rollout_authorization_freeze": not release_valid,
            "deployment_health_freeze": not deployment_ready,
            "production_observability_freeze": not observability_ready,
            "escalation_chain_freeze": not escalation_chain_ready,
            "warning_freeze": bool(warnings),
        }

        activation_score = round(
            mean(
                [
                    readiness_score,
                    _bool_score(tenant_ready),
                    _bool_score(operator_ready),
                    _bool_score(supervision_ready),
                    _bool_score(deployment_ready),
                    _bool_score(observability_ready),
                    _bool_score(escalation_chain_ready),
                    _bool_score(release_valid),
                    _bool_score(release_ready),
                    _bool_score(rollout_ready),
                    _bool_score(not operator_saturation_indicators["operator_saturation_active"]),
                ]
            ),
            2,
        )
        freeze_active = bool(freeze_indicators["freeze_active"])
        if freeze_active or activation_score < 70.0 or readiness_score < 70.0:
            activation_status = "blocked"
        elif readiness_score < 85.0 or activation_score < 85.0 or warnings:
            activation_status = "watch"
        elif activation_score >= 85.0 and not warnings:
            activation_status = "ok"
        else:
            activation_status = "watch"
        activation_authority = _authority_from_status(activation_status)
        activation_grade = "ready" if activation_status == "ok" else "watch" if activation_status == "watch" else "blocked"

        activation_entry = {
            "analysis_id": f"{_safe_str(payload.get('validation_id'), 'rollout')}:activation-governance",
            "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
            "validation_id": _safe_str(payload.get("validation_id"), ""),
            "cycle_id": _safe_str(payload.get("validation_id"), "").replace("production-", ""),
            "status": activation_status,
            "activation_governance_status": activation_status,
            "activation_governance_authority": activation_authority,
            "activation_governance_score": activation_score,
            "activation_governance_grade": activation_grade,
            "production_rollout_readiness": activation_status == "ok",
            "production_rollout_readiness_status": "ready" if activation_status == "ok" else "watch" if activation_status == "watch" else "blocked",
            "rollout_ready_for_supervised_deployment": bool(institutional.get("rollout_ready_for_supervised_deployment")),
            "release_authorization_valid": release_valid,
            "tenant_activation_readiness": tenant_activation_readiness,
            "operator_certification_readiness": operator_certification_readiness,
            "supervision_assignment_readiness": supervision_assignment_readiness,
            "staged_rollout_segmentation": staged_rollout_segmentation,
            "throughput_expansion_readiness": throughput_expansion_readiness,
            "rollout_freeze_indicators": freeze_indicators,
            "escalation_readiness": escalation_readiness,
            "operator_saturation_indicators": operator_saturation_indicators,
            "supervision_coverage_indicators": supervision_coverage_indicators,
            "rollout_expansion_history": rollout_history,
            "rollout_expansion_history_summary": rollout_history_summary,
            "deployment_health_summary": deployment_health,
            "production_observability_summary": observability,
            "institutional_rollout_certification_evidence": institutional,
            "latest_release_certification": latest_release or _safe_dict(release_snapshot) or release_certification,
            "release_certification_snapshot": release_snapshot or release_certification,
            "source_artifacts": _safe_dict(payload.get("source_artifacts")),
            "source_runtime": _safe_dict(payload.get("source_runtime")),
            "summary_counts": summary_counts,
            "warnings": warnings
            + (["rollout_freeze_active"] if freeze_active else [])
            + (["operator_saturation_active"] if operator_saturation_indicators["operator_saturation_active"] else [])
            + (["release_authorization_invalid"] if not release_valid else [])
            + (["throughput_expansion_not_ready"] if not throughput_expansion_ready else []),
        }
        return activation_entry

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = []
        for payload in self._load_rollout_payloads(limit=limit):
            entry = self._rollout_entry(payload)
            history.append(entry)
        return history

    def list_activation_governance(self, limit: int = 20) -> Dict[str, Any]:
        history = self._history(limit=limit)
        if not history:
            return {
                "status": "not_found",
                "message": "No activation governance evidence has been recorded yet.",
                "activation_governance_history": [],
            }
        latest = history[0]
        scores = [entry.get("activation_governance_score", 0.0) for entry in history if isinstance(entry, dict)]
        status = latest.get("activation_governance_status", "watch")
        return {
            "status": status,
            "generated_at": latest.get("generated_at", _now_iso()),
            "latest_rollout_validation": _safe_dict(self._latest_rollout_payload()),
            "latest_release_certification": _safe_dict(self._latest_release_certification()),
            "activation_governance_status": status,
            "activation_governance_authority": latest.get("activation_governance_authority", "WATCH"),
            "activation_governance_score": latest.get("activation_governance_score", 0.0),
            "activation_governance_grade": latest.get("activation_governance_grade", "watch"),
            "production_rollout_readiness": latest.get("production_rollout_readiness", False),
            "production_rollout_readiness_status": latest.get("production_rollout_readiness_status", "watch"),
            "latest_activation_governance": latest,
            "activation_governance_history": history,
            "activation_governance_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": _safe_str(latest.get("analysis_id"), ""),
                "latest_score": latest.get("activation_governance_score", 0.0),
                "score_history": _history_points(scores),
            },
            "tenant_activation_readiness": latest.get("tenant_activation_readiness", {}),
            "operator_certification_readiness": latest.get("operator_certification_readiness", {}),
            "supervision_assignment_readiness": latest.get("supervision_assignment_readiness", {}),
            "staged_rollout_segmentation": latest.get("staged_rollout_segmentation", {}),
            "throughput_expansion_readiness": latest.get("throughput_expansion_readiness", {}),
            "rollout_freeze_indicators": latest.get("rollout_freeze_indicators", {}),
            "escalation_readiness": latest.get("escalation_readiness", {}),
            "operator_saturation_indicators": latest.get("operator_saturation_indicators", {}),
            "supervision_coverage_indicators": latest.get("supervision_coverage_indicators", {}),
            "rollout_expansion_history": latest.get("rollout_expansion_history", []),
            "rollout_expansion_history_summary": latest.get("rollout_expansion_history_summary", {}),
            "deployment_health_summary": latest.get("deployment_health_summary", {}),
            "production_observability_summary": latest.get("production_observability_summary", {}),
            "institutional_rollout_certification_evidence": latest.get("institutional_rollout_certification_evidence", {}),
            "release_certification_snapshot": latest.get("release_certification_snapshot", {}),
            "source_artifacts": latest.get("source_artifacts", {}),
            "source_runtime": latest.get("source_runtime", {}),
            "summary_counts": latest.get("summary_counts", {}),
            "warnings": latest.get("warnings", []),
        }

    def latest_activation_governance(self) -> Dict[str, Any]:
        response = self.list_activation_governance(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No activation governance evidence has been recorded yet.",
                "activation_governance": {},
            }
        return {
            "status": response.get("status", "watch"),
            "generated_at": response.get("generated_at", _now_iso()),
            "latest_rollout_validation": response.get("latest_rollout_validation", {}),
            "latest_release_certification": response.get("latest_release_certification", {}),
            "activation_governance_status": response.get("activation_governance_status", "watch"),
            "activation_governance_authority": response.get("activation_governance_authority", "WATCH"),
            "activation_governance_score": response.get("activation_governance_score", 0.0),
            "activation_governance_grade": response.get("activation_governance_grade", "watch"),
            "production_rollout_readiness": response.get("production_rollout_readiness", False),
            "production_rollout_readiness_status": response.get("production_rollout_readiness_status", "watch"),
            "latest_activation_governance": response.get("latest_activation_governance", {}),
            "activation_governance_history": response.get("activation_governance_history", []),
            "activation_governance_history_summary": response.get("activation_governance_history_summary", {}),
            "tenant_activation_readiness": response.get("tenant_activation_readiness", {}),
            "operator_certification_readiness": response.get("operator_certification_readiness", {}),
            "supervision_assignment_readiness": response.get("supervision_assignment_readiness", {}),
            "staged_rollout_segmentation": response.get("staged_rollout_segmentation", {}),
            "throughput_expansion_readiness": response.get("throughput_expansion_readiness", {}),
            "rollout_freeze_indicators": response.get("rollout_freeze_indicators", {}),
            "escalation_readiness": response.get("escalation_readiness", {}),
            "operator_saturation_indicators": response.get("operator_saturation_indicators", {}),
            "supervision_coverage_indicators": response.get("supervision_coverage_indicators", {}),
            "rollout_expansion_history": response.get("rollout_expansion_history", []),
            "rollout_expansion_history_summary": response.get("rollout_expansion_history_summary", {}),
            "deployment_health_summary": response.get("deployment_health_summary", {}),
            "production_observability_summary": response.get("production_observability_summary", {}),
            "institutional_rollout_certification_evidence": response.get("institutional_rollout_certification_evidence", {}),
            "release_certification_snapshot": response.get("release_certification_snapshot", {}),
            "source_artifacts": response.get("source_artifacts", {}),
            "source_runtime": response.get("source_runtime", {}),
            "summary_counts": response.get("summary_counts", {}),
            "warnings": response.get("warnings", []),
        }

    def activation_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_activation_governance(limit=limit)
        return {
            "status": response.get("status", "watch"),
            "count": len(response.get("activation_governance_history", [])),
            "activation_governance_history": response.get("activation_governance_history", []),
            "activation_governance_history_summary": response.get("activation_governance_history_summary", {}),
            "production_rollout_readiness": response.get("production_rollout_readiness", False),
            "production_rollout_readiness_status": response.get("production_rollout_readiness_status", "watch"),
            "rollout_freeze_indicators": response.get("rollout_freeze_indicators", {}),
            "escalation_readiness": response.get("escalation_readiness", {}),
            "operator_saturation_indicators": response.get("operator_saturation_indicators", {}),
            "supervision_coverage_indicators": response.get("supervision_coverage_indicators", {}),
            "warnings": response.get("warnings", []),
        }
