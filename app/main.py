from __future__ import annotations

import importlib
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterable, List, Tuple

from fastapi import FastAPI
from fastapi import Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from app.api.router_registry import RouterSpec, iter_router_specs
from app.config import settings
from app.deployment.deployment_report import build_deployment_report
from app.deployment.environment_validator import validate_environment
from app.deployment.graceful_shutdown import run_graceful_shutdown
from app.deployment.startup_validator import validate_startup
from app.core.runtime_config import get_runtime_config
from app.dashboard.dashboard_service import (
    get_dashboard_summary,
    get_recent_approvals,
    get_recent_proofs,
    get_recent_refusals,
    get_recent_reviews,
    get_recent_workflows,
)
from app.dashboard.health_views import get_dashboard_health
from app.dashboard.operator_actions_service import (
    acknowledge_warning as dashboard_acknowledge_warning,
    add_operator_note as dashboard_add_operator_note,
    archive_workflow as dashboard_archive_workflow,
    refuse_workflow as dashboard_refuse_workflow,
)
from app.dashboard.workflow_queue_service import (
    get_archived_queue,
    get_pending_approval_queue,
    get_proof_capture_queue,
    get_refused_queue,
    get_review_ready_queue,
)
from app.monitoring.health_service import get_system_health
from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.pilot.pilot_metrics import get_pilot_metrics
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.pilot.pilot_run_service import get_pilot_failures, get_pilot_successes, get_pilot_summary
from app.pilot.pilot_signoff import get_pilot_signoffs, get_signoff_history
from app.services.operator_auth_service import ensure_operator_auth_schema
from app.services.operator_auth_service import audit_identity_from_request, resolve_request_operator
from app.services.quote_review_service import ensure_quote_pack_schema


logger = logging.getLogger(__name__)
runtime_config = get_runtime_config()
runtime_config.configure_logging()


def _load_router(spec: RouterSpec) -> Any:
    module = importlib.import_module(spec.module_path)
    return getattr(module, spec.attribute_name)


def _route_signatures(app: FastAPI) -> Dict[Tuple[str, str], List[str]]:
    signatures: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            signatures[(method, route.path)].append(route.name)
    return signatures


def _find_duplicate_routes(app: FastAPI) -> List[Dict[str, Any]]:
    duplicates: List[Dict[str, Any]] = []
    for (method, path), names in sorted(_route_signatures(app).items()):
        if len(names) > 1:
            duplicates.append({"method": method, "path": path, "route_names": names})
    return duplicates


def _include_registered_routers(app: FastAPI, specs: Iterable[RouterSpec]) -> Dict[str, Any]:
    loaded: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []
    seen_modules: set[str] = set()

    for spec in specs:
        if spec.module_path in seen_modules:
            continue
        seen_modules.add(spec.module_path)
        try:
            router = _load_router(spec)
            app.include_router(router)
            loaded.append(
                {
                    "name": spec.name,
                    "module": spec.module_path,
                    "prefix": getattr(router, "prefix", "") or "",
                    "tags": list(getattr(router, "tags", []) or []),
                    "route_count": len(getattr(router, "routes", []) or []),
                }
            )
        except Exception as exc:
            failures.append({"name": spec.name, "module": spec.module_path, "error": str(exc)})

    duplicates = _find_duplicate_routes(app)
    return {"loaded": loaded, "failures": failures, "duplicates": duplicates}


