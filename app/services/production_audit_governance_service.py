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


class ProductionAuditGovernanceService:
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
        audit_retention_ready = all(
            [
                bool(self._bundle_files()),
                bool(self._release_bundle_files()) or bool(LATEST_RELEASE_CERTIFICATION_FILE.exists()),
                _truthy(institutional.get("release_authorization_valid")),
            ]
        )
        audit_completeness_ready = all(
            [
                _truthy(rollout_readiness.get("tenant_isolation_ready")),
                _truthy(rollout_readiness.get("operator_availability_ready")),
                _truthy(rollout_readiness.get("active_supervision_coverage_ready")),
                _truthy(rollout_readiness.get("deployment_health_ready")),
                _truthy(rollout_readiness.get("production_observability_ready")),
                _truthy(rollout_readiness.get("release_authorization_valid")),
                _truthy(rollout_readiness.get("escalation_chain_ready")),
                _safe_int(_safe_list(payload.get("rollout_governance_history")), 0) >= 0,
            ]
        )
        release_governance_history = _safe_list(_safe_dict(release_certification).get("release_governance_history"))
        freeze_history = _safe_list(payload.get("operational_freeze_history"))
        release_decision_history = [
            {
                "audit_type": "release_decision",
                "analysis_id": _safe_str(item.get("analysis_id"), f"{_safe_str(payload.get('validation_id'), 'rollout')}:release"),
                "generated_at": _safe_str(item.get("generated_at"), _safe_str(payload.get("generated_at"), _now_iso())),
                "release_governance_score": _safe_float(item.get("release_governance_score"), _safe_float(_safe_dict(release_certification.get("governance_certification_summary")).get("certification_score"), 0.0)),
                "release_governance_authority": _safe_str(item.get("release_governance_authority"), _safe_str(_safe_dict(release_certification.get("release_authority_certification")).get("active_authority"), "WATCH")),
                "release_governance_status": _safe_str(_safe_dict(release_certification.get("governance_certification_summary")).get("certification_status"), "WATCH"),
            }
            for item in release_governance_history
        ]
        supervised_rollout_actions = [
            {
                "audit_type": "supervised_rollout_action",
                "analysis_id": _safe_str(item.get("analysis_id"), f"{_safe_str(payload.get('validation_id'), 'rollout')}:rollout"),
                "generated_at": _safe_str(item.get("generated_at"), _safe_str(payload.get("generated_at"), _now_iso())),
                "action": _safe_str(_safe_dict(item.get("production_governance_summary")).get("decision"), "support_enterprise_deployment"),
                "status": _safe_str(item.get("production_readiness_status"), "watch"),
                "score": _safe_float(item.get("production_readiness_score"), readiness_score),
            }
            for item in _safe_list(payload.get("rollout_governance_history"))
        ]
        escalation_acknowledgements = [
            {
                "audit_type": "escalation_acknowledgement",
                "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                "review_board_status": _safe_str(escalation.get("review_board_status"), "watch"),
                "escalation_chain_ready": _truthy(escalation.get("escalation_chain_ready")),
                "outstanding_governance_actions": _safe_list(escalation.get("outstanding_governance_actions")),
                "unresolved_operational_exceptions": _safe_list(escalation.get("unresolved_operational_exceptions")),
            }
        ]
        freeze_status = bool(freeze_history) and any(_truthy(item.get("freeze_active")) for item in freeze_history) or not all(
            [
                _truthy(tenant.get("tenant_isolation_ready")),
                _truthy(operator.get("approved_for_supervision")),
                _truthy(operator.get("operator_availability_ready")),
                _truthy(supervision.get("active_supervision_coverage_ready")),
                _truthy(deployment_health.get("deployment_health_ready")),
                _truthy(observability.get("production_observability_ready")),
                _truthy(escalation.get("escalation_chain_ready")),
                _truthy(institutional.get("release_authorization_valid")),
            ]
        )
        operational_freeze_history = [
            {
                "audit_type": "operational_freeze",
                "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                "freeze_active": freeze_status,
                "freeze_reason": "supervision_or_deployment_risk" if freeze_status else "no_freeze",
            }
        ]
        governance_override_history = [
            {
                "audit_type": "governance_override",
                "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                "release_authorization_valid": _truthy(institutional.get("release_authorization_valid")),
                "human_supervision_required": True,
                "override_active": False,
            }
        ]
        operator_acknowledgement_history = [
            {
                "audit_type": "operator_acknowledgement",
                "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                "operator_name": _safe_str(operator.get("operator_name"), "staging-governance-operator"),
                "operator_role": _safe_str(operator.get("operator_role"), "governance_reviewer"),
                "approved_for_supervision": bool(operator.get("approved_for_supervision")),
                "operator_availability_ready": bool(operator.get("operator_availability_ready")),
            }
        ]
        supervision_approval_history = [
            {
                "audit_type": "supervision_approval",
                "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                "active_supervision_coverage_ready": _truthy(supervision.get("active_supervision_coverage_ready")),
                "active_sessions": _safe_int(supervision.get("active_sessions"), 0),
                "assigned_rfqs": _safe_list(supervision.get("assigned_rfqs")),
                "pending_approvals": _safe_list(supervision.get("pending_approvals")),
            }
        ]

        institutional_audit_history = supervised_rollout_actions + release_decision_history
        audit_retention_indicators = {
            "rollout_validation_retained": bool(self._bundle_files()),
            "latest_rollout_validation_retained": LATEST_ROLLOUT_VALIDATION_FILE.exists(),
            "release_certification_retained": bool(self._release_bundle_files()) or LATEST_RELEASE_CERTIFICATION_FILE.exists(),
            "latest_release_certification_retained": LATEST_RELEASE_CERTIFICATION_FILE.exists(),
            "institutional_audit_history_retained": bool(institutional_audit_history),
            "retention_compliant": bool(self._bundle_files()) and (bool(self._release_bundle_files()) or LATEST_RELEASE_CERTIFICATION_FILE.exists()),
        }
        audit_completeness_indicators = {
            "supervised_rollout_actions_recorded": bool(supervised_rollout_actions),
            "escalation_acknowledgements_recorded": bool(escalation_acknowledgements),
            "operational_freeze_history_recorded": bool(operational_freeze_history),
            "governance_override_history_recorded": bool(governance_override_history),
            "operator_acknowledgement_history_recorded": bool(operator_acknowledgement_history),
            "supervision_approval_history_recorded": bool(supervision_approval_history),
            "release_decision_history_recorded": bool(release_decision_history),
            "institutional_audit_history_recorded": bool(institutional_audit_history),
            "audit_completeness_ready": audit_completeness_ready,
        }
        history_score = mean(
            [
                readiness_score,
                _bool_score(audit_retention_indicators["retention_compliant"]),
                _bool_score(audit_completeness_ready),
                _bool_score(audit_retention_indicators["institutional_audit_history_retained"]),
                _bool_score(_truthy(institutional.get("release_authorization_valid"))),
                _bool_score(not freeze_status),
            ]
        )
        audit_status = _status_from_score(history_score)
        if warnings and audit_status == "ok":
            audit_status = "watch"
        audit_authority = _authority_from_status(audit_status)
        audit_grade = "ready" if audit_status == "ok" else "watch" if audit_status == "watch" else "blocked"

        return {
            "analysis_id": f"{_safe_str(payload.get('validation_id'), 'rollout')}:operations-audit",
            "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
            "status": audit_status,
            "operations_audit_status": audit_status,
            "operations_audit_authority": audit_authority,
            "operations_audit_score": round(history_score, 2),
            "operations_audit_grade": audit_grade,
            "supervised_rollout_actions": supervised_rollout_actions,
            "escalation_acknowledgements": escalation_acknowledgements,
            "operational_freeze_history": operational_freeze_history,
            "governance_override_history": governance_override_history,
            "operator_acknowledgement_history": operator_acknowledgement_history,
            "supervision_approval_history": supervision_approval_history,
            "release_decision_history": release_decision_history,
            "audit_retention_indicators": audit_retention_indicators,
            "audit_completeness_indicators": audit_completeness_indicators,
            "institutional_audit_history": institutional_audit_history,
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
            + ([] if audit_retention_indicators["retention_compliant"] else ["Audit retention indicators are incomplete or missing."])
            + ([] if audit_completeness_ready else ["Audit completeness indicators are incomplete or missing."])
            + ([] if not freeze_status else ["Operational freeze indicators are active."]),
        }

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for payload in self._load_rollout_payloads(limit=limit):
            entry = self._history_entry(payload)
            entries.append(
                {
                    "analysis_id": entry["analysis_id"],
                    "generated_at": entry["generated_at"],
                    "operations_audit_status": entry["operations_audit_status"],
                    "operations_audit_authority": entry["operations_audit_authority"],
                    "operations_audit_score": entry["operations_audit_score"],
                    "operations_audit_grade": entry["operations_audit_grade"],
                    "audit_retention_indicators": entry["audit_retention_indicators"],
                    "audit_completeness_indicators": entry["audit_completeness_indicators"],
                    "rollout_readiness_summary": entry["rollout_readiness_summary"],
                    "summary_counts": entry["summary_counts"],
                }
            )
        return entries

    def list_operations_audit(self, limit: int = 20) -> Dict[str, Any]:
        history = self._history(limit=limit)
        latest_payload = self._latest_rollout_payload()
        latest = self._history_entry(latest_payload) if latest_payload else self._history_entry({})
        scores = [float(item.get("operations_audit_score", 0.0)) for item in history] or [latest["operations_audit_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["operations_audit_score"],
            "score_history": _history_points(scores),
        }
        payload = {
            "status": latest["status"],
            "operations_audit_status": latest["operations_audit_status"],
            "operations_audit_authority": latest["operations_audit_authority"],
            "operations_audit_score": latest["operations_audit_score"],
            "operations_audit_grade": latest["operations_audit_grade"],
            **latest,
            "latest_operations_audit": latest,
            "operations_audit_history": history[: max(1, int(limit))],
            "operations_audit_history_summary": summary,
            "summary_counts": latest.get("summary_counts", {}),
            "warnings": latest.get("warnings", []),
        }
        return payload

    def latest_operations_audit(self) -> Dict[str, Any]:
        return self.list_operations_audit(limit=1)

    def operations_audit_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_operations_audit(limit=limit)
        history = latest["operations_audit_history"]
        return {
            "status": latest["status"],
            "operations_audit_status": latest["operations_audit_status"],
            "operations_audit_authority": latest["operations_audit_authority"],
            "operations_audit_score": latest["operations_audit_score"],
            "operations_audit_grade": latest["operations_audit_grade"],
            "count": len(history),
            "operations_audit_history": history,
            "operations_audit_history_summary": latest["operations_audit_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
