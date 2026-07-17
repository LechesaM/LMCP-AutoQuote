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
from app.api.submission_history_recent_api import router as submission_history_recent_router
from app.api.submission_history_pipeline_sync_api import router as submission_history_pipeline_sync_router
from app.api.proof_of_submission_api import router as proof_of_submission_router
from app.api.quotes_stable_api import router as quotes_stable_router
from app.api.rfq_stable_api import router as rfq_stable_router
from app.api.submission_history_proof_enrichment_api import router as submission_history_proof_enrichment_router
from app.api.system_stable_api import router as system_stable_router
from app.api import mission_control_compat_api
from app.core.router_activation import is_router_family_enabled, log_router_activation, router_activation_reason
from app.email_api import router as email_router
from app.opportunities_api import router as opportunities_router
from app.tasks_api import router as tasks_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

APP_VERSION = "2.5.3-v50.7-etenders-promotion-gate"

app = FastAPI(title="LMCP AutoQuote System", version=APP_VERSION)

RUNTIME_DIR = BASE_DIR / "runtime"

MONTHLY_QUOTES_DIR = BASE_DIR / "monthly_quotes"

HANDWRITING_RUNTIME_DIR = RUNTIME_DIR / "handwriting_simulation"

TENDER_FORM_RUNTIME_DIR = RUNTIME_DIR / "tender_form_intelligence"

CLICKABLE_NAVIGATION_V40_RUNTIME_DIR = RUNTIME_DIR / "clickable_navigation_v40"

SUBMISSION_PROOFS_DIR = RUNTIME_DIR / "submission_proofs"

PORTAL_SUBMISSION_DIR = RUNTIME_DIR / "portal_submission"

FINAL_SUBMISSION_DIR = RUNTIME_DIR / "final_submission_v47_5"

PROOF_CENTER_DIR = RUNTIME_DIR / "proof_center"

RUNTIME_STATIC_DIRS = [
    RUNTIME_DIR,
    MONTHLY_QUOTES_DIR,
    HANDWRITING_RUNTIME_DIR,
    TENDER_FORM_RUNTIME_DIR,
    CLICKABLE_NAVIGATION_V40_RUNTIME_DIR,
    SUBMISSION_PROOFS_DIR,
    PORTAL_SUBMISSION_DIR,
    FINAL_SUBMISSION_DIR,
    PROOF_CENTER_DIR,
]

app.mount("/downloads", StaticFiles(directory=str(MONTHLY_QUOTES_DIR), check_dir=False), name="downloads")
app.mount("/runtime", StaticFiles(directory=str(RUNTIME_DIR), check_dir=False), name="runtime")
app.mount("/proofs", StaticFiles(directory=str(SUBMISSION_PROOFS_DIR), check_dir=False), name="proofs")
app.mount("/portal-runtime", StaticFiles(directory=str(PORTAL_SUBMISSION_DIR), check_dir=False), name="portal-runtime")
app.mount("/final-submission-runtime", StaticFiles(directory=str(FINAL_SUBMISSION_DIR), check_dir=False), name="final-submission-runtime")
app.mount("/proof-center-runtime", StaticFiles(directory=str(PROOF_CENTER_DIR), check_dir=False), name="proof-center-runtime")
app.mount("/handwriting-runtime", StaticFiles(directory=str(HANDWRITING_RUNTIME_DIR), check_dir=False), name="handwriting-runtime")
app.mount("/tender-form-runtime", StaticFiles(directory=str(TENDER_FORM_RUNTIME_DIR), check_dir=False), name="tender-form-runtime")
app.mount("/clickable-navigation-v40-runtime", StaticFiles(directory=str(CLICKABLE_NAVIGATION_V40_RUNTIME_DIR), check_dir=False), name="clickable-navigation-v40-runtime")

loaded_routers: List[str] = []
failed_routers: List[Tuple[str, str]] = []
disabled_routers: List[Tuple[str, str]] = []
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


def _safe_include_optional_router(router_name: str, module_path: str, attribute_name: str = "router") -> None:
    if not is_router_family_enabled(router_name):
        reason = router_activation_reason(router_name) or "disabled by operational route baseline"
        disabled_routers.append((router_name, reason))
        log_router_activation(router_name, False)
        return
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
_safe_include_router("submission_history_recent_router", submission_history_recent_router)
_safe_include_router("submission_history_pipeline_sync_router", submission_history_pipeline_sync_router)
_safe_include_router("proof_of_submission_router", proof_of_submission_router)
_safe_include_router("submission_history_proof_enrichment_router", submission_history_proof_enrichment_router)
_safe_include_router("quotes_stable_router", quotes_stable_router)
_safe_include_router("rfq_stable_router", rfq_stable_router)
_safe_include_router("system_stable_router", system_stable_router)

OPTIONAL_ROUTERS: List[Tuple[str, str, str]] = [
    ("audit_api", "app.audit_api", "router"),
    ("compliance_api", "app.compliance_api", "router"),
    ("harvester_api", "app.harvester_api", "router"),
    ("sbd_api", "app.sbd_api", "router"),
    ("system_guard_api", "app.system_guard_api", "router"),
    ("autonomous_api", "app.autonomous_api", "router"),
    ("quote_compilation_router", "app.api.quote_compilation_api", "router"),
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
    ("operator_auth_router", "app.api.operator_auth_api", "router"),
    ("audit_trail_router", "app.api.audit_trail_api", "router"),
    ("go_live_guard_router", "app.api.go_live_guard_api", "router"),
    ("pipeline_enforcement_router", "app.api.pipeline_enforcement_api", "router"),
    ("full_autonomous_cycle_router", "app.api.full_autonomous_cycle_api", "router"),
    ("system_stability_router", "app.api.system_stability_api", "router"),
    ("security_router", "app.api.security_api", "router"),
    ("portal_submission_router", "app.api.portal_submission_api", "router"),
    ("proof_center_router", "app.api.proof_center_api", "router"),
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
    ("auto_pricing_v43_router", "app.api.auto_pricing_v43_api", "router"),
    ("quote_pack_v44_router", "app.api.quote_pack_v44_api", "router"),
    ("submission_pack_v45_router", "app.api.submission_pack_v45_api", "router"),
    ("auto_submission_v46_router", "app.api.auto_submission_v46_api", "router"),
    ("portal_submission_v47_router", "app.api.portal_submission_v47_api", "router"),
    ("portal_form_autofill_v47_1_router", "app.api.portal_form_autofill_v47_1_api", "router"),
    ("assisted_browser_v47_2_router", "app.api.assisted_browser_v47_2_api", "router"),
    ("live_browser_attach_v47_3_router", "app.api.live_browser_attach_v47_3_api", "router"),
    ("smart_upload_v47_4_router", "app.api.smart_upload_v47_4_api", "router"),
    ("final_submission_v47_5_router", "app.api.final_submission_v47_5_api", "router"),
    ("deep_verification_v47_7_router", "app.api.deep_verification_v47_7_api", "router"),
    ("full_autonomous_v48_router", "app.api.full_autonomous_v48_api", "router"),
    ("real_rfq_detail_navigation_v49_router", "app.api.real_rfq_detail_navigation_v49_api", "router"),
    ("detail_page_follow_v49_1_router", "app.api.detail_page_follow_v49_1_api", "router"),
    ("clickable_navigation_v40_router", "app.api.clickable_navigation_v40_api", "router"),
    ("handwriting_simulation_router", "app.api.handwriting_simulation_api", "router"),
    ("handwriting_form_overlay_router", "app.api.handwriting_form_overlay_api", "router"),
    ("handwriting_glyph_router", "app.api.handwriting_glyph_api", "router"),
    ("clean_ink_extraction_v3_router", "app.api.clean_ink_extraction_v3_api", "router"),
    ("handwriting_field_detector_router", "app.api.handwriting_field_detector_api", "router"),
    ("handwriting_full_auto_router", "app.api.handwriting_full_auto_api", "router"),
    ("tender_form_intelligence_router", "app.api.tender_form_intelligence_api", "router"),
    ("csd_persistent_session_router", "app.api.csd_persistent_session_api", "router"),
    ("csd_monthly_refresh_router", "app.api.csd_monthly_refresh_api", "router"),
    ("final_automation_router", "app.api.final_automation_layer_api", "router"),
    ("sbd_intelligence_router", "app.api.sbd_intelligence_api", "router"),
    ("production_lock_router", "app.api.production_lock_api", "router"),
    ("safe_autonomous_scheduler_router", "app.api.safe_autonomous_scheduler_api", "router"),
    ("real_profit_pricing_router", "app.api.real_profit_pricing_api", "router"),
    ("rfq_lifecycle_router", "app.api.rfq_lifecycle_api", "router"),

    # V50.7 upgrade routers
    ("etenders_real_detail_navigation_v50_7_router", "app.api.etenders_real_detail_navigation_v50_7_api", "router"),
    ("verified_rfq_promotion_gate_v50_7_router", "app.api.verified_rfq_promotion_gate_v50_7_api", "router"),
    ("true_etenders_detail_resolution_v50_8_router", "app.api.true_etenders_detail_resolution_v50_8_api", "router"),
    ("etenders_ajax_datatables_resolver_v50_8_1_router", "app.api.etenders_ajax_datatables_resolver_v50_8_1_api", "router"),
    ("etenders_document_url_reconstruction_v50_8_2_router", "app.api.etenders_document_url_reconstruction_v50_8_2_api", "router"),
    ("etenders_structured_json_parser_v50_8_3_router", "app.api.etenders_structured_json_parser_v50_8_3_api", "router"),
    ("etenders_status_enumerator_v50_8_4_router", "app.api.etenders_status_enumerator_v50_8_4_api", "router"),
    ("etenders_local_filter_v50_8_5_router", "app.api.etenders_local_filter_v50_8_5_api", "router"),
    ("etenders_document_download_v50_9_router", "app.api.etenders_document_download_v50_9_api", "router"),
    ("etenders_tenderdetails_json_v50_9_1_router", "app.api.etenders_tenderdetails_json_v50_9_1_api", "router"),
    ("etenders_support_document_download_v50_9_2_router", "app.api.etenders_support_document_download_v50_9_2_api", "router"),
    ("etenders_browser_download_interceptor_v50_9_3_router", "app.api.etenders_browser_download_interceptor_v50_9_3_api", "router"),
    ("etenders_dom_modal_autoclick_v50_9_4_router", "app.api.etenders_dom_modal_autoclick_v50_9_4_api", "router"),
    ("etenders_dom_trigger_forced_click_v50_9_5_router", "app.api.etenders_dom_trigger_forced_click_v50_9_5_api", "router"),
    ("etenders_hidden_api_discovery_v50_9_6_router", "app.api.etenders_hidden_api_discovery_v50_9_6_api", "router"),
    ("etenders_document_mapping_resolver_v50_9_7_router", "app.api.etenders_document_mapping_resolver_v50_9_7_api", "router"),
    ("etenders_download_replay_reconstruction_v50_9_8_router", "app.api.etenders_download_replay_reconstruction_v50_9_8_api", "router"),
    ("etenders_runtime_download_interceptor_v50_9_9_router", "app.api.etenders_runtime_download_interceptor_v50_9_9_api", "router"),
    ("etenders_tender_download_correlation_v50_9_10_router", "app.api.etenders_tender_download_correlation_v50_9_10_api", "router"),
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
    initialize_runtime_static_dirs()
    logger.info("LMCP AutoQuote API startup complete")
    logger.info("Loaded routers: %s", loaded_routers)
    logger.info("Failed routers: %s", failed_routers)
    logger.info("Disabled routers: %s", disabled_routers)
    logger.info("Runtime static path: %s", RUNTIME_DIR)
    logger.info("Monthly quotes static path: %s", MONTHLY_QUOTES_DIR)
    logger.info("Submission proofs static path: %s", SUBMISSION_PROOFS_DIR)
    logger.info("Portal submission static path: %s", PORTAL_SUBMISSION_DIR)
    logger.info("Final submission static path: %s", FINAL_SUBMISSION_DIR)
    logger.info("Proof center static path: %s", PROOF_CENTER_DIR)


def initialize_runtime_static_dirs() -> Dict[str, Any]:
    created = []
    for path in RUNTIME_STATIC_DIRS:
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path))
    return {"status": "ok", "directories": created}