def _allow_degraded_startup() -> bool:
    return runtime_config.allow_degraded_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_directories()
    app.state.database_startup_degraded = False
    app.state.database_startup_error = ""
    app.state.environment_validation = validate_environment()
    app.state.startup_validation = validate_startup(allow_degraded_startup=_allow_degraded_startup())
    app.state.deployment_report = build_deployment_report()
    ensure_operator_auth_schema()
    try:
        ensure_quote_pack_schema()
    except Exception as exc:
        if not _allow_degraded_startup():
            raise
        app.state.database_startup_degraded = True
        app.state.database_startup_error = str(exc)
        logger.warning(
            "Quote pack schema initialization failed during degraded startup; continuing without database access: %s",
            exc,
        )
    if app.state.environment_validation.get("status") == "unhealthy":
        if not _allow_degraded_startup():
            raise RuntimeError(f"Environment validation failed: {app.state.environment_validation.get('issues', [])}")
        app.state.database_startup_degraded = True
    if app.state.startup_validation.get("status") == "unhealthy":
        if not _allow_degraded_startup():
            raise RuntimeError(f"Startup validation failed: {app.state.startup_validation.get('issues', [])}")
        app.state.database_startup_degraded = True
    report = app.state.router_report
    if app.state.database_startup_degraded:
        logger.warning("LMCP AutoQuote API startup complete in degraded mode.")
    else:
        logger.info("LMCP AutoQuote API startup complete")
    logger.info("Loaded routers: %s", [item["name"] for item in report["loaded"]])
    if report["failures"]:
        logger.error("Router load failures: %s", report["failures"])
        raise RuntimeError(f"Router load failures detected: {report['failures']}")
    if report["duplicates"]:
        logger.error("Duplicate routes detected: %s", report["duplicates"])
        raise RuntimeError(f"Duplicate routes detected: {report['duplicates']}")
    logger.info("Runtime static path: %s", settings.runtime_dir)
    logger.info("Monthly quotes static path: %s", settings.monthly_quotes_dir)
    logger.info("Submission proofs static path: %s", settings.submission_proofs_dir)
    logger.info("Portal submission static path: %s", settings.portal_submission_dir)
    logger.info("Final submission static path: %s", settings.final_submission_dir)
    logger.info("Proof center static path: %s", settings.proof_center_dir)
    yield
    app.state.shutdown_snapshot = run_graceful_shutdown(reason="fastapi lifespan shutdown")
    logger.info("Deployment shutdown snapshot: %s", app.state.shutdown_snapshot.get("status", "unknown"))
    logger.info("LMCP AutoQuote API shutdown complete")


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

    mounts = (
        ("/downloads", settings.monthly_quotes_dir, "downloads"),
        ("/runtime", settings.runtime_dir, "runtime"),
        ("/proofs", settings.submission_proofs_dir, "proofs"),
        ("/portal-runtime", settings.portal_submission_dir, "portal-runtime"),
        ("/final-submission-runtime", settings.final_submission_dir, "final-submission-runtime"),
        ("/proof-center-runtime", settings.proof_center_dir, "proof-center-runtime"),
        ("/handwriting-runtime", settings.handwriting_runtime_dir, "handwriting-runtime"),
        ("/tender-form-runtime", settings.tender_form_runtime_dir, "tender-form-runtime"),
        ("/clickable-navigation-v40-runtime", settings.clickable_navigation_runtime_dir, "clickable-navigation-v40-runtime"),
    )
    for mount_path, directory, name in mounts:
        app.mount(mount_path, StaticFiles(directory=str(directory)), name=name)

    app.state.router_report = _include_registered_routers(app, iter_router_specs())
    return app


app = build_application()


def _base_status_payload() -> Dict[str, Any]:
    report = app.state.router_report
    return {
        "version": settings.app_version,
        "environment": settings.environment,
        "production_mode": settings.production_mode,
        "loaded_routers": [item["name"] for item in report["loaded"]],
        "loaded_routers_count": len(report["loaded"]),
        "failed_routers": report["failures"],
        "failed_routers_count": len(report["failures"]),
        "duplicate_routes": report["duplicates"],
        "duplicate_routes_count": len(report["duplicates"]),
        "downloads_url": "/downloads",
        "runtime_url": "/runtime",
        "portal_runtime_url": "/portal-runtime",
        "final_submission_runtime_url": "/final-submission-runtime",
        "proof_center_runtime_url": "/proof-center-runtime",
        "submission_proofs_url": "/proofs",
        "business_rules": {
            "country": settings.target_country,
            "focus": "supply and delivery tenders only",
            "excluded_segments": list(settings.excluded_tender_segments),
            "minimum_profit_margin_zar": settings.minimum_profit_margin_zar,
            "minimum_supply_margin_ratio": settings.minimum_supply_margin_ratio,
            "final_submit_manual_only": settings.final_submit_manual_only,
            "require_buyer_pricing_schedule_completion": settings.require_buyer_pricing_schedule_completion,
        },
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "message": f"{settings.app_name} API is running",
        "status": "ok",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        **_base_status_payload(),
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.environment,
        "production_mode": settings.production_mode,
        "runtime_dir": str(settings.runtime_dir),
        "log_dir": str(settings.log_dir),
        "monthly_quotes_dir": str(settings.monthly_quotes_dir),
        "submission_proofs_dir": str(settings.submission_proofs_dir),
        "portal_submission_dir": str(settings.portal_submission_dir),
        "final_submission_dir": str(settings.final_submission_dir),
        "proof_center_dir": str(settings.proof_center_dir),
        "project_root": str(settings.project_root),
        "database_configured": bool(settings.database_url),
        **_base_status_payload(),
    }


