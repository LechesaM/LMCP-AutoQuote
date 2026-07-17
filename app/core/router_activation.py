from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, Optional

logger = logging.getLogger(__name__)

DISABLED_BY_DEFAULT: Dict[str, str] = {
    "smart_harvester_v31_router": "acquisition execution",
    "real_rfq_harvester_v32_router": "acquisition execution",
    "real_portal_rfq_extraction_v33_router": "portal acquisition",
    "structured_rfq_extractor_v34_router": "portal acquisition",
    "playwright_live_dom_extractor_v35_router": "browser automation",
    "interactive_playwright_extractor_v36_router": "browser automation",
    "deep_rfq_link_extractor_v37_router": "acquisition enrichment",
    "interactive_click_deep_extraction_v38_router": "browser automation",
    "true_navigation_extraction_v39_router": "browser automation",
    "clickable_navigation_v40_router": "browser automation",
    "auto_pricing_v43_router": "pricing mutation",
    "quote_pack_v44_router": "artifact generation",
    "submission_pack_v45_router": "submission pack generation",
    "full_autonomous_cycle_router": "autonomous execution",
    "portal_submission_router": "portal upload",
    "auto_submission_v46_router": "submission automation",
    "portal_submission_v47_router": "portal upload",
    "portal_form_autofill_v47_1_router": "portal automation",
    "assisted_browser_v47_2_router": "browser automation",
    "live_browser_attach_v47_3_router": "browser automation",
    "smart_upload_v47_4_router": "portal upload",
    "final_submission_v47_5_router": "final submission",
    "deep_verification_v47_7_router": "portal verification",
    "full_autonomous_v48_router": "autonomous execution",
    "real_rfq_detail_navigation_v49_router": "browser navigation",
    "detail_page_follow_v49_1_router": "browser navigation",
    "clean_ink_extraction_v3_router": "document processing",
    "handwriting_simulation_router": "document generation",
    "handwriting_form_overlay_router": "document generation",
    "handwriting_glyph_router": "document generation",
    "handwriting_field_detector_router": "document processing",
    "handwriting_full_auto_router": "document automation",
    "csd_persistent_session_router": "external session automation",
    "csd_monthly_refresh_router": "external refresh automation",
    "final_automation_router": "final automation",
    "safe_autonomous_scheduler_router": "autonomous scheduling",
    "real_profit_pricing_router": "pricing mutation",
    "etenders_real_detail_navigation_v50_7_router": "browser navigation",
    "verified_rfq_promotion_gate_v50_7_router": "RFQ promotion mutation",
    "true_etenders_detail_resolution_v50_8_router": "eTenders acquisition",
    "etenders_ajax_datatables_resolver_v50_8_1_router": "eTenders acquisition",
    "etenders_document_url_reconstruction_v50_8_2_router": "document acquisition",
    "etenders_structured_json_parser_v50_8_3_router": "eTenders acquisition",
    "etenders_status_enumerator_v50_8_4_router": "eTenders acquisition",
    "etenders_local_filter_v50_8_5_router": "RFQ processing",
    "etenders_document_download_v50_9_router": "document download",
    "etenders_tenderdetails_json_v50_9_1_router": "document download",
    "etenders_support_document_download_v50_9_2_router": "document download",
    "etenders_browser_download_interceptor_v50_9_3_router": "browser download",
    "etenders_dom_modal_autoclick_v50_9_4_router": "browser automation",
    "etenders_dom_trigger_forced_click_v50_9_5_router": "browser automation",
    "etenders_hidden_api_discovery_v50_9_6_router": "hidden API discovery",
    "etenders_document_mapping_resolver_v50_9_7_router": "document download",
    "etenders_download_replay_reconstruction_v50_9_8_router": "download replay",
    "etenders_runtime_download_interceptor_v50_9_9_router": "browser download",
    "etenders_tender_download_correlation_v50_9_10_router": "download correlation",
}


def _csv_env(name: str) -> Iterable[str]:
    value = os.getenv(name, "")
    return {part.strip() for part in value.split(",") if part.strip()}


def router_activation_reason(router_name: str) -> Optional[str]:
    return DISABLED_BY_DEFAULT.get(router_name)


def is_router_family_enabled(router_name: str) -> bool:
    if router_name not in DISABLED_BY_DEFAULT:
        return True

    if os.getenv("LMCP_ENABLE_HIGH_RISK_ROUTERS", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True

    enabled = set(_csv_env("LMCP_ENABLE_ROUTER_FAMILIES"))
    return router_name in enabled or "*" in enabled


def log_router_activation(router_name: str, enabled: bool) -> None:
    if enabled:
        return
    logger.info(
        "Router disabled by operational baseline: %s (%s)",
        router_name,
        DISABLED_BY_DEFAULT.get(router_name, "controlled route family"),
    )
