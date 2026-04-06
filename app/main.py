from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.api.tender_pipeline_api import router as tender_pipeline_router
from app.api.quote_engine_api import router as quote_engine_router
from app.api.submission_pipeline_api import router as submission_pipeline_router
from app.api.test_pricing_api import router as test_pricing_router
from app.api.supplier_quotes_api import router as supplier_quotes_router
from app.api.email_ingestion_api import router as email_ingestion_router
from app.api.csd_api import router as csd_router
from app.email_api import router as email_router
from app.tasks_api import router as tasks_router
from app.opportunities_api import router as opportunities_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

APP_VERSION = "2.1.0"

app = FastAPI(
    title="LMCP AutoQuote System",
    version=APP_VERSION,
)

# -------------------------------------------------------------------
# Router tracking
# -------------------------------------------------------------------
loaded_routers: List[str] = []
failed_routers: List[Tuple[str, str]] = []
_registered_router_keys: Set[str] = set()


def _router_key(router_name: str, router: Any) -> str:
    prefix = getattr(router, "prefix", "") or ""
    return f"{router_name}:{prefix}"


def _safe_include_router(router_name: str, router: Any) -> None:
    try:
        key = _router_key(router_name, router)
        if key in _registered_router_keys:
            logger.info("Skipping duplicate router registration: %s", key)
            return

        app.include_router(router)
        _registered_router_keys.add(key)
        loaded_routers.append(router_name)
        logger.info("Loaded router: %s", router_name)

    except Exception as exc:
        failed_routers.append((router_name, str(exc)))
        logger.warning("Failed to load router %s: %s", router_name, exc)


def _safe_include_optional_router(
    router_name: str,
    module_path: str,
    attribute_name: str = "router",
) -> None:
    try:
        module = importlib.import_module(module_path)
        router = getattr(module, attribute_name)
        _safe_include_router(router_name, router)
        logger.info("Loaded optional router: %s (%s)", router_name, module_path)
    except Exception as exc:
        failed_routers.append((router_name, str(exc)))
        logger.warning("Failed to load router %s from %s: %s", router_name, module_path, exc)


# -------------------------------------------------------------------
# Core routers loaded directly
# -------------------------------------------------------------------
_safe_include_router("tender_pipeline_router", tender_pipeline_router)
_safe_include_router("quote_engine_router", quote_engine_router)
_safe_include_router("submission_pipeline_router", submission_pipeline_router)
_safe_include_router("email_router", email_router)
_safe_include_router("test_pricing_router", test_pricing_router)
_safe_include_router("tasks_router", tasks_router)
_safe_include_router("supplier_quotes_router", supplier_quotes_router)
_safe_include_router("email_ingestion_router", email_ingestion_router)
_safe_include_router("csd_router", csd_router)

# IMPORTANT:
# Let each router define its own prefix internally.
_safe_include_router("opportunities_router", opportunities_router)

# -------------------------------------------------------------------
# Optional legacy / extended routers
# -------------------------------------------------------------------
OPTIONAL_ROUTERS: List[Tuple[str, str, str]] = [
    ("audit_api", "app.audit_api", "router"),
    ("compliance_api", "app.compliance_api", "router"),
    ("harvester_api", "app.harvester_api", "router"),
    ("sbd_api", "app.sbd_api", "router"),
    ("system_guard_api", "app.system_guard_api", "router"),
    ("autonomous_api", "app.api.autonomous_api", "router"),
    ("dashboard", "app.api.dashboard", "router"),
    ("form_filler_api", "app.api.form_filler_api", "router"),
    ("revenue_dashboard_api", "app.api.revenue_dashboard_api", "router"),
    ("sbd_version_detector_api", "app.api.sbd_version_detector_api", "router"),
    ("self_healing_harvester", "app.api.self_healing_harvester", "router"),
    ("supervisor", "app.api.supervisor", "router"),
    ("supply_command_api", "app.api.supply_command_api", "router"),
    ("system_api", "app.api.system", "router"),
    ("tender_form_priority_api", "app.api.tender_form_priority_api", "router"),
]

for router_name, module_path, attribute_name in OPTIONAL_ROUTERS:
    _safe_include_optional_router(router_name, module_path, attribute_name)

# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------
@app.on_event("startup")
async def startup_event() -> None:
    logger.info("LMCP AutoQuote API startup complete")
    logger.info("Loaded routers: %s", loaded_routers)
    if failed_routers:
        logger.warning("Failed routers: %s", failed_routers)


# -------------------------------------------------------------------
# Basic routes
# -------------------------------------------------------------------
@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "message": "LMCP AutoQuote System API is running",
        "version": APP_VERSION,
        "status": "ok",
        "loaded_routers": loaded_routers,
        "failed_routers": failed_routers,
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "LMCP AutoQuote System",
        "version": APP_VERSION,
        "loaded_routers": loaded_routers,
        "loaded_routers_count": len(loaded_routers),
        "failed_routers": failed_routers,
        "failed_routers_count": len(failed_routers),
    }
