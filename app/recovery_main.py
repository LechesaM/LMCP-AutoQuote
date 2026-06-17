from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.route_policy import apply_recovery_route_policy, build_recovery_policy_introspection
from app.config import settings


def _build_placeholder_summary(name: str) -> Dict[str, Any]:
    return {
        "status": "ok",
        "mode": "recovery",
        "name": name,
    }


def build_application() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    allow_origins = list(settings.cors_origins) if settings.cors_origins else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root() -> Dict[str, Any]:
        return {
            "message": f"{settings.app_name} API is running",
            "status": "ok",
            "mode": "recovery",
        }

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": settings.app_name,
            "mode": "recovery",
        }

    @app.get("/health/system")
    def system_health() -> Dict[str, Any]:
        return _build_placeholder_summary("system-health")

    @app.get("/health/workflows")
    def workflow_health() -> Dict[str, Any]:
        return _build_placeholder_summary("workflow-health")

    @app.get("/health/operational-report")
    def operational_report() -> Dict[str, Any]:
        return _build_placeholder_summary("operational-report")

    @app.get("/dashboard/workflows")
    def dashboard_workflows() -> Dict[str, Any]:
        return {"status": "ok", "workflows": []}

    @app.get("/dashboard/refusals")
    def dashboard_refusals() -> Dict[str, Any]:
        return {"status": "ok", "refusals": []}

    @app.get("/dashboard/health")
    def dashboard_health() -> Dict[str, Any]:
        return _build_placeholder_summary("dashboard-health")

    @app.get("/dashboard/queues")
    def dashboard_queues() -> Dict[str, Any]:
        return {"status": "ok", "queues": {}}

    @app.get("/dashboard/summary")
    def dashboard_summary() -> Dict[str, Any]:
        return {"status": "ok", "summary": {}}

    @app.get("/pilot/summary")
    def pilot_summary() -> Dict[str, Any]:
        return _build_placeholder_summary("pilot-summary")

    @app.get("/pilot/readiness")
    def pilot_readiness() -> Dict[str, Any]:
        return _build_placeholder_summary("pilot-readiness")

    @app.get("/pilot/signoffs")
    def pilot_signoffs() -> Dict[str, Any]:
        return {"status": "ok", "signoffs": []}

    @app.get("/telemetry/dashboard")
    def telemetry_dashboard(limit: int = 100) -> Dict[str, Any]:
        return {"status": "ok", "limit": limit}

    @app.get("/telemetry/review-queue")
    def telemetry_review_queue(limit: int = 100) -> Dict[str, Any]:
        return {"status": "ok", "limit": limit}

    @app.get("/telemetry/source-health")
    def telemetry_source_health(limit: int = 100) -> Dict[str, Any]:
        return {"status": "ok", "limit": limit}

    @app.get("/telemetry/operational-health")
    def telemetry_operational_health(limit: int = 100) -> Dict[str, Any]:
        return {"status": "ok", "limit": limit}

    @app.get("/telemetry/qualification")
    def telemetry_qualification(limit: int = 100) -> Dict[str, Any]:
        return {"status": "ok", "limit": limit}

    @app.get("/supplier-quotes/status")
    def supplier_quotes_status() -> Dict[str, Any]:
        return _build_placeholder_summary("supplier-quotes-status")

    @app.get("/supplier-quotes/auto-ingest/status")
    def supplier_quotes_auto_ingest_status() -> Dict[str, Any]:
        return _build_placeholder_summary("supplier-quotes-auto-ingest-status")

    @app.get("/supplier-quotes/intelligence/status")
    def supplier_quotes_intelligence_status() -> Dict[str, Any]:
        return _build_placeholder_summary("supplier-quotes-intelligence-status")

    @app.get("/operations/runtime-metrics")
    def operations_runtime_metrics() -> Dict[str, Any]:
        return _build_placeholder_summary("operations-runtime-metrics")

    @app.get("/operations/backup-validation")
    def operations_backup_validation() -> Dict[str, Any]:
        return _build_placeholder_summary("operations-backup-validation")

    @app.get("/governance/compliance-report")
    def governance_compliance_report() -> Dict[str, Any]:
        return _build_placeholder_summary("governance-compliance-report")

    @app.get("/governance/compliance-controls")
    def governance_compliance_controls() -> Dict[str, Any]:
        return _build_placeholder_summary("governance-compliance-controls")

    @app.get("/governance/policies")
    def governance_policies() -> Dict[str, Any]:
        return _build_placeholder_summary("governance-policies")

    @app.get("/observability/uptime")
    def observability_uptime() -> Dict[str, Any]:
        return _build_placeholder_summary("observability-uptime")

    @app.get("/observability/sla")
    def observability_sla() -> Dict[str, Any]:
        return _build_placeholder_summary("observability-sla")

    @app.get("/observability/anomalies")
    def observability_anomalies() -> Dict[str, Any]:
        return _build_placeholder_summary("observability-anomalies")

    @app.get("/productivity/review-efficiency")
    def productivity_review_efficiency() -> Dict[str, Any]:
        return _build_placeholder_summary("productivity-review-efficiency")

    @app.get("/productivity/focus-sessions")
    def productivity_focus_sessions() -> Dict[str, Any]:
        return _build_placeholder_summary("productivity-focus-sessions")

    @app.get("/stabilization/runtime")
    def stabilization_runtime() -> Dict[str, Any]:
        return _build_placeholder_summary("stabilization-runtime")

    @app.get("/stabilization/fallback-health")
    def stabilization_fallback_health() -> Dict[str, Any]:
        return _build_placeholder_summary("stabilization-fallback-health")

    @app.get("/business/executive-summary")
    def business_executive_summary() -> Dict[str, Any]:
        return _build_placeholder_summary("business-executive-summary")

    @app.get("/business/profitability")
    def business_profitability() -> Dict[str, Any]:
        return _build_placeholder_summary("business-profitability")

    @app.get("/system/recovery-policy")
    def recovery_policy() -> Dict[str, Any]:
        return build_recovery_policy_introspection(app.routes)

    @app.post("/auth/login")
    def auth_login() -> Dict[str, Any]:
        return _build_placeholder_summary("auth-login")

    @app.get("/operator-auth/status")
    def operator_auth_status() -> Dict[str, Any]:
        return _build_placeholder_summary("operator-auth-status")

    app.state.route_policy_report = build_recovery_policy_introspection(app.routes)
    apply_recovery_route_policy(app)
    return app


app = build_application()
