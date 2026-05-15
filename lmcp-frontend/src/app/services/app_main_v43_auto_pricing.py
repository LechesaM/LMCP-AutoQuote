from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from app.api.csd_api import router as csd_router
from app.api.email_ingestion_api import router as email_ingestion_router
from app.api.quote_engine_api import router as quote_engine_router
from app.api.submission_pipeline_api import router as submission_pipeline_router
from app.api.supplier_quotes_api import router as supplier_quotes_router
from app.api.system_control import router as system_control_router
from app.api.tender_pipeline_api import router as tender_pipeline_router
from app.api.test_pricing_api import router as test_pricing_router
from app.email_api import router as email_router
from app.opportunities_api import router as opportunities_router
from app.tasks_api import router as tasks_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

APP_VERSION = "2.5.0-v43-auto-pricing"

app = FastAPI(
    title="LMCP AutoQuote System",
    version=APP_VERSION,
)

MONTHLY_QUOTES_DIR = BASE_DIR / "monthly_quotes"
MONTHLY_QUOTES_DIR.mkdir(parents=True, exist_ok=True)

HANDWRITING_RUNTIME_DIR = BASE_DIR / "runtime" / "handwriting_simulation"
HANDWRITING_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

TENDER_FORM_RUNTIME_DIR = BASE_DIR / "runtime" / "tender_form_intelligence"
TENDER_FORM_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

CLICKABLE_NAVIGATION_V40_RUNTIME_DIR = BASE_DIR / "runtime" / "clickable_navigation_v40"
CLICKABLE_NAVIGATION_V40_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/downloads",
    StaticFiles(directory=str(MONTHLY_QUOTES_DIR)),
    name="downloads",
)

app.mount(
    "/handwriting-runtime",
    StaticFiles(directory=str(HANDWRITING_RUNTIME_DIR)),
    name="handwriting-runtime",
)

app.mount(
    "/tender-form-runtime",
    StaticFiles(directory=str(TENDER_FORM_RUNTIME_DIR)),
    name="tender-form-runtime",
)

app.mount(
    "/clickable-navigation-v40-runtime",
    StaticFiles(directory=str(CLICKABLE_NAVIGATION_V40_RUNTIME_DIR)),
    name="clickable-navigation-v40-runtime",
)

loaded_routers: List[str] = []
failed_routers: List[Tuple[str, str]] = []
_registered_router_keys: Set[str] = set()


def _router_key(router_name: str, router: Any) -> str:
    prefix = getattr(router, "prefix", "") or ""
    route_count = len(getattr(router, "routes", []) or [])
    return f"{router_name}:{prefix}:{route_count}"


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


_safe_include_router("tender_pipeline_router", tender_pipeline_router)
_safe_include_router("quote_engine_router", quote_engine_router)
_safe_include_router("submission_pipeline_router", submission_pipeline_router)
_safe_include_router("email_router", email_router)
_safe_include_router("test_pricing_router", test_pricing_router)
_safe_include_router("tasks_router", tasks_router)
_safe_include_router("supplier_quotes_router", supplier_quotes_router)
_safe_include_router("email_ingestion_router", email_ingestion_router)
_safe_include_router("csd_router", csd_router)
_safe_include_router("opportunities_router", opportunities_router)
_safe_include_router("system_control_router", system_control_router)

