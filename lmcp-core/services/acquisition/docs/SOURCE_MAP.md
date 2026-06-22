# Acquisition Source Map

This source map identifies the current runtime assets that belong logically to the Acquisition Service boundary.

## Primary Service Modules

- `app/services/tender_harvester.py`
- `app/services/harvest_scheduler_service.py`
- `app/services/local_harvest_service.py`
- `app/services/harvest_source_registry_service.py`
- `app/services/harvester_adapter.py`
- `app/services/rfq_document_acquisition_engine.py`
- `app/services/portal_radar_service.py`
- `app/services/national_portal_radar.py`
- `app/services/source_parser_routing_service.py`
- `app/services/direct_portal_harvesters.py`
- `app/services/autonomous_tender_hunter.py`
- `app/services/adaptive_crawler.py`
- `app/services/self_healing_harvester.py`
- `app/services/priority_harvest_queue.py`

## eTenders and Browser Acquisition

- `app/services/etenders_playwright.py`
- `app/services/etenders_persistent_session_service.py`
- `app/services/etenders_web_parser.py`
- `app/services/etenders_ajax_datatables_resolver_v50_8_1_service.py`
- `app/services/etenders_real_detail_navigation_v50_7_service.py`
- `app/services/true_etenders_detail_resolution_v50_8_service.py`
- `app/services/etenders_hidden_api_discovery_v50_9_6_service.py`
- `app/services/etenders_document_download_v50_9_service.py`
- `app/services/etenders_support_document_download_v50_9_2_service.py`
- `app/services/etenders_runtime_download_interceptor_v50_9_9.py`
- `app/services/etenders_tender_download_correlation_v50_9_10.py`
- `app/services/etenders_document_mapping_resolver_v50_9_7_service.py`
- `app/services/etenders_document_url_reconstruction_v50_8_2_service.py`

## Portal Discovery and Opportunity Detection

- `app/services/portal_registry.py`
- `app/services/portal_isolation.py`
- `app/services/portal_crawl_priority.py`
- `app/services/real_rfq_harvester_v32_service.py`
- `app/services/real_portal_rfq_extraction_v33_service.py`
- `app/services/smart_harvester_v31_service.py`
- `app/services/interactive_playwright_extractor_v36_service.py`
- `app/services/playwright_live_dom_extractor_v35_service.py`
- `app/services/harvest_to_opportunity.py`
- `app/services/opportunity_persistence.py`

## Acquisition Entry Points

Active task and runtime entrypoints currently include:

- `app.tasks.run_supply_intelligence_scan`
- `app.tasks.run_harvest_only`
- `app.tasks.run_harvest_pipeline`
- `app.tasks.run_scheduled_tender_harvest_task`
- `app.tasks.run_rfq_lifecycle_golden_cycle`
- `app.tasks.rfq_lifecycle_acquisition_task`

Active API surfaces that expose or trigger acquisition behavior include:

- `app/api/opportunities_api.py`
- `app/api/rfq_lifecycle_api.py`
- `app/api/real_rfq_harvester_v32_api.py`
- `app/api/real_portal_rfq_extraction_v33_api.py`
- `app/api/smart_harvester_v31_api.py`
- `app/api/self_healing_harvester.py`
- `app/api/etenders_*`

## Runtime and Filesystem Dependencies

The current acquisition surface depends directly on:

- `runtime/live_rfqs.json`
- `runtime/source_health.json`
- `runtime/harvest_runs/`
- `runtime/multi_portal_discovery/`
- `runtime/opportunity_extraction/`
- `runtime/downloaded_tender_documents/`
- `runtime/rfq_document_acquisition/`
- `runtime/portal_fetch/`
- `runtime/playwright/`
- `runtime/playwright_profiles/`
- `runtime/etenders_session/`
- `runtime/harvest.db`

## Not Migrated In This Step

These runtime-owned API and Python modules remain in place and are not moved in this first acquisition extraction step.
