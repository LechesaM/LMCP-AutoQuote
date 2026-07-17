# Import-Time Side Effect Inventory

Audit date: 2026-07-16
Branch: recovery/rfq-quote-pack-bridge
Commit: c02c0d56
Evidence input: `/Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation/failed-router-import-lines.json`

## Scope

This inventory covers the 14 router families that failed host-side router import before the import-safety repair. The shared failure mode was module-level directory creation using a hard-coded or container-oriented `/app` project root. No Docker restart was performed. No runtime stores were modified.

## Shared Root Cause

The affected services declared runtime/log/download/profile paths at module import and immediately called `mkdir(parents=True, exist_ok=True)`. In the running container this can succeed because `/app` is writable or already exists in the process context. During recovered-source validation outside the container, `/app` resolved to a read-only or unavailable filesystem path, so router import failed before route registration.

The repair keeps the same path semantics for actual operation but moves directory creation behind explicit `ensure_*_runtime_dirs()` functions called from operational code paths such as log writes, extraction runs, downloads, browser startup, or status writes.

## Inventory

| Router family | Module | Import-time side effect before repair | Current path intent | Runtime initialization required at import? | Repair | Confidence | Behavior risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `smart_harvester_v31_router` | `app/services/smart_harvester_v31_service.py` | `LOG_DIR.mkdir(...)` | `runtime/v31_smart_harvester/logs` | No | Added `ensure_v31_runtime_dirs()`; called before V31 log/write operations. | HIGH | Low |
| `real_rfq_harvester_v32_router` | `app/services/real_rfq_harvester_v32_service.py` | `LOG_DIR.mkdir(...)` | `runtime/v32_real_rfq_harvester/logs` | No | Added `ensure_v32_runtime_dirs()`; called before V32 harvest/log operations. | HIGH | Low |
| `real_portal_rfq_extraction_v33_router` | `app/services/real_portal_rfq_extraction_v33_service.py` | `LOG_DIR.mkdir(...)` | `runtime/v33_real_portal_rfq_extraction/logs` | No | Added `ensure_v33_runtime_dirs()`; called before log writes. | HIGH | Low |
| `structured_rfq_extractor_v34_router` | `app/services/structured_rfq_extractor_v34_service.py` | `LOG_DIR.mkdir(...)` | `runtime/v34_structured_rfq_extractor/logs` | No | Added `ensure_v34_runtime_dirs()`; called before log writes. | HIGH | Low |
| `playwright_live_dom_extractor_v35_router` | `app/services/playwright_live_dom_extractor_v35_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)` | `runtime/v35_playwright_live_dom/{logs,proof}` | No | Added `ensure_v35_runtime_dirs()`; called before log writes and live DOM extraction. | HIGH | Low |
| `interactive_playwright_extractor_v36_router` | `app/services/interactive_playwright_extractor_v36_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)`, `PROFILE_DIR.mkdir(...)` | `runtime/v36_interactive_playwright/{logs,proof,profile}` | No | Added `ensure_v36_runtime_dirs()`; called before log writes and interactive extraction. | HIGH | Low |
| `deep_rfq_link_extractor_v37_router` | `app/services/deep_rfq_link_extractor_v37_service.py` | `LOG_DIR.mkdir(...)`, `DOWNLOAD_DIR.mkdir(...)` | `runtime/v37_deep_rfq_links/{logs,downloads}` | No | Added `ensure_v37_runtime_dirs()`; called before log writes and document downloads. | HIGH | Low |
| `interactive_click_deep_extraction_v38_router` | `app/services/interactive_click_deep_extraction_v38_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)`, `PROFILE_DIR.mkdir(...)` | `runtime/v38_interactive_click_deep/{logs,proof,profile}` | No | Added `ensure_v38_runtime_dirs()`; called before log writes and deep-click extraction. | HIGH | Low |
| `true_navigation_extraction_v39_router` | `app/services/true_navigation_extraction_v39_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)`, `PROFILE_DIR.mkdir(...)` | `runtime/v39_true_navigation/{logs,proof,profile}` | No | Added `ensure_v39_runtime_dirs()`; called before log writes and true-navigation extraction. | HIGH | Low |
| `tender_form_intelligence_router` | `app/services/tender_form_intelligence_engine.py` | Loop creating runtime, output, debug, and profile directories | `runtime/tender_form_intelligence/*` | No | Added `ensure_tender_form_runtime_dirs()`; called from form planning and PDF completion operations. | HIGH | Low |
| `sbd_intelligence_router` | `app/services/tender_form_intelligence_engine.py` | Same tender-form engine import-time directory loop | `runtime/tender_form_intelligence/*` | No | Same shared `ensure_tender_form_runtime_dirs()` repair. | HIGH | Low |
| `csd_persistent_session_router` | `app/services/csd_persistent_session_service.py` | Loop creating compliance, Playwright profile, refresh, download, and proof directories | `runtime/compliance`, `runtime/playwright/csd_profile`, `runtime/csd_monthly_refresh/*` | No | Added `ensure_csd_persistent_runtime_dirs()`; called from status writes, browser session startup, report copy, refresh, and clear operations. | HIGH | Low |
| `csd_monthly_refresh_router` | `app/services/csd_monthly_refresh_service.py` | Loop creating compliance, monthly refresh, download, proof, and evidence directories | `runtime/compliance`, `runtime/csd_monthly_refresh/*`, `monthly_quotes/csd_evidence` | No | Added `ensure_csd_monthly_runtime_dirs()`; called from status writes, report copy, refresh, and scheduler operations. | HIGH | Low |
| `final_automation_router` | `app/services/final_automation_layer_service.py` | Loop creating final automation log/proof directories | `runtime/final_automation/{logs,proof}` | No | Added `ensure_final_automation_runtime_dirs()`; called before automation log writes and explicit automation run. | HIGH | Low |

## Non-Target Import-Time Writes

Repository-wide text search still finds other module-level `mkdir()` calls outside the 14 affected router families. They were not changed in this controlled patch because they were not part of the established failed-router set and touching them would broaden behavioral risk.

Examples include quote draft/proof/security/pipeline/document-extraction services. They should be handled in a separate import-safety hardening pass if needed.

## Safety Result

Focused tests imported all 14 router modules under temporary path overrides and verified that import alone did not create files or directories under the temporary runtime root. Explicit ensure functions were then called and verified to create directories idempotently.
