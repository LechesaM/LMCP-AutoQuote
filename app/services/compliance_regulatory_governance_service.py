from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PLACEHOLDERS = {
    "regulatory_framework_readiness": "regulatory-framework-placeholder.yaml",
    "procurement_compliance_readiness": "procurement-compliance-placeholder.yaml",
    "audit_retention_readiness": "audit-retention-placeholder.yaml",
    "governance_evidence_completeness": "evidence-completeness-placeholder.yaml",
    "policy_exception_escalation_readiness": "policy-exception-escalation-placeholder.yaml",
    "compliance_review_supervision": "review-supervision-placeholder.yaml",
    "regulatory_blocker_visibility": "regulatory-blocker-visibility-placeholder.yaml",
}

FORBIDDEN_CONTENT_MARKERS = (
    "https://",
    "http://",
    "webhook_configs",
    "client_secret",
    "api_key",
    "access_token",
    "production-authority: true",
    "autonomous-approvals: true",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _placeholder_ready(path: Path) -> bool:
    content = _load_text(path)
    if not content:
        return False
    lowered = content.lower()
    return not any(marker in lowered for marker in FORBIDDEN_CONTENT_MARKERS)


def _blocked_reason(path: Path, *, label: str) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return {"source": label, "path": str(path), "issue": "missing_placeholder"}
    content = _load_text(path)
    lowered = content.lower()
    for marker in FORBIDDEN_CONTENT_MARKERS:
        if marker in lowered:
            return {
                "source": label,
                "path": str(path),
                "issue": "live_or_autonomous_control_detected",
                "marker": marker,
            }
    return None


@dataclass(frozen=True)
class ComplianceRegulatoryGovernanceSnapshot:
    generated_at: str
    environment: str
    governance_mode: str

    regulatory_framework_readiness: bool
    procurement_compliance_readiness: bool
    audit_retention_readiness: bool
    governance_evidence_completeness: bool
    policy_exception_escalation_readiness: bool
    compliance_review_supervision: bool
    regulatory_blocker_visibility: bool

    dry_run_enforced: bool
    human_supervision_required: bool
    autonomous_approvals_enabled: bool
    production_authority_enabled: bool
    live_regulator_integrations_present: bool

    unresolved_blockers: List[str]
    blocker_sources: List[Dict[str, Any]]
    recovery_state_history: List[Dict[str, Any]]
    recovery_rationale: Dict[str, Any]
    governance_history: List[Dict[str, Any]]

    @property
    def ready(self) -> bool:
        readiness_checks = [
            self.regulatory_framework_readiness,
            self.procurement_compliance_readiness,
            self.audit_retention_readiness,
            self.governance_evidence_completeness,
            self.policy_exception_escalation_readiness,
            self.compliance_review_supervision,
            self.regulatory_blocker_visibility,
        ]
        safety_checks = [
            self.environment == "staging",
            self.governance_mode == "read_only",
            self.dry_run_enforced,
            self.human_supervision_required,
            not self.autonomous_approvals_enabled,
            not self.production_authority_enabled,
            not self.live_regulator_integrations_present,
        ]
        return all(readiness_checks) and all(safety_checks) and not self.unresolved_blockers

    @property
    def status(self) -> str:
        if self.ready:
            return "ok"
        if self.unresolved_blockers:
            return "blocked"
        return "watch"

    @property
    def authority(self) -> str:
        return "GO" if self.ready else "NO_GO" if self.unresolved_blockers else "WATCH"

    @property
    def score(self) -> float:
        checks = [
            self.regulatory_framework_readiness,
            self.procurement_compliance_readiness,
            self.audit_retention_readiness,
            self.governance_evidence_completeness,
            self.policy_exception_escalation_readiness,
            self.compliance_review_supervision,
            self.regulatory_blocker_visibility,
            self.environment == "staging",
            self.governance_mode == "read_only",
            self.dry_run_enforced,
            self.human_supervision_required,
            not self.autonomous_approvals_enabled,
            not self.production_authority_enabled,
            not self.live_regulator_integrations_present,
        ]
        return round((sum(1 for item in checks if item) / len(checks)) * 100.0, 2)

    @property
    def grade(self) -> str:
        if self.ready:
            return "ready"
        if self.unresolved_blockers:
            return "blocked"
        return "watch"

    @property
    def recovery_state(self) -> str:
        if self.ready:
            return "recovered"
        if self.unresolved_blockers:
            return "unresolved-blocked"
        return "degraded-but-recovering"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.update(
            {
                "ready": self.ready,
                "status": self.status,
                "compliance_regulatory_governance_status": self.status,
                "compliance_regulatory_governance_authority": self.authority,
                "compliance_regulatory_governance_score": self.score,
                "compliance_regulatory_governance_grade": self.grade,
                "recovery_state": self.recovery_state,
                "score": self.score,
            }
        )
        return data


class ComplianceRegulatoryGovernanceService:
    """
    Read-only staging governance service for compliance and regulatory readiness.
    """

    def __init__(self, k8s_root: Optional[Path] = None) -> None:
        self.compliance_regulatory_root = (k8s_root or PROJECT_ROOT / "k8s") / "base" / "compliance-regulatory"

    def _placeholder_path(self, filename: str) -> Path:
        return self.compliance_regulatory_root / filename

    def _evaluate_placeholder(self, label: str, filename: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        path = self._placeholder_path(filename)
        blocker = _blocked_reason(path, label=label)
        return _placeholder_ready(path), blocker

    def _build_snapshot(self) -> ComplianceRegulatoryGovernanceSnapshot:
        now = _now_iso()

        readiness_map: Dict[str, bool] = {}
        blocker_sources: List[Dict[str, Any]] = []
        unresolved_blockers: List[str] = []

        for label, filename in REQUIRED_PLACEHOLDERS.items():
            ready, blocker = self._evaluate_placeholder(label, filename)
            readiness_map[label] = ready
            if blocker:
                blocker_sources.append(blocker)
                unresolved_blockers.append(f"{label}:{blocker['issue']}")

        live_regulator_integrations_present = any(
            blocker.get("issue") == "live_or_autonomous_control_detected" for blocker in blocker_sources
        )
        autonomous_approvals_enabled = False
        production_authority_enabled = False
        dry_run_enforced = True
        human_supervision_required = True

        recovery_state_history = [
            {
                "recovery_state": "recovered" if not unresolved_blockers and all(readiness_map.values()) else "unresolved-blocked",
                "generated_at": now,
                "status": "ready" if not unresolved_blockers and all(readiness_map.values()) else "blocked",
            }
        ]

        readiness_count = sum(1 for value in readiness_map.values() if value)
        score = round(((readiness_count + 7 - int(live_regulator_integrations_present)) / 14) * 100.0, 2)
        recovery_rationale = {
            "summary": (
                "Compliance and regulatory governance remains read-only and staging-only."
                if not unresolved_blockers
                else "Compliance and regulatory governance is blocked until placeholder or safety violations are resolved."
            ),
            "score_impact": {
                "readiness_pass_count": readiness_count,
                "total_readiness_signals": len(readiness_map),
                "final_score": score,
            },
        }

        governance_history = [
            {
                "event": "compliance_regulatory_governance_initialized",
                "status": "ready" if not unresolved_blockers and all(readiness_map.values()) else "blocked",
                "environment": "staging",
                "mode": "read_only",
                "timestamp": now,
            },
            {
                "event": "compliance_regulatory_safety_verified",
                "status": "passed" if dry_run_enforced and human_supervision_required else "failed",
                "dry_run_enforced": dry_run_enforced,
                "human_supervision_required": human_supervision_required,
                "autonomous_approvals_enabled": autonomous_approvals_enabled,
                "production_authority_enabled": production_authority_enabled,
                "live_regulator_integrations_present": live_regulator_integrations_present,
                "timestamp": now,
            },
        ]

        return ComplianceRegulatoryGovernanceSnapshot(
            generated_at=now,
            environment="staging",
            governance_mode="read_only",
            regulatory_framework_readiness=readiness_map["regulatory_framework_readiness"],
            procurement_compliance_readiness=readiness_map["procurement_compliance_readiness"],
            audit_retention_readiness=readiness_map["audit_retention_readiness"],
            governance_evidence_completeness=readiness_map["governance_evidence_completeness"],
            policy_exception_escalation_readiness=readiness_map["policy_exception_escalation_readiness"],
            compliance_review_supervision=readiness_map["compliance_review_supervision"],
            regulatory_blocker_visibility=readiness_map["regulatory_blocker_visibility"],
            dry_run_enforced=dry_run_enforced,
            human_supervision_required=human_supervision_required,
            autonomous_approvals_enabled=autonomous_approvals_enabled,
            production_authority_enabled=production_authority_enabled,
            live_regulator_integrations_present=live_regulator_integrations_present,
            unresolved_blockers=unresolved_blockers,
            blocker_sources=blocker_sources,
            recovery_state_history=recovery_state_history,
            recovery_rationale=recovery_rationale,
            governance_history=governance_history,
        )

    def list_compliance_regulatory_governance(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self._build_snapshot().to_dict()
        snapshot["count"] = 1
        snapshot["summary_counts"] = {"PASS": 1 if snapshot["ready"] else 0, "WARN": 0 if snapshot["ready"] else 1, "FAIL": 0}
        snapshot["warnings"] = snapshot["unresolved_blockers"]
        snapshot["latest_compliance_regulatory_governance"] = dict(snapshot)
        snapshot["compliance_regulatory_governance_history"] = snapshot["governance_history"][:limit]
        return snapshot

    def latest_compliance_regulatory_governance(self) -> Dict[str, Any]:
        return self._build_snapshot().to_dict()

    def compliance_regulatory_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = snapshot.governance_history[:limit]
        return {
            "status": snapshot.status,
            "environment": snapshot.environment,
            "governance_mode": snapshot.governance_mode,
            "recovery_state": snapshot.recovery_state,
            "count": len(history),
            "history": history,
            "warnings": snapshot.unresolved_blockers,
        }


compliance_regulatory_governance_service = ComplianceRegulatoryGovernanceService()
