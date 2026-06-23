from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.activation_governance_service import ActivationGovernanceService
from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.operational_intelligence_service import OperationalIntelligenceService
from app.services.production_audit_governance_service import ProductionAuditGovernanceService
from app.services.production_continuity_governance_service import ProductionContinuityGovernanceService
from app.services.production_incident_governance_service import ProductionIncidentGovernanceService
from app.services.production_release_governance_service import ProductionReleaseGovernanceService
from app.services.production_supervision_command_service import ProductionSupervisionCommandService
from app.services.executive_command_service import ExecutiveCommandService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROLLOUT_VALIDATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "production-rollout-validations"
RELEASE_CERTIFICATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "release-certifications"


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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified"}
    return bool(value)


class ExecutiveGovernanceIndexService:
    def __init__(
        self,
        validation_root: Optional[Path] = None,
        release_certification_root: Optional[Path] = None,
        activation_service: Optional[ActivationGovernanceService] = None,
        supervision_command_service: Optional[ProductionSupervisionCommandService] = None,
        audit_service: Optional[ProductionAuditGovernanceService] = None,
        incident_service: Optional[ProductionIncidentGovernanceService] = None,
        continuity_service: Optional[ProductionContinuityGovernanceService] = None,
        release_service: Optional[ProductionReleaseGovernanceService] = None,
        intelligence_service: Optional[OperationalIntelligenceService] = None,
        executive_command_service: Optional[ExecutiveCommandService] = None,
    ) -> None:
        self.validation_root = validation_root or ROLLOUT_VALIDATION_ROOT
        self.release_certification_root = release_certification_root or RELEASE_CERTIFICATION_ROOT
        self.activation_service = activation_service or ActivationGovernanceService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )
        self.supervision_command_service = supervision_command_service or ProductionSupervisionCommandService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )
        self.audit_service = audit_service or ProductionAuditGovernanceService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )
        self.incident_service = incident_service or ProductionIncidentGovernanceService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )
        self.continuity_service = continuity_service or ProductionContinuityGovernanceService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )
        self.release_service = release_service or ProductionReleaseGovernanceService(validation_root=self.validation_root)
        self.intelligence_service = intelligence_service or OperationalIntelligenceService()
        self.executive_command_service = executive_command_service or ExecutiveCommandService(
            cycle_root=PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles",
            evidence_pack_root=PROJECT_ROOT / "runtime" / "staging" / "evidence-packs",
        )

    @staticmethod
    def _section(payload: Dict[str, Any], *, status_key: str, authority_key: str, score_key: str, grade_key: str) -> Dict[str, Any]:
        status = _safe_str(payload.get(status_key), "watch")
        authority = _safe_str(payload.get(authority_key), "")
        if not authority:
            authority = _authority_from_status(status)
        return {
            "status": status,
            "authority": authority.upper(),
            "score": _safe_float(payload.get(score_key), 0.0),
            "grade": _safe_str(payload.get(grade_key), "blocked"),
        }

    @staticmethod
    def _component_score(section: Dict[str, Any]) -> float:
        return _safe_float(section.get("score"), 0.0)

    @staticmethod
    def _component_status(section: Dict[str, Any]) -> str:
        return _safe_str(section.get("status"), "watch").lower()

    @staticmethod
    def _component_authority(section: Dict[str, Any]) -> str:
        return _safe_str(section.get("authority"), "WATCH").upper()

    def _latest_snapshots(self) -> Dict[str, Dict[str, Any]]:
        activation = _safe_dict(self.activation_service.latest_activation_governance())
        supervision = _safe_dict(self.supervision_command_service.latest_supervision_command())
        audit = _safe_dict(self.audit_service.latest_operations_audit())
        incident = _safe_dict(self.incident_service.latest_incident_governance())
        continuity = _safe_dict(self.continuity_service.latest_continuity_governance())
        release = _safe_dict(self.release_service.latest_release_governance())
        intelligence = _safe_dict(self.intelligence_service.latest_operational_intelligence())
        executive_command = _safe_dict(self.executive_command_service.latest_executive_command())
        return {
            "activation": activation,
            "supervision": supervision,
            "audit": audit,
            "incident": incident,
            "continuity": continuity,
            "release": release,
            "intelligence": intelligence,
            "executive_command": executive_command,
        }

    def _history_sources(self) -> Dict[str, List[Dict[str, Any]]]:
        snapshots = self._latest_snapshots()
        return {
            "activation": _safe_list(snapshots["activation"].get("activation_governance_history")),
            "supervision": _safe_list(snapshots["supervision"].get("supervision_governance_history")),
            "audit": _safe_list(snapshots["audit"].get("operations_audit_history")),
            "incident": _safe_list(snapshots["incident"].get("incident_governance_history")),
            "continuity": _safe_list(snapshots["continuity"].get("continuity_governance_history")),
            "release": _safe_list(snapshots["release"].get("release_governance_history")),
            "intelligence": _safe_list(snapshots["intelligence"].get("operational_intelligence_history")),
            "executive_command": _safe_list(snapshots["executive_command"].get("executive_intelligence_history")),
        }

    def _consolidated_history_entry(self, index: int, sources: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        activation = _safe_dict(sources["activation"][index] if index < len(sources["activation"]) else {})
        supervision = _safe_dict(sources["supervision"][index] if index < len(sources["supervision"]) else {})
        audit = _safe_dict(sources["audit"][index] if index < len(sources["audit"]) else {})
        incident = _safe_dict(sources["incident"][index] if index < len(sources["incident"]) else {})
        continuity = _safe_dict(sources["continuity"][index] if index < len(sources["continuity"]) else {})
        release = _safe_dict(sources["release"][index] if index < len(sources["release"]) else {})
        intelligence = _safe_dict(sources["intelligence"][index] if index < len(sources["intelligence"]) else {})
        executive_command = _safe_dict(sources["executive_command"][index] if index < len(sources["executive_command"]) else {})

        activation_section = self._section(activation, status_key="activation_governance_status", authority_key="activation_governance_authority", score_key="activation_governance_score", grade_key="activation_governance_grade")
        supervision_section = self._section(supervision, status_key="supervision_command_status", authority_key="supervision_command_authority", score_key="supervision_command_score", grade_key="supervision_command_grade")
        audit_section = self._section(audit, status_key="operations_audit_status", authority_key="operations_audit_authority", score_key="operations_audit_score", grade_key="operations_audit_grade")
        incident_section = self._section(incident, status_key="incident_governance_status", authority_key="incident_governance_authority", score_key="incident_governance_score", grade_key="incident_governance_grade")
        continuity_section = self._section(continuity, status_key="continuity_governance_status", authority_key="continuity_governance_authority", score_key="continuity_governance_score", grade_key="continuity_governance_grade")
        release_section = self._section(release, status_key="release_governance_status", authority_key="release_governance_authority", score_key="release_governance_score", grade_key="release_governance_grade")
        intelligence_section = self._section(intelligence, status_key="operational_intelligence_status", authority_key="operational_intelligence_authority", score_key="operational_intelligence_score", grade_key="operational_intelligence_grade")
        executive_section = self._section(executive_command, status_key="executive_governance_status", authority_key="executive_governance_authority", score_key="executive_governance_score", grade_key="executive_governance_grade")

        score_components = [
            activation_section["score"],
            supervision_section["score"],
            audit_section["score"],
            incident_section["score"],
            continuity_section["score"],
            release_section["score"],
            intelligence_section["score"],
            executive_section["score"],
        ]
        executive_score = round(mean(score_components), 2) if score_components else 0.0
        status = _status_from_score(executive_score)
        if any(section["authority"] == "NO_GO" for section in [activation_section, supervision_section, audit_section, incident_section, continuity_section, release_section, intelligence_section, executive_section]):
            status = "blocked"
        elif any(section["authority"] == "WATCH" for section in [activation_section, supervision_section, audit_section, incident_section, continuity_section, release_section, intelligence_section, executive_section]):
            if status == "ok":
                status = "watch"
        authority = _authority_from_status(status)
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"
        institutional_rollout_readiness = {
            "ready_for_controlled_rollout": status == "ok" and release_section["authority"] == "GO" and activation_section["authority"] == "GO" and supervision_section["authority"] == "GO",
            "rollout_readiness_status": "PASS" if status == "ok" else "WARN" if status == "watch" else "FAIL",
            "rollout_readiness_score": executive_score,
            "rollout_readiness_grade": grade,
            "release_authority_valid": release_section["authority"] == "GO",
            "activation_ready": activation_section["authority"] == "GO",
            "supervision_ready": supervision_section["authority"] == "GO",
            "audit_ready": audit_section["authority"] == "GO",
            "incident_ready": incident_section["authority"] == "GO",
            "continuity_ready": continuity_section["authority"] == "GO",
            "intelligence_ready": intelligence_section["authority"] == "GO",
        }
        governance_degradation_indicators = {
            "activation_degradation": activation_section["status"] != "ok",
            "supervision_degradation": supervision_section["status"] != "ok",
            "audit_degradation": audit_section["status"] != "ok",
            "incident_degradation": incident_section["status"] != "ok",
            "continuity_degradation": continuity_section["status"] != "ok",
            "release_degradation": release_section["status"] != "ok",
            "intelligence_degradation": intelligence_section["status"] != "ok",
            "executive_degradation": executive_section["status"] != "ok",
        }
        executive_escalation_indicators = {
            "escalation_required": status != "ok",
            "high_risk": executive_score < 70.0 or any(section["authority"] == "NO_GO" for section in [activation_section, supervision_section, audit_section, incident_section, continuity_section, release_section]),
            "governance_degradation": any(governance_degradation_indicators.values()),
            "supervision_saturation": supervision_section["status"] != "ok",
            "audit_gap": audit_section["status"] != "ok",
            "incident_escalation": incident_section["status"] != "ok",
            "continuity_gap": continuity_section["status"] != "ok",
            "release_blocker": release_section["authority"] != "GO",
            "intelligence_drift": intelligence_section["status"] != "ok",
            "rollout_freeze": bool(_safe_dict(activation.get("rollout_freeze_indicators")).get("freeze_active")) or bool(_safe_dict(continuity.get("continuity_freeze_indicators"))),
            "human_supervision_required": True,
        }
        warnings = _safe_list(activation.get("warnings")) + _safe_list(supervision.get("warnings")) + _safe_list(audit.get("warnings")) + _safe_list(incident.get("warnings")) + _safe_list(continuity.get("warnings")) + _safe_list(release.get("warnings")) + _safe_list(intelligence.get("warnings")) + _safe_list(executive_command.get("warnings"))
        if status != "ok" and "executive_governance_watch" not in warnings:
            warnings.append("executive_governance_watch")
        return {
            "analysis_id": _safe_str(activation.get("analysis_id") or release.get("analysis_id") or executive_command.get("analysis_id"), f"executive-governance-index:{_now_iso()}"),
            "generated_at": _safe_str(activation.get("generated_at") or release.get("generated_at") or executive_command.get("generated_at"), _now_iso()),
            "activation_readiness": activation_section,
            "supervision_readiness": supervision_section,
            "audit_completeness": audit_section,
            "incident_severity": incident_section,
            "continuity_readiness": continuity_section,
            "release_authority": release_section,
            "operational_intelligence": intelligence_section,
            "executive_command": executive_section,
            "executive_governance_index_score": executive_score,
            "executive_governance_index_status": status,
            "executive_governance_index_authority": authority,
            "executive_governance_index_grade": grade,
            "institutional_rollout_readiness": institutional_rollout_readiness,
            "governance_degradation_indicators": governance_degradation_indicators,
            "executive_escalation_indicators": executive_escalation_indicators,
            "summary_components": {
                "activation": activation_section["score"],
                "supervision": supervision_section["score"],
                "audit": audit_section["score"],
                "incident": incident_section["score"],
                "continuity": continuity_section["score"],
                "release": release_section["score"],
                "intelligence": intelligence_section["score"],
                "executive_command": executive_section["score"],
            },
            "warnings": warnings,
        }

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        sources = self._history_sources()
        base_source = sources["activation"] or sources["release"] or sources["supervision"] or sources["executive_command"] or sources["intelligence"]
        if not base_source:
            return []
        entries: List[Dict[str, Any]] = []
        max_items = min(max(1, int(limit)), len(base_source))
        for index in range(max_items):
            entry = self._consolidated_history_entry(index, sources)
            entries.append(entry)
        return entries

    def _summarize(self, history: List[Dict[str, Any]], latest: Dict[str, Any]) -> Dict[str, Any]:
        scores = [_safe_float(item.get("executive_governance_index_score"), 0.0) for item in history]
        return {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(latest.get("analysis_id"), ""),
            "latest_score": _safe_float(latest.get("executive_governance_index_score"), 0.0),
            "score_history": _history_points(scores[: max(1, len(scores))]) if scores else _history_points([]),
        }

    def list_executive_governance_index(self, limit: int = 20) -> Dict[str, Any]:
        latest_snapshots = self._latest_snapshots()
        history = self._history(limit=limit)
        latest = self._latest_history_entry_from_snapshots(latest_snapshots)
        if history:
            latest = {**history[0], **latest}
        status = _safe_str(latest.get("executive_governance_index_status"), "watch")
        if status == "ok":
            warnings: List[str] = []
        else:
            warnings = _safe_list(latest.get("warnings"))
        if not history and all(_safe_str(snapshot.get("status"), "not_found") == "not_found" for snapshot in latest_snapshots.values()):
            return {
                "status": "not_found",
                "message": "No executive governance index history has been recorded yet.",
                "executive_governance_index": {},
            }
        summary = self._summarize(history, latest)
        return {
            "status": status,
            "generated_at": _now_iso(),
            "executive_governance_index_status": status,
            "executive_governance_index_authority": _safe_str(latest.get("executive_governance_index_authority"), _authority_from_status(status)),
            "executive_governance_index_score": _safe_float(latest.get("executive_governance_index_score"), 0.0),
            "executive_governance_index_grade": _safe_str(latest.get("executive_governance_index_grade"), "blocked"),
            "latest_executive_governance_index": latest,
            "executive_governance_index_history": history,
            "executive_governance_index_history_summary": summary,
            "consolidated_governance_history": history,
            "consolidated_governance_history_summary": summary,
            "activation_readiness": latest.get("activation_readiness", {}),
            "supervision_readiness": latest.get("supervision_readiness", {}),
            "audit_completeness": latest.get("audit_completeness", {}),
            "incident_severity": latest.get("incident_severity", {}),
            "continuity_readiness": latest.get("continuity_readiness", {}),
            "release_authority": latest.get("release_authority", {}),
            "operational_intelligence": latest.get("operational_intelligence", {}),
            "institutional_rollout_readiness": latest.get("institutional_rollout_readiness", {}),
            "governance_degradation_indicators": latest.get("governance_degradation_indicators", {}),
            "executive_escalation_indicators": latest.get("executive_escalation_indicators", {}),
            "summary_components": latest.get("summary_components", {}),
            "warnings": warnings,
            "latest_activation_governance": latest_snapshots["activation"],
            "latest_supervision_command": latest_snapshots["supervision"],
            "latest_operations_audit": latest_snapshots["audit"],
            "latest_incident_governance": latest_snapshots["incident"],
            "latest_continuity_governance": latest_snapshots["continuity"],
            "latest_release_governance": latest_snapshots["release"],
            "latest_operational_intelligence": latest_snapshots["intelligence"],
            "latest_executive_command": latest_snapshots["executive_command"],
        }

    def _latest_history_entry_from_snapshots(self, snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        activation = _safe_dict(snapshots["activation"])
        supervision = _safe_dict(snapshots["supervision"])
        audit = _safe_dict(snapshots["audit"])
        incident = _safe_dict(snapshots["incident"])
        continuity = _safe_dict(snapshots["continuity"])
        release = _safe_dict(snapshots["release"])
        intelligence = _safe_dict(snapshots["intelligence"])
        executive_command = _safe_dict(snapshots["executive_command"])

        activation_section = self._section(activation, status_key="activation_governance_status", authority_key="activation_governance_authority", score_key="activation_governance_score", grade_key="activation_governance_grade")
        supervision_section = self._section(supervision, status_key="supervision_command_status", authority_key="supervision_command_authority", score_key="supervision_command_score", grade_key="supervision_command_grade")
        audit_section = self._section(audit, status_key="operations_audit_status", authority_key="operations_audit_authority", score_key="operations_audit_score", grade_key="operations_audit_grade")
        incident_section = self._section(incident, status_key="incident_governance_status", authority_key="incident_governance_authority", score_key="incident_governance_score", grade_key="incident_governance_grade")
        continuity_section = self._section(continuity, status_key="continuity_governance_status", authority_key="continuity_governance_authority", score_key="continuity_governance_score", grade_key="continuity_governance_grade")
        release_section = self._section(release, status_key="release_governance_status", authority_key="release_governance_authority", score_key="release_governance_score", grade_key="release_governance_grade")
        intelligence_section = self._section(intelligence, status_key="operational_intelligence_status", authority_key="operational_intelligence_authority", score_key="operational_intelligence_score", grade_key="operational_intelligence_grade")
        executive_section = self._section(executive_command, status_key="executive_governance_status", authority_key="executive_governance_authority", score_key="executive_governance_score", grade_key="executive_governance_grade")

        score_components = [
            activation_section["score"],
            supervision_section["score"],
            audit_section["score"],
            incident_section["score"],
            continuity_section["score"],
            release_section["score"],
            intelligence_section["score"],
            executive_section["score"],
        ]
        executive_score = round(mean(score_components), 2) if score_components else 0.0
        status = _status_from_score(executive_score)
        if any(section["authority"] == "NO_GO" for section in [activation_section, supervision_section, audit_section, incident_section, continuity_section, release_section, intelligence_section, executive_section]):
            status = "blocked"
        elif any(section["authority"] == "WATCH" for section in [activation_section, supervision_section, audit_section, incident_section, continuity_section, release_section, intelligence_section, executive_section]):
            if status == "ok":
                status = "watch"
        authority = _authority_from_status(status)
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"
        governance_degradation_indicators = {
            "activation_degradation": activation_section["status"] != "ok",
            "supervision_degradation": supervision_section["status"] != "ok",
            "audit_degradation": audit_section["status"] != "ok",
            "incident_degradation": incident_section["status"] != "ok",
            "continuity_degradation": continuity_section["status"] != "ok",
            "release_degradation": release_section["status"] != "ok",
            "intelligence_degradation": intelligence_section["status"] != "ok",
            "executive_degradation": executive_section["status"] != "ok",
        }
        executive_escalation_indicators = {
            "escalation_required": status != "ok",
            "high_risk": executive_score < 70.0 or any(section["authority"] == "NO_GO" for section in [activation_section, supervision_section, audit_section, incident_section, continuity_section, release_section]),
            "governance_degradation": any(governance_degradation_indicators.values()),
            "supervision_saturation": supervision_section["status"] != "ok",
            "audit_gap": audit_section["status"] != "ok",
            "incident_escalation": incident_section["status"] != "ok",
            "continuity_gap": continuity_section["status"] != "ok",
            "release_blocker": release_section["authority"] != "GO",
            "intelligence_drift": intelligence_section["status"] != "ok",
            "rollout_freeze": bool(_safe_dict(activation.get("rollout_freeze_indicators")).get("freeze_active")) or bool(_safe_dict(continuity.get("continuity_freeze_indicators"))),
            "human_supervision_required": True,
        }
        institutional_rollout_readiness = {
            "ready_for_controlled_rollout": status == "ok" and release_section["authority"] == "GO" and activation_section["authority"] == "GO" and supervision_section["authority"] == "GO",
            "rollout_readiness_status": "PASS" if status == "ok" else "WARN" if status == "watch" else "FAIL",
            "rollout_readiness_score": executive_score,
            "rollout_readiness_grade": grade,
            "release_authority_valid": release_section["authority"] == "GO",
            "activation_ready": activation_section["authority"] == "GO",
            "supervision_ready": supervision_section["authority"] == "GO",
            "audit_ready": audit_section["authority"] == "GO",
            "incident_ready": incident_section["authority"] == "GO",
            "continuity_ready": continuity_section["authority"] == "GO",
            "intelligence_ready": intelligence_section["authority"] == "GO",
        }
        warnings = _safe_list(activation.get("warnings")) + _safe_list(supervision.get("warnings")) + _safe_list(audit.get("warnings")) + _safe_list(incident.get("warnings")) + _safe_list(continuity.get("warnings")) + _safe_list(release.get("warnings")) + _safe_list(intelligence.get("warnings")) + _safe_list(executive_command.get("warnings"))
        if status != "ok" and "executive_governance_watch" not in warnings:
            warnings.append("executive_governance_watch")
        return {
            "analysis_id": _safe_str(activation.get("analysis_id") or release.get("analysis_id") or executive_command.get("analysis_id"), f"executive-governance-index:{_now_iso()}"),
            "generated_at": _safe_str(activation.get("generated_at") or release.get("generated_at") or executive_command.get("generated_at"), _now_iso()),
            "activation_readiness": activation_section,
            "supervision_readiness": supervision_section,
            "audit_completeness": audit_section,
            "incident_severity": incident_section,
            "continuity_readiness": continuity_section,
            "release_authority": release_section,
            "operational_intelligence": intelligence_section,
            "executive_command": executive_section,
            "executive_governance_index_score": executive_score,
            "executive_governance_index_status": status,
            "executive_governance_index_authority": authority,
            "executive_governance_index_grade": grade,
            "institutional_rollout_readiness": institutional_rollout_readiness,
            "governance_degradation_indicators": governance_degradation_indicators,
            "executive_escalation_indicators": executive_escalation_indicators,
            "summary_components": {
                "activation": activation_section["score"],
                "supervision": supervision_section["score"],
                "audit": audit_section["score"],
                "incident": incident_section["score"],
                "continuity": continuity_section["score"],
                "release": release_section["score"],
                "intelligence": intelligence_section["score"],
                "executive_command": executive_section["score"],
            },
            "warnings": warnings,
        }

    def latest_executive_governance_index(self) -> Dict[str, Any]:
        response = self.list_executive_governance_index(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No executive governance index history has been recorded yet.",
                "executive_governance_index": {},
            }
        return {
            "status": response.get("status", "watch"),
            "executive_governance_index_status": response.get("executive_governance_index_status", "watch"),
            "executive_governance_index_authority": response.get("executive_governance_index_authority", "WATCH"),
            "executive_governance_index_score": response.get("executive_governance_index_score", 0.0),
            "executive_governance_index_grade": response.get("executive_governance_index_grade", "blocked"),
            "latest_executive_governance_index": response.get("latest_executive_governance_index", {}),
            "executive_governance_index_history": response.get("executive_governance_index_history", []),
            "executive_governance_index_history_summary": response.get("executive_governance_index_history_summary", {}),
            "consolidated_governance_history": response.get("consolidated_governance_history", []),
            "consolidated_governance_history_summary": response.get("consolidated_governance_history_summary", {}),
            "activation_readiness": response.get("activation_readiness", {}),
            "supervision_readiness": response.get("supervision_readiness", {}),
            "audit_completeness": response.get("audit_completeness", {}),
            "incident_severity": response.get("incident_severity", {}),
            "continuity_readiness": response.get("continuity_readiness", {}),
            "release_authority": response.get("release_authority", {}),
            "operational_intelligence": response.get("operational_intelligence", {}),
            "institutional_rollout_readiness": response.get("institutional_rollout_readiness", {}),
            "governance_degradation_indicators": response.get("governance_degradation_indicators", {}),
            "executive_escalation_indicators": response.get("executive_escalation_indicators", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
            "latest_activation_governance": response.get("latest_activation_governance", {}),
            "latest_supervision_command": response.get("latest_supervision_command", {}),
            "latest_operations_audit": response.get("latest_operations_audit", {}),
            "latest_incident_governance": response.get("latest_incident_governance", {}),
            "latest_continuity_governance": response.get("latest_continuity_governance", {}),
            "latest_release_governance": response.get("latest_release_governance", {}),
            "latest_operational_intelligence": response.get("latest_operational_intelligence", {}),
            "latest_executive_command": response.get("latest_executive_command", {}),
        }

    def executive_governance_index_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_executive_governance_index(limit=limit)
        return {
            "status": response.get("status", "watch"),
            "count": len(response.get("executive_governance_index_history", [])),
            "executive_governance_index_history": response.get("executive_governance_index_history", []),
            "executive_governance_index_history_summary": response.get("executive_governance_index_history_summary", {}),
            "consolidated_governance_history": response.get("consolidated_governance_history", []),
            "consolidated_governance_history_summary": response.get("consolidated_governance_history_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }
