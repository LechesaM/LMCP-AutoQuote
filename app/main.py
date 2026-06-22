from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", message="builtin type SwigPyPacked has no __module__ attribute")
warnings.filterwarnings("ignore", message="builtin type SwigPyObject has no __module__ attribute")
warnings.filterwarnings("ignore", message="builtin type swigvarlink has no __module__ attribute")

import importlib
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from collections import defaultdict
from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

try:
    from redis import Redis
except Exception:  # pragma: no cover - optional runtime dependency
    Redis = None

from app.api.router_registry import RouterSpec, iter_router_specs
from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401
from app.monitoring.health_service import get_system_health
from app.monitoring.workflow_monitor import get_workflow_summary
from app.legacy_router_quarantine import QUARANTINED_ROOT_ROUTER_MODULES
from app.services.operator_auth_service import ensure_operator_auth_schema
from app.services.quote_review_service import ensure_quote_pack_schema


logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_lmcp_logging_configured", False):
        return

    log_dir = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)

    app_log = RotatingFileHandler(log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    app_log.setLevel(logging.INFO)
    app_log.setFormatter(formatter)

    error_log = RotatingFileHandler(log_dir / "error.log", maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8")
    error_log.setLevel(logging.ERROR)
    error_log.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(app_log)
    root.addHandler(error_log)
    root._lmcp_logging_configured = True  # type: ignore[attr-defined]


_configure_logging()


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
    return str(os.getenv("LMCP_ALLOW_DEGRADED_STARTUP", "false")).strip().lower() == "true"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_payload(status: str = "ok", data_source: str = "runtime") -> Dict[str, Any]:
    return {
        "status": status,
        "generated_at": _utc_now_iso(),
        "data_source": data_source,
    }


def _is_database_connection_error(exc: Exception) -> bool:
    current: Exception | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OperationalError):
            return True
        next_exc = current.__cause__ if isinstance(current.__cause__, Exception) else None
        if next_exc is None and isinstance(current.__context__, Exception):
            next_exc = current.__context__
        current = next_exc
    return False


def _probe_database_connectivity() -> Dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"configured": bool(settings.database_url), "connected": True, "status": "ok"}
    except Exception as exc:
        return {
            "configured": bool(settings.database_url),
            "connected": False,
            "status": "error",
            "error": exc.__class__.__name__,
        }


def _probe_broker_connectivity() -> Dict[str, Any]:
    queue_backend = str(os.getenv("LMCP_QUEUE_BACKEND", "")).strip().lower()
    redis_url = str(os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", settings.redis_url or ""))).strip()

    if queue_backend in {"", "local"}:
        return {
            "configured": False,
            "connected": False,
            "status": "skipped",
            "detail": "local queue backend configured",
        }

    if not redis_url:
        return {
            "configured": False,
            "connected": False,
            "status": "skipped",
            "detail": "broker URL not configured",
        }

    if Redis is None:
        return {
            "configured": True,
            "connected": False,
            "status": "skipped",
            "detail": "redis client not installed in current runtime",
        }

    try:
        client = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            client.ping()
        finally:
            client.close()
        return {"configured": True, "connected": True, "status": "ok"}
    except Exception as exc:
        return {
            "configured": True,
            "connected": False,
            "status": "error",
            "error": exc.__class__.__name__,
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_directories()
    app.state.database_startup_degraded = False
    app.state.database_startup_error = ""
    ensure_operator_auth_schema()
    try:
        ensure_quote_pack_schema()
    except Exception as exc:
        if not (_allow_degraded_startup() or _is_database_connection_error(exc)):
            raise
        app.state.database_startup_degraded = True
        app.state.database_startup_error = str(exc)
        logger.warning(
            "Quote pack schema initialization failed during degraded startup; continuing without database access: %s",
            exc,
        )
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        if not (_allow_degraded_startup() or _is_database_connection_error(exc)):
            raise
        app.state.database_startup_degraded = True
        app.state.database_startup_error = str(exc)
        logger.warning(
            "Database bootstrap failed during degraded startup; continuing without database access: %s",
            exc,
        )
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
    logger.info("LMCP AutoQuote API shutdown complete")


def build_application() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
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
        "loaded_routers": [item["name"] for item in report["loaded"]],
        "loaded_routers_count": len(report["loaded"]),
        "failed_routers": report["failures"],
        "failed_routers_count": len(report["failures"]),
        "duplicate_routes": report["duplicates"],
        "duplicate_routes_count": len(report["duplicates"]),
        "quarantined_root_router_modules": list(QUARANTINED_ROOT_ROUTER_MODULES),
        "quarantined_root_router_modules_count": len(QUARANTINED_ROOT_ROUTER_MODULES),
        "downloads_url": "/downloads",
        "runtime_url": "/runtime",
        "portal_runtime_url": "/portal-runtime",
        "final_submission_runtime_url": "/final-submission-runtime",
        "proof_center_runtime_url": "/proof-center-runtime",
        "submission_proofs_url": "/proofs",
        "handwriting_stack_url": "/handwriting-stack/status",
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
        "alive": True,
        "service": settings.app_name,
        "environment": settings.environment,
        "timestamp": _utc_now_iso(),
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


@app.get("/status")
def status() -> Dict[str, Any]:
    return {
        "api_status": "alive",
        "database": _probe_database_connectivity(),
        "broker": _probe_broker_connectivity(),
        "environment": settings.environment,
        "timestamp": _utc_now_iso(),
    }


@app.get("/health/system")
def health_system() -> Dict[str, Any]:
    return get_system_health()


@app.get("/health/workflows")
def health_workflows() -> Dict[str, Any]:
    return get_workflow_summary(limit=50)


@app.get("/health/operational-report")
def health_operational_report() -> Dict[str, Any]:
    return {
        **_runtime_payload(),
        "summary": {},
        "warnings": [],
        "blockers": [],
    }



QUOTE_PACK_DASHBOARD_METRICS = Path(
    "/Users/cash/Documents/runtime/manual_production/quote_pack_dashboard_metrics.json"
)


def _load_quote_pack_dashboard_metrics() -> Dict[str, Any]:
    try:
        if not QUOTE_PACK_DASHBOARD_METRICS.exists():
            return {}
        with open(QUOTE_PACK_DASHBOARD_METRICS, "r") as f:
            return json.load(f)
    except Exception:
        return {}


@app.get("/telemetry/dashboard")
def telemetry_dashboard(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(),
        "limit": limit,
        "handwriting_stack_url": "/handwriting-stack/status",
        "selected_tender": {},
        "selected_tender_id": "",
        "total_harvested_rfqs": 0,
        "eligible_rfqs": 0,
        "total_estimated_value": 0,
        "high_profit_rfqs": 0,
        "avg_estimated_profit": 0,
        "avg_margin": 0,
        "eligible_rate": 0,
        "province_distribution": [],
        "opportunity_breakdown": [],
        "top_high_profit_rfqs": [],
        "recent_alerts": [],
        "quote_pack_dashboard": _load_quote_pack_dashboard_metrics(),
    }


@app.get("/telemetry/review-queue")
def telemetry_review_queue(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(),
        "limit": limit,
        "items": [],
        "summary": {
            "total": 0,
            "goCount": 0,
            "manualCount": 0,
            "alerts": [],
            "pendingReviews": 0,
            "approvedToday": 0,
            "manualReviewRequired": 0,
            "blockedReviews": 0,
            "overdueReviews": 0,
            "operatorCapacity": 1000,
            "operatorCapacityUsed": 0,
            "operatorCapacityRemaining": 1000,
            "queueLagMinutes": 0,
        },
    }


@app.get("/telemetry/source-health")
def telemetry_source_health(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(),
        "limit": limit,
        "sources": [],
        "total_sources": 0,
        "active_sources": 0,
        "healthy_sources": 0,
        "degraded_sources": 0,
        "failing_sources": 0,
        "disabled_sources": 0,
        "parser_failure_rate": 0,
        "average_response_time_ms": 0,
        "tier_breakdown": {},
        "recent_source_failures": [],
    }


@app.get("/telemetry/operational-health")
def telemetry_operational_health(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(),
        "limit": limit,
        "source_failures": 0,
        "parser_failures": 0,
        "queue_lag": 0,
        "operator_capacity": 1000,
        "rfq_aging": 0,
        "stale_evidence": 0,
        "workflow_failures": 0,
        "persistence_failures": 0,
        "audit_failures": 0,
        "governance_compliance_score": 0,
        "manual_governance_integrity_score": 0,
    }


@app.get("/telemetry/qualification")
def telemetry_qualification(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(),
        "limit": limit,
        "goCount": 0,
        "manualReviewCount": 0,
        "rejectCount": 0,
        "lowConfidenceCount": 0,
        "topRejectionReasons": [],
        "topManualReviewTriggers": [],
        "avgQualificationScore": 0,
        "avgRiskScore": 0,
        "manualGovernanceOnly": True,
        "reviewReadyRequired": True,
        "proofCaptureRequired": True,
    }


@app.get("/operations/source-health-details")
def operations_source_health_details(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(),
        "limit": limit,
        "rows": [],
        "tierBreakdown": {},
        "summary": {
            "totalSources": 0,
            "healthySources": 0,
            "degradedSources": 0,
            "failingSources": 0,
            "disabledSources": 0,
        },
    }


@app.get("/observability/prometheus")
def observability_prometheus(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="runtime"),
        "limit": limit,
        "metrics_count": 0,
        "metrics": {},
        "text": "",
    }


@app.get("/observability/grafana")
def observability_grafana(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="runtime"),
        "limit": limit,
        "dashboards": [],
    }


@app.get("/observability/sentry")
def observability_sentry(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="fallback", data_source="fallback"),
        "limit": limit,
        "sentry": {
            "enabled": False,
            "dsnConfigured": False,
            "environment": "",
            "release": "",
            "sampleRate": 0,
        },
    }


@app.get("/observability/sla")
def observability_sla(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="runtime"),
        "limit": limit,
        "sla_metrics": [],
        "breached_metrics": [],
        "warning_metrics": [],
        "summary": {
            "healthy": 0,
            "degraded": 0,
            "failing": 0,
        },
    }


@app.get("/observability/anomalies")
def observability_anomalies(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="runtime"),
        "limit": limit,
        "anomalies": [],
        "anomaly_count": 0,
        "severity_counts": {},
        "advisory_only": True,
    }


@app.get("/observability/alerts")
def observability_alerts(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="runtime"),
        "limit": limit,
        "alerts": [],
        "route_count": 0,
        "category_counts": {},
        "target_counts": {},
        "advisory_only": True,
    }


@app.get("/observability/logs")
def observability_logs(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="runtime"),
        "limit": limit,
        "logs": {
            "totalLogs": 0,
            "logSources": {},
            "categoryCounts": {},
            "severityDistribution": {},
            "redactedSamples": [],
        },
    }


@app.get("/observability/uptime")
def observability_uptime(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="healthy"),
        "limit": limit,
        "uptime": {
            "status": "runtime",
            "apiUptimePercentage": 100,
            "observedWindowMinutes": 60,
            "systemHealth": {},
            "runtimeMetrics": {},
        },
    }


@app.get("/observability/performance")
def observability_performance(limit: int = 100) -> Dict[str, Any]:
    return {
        **_runtime_payload(status="runtime"),
        "limit": limit,
        "performance": {
            "status": "runtime",
            "apiLatencyMs": 0,
            "queueResponseTimeMs": 0,
            "dbResponseHealth": "unknown",
            "frontendBuildFreshnessMinutes": -1,
            "deploymentHealth": "degraded",
            "telemetryFreshnessMinutes": 0,
        },
    }


@app.get("/system-control/policy")
def system_control_policy_dash_alias() -> Dict[str, Any]:
    return {
        "status": "ok",
        "enabled": False,
        "mode": "safe",
        "allow_final_submit": False,
        "manual_review_required": True,
        "source": "system_control_dash_alias",
    }