def _base_status_payload() -> Dict[str, Any]:
    return {
        "version": APP_VERSION,
        "loaded_routers": loaded_routers,
        "loaded_routers_count": len(loaded_routers),
        "failed_routers": failed_routers,
        "failed_routers_count": len(failed_routers),
        "disabled_routers": disabled_routers,
        "disabled_routers_count": len(disabled_routers),
        "downloads_url": "/downloads",
        "runtime_url": "/runtime",
        "portal_runtime_url": "/portal-runtime",
        "final_submission_runtime_url": "/final-submission-runtime",
        "proof_center_runtime_url": "/proof-center-runtime",
        "submission_proofs_url": "/proofs",
        "submission_proofs_runtime_url": "/runtime/submission_proofs",
        "submission_history_url": "/submission-history",
        "submission_history_recent_url": "/submission-history/recent",
        "submission_history_recent_real_url": "/submission-history/recent-real",
        "submission_history_sync_url": "/submission-history/sync",
        "submission_proof_status_url": "/submission-proof/status",
        "submission_proof_latest_url": "/submission-proof/latest",
        "submission_proof_generate_url": "/submission-proof/generate",
        "submission_proof_generate_all_url": "/submission-proof/generate-all",
        "submission_history_proof_sync_url": "/submission-history/proof-sync",
        "submission_history_recent_with_proofs_url": "/submission-history/recent-with-proofs",
        "portal_submission_url": "/portal-submission/status",
        "portal_submission_classify_url": "/portal-submission/classify",
        "portal_submission_prepare_url": "/portal-submission/prepare",
        "portal_submission_proof_url": "/portal-submission/proof",
        "portal_submission_auto_submit_url": "/portal-submission/auto-submit",
        "proof_center_health_url": "/proof-center/health",
        "proof_center_scan_url": "/proof-center/scan",
        "proof_center_url": "/proof-center",
        "etenders_session_url": "/etenders-session/status",
        "full_autonomous_cycle_url": "/full-autonomous-cycle/status",
        "full_autonomous_v48_url": "/v48-autonomous/status",
        "v50_7_etenders_navigation_url": "/v50-7-etenders-navigation/status",
        "v50_7_promotion_gate_url": "/v50-7-promotion-gate/status",
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "message": "LMCP AutoQuote System API is running",
        "status": "ok",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        **_base_status_payload(),
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "LMCP AutoQuote System",
        "monthly_quotes_dir": str(MONTHLY_QUOTES_DIR),
        "runtime_dir": str(RUNTIME_DIR),
        "submission_proofs_dir": str(SUBMISSION_PROOFS_DIR),
        "portal_submission_dir": str(PORTAL_SUBMISSION_DIR),
        "final_submission_dir": str(FINAL_SUBMISSION_DIR),
        "proof_center_dir": str(PROOF_CENTER_DIR),
        "proof_center_url": "/proof-center",
        "proof_center_scan_url": "/proof-center/scan",
        "proof_center_health_url": "/proof-center/health",
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
        "system_stability_url": "/system-stability/watchdog",
        "security_url": "/security/status",
        "sbd_completion_url": "/sbd-completion/summary",
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
        "v50_7_etenders_navigation_url": "/v50-7-etenders-navigation/status",
        "v50_7_etenders_navigation_analyse_url": "/v50-7-etenders-navigation/analyse",
        "v50_7_promotion_gate_url": "/v50-7-promotion-gate/status",
        "v50_7_promotion_gate_evaluate_url": "/v50-7-promotion-gate/evaluate",
        "v50_7_promotion_gate_batch_evaluate_url": "/v50-7-promotion-gate/batch-evaluate",
        **_base_status_payload(),
    }


@app.get("/health/workflows")
def workflow_health() -> Dict[str, Any]:
    return {
        "status": "ok" if not failed_routers else "degraded",
        "service": "LMCP AutoQuote workflows",
        "loaded_routers_count": len(loaded_routers),
        "failed_routers_count": len(failed_routers),
        "disabled_routers_count": len(disabled_routers),
        "loaded_routers": loaded_routers,
        "failed_routers": failed_routers,
        "disabled_routers": disabled_routers,
        "safety": {
            "autonomous_default_disabled": True,
            "high_risk_source_only_routers_default_disabled": True,
            "read_only": True,
        },
    }

app.include_router(mission_control_compat_api.router)
