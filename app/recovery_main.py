from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterable, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.deployment.graceful_shutdown import run_graceful_shutdown
from app.deployment.request_id import RequestIdMiddleware
from app.deployment.security_headers import SecurityHeadersMiddleware
from app.deployment.rate_limit import RateLimitMiddleware
from app.core.runtime_config import env, env_bool
from app.api.route_policy import apply_recovery_route_policy, build_recovery_policy_introspection
from app.auth.session_service import ensure_auth_schema
from app.services.operator_auth_service import ensure_operator_auth_schema

logger = logging.getLogger(__name__)


def _include_router(app: FastAPI, module_path: str) -> None:
    module = __import__(module_path, fromlist=["router"])
    app.include_router(getattr(module, "router"))


RECOVERY_ROUTERS: Tuple[str, ...] = (
    "app.api.auth_routes",
    "app.api.operator_auth_api",
    "app.api.dashboard",
    "app.api.operator_workflow_routes",
    "app.api.operator_ops_routes",
    "app.api.rfq_stable_api",
    "app.api.governance_routes",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Recovery startup: ensure_operator_auth_schema")
    ensure_operator_auth_schema()
    logger.info("Recovery startup: ensure_auth_schema")
    ensure_auth_schema()
    logger.info("Recovery startup: ready_to_yield")
    yield
    app.state.shutdown_snapshot = run_graceful_shutdown(reason="fastapi lifespan shutdown")
    logger.info("Recovery shutdown snapshot: %s", app.state.shutdown_snapshot.get("status", "unknown"))


def build_application() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    allow_origins = list(settings.cors_origins) if settings.cors_origins else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if env_bool("LMCP_RATE_LIMIT_ENABLED", True):
        app.add_middleware(
            RateLimitMiddleware,
            enabled=True,
            max_requests=int(env("LMCP_RATE_LIMIT_PER_MINUTE", "60")),
            window_seconds=60,
        )

    for module_path in RECOVERY_ROUTERS:
        _include_router(app, module_path)

    @app.get("/")
    def root() -> Dict[str, Any]:
        return {
            "message": f"{settings.app_name} API is running",
            "status": "ok",
            "mode": "recovery",
            "loaded_routers": list(RECOVERY_ROUTERS),
        }

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": settings.app_name,
            "mode": "recovery",
            "loaded_routers": list(RECOVERY_ROUTERS),
        }

    @app.get("/health/system")
    def system_health() -> Dict[str, Any]:
        from app.monitoring.health_service import get_system_health

        return get_system_health()

    @app.get("/health/workflows")
    def workflow_health() -> Dict[str, Any]:
        from app.monitoring.workflow_monitor import get_workflow_summary

        return get_workflow_summary()

    @app.get("/health/operational-report")
    def operational_report() -> Dict[str, Any]:
        from app.monitoring.reporting_service import build_operational_report

        return build_operational_report()

    @app.get("/dashboard/workflows")
    def dashboard_workflows() -> Dict[str, Any]:
        from app.dashboard.dashboard_service import (
            get_recent_approvals,
            get_recent_proofs,
            get_recent_refusals,
            get_recent_reviews,
            get_recent_workflows,
        )

        return {
            "workflows": get_recent_workflows(),
            "approvals": get_recent_approvals(),
            "reviews": get_recent_reviews(),
            "proofs": get_recent_proofs(),
            "refusals": get_recent_refusals(),
        }

    @app.get("/dashboard/refusals")
    def dashboard_refusals() -> Dict[str, Any]:
        from app.dashboard.dashboard_service import get_recent_refusals

        return {
            "refusals": get_recent_refusals(),
        }

    @app.get("/dashboard/health")
    def dashboard_health() -> Dict[str, Any]:
        from app.dashboard.health_views import get_dashboard_health

        return get_dashboard_health()

    @app.get("/dashboard/queues")
    def dashboard_queues() -> Dict[str, Any]:
        from app.dashboard.workflow_queue_service import (
            get_archived_queue,
            get_pending_approval_queue,
            get_proof_capture_queue,
            get_refused_queue,
            get_review_ready_queue,
        )

        return {
            "pending_approvals": get_pending_approval_queue(),
            "review_ready": get_review_ready_queue(),
            "proof_capture": get_proof_capture_queue(),
            "refused": get_refused_queue(),
            "archived": get_archived_queue(),
        }

    @app.get("/pilot/summary")
    def pilot_summary() -> Dict[str, Any]:
        from app.pilot.pilot_metrics import get_pilot_metrics
        from app.pilot.pilot_run_service import get_pilot_failures, get_pilot_successes, get_pilot_summary

        return {
            "pilot_summary": get_pilot_summary(),
            "pilot_metrics": get_pilot_metrics(),
            "pilot_failures": get_pilot_failures(),
            "pilot_successes": get_pilot_successes(),
        }

    @app.get("/pilot/readiness")
    def pilot_readiness() -> Dict[str, Any]:
        from app.pilot.pilot_readiness_report import build_pilot_readiness_report

        return build_pilot_readiness_report()

    @app.get("/pilot/signoffs")
    def pilot_signoffs() -> Dict[str, Any]:
        from app.pilot.pilot_signoff import get_pilot_signoffs

        return {"signoffs": get_pilot_signoffs(limit=200)}

    @app.get("/telemetry/dashboard")
    def telemetry_dashboard(limit: int = 100) -> Dict[str, Any]:
        from app.api.telemetry_contracts import build_dashboard_telemetry_response

        return build_dashboard_telemetry_response(limit=limit)

    @app.get("/telemetry/review-queue")
    def telemetry_review_queue(limit: int = 100) -> Dict[str, Any]:
        from app.api.telemetry_contracts import build_review_queue_telemetry_response

        return build_review_queue_telemetry_response(limit=limit)

    @app.get("/telemetry/source-health")
    def telemetry_source_health(limit: int = 100) -> Dict[str, Any]:
        from app.api.telemetry_contracts import build_source_health_telemetry_response

        return build_source_health_telemetry_response(limit=limit)

    @app.get("/telemetry/operational-health")
    def telemetry_operational_health(limit: int = 100) -> Dict[str, Any]:
        from app.api.telemetry_contracts import build_operational_health_telemetry_response

        return build_operational_health_telemetry_response(limit=limit)

    @app.get("/telemetry/qualification")
    def telemetry_qualification(limit: int = 100) -> Dict[str, Any]:
        from app.api.telemetry_contracts import build_qualification_telemetry_response

        return build_qualification_telemetry_response(limit=limit)

    @app.get("/system/recovery-policy")
    def recovery_policy() -> Dict[str, Any]:
        return build_recovery_policy_introspection(app.routes)

    return app


app = build_application()
app.state.route_policy_report = apply_recovery_route_policy(app)
