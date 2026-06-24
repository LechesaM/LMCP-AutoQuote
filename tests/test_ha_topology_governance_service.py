from __future__ import annotations

import importlib
from pathlib import Path


class _DummyOperationalizationService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_production_governance(self):
        return self._payload

    def production_governance_history(self, limit: int = 20):
        return {
            "status": self._payload["status"],
            "count": len(self._payload["production_governance_history"]),
            "production_governance_history": self._payload["production_governance_history"],
            "production_governance_history_summary": self._payload["production_governance_history_summary"],
            "summary_components": self._payload["summary_components"],
            "warnings": self._payload["warnings"],
        }


class _DummySupervisionService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_supervision_command(self):
        return self._payload


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_k8s_package(root: Path, *, redis_replicas: int, postgres_replicas: int) -> None:
    _write(
        root / "k8s" / "base" / "kustomization.yaml",
        """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - configmap.yaml
  - secret-placeholders.yaml
  - backend-deployment.yaml
  - backend-service.yaml
  - frontend-deployment.yaml
  - frontend-service.yaml
  - worker-deployment.yaml
  - redis-deployment.yaml
  - redis-service.yaml
  - postgres-statefulset.yaml
  - postgres-service.yaml
  - prometheus-deployment.yaml
  - prometheus-service.yaml
  - grafana-deployment.yaml
  - grafana-service.yaml
  - network-policy.yaml
  - persistent-volume-claims.yaml
""",
    )
    _write(root / "k8s" / "base" / "namespace.yaml", "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: lmcp\n")
    _write(
        root / "k8s" / "base" / "configmap.yaml",
        """apiVersion: v1
kind: ConfigMap
metadata:
  name: lmcp-runtime-config
data:
  LMCP_ENV: staging
  LMCP_DEPLOYMENT_PROFILE: distributed-staging
  LMCP_ALLOW_FINAL_AUTOMATION: "false"
  LMCP_DRY_RUN_MODE: "true"
  LMCP_REQUIRE_HUMAN_SUPERVISION: "true"
  LMCP_SUBMISSION_LOCK_FILE: /app/runtime/staging/go_live_guards/submission_locks.json
""",
    )
    _write(root / "k8s" / "base" / "secret-placeholders.yaml", "apiVersion: v1\nkind: Secret\nmetadata:\n  name: lmcp-secret-placeholders\ntype: Opaque\ndata:\n  POSTGRES_PASSWORD: cGxhY2Vob2xkZXI=\n")
    _write(root / "k8s" / "base" / "backend-deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: backend\nspec:\n  replicas: 3\n")
    _write(root / "k8s" / "base" / "backend-service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: backend\n")
    _write(root / "k8s" / "base" / "frontend-deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: frontend\nspec:\n  replicas: 2\n")
    _write(root / "k8s" / "base" / "frontend-service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: frontend\n")
    _write(root / "k8s" / "base" / "worker-deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: worker\nspec:\n  replicas: 3\n")
    _write(root / "k8s" / "base" / "redis-deployment.yaml", f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: redis\nspec:\n  replicas: {redis_replicas}\n")
    _write(root / "k8s" / "base" / "redis-service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: redis\n")
    _write(root / "k8s" / "base" / "postgres-statefulset.yaml", f"apiVersion: apps/v1\nkind: StatefulSet\nmetadata:\n  name: postgres\nspec:\n  replicas: {postgres_replicas}\n")
    _write(root / "k8s" / "base" / "postgres-service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: postgres\n")
    _write(root / "k8s" / "base" / "prometheus-deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: prometheus\n")
    _write(root / "k8s" / "base" / "prometheus-service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: prometheus\n")
    _write(root / "k8s" / "base" / "grafana-deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: grafana\n")
    _write(root / "k8s" / "base" / "grafana-service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: grafana\n")
    _write(root / "k8s" / "base" / "network-policy.yaml", "apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata:\n  name: default-deny-all\n")
    _write(root / "k8s" / "base" / "persistent-volume-claims.yaml", "apiVersion: v1\nkind: PersistentVolumeClaim\nmetadata:\n  name: postgres-data\n")
    _write(root / "k8s" / "overlays" / "staging" / "kustomization.yaml", "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - ../../base\npatchesStrategicMerge:\n  - patches/staging-safety-patch.yaml\n")
    _write(root / "k8s" / "overlays" / "production" / "kustomization.yaml", "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - ../../base\npatchesStrategicMerge:\n  - patches/production-safety-patch.yaml\n")
    _write(
        root / "k8s" / "overlays" / "staging" / "patches" / "staging-safety-patch.yaml",
        """apiVersion: v1
kind: ConfigMap
metadata:
  name: lmcp-runtime-config
data:
  LMCP_ENV: staging
  LMCP_DEPLOYMENT_PROFILE: distributed-staging
  LMCP_ALLOW_FINAL_AUTOMATION: "false"
  LMCP_DRY_RUN_MODE: "true"
  LMCP_REQUIRE_HUMAN_SUPERVISION: "true"
  LMCP_SUBMISSION_LOCK_FILE: /app/runtime/staging/go_live_guards/submission_locks.json
""",
    )
    _write(
        root / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml",
        """apiVersion: v1
kind: ConfigMap
metadata:
  name: lmcp-runtime-config
data:
  LMCP_ENV: production
  LMCP_DEPLOYMENT_PROFILE: distributed-production
  LMCP_ALLOW_FINAL_AUTOMATION: "false"
  LMCP_DRY_RUN_MODE: "true"
  LMCP_REQUIRE_HUMAN_SUPERVISION: "true"
  LMCP_SUBMISSION_LOCK_FILE: /app/runtime/production/go_live_guards/submission_locks.json
""",
    )


def _ready_operationalization_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "production_readiness_status": "ok",
        "production_readiness_score": 96.0,
        "latest_production_governance": {"analysis_id": "production-governance:ready"},
        "production_governance_history": [
            {"analysis_id": "cycle-2:production", "generated_at": "2026-06-24T10:00:00+00:00", "production_readiness_score": 96.0, "production_readiness_status": "ok"},
            {"analysis_id": "cycle-1:production", "generated_at": "2026-06-23T10:00:00+00:00", "production_readiness_score": 94.0, "production_readiness_status": "ok"},
        ],
        "production_governance_history_summary": {"analysis_count": 2, "latest_analysis_id": "cycle-2:production", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 95.0, "latest": 96.0, "previous": 94.0, "points": [96.0, 94.0]}},
        "summary_components": {"deployment_readiness": 96.0},
        "warnings": [],
        "high_availability_governance": {"high_availability_governance_status": "ok", "ha_readiness_indicators": {"queue_stable": True}},
        "backup_restore_governance": {"backup_restore_governance_status": "ok", "recovery_readiness_indicators": {"evidence_pack_available": True, "readiness_threshold_met": True}},
        "disaster_recovery_governance": {"disaster_recovery_governance_status": "ok", "recovery_readiness_indicators": {"final_readiness_cleared": True}},
        "operator_access_governance": {"operator_access_governance_status": "ok", "operator_access_risk_indicators": {"pending_approval_backlog": False}},
        "deployment_risk_indicators": {"deployment_risk": False},
        "ha_readiness_indicators": {"queue_stable": True},
        "recovery_readiness_indicators": {"final_readiness_cleared": True},
    }


