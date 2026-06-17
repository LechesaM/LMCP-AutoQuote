from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class RouterSpec:
    name: str
    module_path: str
    attribute_name: str = "router"

    @property
    def status(self) -> str:
        return "production" if not _is_legacy_router_spec(self) else "legacy"


_ALL_ROUTER_SPECS: Tuple[RouterSpec, ...] = (
    RouterSpec("tender_pipeline_router", "app.api.tender_pipeline_api"),
    RouterSpec("quote_engine_router", "app.api.quote_engine_api"),
    RouterSpec("submission_pipeline_router", "app.api.submission_pipeline_api"),
    RouterSpec("email_router", "app.email_api"),
    RouterSpec("test_pricing_router", "app.api.test_pricing_api"),
    RouterSpec("tasks_router", "app.tasks_api"),
    RouterSpec("supplier_quotes_router", "app.api.supplier_quotes_api"),
    RouterSpec("email_ingestion_router", "app.api.email_ingestion_api"),
    RouterSpec("csd_router", "app.api.csd_api"),
    RouterSpec("opportunities_router", "app.api.opportunities_api"),
    RouterSpec("system_control_router", "app.api.system_control"),
    RouterSpec("submission_history_recent_router", "app.api.submission_history_recent_api"),
    RouterSpec("submission_history_pipeline_sync_router", "app.api.submission_history_pipeline_sync_api"),
    RouterSpec("proof_of_submission_router", "app.api.proof_of_submission_api"),
    RouterSpec("submission_history_proof_enrichment_router", "app.api.submission_history_proof_enrichment_api"),
    RouterSpec("quotes_stable_router", "app.api.quotes_stable_api"),
    RouterSpec("rfq_stable_router", "app.api.rfq_stable_api"),
    RouterSpec("system_stable_router", "app.api.system_stable_api"),
    RouterSpec("ui_routes", "app.ui_routes"),
    RouterSpec("audit_api", "app.audit_api"),
    RouterSpec("compliance_api", "app.compliance_api"),
    RouterSpec("harvester_api", "app.harvester_api"),
    RouterSpec("sbd_api", "app.sbd_api"),
    RouterSpec("system_guard_api", "app.system_guard_api"),
    RouterSpec("autonomous_api", "app.api.autonomous_api"),
    RouterSpec("quote_compilation_router", "app.api.quote_compilation_api"),
    RouterSpec("dashboard", "app.api.dashboard"),
    RouterSpec("business_intelligence_router", "app.api.business_intelligence_routes"),
    RouterSpec("form_filler_api", "app.api.form_filler_api"),
    RouterSpec("revenue_dashboard_api", "app.api.revenue_dashboard_api"),
    RouterSpec("sbd_version_detector_api", "app.api.sbd_version_detector_api"),
    RouterSpec("self_healing_harvester", "app.api.self_healing_harvester"),
    RouterSpec("supervisor", "app.api.supervisor"),
    RouterSpec("supply_command_api", "app.api.supply_command_api"),
    RouterSpec("system_api", "app.api.system"),
    RouterSpec("tender_form_priority_api", "app.api.tender_form_priority_api"),
    RouterSpec("submission_history_router", "app.api.submission_history"),
    RouterSpec("submission_retry_router", "app.api.submission_retry_api"),
    RouterSpec("submission_scheduler_router", "app.api.submission_scheduler_api"),
    RouterSpec("submission_analytics_router", "app.api.submission_analytics_api"),
    RouterSpec("ws_live_router", "app.api.ws_live"),
    RouterSpec("decision_intelligence_router", "app.api.decision_intelligence_api"),
    RouterSpec("operator_actions_router", "app.api.operator_actions_api"),
    RouterSpec("operator_ops_router", "app.api.operator_ops_routes"),
    RouterSpec("operator_workflow_router", "app.api.operator_workflow_routes"),
    RouterSpec("operator_auth_router", "app.api.operator_auth_api"),
    RouterSpec("audit_trail_router", "app.api.audit_trail_api"),
    RouterSpec("go_live_guard_router", "app.api.go_live_guard_api"),
    RouterSpec("pipeline_enforcement_router", "app.api.pipeline_enforcement_api"),
    RouterSpec("full_autonomous_cycle_router", "app.api.full_autonomous_cycle_api"),
    RouterSpec("system_stability_router", "app.api.system_stability_api"),
    RouterSpec("security_router", "app.api.security_api"),
    RouterSpec("portal_submission_router", "app.api.portal_submission_api"),
    RouterSpec("proof_center_router", "app.api.proof_center_api"),
    RouterSpec("sbd_completion_router", "app.api.sbd_completion_api"),
    RouterSpec("etenders_session_router", "app.api.etenders_session_api"),
    RouterSpec("smart_harvester_v31_router", "app.api.smart_harvester_v31_api"),
    RouterSpec("real_rfq_harvester_v32_router", "app.api.real_rfq_harvester_v32_api"),
    RouterSpec("real_portal_rfq_extraction_v33_router", "app.api.real_portal_rfq_extraction_v33_api"),
    RouterSpec("structured_rfq_extractor_v34_router", "app.api.structured_rfq_extractor_v34_api"),
    RouterSpec("playwright_live_dom_extractor_v35_router", "app.api.playwright_live_dom_extractor_v35_api"),
    RouterSpec("interactive_playwright_extractor_v36_router", "app.api.interactive_playwright_extractor_v36_api"),
    RouterSpec("deep_rfq_link_extractor_v37_router", "app.api.deep_rfq_link_extractor_v37_api"),
    RouterSpec("interactive_click_deep_extraction_v38_router", "app.api.interactive_click_deep_extraction_v38_api"),
    RouterSpec("true_navigation_extraction_v39_router", "app.api.true_navigation_extraction_v39_api"),
    RouterSpec("auto_pricing_v43_router", "app.api.auto_pricing_v43_api"),
    RouterSpec("quote_pack_v44_router", "app.api.quote_pack_v44_api"),
    RouterSpec("submission_pack_v45_router", "app.api.submission_pack_v45_api"),
    RouterSpec("auto_submission_v46_router", "app.api.auto_submission_v46_api"),
    RouterSpec("portal_submission_v47_router", "app.api.portal_submission_v47_api"),
    RouterSpec("portal_form_autofill_v47_1_router", "app.api.portal_form_autofill_v47_1_api"),
    RouterSpec("assisted_browser_v47_2_router", "app.api.assisted_browser_v47_2_api"),
    RouterSpec("live_browser_attach_v47_3_router", "app.api.live_browser_attach_v47_3_api"),
    RouterSpec("smart_upload_v47_4_router", "app.api.smart_upload_v47_4_api"),
    RouterSpec("final_submission_v47_5_router", "app.api.final_submission_v47_5_api"),
    RouterSpec("deep_verification_v47_7_router", "app.api.deep_verification_v47_7_api"),
    RouterSpec("full_autonomous_v48_router", "app.api.full_autonomous_v48_api"),
    RouterSpec("real_rfq_detail_navigation_v49_router", "app.api.real_rfq_detail_navigation_v49_api"),
    RouterSpec("detail_page_follow_v49_1_router", "app.api.detail_page_follow_v49_1_api"),
    RouterSpec("clickable_navigation_v40_router", "app.api.clickable_navigation_v40_api"),
    RouterSpec("handwriting_simulation_router", "app.api.handwriting_simulation_api"),
    RouterSpec("handwriting_form_overlay_router", "app.api.handwriting_form_overlay_api"),
    RouterSpec("handwriting_glyph_router", "app.api.handwriting_glyph_api"),
    RouterSpec("handwriting_line_ink_v5_router", "app.api.handwriting_line_ink_v5_api"),
    RouterSpec("handwriting_stack_router", "app.api.handwriting_stack_api"),
    RouterSpec("clean_ink_extraction_v3_router", "app.api.clean_ink_extraction_v3_api"),
    RouterSpec("handwriting_field_detector_router", "app.api.handwriting_field_detector_api"),
    RouterSpec("handwriting_full_auto_router", "app.api.handwriting_full_auto_api"),
    RouterSpec("tender_form_intelligence_router", "app.api.tender_form_intelligence_api"),
    RouterSpec("csd_persistent_session_router", "app.api.csd_persistent_session_api"),
    RouterSpec("csd_monthly_refresh_router", "app.api.csd_monthly_refresh_api"),
    RouterSpec("final_automation_router", "app.api.final_automation_layer_api"),
    RouterSpec("sbd_intelligence_router", "app.api.sbd_intelligence_api"),
    RouterSpec("production_lock_router", "app.api.production_lock_api"),
    RouterSpec("safe_autonomous_scheduler_router", "app.api.safe_autonomous_scheduler_api"),
    RouterSpec("real_profit_pricing_router", "app.api.real_profit_pricing_api"),
    RouterSpec("rfq_lifecycle_router", "app.api.rfq_lifecycle_api"),
    RouterSpec("etenders_real_detail_navigation_v50_7_router", "app.api.etenders_real_detail_navigation_v50_7_api"),
    RouterSpec("verified_rfq_promotion_gate_v50_7_router", "app.api.verified_rfq_promotion_gate_v50_7_api"),
    RouterSpec("true_etenders_detail_resolution_v50_8_router", "app.api.true_etenders_detail_resolution_v50_8_api"),
    RouterSpec("etenders_ajax_datatables_resolver_v50_8_1_router", "app.api.etenders_ajax_datatables_resolver_v50_8_1_api"),
    RouterSpec("etenders_document_url_reconstruction_v50_8_2_router", "app.api.etenders_document_url_reconstruction_v50_8_2_api"),
    RouterSpec("etenders_structured_json_parser_v50_8_3_router", "app.api.etenders_structured_json_parser_v50_8_3_api"),
    RouterSpec("etenders_status_enumerator_v50_8_4_router", "app.api.etenders_status_enumerator_v50_8_4_api"),
    RouterSpec("etenders_local_filter_v50_8_5_router", "app.api.etenders_local_filter_v50_8_5_api"),
    RouterSpec("etenders_document_download_v50_9_router", "app.api.etenders_document_download_v50_9_api"),
    RouterSpec("etenders_tenderdetails_json_v50_9_1_router", "app.api.etenders_tenderdetails_json_v50_9_1_api"),
    RouterSpec("etenders_support_document_download_v50_9_2_router", "app.api.etenders_support_document_download_v50_9_2_api"),
    RouterSpec("etenders_browser_download_interceptor_v50_9_3_router", "app.api.etenders_browser_download_interceptor_v50_9_3_api"),
    RouterSpec("etenders_dom_modal_autoclick_v50_9_4_router", "app.api.etenders_dom_modal_autoclick_v50_9_4_api"),
    RouterSpec("etenders_dom_trigger_forced_click_v50_9_5_router", "app.api.etenders_dom_trigger_forced_click_v50_9_5_api"),
    RouterSpec("etenders_hidden_api_discovery_v50_9_6_router", "app.api.etenders_hidden_api_discovery_v50_9_6_api"),
    RouterSpec("etenders_document_mapping_resolver_v50_9_7_router", "app.api.etenders_document_mapping_resolver_v50_9_7_api"),
    RouterSpec("etenders_download_replay_reconstruction_v50_9_8_router", "app.api.etenders_download_replay_reconstruction_v50_9_8_api"),
    RouterSpec("etenders_runtime_download_interceptor_v50_9_9_router", "app.api.etenders_runtime_download_interceptor_v50_9_9_api"),
    RouterSpec("etenders_tender_download_correlation_v50_9_10_router", "app.api.etenders_tender_download_correlation_v50_9_10_api"),
    RouterSpec("mission_control_ai_scoring_router", "app.api.mission_control_ai_scoring_api"),
    RouterSpec("mission_control_snapshot_router", "app.api.mission_control_snapshot_api"),
    RouterSpec("mission_control_compat_router", "app.api.mission_control_compat_api"),
)