OPTIONAL_ROUTERS: List[Tuple[str, str, str]] = [
    ("audit_api", "app.audit_api", "router"),
    ("compliance_api", "app.compliance_api", "router"),
    ("harvester_api", "app.harvester_api", "router"),
    ("sbd_api", "app.sbd_api", "router"),
    ("system_guard_api", "app.system_guard_api", "router"),
    ("autonomous_api", "app.autonomous_api", "router"),
    ("dashboard", "app.api.dashboard", "router"),
    ("form_filler_api", "app.api.form_filler_api", "router"),
    ("revenue_dashboard_api", "app.api.revenue_dashboard_api", "router"),
    ("sbd_version_detector_api", "app.api.sbd_version_detector_api", "router"),
    ("self_healing_harvester", "app.api.self_healing_harvester", "router"),
    ("supervisor", "app.api.supervisor", "router"),
    ("supply_command_api", "app.api.supply_command_api", "router"),
    ("system_api", "app.api.system", "router"),
    ("tender_form_priority_api", "app.api.tender_form_priority_api", "router"),
    ("submission_history_router", "app.api.submission_history", "router"),
    ("submission_retry_router", "app.api.submission_retry_api", "router"),
    ("submission_scheduler_router", "app.api.submission_scheduler_api", "router"),
    ("submission_analytics_router", "app.api.submission_analytics_api", "router"),
    ("ws_live_router", "app.api.ws_live", "router"),
    ("decision_intelligence_router", "app.api.decision_intelligence_api", "router"),
    ("operator_actions_router", "app.api.operator_actions_api", "router"),
    ("audit_trail_router", "app.api.audit_trail_api", "router"),
    ("go_live_guard_router", "app.api.go_live_guard_api", "router"),
    ("pipeline_enforcement_router", "app.api.pipeline_enforcement_api", "router"),
    ("full_autonomous_cycle_router", "app.api.full_autonomous_cycle_api", "router"),
    ("system_stability_router", "app.api.system_stability_api", "router"),
    ("security_router", "app.api.security_api", "router"),
    ("portal_submission_router", "app.api.portal_submission_api", "router"),
    ("sbd_completion_router", "app.api.sbd_completion_api", "router"),
    ("etenders_session_router", "app.api.etenders_session_api", "router"),
    ("smart_harvester_v31_router", "app.api.smart_harvester_v31_api", "router"),
    ("real_rfq_harvester_v32_router", "app.api.real_rfq_harvester_v32_api", "router"),
    ("real_portal_rfq_extraction_v33_router", "app.api.real_portal_rfq_extraction_v33_api", "router"),
    ("structured_rfq_extractor_v34_router", "app.api.structured_rfq_extractor_v34_api", "router"),
    ("playwright_live_dom_extractor_v35_router", "app.api.playwright_live_dom_extractor_v35_api", "router"),
    ("interactive_playwright_extractor_v36_router", "app.api.interactive_playwright_extractor_v36_api", "router"),
    ("deep_rfq_link_extractor_v37_router", "app.api.deep_rfq_link_extractor_v37_api", "router"),
    ("interactive_click_deep_extraction_v38_router", "app.api.interactive_click_deep_extraction_v38_api", "router"),
    ("true_navigation_extraction_v39_router", "app.api.true_navigation_extraction_v39_api", "router"),

    # V40 Clickable Navigation Extractor.
    ("clickable_navigation_v40_router", "app.api.clickable_navigation_v40_api", "router"),

    # Handwriting / form-overlay stack.
    ("handwriting_simulation_router", "app.api.handwriting_simulation_api", "router"),
    ("handwriting_form_overlay_router", "app.api.handwriting_form_overlay_api", "router"),
    ("handwriting_glyph_router", "app.api.handwriting_glyph_api", "router"),
    ("clean_ink_extraction_v3_router", "app.api.clean_ink_extraction_v3_api", "router"),

    # V15 Auto-Detect Fields stack.
    ("handwriting_field_detector_router", "app.api.handwriting_field_detector_api", "router"),

    # V16 Full Auto Handwriting stack.
    ("handwriting_full_auto_router", "app.api.handwriting_full_auto_api", "router"),

    # V18+ Tender Form Intelligence stack.
    ("tender_form_intelligence_router", "app.api.tender_form_intelligence_api", "router"),

    # V25.1 Persistent CSD session engine.
    ("csd_persistent_session_router", "app.api.csd_persistent_session_api", "router"),

    # V25 Monthly CSD refresh engine.
    ("csd_monthly_refresh_router", "app.api.csd_monthly_refresh_api", "router"),

    # V28 Final Automation Layer.
    ("final_automation_router", "app.api.final_automation_layer_api", "router"),

    # V22.3 Stroke Flow compatibility bridge for existing /sbd-intelligence endpoints.
    ("sbd_intelligence_router", "app.api.sbd_intelligence_api", "router"),
]

