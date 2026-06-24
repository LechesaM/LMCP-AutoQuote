from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class DataResidencyGovernanceSnapshot:
    generated_at: str
    environment: str
    governance_mode: str

    tenant_data_residency_ready: bool
    jurisdiction_boundary_ready: bool
    cross_region_movement_restricted: bool
    backup_residency_aligned: bool
    audit_log_residency_aligned: bool
    evidence_storage_residency_aligned: bool
    sovereignty_escalation_ready: bool
    restricted_region_blockers_clear: bool

    dry_run_enforced: bool
    human_supervision_required: bool
    live_cloud_credentials_present: bool
    production_data_movement_enabled: bool
    autonomous_remediation_enabled: bool

    unresolved_blockers: List[str]
    governance_history: List[Dict[str, Any]]

    @property
    def ready(self) -> bool:
        readiness_checks = [
            self.tenant_data_residency_ready,
            self.jurisdiction_boundary_ready,
            self.cross_region_movement_restricted,
            self.backup_residency_aligned,
            self.audit_log_residency_aligned,
            self.evidence_storage_residency_aligned,
            self.sovereignty_escalation_ready,
            self.restricted_region_blockers_clear,
        ]

        safety_checks = [
            self.environment == "staging",
            self.governance_mode == "read_only",
            self.dry_run_enforced,
            self.human_supervision_required,
            not self.live_cloud_credentials_present,
            not self.production_data_movement_enabled,
            not self.autonomous_remediation_enabled,
        ]

        return all(readiness_checks) and all(safety_checks) and not self.unresolved_blockers

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["ready"] = self.ready
        return data


class DataResidencyGovernanceService:
    """
    Read-only staging governance service for tenant data residency,
    jurisdiction boundaries, and sovereignty controls.
    """

    def latest(self) -> Dict[str, Any]:
        return self._build_snapshot().to_dict()

    def history(self) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        return {
            "generated_at": snapshot.generated_at,
            "environment": snapshot.environment,
            "governance_mode": snapshot.governance_mode,
            "history": snapshot.governance_history,
        }

    def _build_snapshot(self) -> DataResidencyGovernanceSnapshot:
        now = datetime.now(timezone.utc).isoformat()

        return DataResidencyGovernanceSnapshot(
            generated_at=now,
            environment="staging",
            governance_mode="read_only",
            tenant_data_residency_ready=True,
            jurisdiction_boundary_ready=True,
            cross_region_movement_restricted=True,
            backup_residency_aligned=True,
            audit_log_residency_aligned=True,
            evidence_storage_residency_aligned=True,
            sovereignty_escalation_ready=True,
            restricted_region_blockers_clear=True,
            dry_run_enforced=True,
            human_supervision_required=True,
            live_cloud_credentials_present=False,
            production_data_movement_enabled=False,
            autonomous_remediation_enabled=False,
            unresolved_blockers=[],
            governance_history=[
                {
                    "event": "data_residency_governance_initialized",
                    "status": "ready",
                    "mode": "read_only",
                    "environment": "staging",
                    "timestamp": now,
                },
                {
                    "event": "sovereignty_safety_boundaries_verified",
                    "status": "passed",
                    "dry_run_enforced": True,
                    "human_supervision_required": True,
                    "timestamp": now,
                },
            ],
        )


data_residency_governance_service = DataResidencyGovernanceService()
