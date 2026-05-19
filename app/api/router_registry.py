from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple


VALID_ROUTER_STATUSES = {"production", "legacy", "experimental", "deprecated"}


@dataclass(frozen=True)
class RouterSpec:
    name: str
    module_path: str
    attribute_name: str = "router"
    status: str = "production"


def _spec(name: str, module_path: str, *, status: str = "production", attribute_name: str = "router") -> RouterSpec:
    return RouterSpec(name=name, module_path=module_path, attribute_name=attribute_name, status=status)


PRODUCTION_ROUTER_SPECS: Tuple[RouterSpec, ...] = (
    _spec("supplier_quotes_router", "app.api.supplier_quotes_api"),
    _spec("email_ingestion_router", "app.api.email_ingestion_api"),
    _spec("csd_router", "app.api.csd_api"),
    _spec("opportunities_router", "app.api.opportunities_api"),
    _spec("submission_history_recent_router", "app.api.submission_history_recent_api"),
    _spec("submission_history_pipeline_sync_router", "app.api.submission_history_pipeline_sync_api"),
    _spec("proof_of_submission_router", "app.api.proof_of_submission_api"),
    _spec("submission_history_proof_enrichment_router", "app.api.submission_history_proof_enrichment_api"),
    _spec("quotes_stable_router", "app.api.quotes_stable_api"),
    _spec("rfq_stable_router", "app.api.rfq_stable_api"),
    _spec("system_stable_router", "app.api.system_stable_api"),
    _spec("audit_api", "app.audit_api"),
    _spec("compliance_api", "app.compliance_api"),
    _spec("harvester_api", "app.harvester_api"),
    _spec("sbd_api", "app.sbd_api"),
    _spec("system_guard_api", "app.system_guard_api"),
    _spec("quote_compilation_router", "app.api.quote_compilation_api"),
    _spec("dashboard", "app.api.dashboard"),
    _spec("form_filler_api", "app.api.form_filler_api"),
    _spec("sbd_version_detector_api", "app.api.sbd_version_detector_api"),
    _spec("supply_command_api", "app.api.supply_command_api"),
    _spec("submission_history_router", "app.api.submission_history"),
    _spec("submission_analytics_router", "app.api.submission_analytics_api"),
    _spec("decision_intelligence_router", "app.api.decision_intelligence_api"),
    _spec("operator_actions_router", "app.api.operator_actions_api"),
    _spec("operator_auth_router", "app.api.operator_auth_api"),
    _spec("audit_trail_router", "app.api.audit_trail_api"),
    _spec("go_live_guard_router", "app.api.go_live_guard_api"),
    _spec("pipeline_enforcement_router", "app.api.pipeline_enforcement_api"),
    _spec("security_router", "app.api.security_api"),
    _spec("portal_submission_router", "app.api.portal_submission_api"),
    _spec("proof_center_router", "app.api.proof_center_api"),
    _spec("sbd_completion_router", "app.api.sbd_completion_api"),
    _spec("etenders_session_router", "app.api.etenders_session_api"),
    _spec("handwriting_form_overlay_router", "app.api.handwriting_form_overlay_api"),
    _spec("handwriting_glyph_router", "app.api.handwriting_glyph_api"),
    _spec("handwriting_field_detector_router", "app.api.handwriting_field_detector_api"),
    _spec("tender_form_intelligence_router", "app.api.tender_form_intelligence_api"),
    _spec("csd_persistent_session_router", "app.api.csd_persistent_session_api"),
    _spec("csd_monthly_refresh_router", "app.api.csd_monthly_refresh_api"),
    _spec("sbd_intelligence_router", "app.api.sbd_intelligence_api"),
    _spec("production_lock_router", "app.api.production_lock_api"),
    _spec("real_profit_pricing_router", "app.api.real_profit_pricing_api"),
    _spec("rfq_lifecycle_router", "app.api.rfq_lifecycle_api"),
    _spec("mission_control_compat_router", "app.api.mission_control_compat_api"),
    _spec("harvest_router", "app.api.harvest_routes"),
    _spec("telemetry_router", "app.api.telemetry_routes"),
    _spec("operator_workflow_router", "app.api.operator_workflow_routes"),
    _spec("operator_ops_router", "app.api.operator_ops_routes"),
)