@app.get("/health/system")
def system_health() -> Dict[str, Any]:
    return get_system_health()


@app.get("/health/workflows")
def workflow_health() -> Dict[str, Any]:
    return get_workflow_summary()


@app.get("/health/operational-report")
def operational_report() -> Dict[str, Any]:
    return build_operational_report()


@app.get("/dashboard/summary")
def dashboard_summary() -> Dict[str, Any]:
    return get_dashboard_summary()


@app.get("/dashboard/workflows")
def dashboard_workflows() -> Dict[str, Any]:
    return {
        "workflows": get_recent_workflows(),
        "approvals": get_recent_approvals(),
        "reviews": get_recent_reviews(),
        "proofs": get_recent_proofs(),
        "refusals": get_recent_refusals(),
    }


@app.get("/dashboard/refusals")
def dashboard_refusals() -> Dict[str, Any]:
    return {
        "refusals": get_recent_refusals(),
    }


@app.get("/dashboard/health")
def dashboard_health() -> Dict[str, Any]:
    return get_dashboard_health()


@app.get("/dashboard/queues")
def dashboard_queues() -> Dict[str, Any]:
    return {
        "pending_approvals": get_pending_approval_queue(),
        "review_ready": get_review_ready_queue(),
        "proof_capture": get_proof_capture_queue(),
        "refused": get_refused_queue(),
        "archived": get_archived_queue(),
    }


@app.post("/dashboard/archive")
def dashboard_archive(request: Request, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    operator = resolve_request_operator(request, "dashboard_archive_workflow")
    tender_id = str(payload.get("tender_id") or "").strip()
    reason = str(payload.get("reason") or "").strip() or "dashboard archive"
    details = dict(payload.get("details") or {})
    result = dashboard_archive_workflow(tender_id=tender_id, actor=operator.display_name, reason=reason, details=details)
    return {"status": "ok", "operator": audit_identity_from_request(request), "result": result}


@app.post("/dashboard/refuse")
def dashboard_refuse(request: Request, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    operator = resolve_request_operator(request, "dashboard_refuse_workflow")
    tender_id = str(payload.get("tender_id") or "").strip()
    reason = str(payload.get("reason") or "").strip() or "dashboard refuse"
    details = dict(payload.get("details") or {})
    result = dashboard_refuse_workflow(tender_id=tender_id, actor=operator.display_name, reason=reason, details=details)
    return {"status": "ok", "operator": audit_identity_from_request(request), "result": result}


@app.post("/dashboard/operator-note")
def dashboard_operator_note(request: Request, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    operator = resolve_request_operator(request, "dashboard_operator_note")
    tender_id = str(payload.get("tender_id") or "").strip()
    note = str(payload.get("note") or "").strip()
    details = dict(payload.get("details") or {})
    result = dashboard_add_operator_note(tender_id=tender_id, actor=operator.display_name, note=note, details=details)
    return {"status": "ok", "operator": audit_identity_from_request(request), "result": result}


@app.post("/dashboard/acknowledge-warning")
def dashboard_acknowledge_warning_endpoint(request: Request, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    operator = resolve_request_operator(request, "dashboard_acknowledge_warning")
    tender_id = str(payload.get("tender_id") or "").strip()
    warning = str(payload.get("warning") or "").strip()
    details = dict(payload.get("details") or {})
    result = dashboard_acknowledge_warning(tender_id=tender_id, actor=operator.display_name, warning=warning, details=details)
    return {"status": "ok", "operator": audit_identity_from_request(request), "result": result}


@app.get("/pilot/summary")
def pilot_summary() -> Dict[str, Any]:
    return {
        "pilot_summary": get_pilot_summary(),
        "pilot_metrics": get_pilot_metrics(),
        "pilot_failures": get_pilot_failures(),
        "pilot_successes": get_pilot_successes(),
    }


@app.get("/pilot/readiness")
def pilot_readiness() -> Dict[str, Any]:
    return build_pilot_readiness_report()


@app.get("/pilot/signoffs")
def pilot_signoffs() -> Dict[str, Any]:
    return {"signoffs": get_pilot_signoffs(limit=200)}