LEGACY_ROUTER_ENV_VAR = "LMCP_ENABLE_LEGACY_ROUTERS"
_LEGACY_VERSION_PATTERN = re.compile(r"_v\d+")
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "y", "on"}


def _is_legacy_router_spec(spec: RouterSpec) -> bool:
    if _LEGACY_VERSION_PATTERN.search(spec.name) or _LEGACY_VERSION_PATTERN.search(spec.module_path):
        return True
    return spec.name in {
        "autonomous_api",
        "final_automation_router",
        "full_autonomous_cycle_router",
        "go_live_guard_router",
        "pipeline_enforcement_router",
        "production_lock_router",
        "real_profit_pricing_router",
        "sbd_intelligence_router",
        "supervisor",
        "tender_form_intelligence_router",
        "csd_persistent_session_router",
        "csd_monthly_refresh_router",
        "system_api",
        "system_control_router",
        "system_stability_router",
        "submission_pipeline_router",
        "submission_retry_router",
        "submission_scheduler_router",
        "safe_autonomous_scheduler_router",
    }


def _detect_duplicate_router_names(specs: Sequence[RouterSpec]) -> Tuple[str, ...]:
    counts: dict[str, int] = {}
    for spec in specs:
        counts[spec.name] = counts.get(spec.name, 0) + 1
    return tuple(sorted(name for name, count in counts.items() if count > 1))