LEGACY_ROUTER_SPECS: Tuple[RouterSpec, ...] = (
    _spec("tender_pipeline_router", "app.api.tender_pipeline_api", status="legacy"),
    _spec("quote_engine_router", "app.api.quote_engine_api", status="legacy"),
    _spec("submission_pipeline_router", "app.api.submission_pipeline_api", status="legacy"),
    _spec("email_router", "app.email_api", status="legacy"),
    _spec("test_pricing_router", "app.api.test_pricing_api", status="experimental"),
    _spec("tasks_router", "app.tasks_api", status="legacy"),
    _spec("system_control_router", "app.api.system_control", status="legacy"),
    _spec("autonomous_api", "app.api.autonomous_api", status="deprecated"),
    _spec("revenue_dashboard_api", "app.api.revenue_dashboard_api", status="legacy"),
    _spec("self_healing_harvester", "app.api.self_healing_harvester", status="experimental"),
    _spec("supervisor", "app.api.supervisor", status="legacy"),
    _spec("system_api", "app.api.system", status="legacy"),
    _spec("tender_form_priority_api", "app.api.tender_form_priority_api", status="legacy"),
    _spec("submission_retry_router", "app.api.submission_retry_api", status="legacy"),
    _spec("submission_scheduler_router", "app.api.submission_scheduler_api", status="legacy"),
    _spec("ws_live_router", "app.api.ws_live", status="legacy"),
    _spec("full_autonomous_cycle_router", "app.api.full_autonomous_cycle_api", status="deprecated"),
    _spec("system_stability_router", "app.api.system_stability_api", status="legacy"),
    _spec("smart_harvester_v31_router", "app.api.smart_harvester_v31_api", status="legacy"),
    _spec("real_rfq_harvester_v32_router", "app.api.real_rfq_harvester_v32_api", status="legacy"),
    _spec("real_portal_rfq_extraction_v33_router", "app.api.real_portal_rfq_extraction_v33_api", status="legacy"),
    _spec("structured_rfq_extractor_v34_router", "app.api.structured_rfq_extractor_v34_api", status="legacy"),
    _spec("playwright_live_dom_extractor_v35_router", "app.api.playwright_live_dom_extractor_v35_api", status="legacy"),
    _spec("interactive_playwright_extractor_v36_router", "app.api.interactive_playwright_extractor_v36_api", status="legacy"),
    _spec("deep_rfq_link_extractor_v37_router", "app.api.deep_rfq_link_extractor_v37_api", status="legacy"),
    _spec("interactive_click_deep_extraction_v38_router", "app.api.interactive_click_deep_extraction_v38_api", status="legacy"),
    _spec("true_navigation_extraction_v39_router", "app.api.true_navigation_extraction_v39_api", status="legacy"),
    _spec("auto_pricing_v43_router", "app.api.auto_pricing_v43_api", status="legacy"),
    _spec("quote_pack_v44_router", "app.api.quote_pack_v44_api", status="legacy"),
    _spec("submission_pack_v45_router", "app.api.submission_pack_v45_api", status="legacy"),
    _spec("auto_submission_v46_router", "app.api.auto_submission_v46_api", status="deprecated"),
    _spec("portal_submission_v47_router", "app.api.portal_submission_v47_api", status="legacy"),
    _spec("portal_form_autofill_v47_1_router", "app.api.portal_form_autofill_v47_1_api", status="legacy"),
    _spec("assisted_browser_v47_2_router", "app.api.assisted_browser_v47_2_api", status="legacy"),
    _spec("live_browser_attach_v47_3_router", "app.api.live_browser_attach_v47_3_api", status="legacy"),
    _spec("smart_upload_v47_4_router", "app.api.smart_upload_v47_4_api", status="legacy"),
    _spec("final_submission_v47_5_router", "app.api.final_submission_v47_5_api", status="deprecated"),
    _spec("deep_verification_v47_7_router", "app.api.deep_verification_v47_7_api", status="legacy"),
    _spec("full_autonomous_v48_router", "app.api.full_autonomous_v48_api", status="deprecated"),
    _spec("real_rfq_detail_navigation_v49_router", "app.api.real_rfq_detail_navigation_v49_api", status="legacy"),
    _spec("detail_page_follow_v49_1_router", "app.api.detail_page_follow_v49_1_api", status="legacy"),
    _spec("clickable_navigation_v40_router", "app.api.clickable_navigation_v40_api", status="legacy"),
    _spec("handwriting_simulation_router", "app.api.handwriting_simulation_api", status="legacy"),
    _spec("clean_ink_extraction_v3_router", "app.api.clean_ink_extraction_v3_api", status="legacy"),
    _spec("handwriting_full_auto_router", "app.api.handwriting_full_auto_api", status="experimental"),
    _spec("final_automation_router", "app.api.final_automation_layer_api", status="deprecated"),
    _spec("safe_autonomous_scheduler_router", "app.api.safe_autonomous_scheduler_api", status="deprecated"),
    _spec("etenders_real_detail_navigation_v50_7_router", "app.api.etenders_real_detail_navigation_v50_7_api", status="legacy"),
    _spec("verified_rfq_promotion_gate_v50_7_router", "app.api.verified_rfq_promotion_gate_v50_7_api", status="legacy"),
    _spec("true_etenders_detail_resolution_v50_8_router", "app.api.true_etenders_detail_resolution_v50_8_api", status="legacy"),
    _spec("etenders_ajax_datatables_resolver_v50_8_1_router", "app.api.etenders_ajax_datatables_resolver_v50_8_1_api", status="legacy"),
    _spec("etenders_document_url_reconstruction_v50_8_2_router", "app.api.etenders_document_url_reconstruction_v50_8_2_api", status="legacy"),
    _spec("etenders_structured_json_parser_v50_8_3_router", "app.api.etenders_structured_json_parser_v50_8_3_api", status="legacy"),
    _spec("etenders_status_enumerator_v50_8_4_router", "app.api.etenders_status_enumerator_v50_8_4_api", status="legacy"),
    _spec("etenders_local_filter_v50_8_5_router", "app.api.etenders_local_filter_v50_8_5_api", status="legacy"),
    _spec("etenders_document_download_v50_9_router", "app.api.etenders_document_download_v50_9_api", status="legacy"),
    _spec("etenders_tenderdetails_json_v50_9_1_router", "app.api.etenders_tenderdetails_json_v50_9_1_api", status="legacy"),
    _spec("etenders_support_document_download_v50_9_2_router", "app.api.etenders_support_document_download_v50_9_2_api", status="legacy"),
    _spec("etenders_browser_download_interceptor_v50_9_3_router", "app.api.etenders_browser_download_interceptor_v50_9_3_api", status="legacy"),
    _spec("etenders_dom_modal_autoclick_v50_9_4_router", "app.api.etenders_dom_modal_autoclick_v50_9_4_api", status="legacy"),
    _spec("etenders_dom_trigger_forced_click_v50_9_5_router", "app.api.etenders_dom_trigger_forced_click_v50_9_5_api", status="legacy"),
    _spec("etenders_hidden_api_discovery_v50_9_6_router", "app.api.etenders_hidden_api_discovery_v50_9_6_api", status="legacy"),
    _spec("etenders_document_mapping_resolver_v50_9_7_router", "app.api.etenders_document_mapping_resolver_v50_9_7_api", status="legacy"),
    _spec("etenders_download_replay_reconstruction_v50_9_8_router", "app.api.etenders_download_replay_reconstruction_v50_9_8_api", status="legacy"),
    _spec("etenders_runtime_download_interceptor_v50_9_9_router", "app.api.etenders_runtime_download_interceptor_v50_9_9_api", status="legacy"),
    _spec("etenders_tender_download_correlation_v50_9_10_router", "app.api.etenders_tender_download_correlation_v50_9_10_api", status="legacy"),
)