def _watch_operationalization_payload() -> dict[str, object]:
    payload = _ready_operationalization_payload()
    payload["production_readiness_score"] = 74.0
    payload["production_readiness_status"] = "watch"
    payload["latest_production_governance"] = {"analysis_id": "production-governance:watch"}
    payload["production_governance_history"] = [
        {"analysis_id": "cycle-1:production", "generated_at": "2026-06-24T09:00:00+00:00", "production_readiness_score": 74.0, "production_readiness_status": "watch"}
    ]
    payload["production_governance_history_summary"] = {"analysis_count": 1, "latest_analysis_id": "cycle-1:production", "latest_score": 74.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 74.0, "latest": 74.0, "previous": 74.0, "points": [74.0]}}
    payload["high_availability_governance"] = {"high_availability_governance_status": "watch", "ha_readiness_indicators": {"queue_stable": False}}
    payload["backup_restore_governance"] = {"backup_restore_governance_status": "watch", "recovery_readiness_indicators": {"evidence_pack_available": True, "readiness_threshold_met": False}}
    payload["disaster_recovery_governance"] = {"disaster_recovery_governance_status": "watch", "recovery_readiness_indicators": {"final_readiness_cleared": False}}
    payload["operator_access_governance"] = {"operator_access_governance_status": "watch", "operator_access_risk_indicators": {"pending_approval_backlog": True}}
    payload["deployment_risk_indicators"] = {"deployment_risk": True}
    payload["ha_readiness_indicators"] = {"queue_stable": False}
    payload["recovery_readiness_indicators"] = {"final_readiness_cleared": False}
    return payload