def _validate_router_specs(specs: Sequence[RouterSpec], label: str = "router specs") -> Tuple[RouterSpec, ...]:
    validated = tuple(specs)
    duplicates = _detect_duplicate_router_names(validated)
    if duplicates:
        joined = ", ".join(duplicates)
        raise ValueError(f"Duplicate router names detected in {label}: {joined}")
    return validated


def _legacy_routers_enabled(environ: Mapping[str, str] | None = None) -> bool:
    source = environ if environ is not None else os.environ
    raw_value = str(source.get(LEGACY_ROUTER_ENV_VAR, "")).strip().lower()
    return raw_value in _TRUTHY_ENV_VALUES


PRODUCTION_ROUTER_SPECS: Tuple[RouterSpec, ...] = tuple(
    spec for spec in _ALL_ROUTER_SPECS if not _is_legacy_router_spec(spec)
)
LEGACY_ROUTER_SPECS: Tuple[RouterSpec, ...] = tuple(
    spec for spec in _ALL_ROUTER_SPECS if _is_legacy_router_spec(spec)
)
CORE_ROUTER_SPECS: Tuple[RouterSpec, ...] = PRODUCTION_ROUTER_SPECS + LEGACY_ROUTER_SPECS

_validate_router_specs(PRODUCTION_ROUTER_SPECS, "PRODUCTION_ROUTER_SPECS")
_validate_router_specs(LEGACY_ROUTER_SPECS, "LEGACY_ROUTER_SPECS")
_validate_router_specs(CORE_ROUTER_SPECS, "CORE_ROUTER_SPECS")


def iter_router_specs(
    *,
    include_legacy: bool | None = None,
    production_router_specs: Sequence[RouterSpec] = PRODUCTION_ROUTER_SPECS,
    legacy_router_specs: Sequence[RouterSpec] = LEGACY_ROUTER_SPECS,
) -> Iterable[RouterSpec]:
    production_specs = _validate_router_specs(production_router_specs, "production router specs")
    specs = production_specs

    if include_legacy is None:
        include_legacy = _legacy_routers_enabled()
    if include_legacy:
        specs = production_specs + _validate_router_specs(legacy_router_specs, "legacy router specs")

    return _validate_router_specs(specs, "selected router specs")


def versioned_router_names() -> tuple[str, ...]:
    return tuple(sorted(spec.name for spec in LEGACY_ROUTER_SPECS))