CORE_ROUTER_SPECS: Tuple[RouterSpec, ...] = PRODUCTION_ROUTER_SPECS + LEGACY_ROUTER_SPECS

LEGACY_ROUTER_ENV_VAR = "LMCP_ENABLE_LEGACY_ROUTERS"
_LEGACY_VERSION_PATTERN = re.compile(r"_v\d+")
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "y", "on"}


def _is_legacy_router_spec(spec: RouterSpec) -> bool:
    return spec.status != "production"


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
    invalid_statuses = sorted({spec.status for spec in validated if spec.status not in VALID_ROUTER_STATUSES})
    if invalid_statuses:
        joined = ", ".join(invalid_statuses)
        raise ValueError(f"Invalid router statuses detected in {label}: {joined}")
    return validated


def _legacy_routers_enabled(environ: Mapping[str, str] | None = None) -> bool:
    source = environ if environ is not None else os.environ
    raw_value = str(source.get(LEGACY_ROUTER_ENV_VAR, "")).strip().lower()
    return raw_value in _TRUTHY_ENV_VALUES


def versioned_router_names(specs: Sequence[RouterSpec] = CORE_ROUTER_SPECS) -> Tuple[str, ...]:
    return tuple(
        spec.name
        for spec in specs
        if _LEGACY_VERSION_PATTERN.search(spec.name) or _LEGACY_VERSION_PATTERN.search(spec.module_path)
    )


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