for router_name, module_path, attribute_name in OPTIONAL_ROUTERS:
    _safe_include_optional_router(router_name, module_path, attribute_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("LMCP AutoQuote API startup complete")
    logger.info("Loaded routers: %s", loaded_routers)
    logger.info("Failed routers: %s", failed_routers)
    logger.info("Monthly quotes static path: %s", MONTHLY_QUOTES_DIR)
    logger.info("Handwriting runtime static path: %s", HANDWRITING_RUNTIME_DIR)
    logger.info("Tender form runtime static path: %s", TENDER_FORM_RUNTIME_DIR)
    logger.info("Clickable navigation V40 runtime static path: %s", CLICKABLE_NAVIGATION_V40_RUNTIME_DIR)


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "message": "LMCP AutoQuote System API is running",
        "version": APP_VERSION,
        "status": "ok",
        "loaded_routers": loaded_routers,
        "loaded_routers_count": len(loaded_routers),
        "failed_routers": failed_routers,
        "failed_routers_count": len(failed_routers),
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        "downloads_url": "/downloads",
        "handwriting_runtime_url": "/handwriting-runtime",
        "tender_form_runtime_url": "/tender-form-runtime",
        "clickable_navigation_v40_runtime_url": "/clickable-navigation-v40-runtime",
        "submission_history_url": "/submission-history",
        "submission_retry_url": "/submission-retry/run",
        "submission_scheduler_health_url": "/submission-scheduler/health",
        "submission_scheduler_run_now_url": "/submission-scheduler/run-now",
        "submission_scheduler_enqueue_url": "/submission-scheduler/enqueue",
        "submission_analytics_success_url": "/submission-analytics/success",
        "submission_analytics_profit_url": "/submission-analytics/profit",
        "submission_analytics_summary_url": "/submission-analytics/summary",
        "system_control_status_url": "/system/control/status",
        "system_control_on_url": "/system/control/on",
        "system_control_off_url": "/system/control/off",
        "system_control_pause_harvest_url": "/system/control/pause-harvest",
        "system_control_pause_submissions_url": "/system/control/pause-submissions",
        "system_control_emergency_stop_url": "/system/control/emergency-stop",
        "system_control_resume_all_url": "/system/control/resume-all",
        "websocket_root_url": "/ws",
        "websocket_live_url": "/ws/live",
        "websocket_dashboard_url": "/ws/dashboard",
        "websocket_tenders_url": "/ws/tenders",
        "decision_intelligence_summary_url": "/decision-intelligence/summary",
        "operator_actions_summary_url": "/operator-actions/summary",
        "audit_trail_summary_url": "/audit-trail/summary",
        "go_live_guard_summary_url": "/go-live-guards/summary",
        "pipeline_enforcement_summary_url": "/pipeline-enforcement/summary",
        "full_autonomous_cycle_status_url": "/full-autonomous-cycle/status",
        "full_autonomous_cycle_run_url": "/full-autonomous-cycle/run",
        "full_autonomous_cycle_dry_run_url": "/full-autonomous-cycle/dry-run",
        "system_stability_watchdog_url": "/system-stability/watchdog",
        "system_stability_retry_queue_url": "/system-stability/retry-queue",
        "security_status_url": "/security/status",
        "security_verify_pin_url": "/security/verify-pin",
        "security_protected_test_url": "/security/protected-test",
        "portal_submission_status_url": "/portal-submission/status",
        "portal_submission_classify_url": "/portal-submission/classify",
        "portal_submission_prepare_url": "/portal-submission/prepare",
        "portal_submission_proof_url": "/portal-submission/proof",
        "sbd_completion_summary_url": "/sbd-completion/summary",
        "sbd_completion_evaluate_url": "/sbd-completion/evaluate",
        "sbd_completion_record_url": "/sbd-completion/record",
        "etenders_session_status_url": "/etenders-session/status",
        "etenders_session_probe_url": "/etenders-session/probe",
        "etenders_session_submission_readiness_url": "/etenders-session/submission-readiness",
        "smart_harvester_v31_status_url": "/smart-harvester-v31/status",
        "real_rfq_harvester_v32_status_url": "/real-rfq-harvester-v32/status",
        "real_portal_rfq_extraction_v33_status_url": "/real-portal-rfq-extraction-v33/status",
        "structured_rfq_extractor_v34_status_url": "/structured-rfq-extractor-v34/status",
        "playwright_live_dom_extractor_v35_status_url": "/playwright-live-dom-extractor-v35/status",
        "interactive_playwright_extractor_v36_status_url": "/interactive-playwright-extractor-v36/status",
        "deep_rfq_link_extractor_v37_status_url": "/deep-rfq-link-extractor-v37/status",
        "interactive_click_deep_extraction_v38_status_url": "/interactive-click-deep-extraction-v38/status",
        "true_navigation_extraction_v39_status_url": "/v39-true-navigation/status",
        "clickable_navigation_v40_status_url": "/v40-clickable-navigation/status",
        "clickable_navigation_v40_extract_url": "/v40-clickable-navigation/extract",
        "handwriting_simulation_status_url": "/handwriting-simulation/status",
        "handwriting_simulation_example_payload_url": "/handwriting-simulation/example-payload",
        "handwriting_simulation_complete_form_url": "/handwriting-simulation/complete-form",
        "handwriting_simulation_simulate_url": "/handwriting-simulation/simulate",
        "handwriting_simulation_run_url": "/handwriting-simulation/run",
        "handwriting_form_status_url": "/handwriting-form/status",
        "handwriting_form_example_payload_url": "/handwriting-form/example-payload",
        "handwriting_form_overlay_existing_pdf_url": "/handwriting-form/overlay-existing-pdf",
        "handwriting_glyph_status_url": "/handwriting-glyph/status",
        "handwriting_glyph_build_cache_url": "/handwriting-glyph/build-cache",
        "handwriting_glyph_example_payload_url": "/handwriting-glyph/example-payload",
        "handwriting_glyph_overlay_existing_pdf_url": "/handwriting-glyph/overlay-existing-pdf",
        "clean_ink_v3_status_url": "/clean-ink-v3/status",
        "clean_ink_v3_extract_url": "/clean-ink-v3/extract",
        "clean_ink_v3_extract_latest_url": "/clean-ink-v3/extract-latest",
        "handwriting_field_detector_status_url": "/handwriting-field-detector/status",
        "handwriting_field_detector_example_payload_url": "/handwriting-field-detector/example-payload",
        "handwriting_field_detector_detect_url": "/handwriting-field-detector/detect",
        "handwriting_field_detector_build_payload_url": "/handwriting-field-detector/build-handwriting-payload",
        "handwriting_full_auto_status_url": "/handwriting-full-auto/status",
        "handwriting_full_auto_example_payload_url": "/handwriting-full-auto/example-payload",
        "handwriting_full_auto_complete_url": "/handwriting-full-auto/complete",
        "tender_form_intelligence_status_url": "/tender-form-intelligence/status",
        "tender_form_intelligence_example_payload_url": "/tender-form-intelligence/example-payload",
        "tender_form_intelligence_classify_url": "/tender-form-intelligence/classify",
        "tender_form_intelligence_complete_url": "/tender-form-intelligence/complete",
        "csd_monthly_refresh_status_url": "/csd-monthly-refresh/status",
        "csd_monthly_refresh_run_if_due_url": "/csd-monthly-refresh/run-if-due",
        "csd_monthly_refresh_run_now_url": "/csd-monthly-refresh/run-now",
        "csd_persistent_session_status_url": "/csd-persistent-session/status",
        "csd_persistent_session_start_manual_login_url": "/csd-persistent-session/start-manual-login",
        "csd_persistent_session_refresh_report_url": "/csd-persistent-session/refresh-report",
        "final_automation_status_url": "/final-automation/status",
        "final_automation_go_live_check_url": "/final-automation/go-live-check",
        "final_automation_run_once_url": "/final-automation/run-once",
        "sbd_intelligence_status_url": "/sbd-intelligence/status",
        "sbd_intelligence_example_payload_url": "/sbd-intelligence/example-payload",
        "sbd_intelligence_complete_url": "/sbd-intelligence/complete",
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
        "downloads_url": "/downloads",
        "monthly_quotes_dir": str(MONTHLY_QUOTES_DIR),
        "handwriting_runtime_url": "/handwriting-runtime",
        "handwriting_runtime_dir": str(HANDWRITING_RUNTIME_DIR),
        "tender_form_runtime_url": "/tender-form-runtime",
        "tender_form_runtime_dir": str(TENDER_FORM_RUNTIME_DIR),
        "clickable_navigation_v40_runtime_url": "/clickable-navigation-v40-runtime",
        "clickable_navigation_v40_runtime_dir": str(CLICKABLE_NAVIGATION_V40_RUNTIME_DIR),
        "decision_intelligence_url": "/decision-intelligence/summary",
        "operator_actions_url": "/operator-actions/summary",
        "audit_trail_url": "/audit-trail/summary",
        "go_live_guard_url": "/go-live-guards/summary",
        "pipeline_enforcement_url": "/pipeline-enforcement/summary",
        "full_autonomous_cycle_url": "/full-autonomous-cycle/status",
        "system_stability_url": "/system-stability/watchdog",
        "security_url": "/security/status",
        "portal_submission_url": "/portal-submission/status",
        "sbd_completion_url": "/sbd-completion/summary",
        "etenders_session_url": "/etenders-session/status",
        "smart_harvester_v31_url": "/smart-harvester-v31/status",
        "real_rfq_harvester_v32_url": "/real-rfq-harvester-v32/status",
        "real_portal_rfq_extraction_v33_url": "/real-portal-rfq-extraction-v33/status",
        "structured_rfq_extractor_v34_url": "/structured-rfq-extractor-v34/status",
        "playwright_live_dom_extractor_v35_url": "/playwright-live-dom-extractor-v35/status",
        "interactive_playwright_extractor_v36_url": "/interactive-playwright-extractor-v36/status",
        "deep_rfq_link_extractor_v37_url": "/deep-rfq-link-extractor-v37/status",
        "interactive_click_deep_extraction_v38_url": "/interactive-click-deep-extraction-v38/status",
        "true_navigation_extraction_v39_url": "/v39-true-navigation/status",
        "clickable_navigation_v40_status_url": "/v40-clickable-navigation/status",
        "clickable_navigation_v40_extract_url": "/v40-clickable-navigation/extract",
        "handwriting_simulation_url": "/handwriting-simulation/status",
        "handwriting_form_url": "/handwriting-form/status",
        "handwriting_glyph_url": "/handwriting-glyph/status",
        "clean_ink_v3_url": "/clean-ink-v3/status",
        "handwriting_field_detector_url": "/handwriting-field-detector/status",
        "handwriting_full_auto_url": "/handwriting-full-auto/status",
        "tender_form_intelligence_url": "/tender-form-intelligence/status",
        "csd_monthly_refresh_url": "/csd-monthly-refresh/status",
        "csd_persistent_session_url": "/csd-persistent-session/status",
        "final_automation_url": "/final-automation/status",
        "sbd_intelligence_url": "/sbd-intelligence/status",
    }