def _supervision_payload() -> dict[str, object]:
    return {
        "supervision_coverage": {"active_supervision_coverage_ready": True, "coverage_score": 96.0},
        "operational_workload_visibility": {"active_session_count": 1, "assigned_rfq_count": 0, "pending_approval_count": 0, "workload_pressure": "low"},
        "supervision_saturation": {"supervision_saturation_active": False, "queue_backlog_count": 0, "worker_backlog_count": 0},
        "warnings": [],
    }


def test_ha_topology_governance_service_reports_ready_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.ha_topology_governance_service")
    _write_k8s_package(tmp_path, redis_replicas=2, postgres_replicas=2)
    service = module.HaTopologyGovernanceService(
        k8s_root=tmp_path / "k8s",
        production_operationalization_service=_DummyOperationalizationService(_ready_operationalization_payload()),
        supervision_command_service=_DummySupervisionService(_supervision_payload()),
    )

    latest = service.latest_ha_topology()
    history = service.ha_topology_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["ha_topology_authority"] == "GO"
    assert latest["redis_ha_readiness"]["ready"] is True
    assert latest["postgres_replication_readiness"]["ready"] is True
    assert latest["quorum_readiness"]["ready"] is True
    assert latest["failover_orchestration_readiness"]["ready"] is True
    assert latest["persistence_durability_readiness"]["ready"] is True
    assert latest["replica_supervision_readiness"]["ready"] is True
    assert latest["split_brain_prevention_readiness"]["ready"] is True
    assert latest["safety_model"]["final_automation_disabled"] is True
    assert latest["safety_model"]["dry_run_mode_enabled"] is True
    assert latest["safety_model"]["human_supervision_required"] is True
    assert history["count"] == 2
    assert history["ha_topology_history"][0]["ha_topology_authority"] == "GO"


def test_ha_topology_governance_service_reports_watch_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.ha_topology_governance_service")
    _write_k8s_package(tmp_path, redis_replicas=1, postgres_replicas=1)
    service = module.HaTopologyGovernanceService(
        k8s_root=tmp_path / "k8s",
        production_operationalization_service=_DummyOperationalizationService(_watch_operationalization_payload()),
        supervision_command_service=_DummySupervisionService(_supervision_payload()),
    )

    latest = service.latest_ha_topology()

    assert latest["status"] == "watch"
    assert latest["ha_topology_authority"] == "WATCH"
    assert latest["redis_ha_readiness"]["ready"] is False
    assert latest["postgres_replication_readiness"]["ready"] is False
    assert latest["ha_degradation_indicators"]["redis_ha_degradation"] is True
    assert latest["warnings"]
