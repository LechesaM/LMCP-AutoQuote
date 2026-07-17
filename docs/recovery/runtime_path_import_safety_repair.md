# Runtime Path Import-Safety Repair

Audit date: 2026-07-16
Branch: recovery/rfq-quote-pack-bridge
Commit: c02c0d56

## Purpose

Repair the shared import-time filesystem path pattern that caused 14 acquisition, portal, CSD, automation, SBD, and tender-form router families to fail host import. The patch does not change endpoint paths, methods, response shapes, operation IDs, route registration lists, runtime data, or Docker state.

## Root Cause

The failed routers imported service modules that immediately created directories under a project root defaulting to `/app`. That import-time write pattern is unsafe outside the running container and failed with `[Errno 30] Read-only file system: '/app'` during recovered-source validation.

## Shared Path Utility

Created `app/core/runtime_paths.py`.

The utility:

- resolves `PROJECT_ROOT` from `LMCP_PROJECT_ROOT` when explicitly set;
- uses `/app` only when `/app/app` exists, preserving container semantics;
- otherwise resolves the repository root from the source file location;
- exposes `RUNTIME_DIR`, `LOG_DIR`, and `MONTHLY_QUOTES_DIR`;
- exposes `ensure_directories()` and `ensure_runtime_directories()`;
- performs no directory creation or file write at import time.

## Modules Changed

| Module | Import-time write removed | Explicit creation now occurs in |
| --- | --- | --- |
| `app/services/smart_harvester_v31_service.py` | `LOG_DIR.mkdir(...)` | `_write_log()`, `run_smart_national_tender_radar()` |
| `app/services/real_rfq_harvester_v32_service.py` | `LOG_DIR.mkdir(...)` | `_write_log()`, `run_v32_real_rfq_harvest()` |
| `app/services/real_portal_rfq_extraction_v33_service.py` | `LOG_DIR.mkdir(...)` | `_write_log()` |
| `app/services/structured_rfq_extractor_v34_service.py` | `LOG_DIR.mkdir(...)` | `_write_log()` |
| `app/services/playwright_live_dom_extractor_v35_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)` | `_write_log()`, `extract_live_dom_portal()` |
| `app/services/interactive_playwright_extractor_v36_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)`, `PROFILE_DIR.mkdir(...)` | `_write_log()`, `extract_interactive_portal()` |
| `app/services/deep_rfq_link_extractor_v37_service.py` | `LOG_DIR.mkdir(...)`, `DOWNLOAD_DIR.mkdir(...)` | `_write_log()`, `_download_doc()` |
| `app/services/interactive_click_deep_extraction_v38_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)`, `PROFILE_DIR.mkdir(...)` | `_write_log()`, `deep_click_extract_candidate()` |
| `app/services/true_navigation_extraction_v39_service.py` | `LOG_DIR.mkdir(...)`, `PROOF_DIR.mkdir(...)`, `PROFILE_DIR.mkdir(...)` | `_write_log()`, `true_navigation_extract_candidate()` |
| `app/services/tender_form_intelligence_engine.py` | import-time creation of tender-form runtime, completed, debug, and profile directories | `build_field_plan()`, `complete_pdf_with_stroke_flow()` |
| `app/services/csd_persistent_session_service.py` | import-time creation of compliance, Playwright, CSD profile, downloads, and proof directories | `_write_status()`, `_copy_to_standard_report()`, manual session, refresh, and clear operations |
| `app/services/csd_monthly_refresh_service.py` | import-time creation of compliance, refresh, downloads, proof, and monthly evidence directories | `_write_status()`, report copy, monthly refresh, and scheduler operations |
| `app/services/final_automation_layer_service.py` | import-time creation of final automation log/proof directories | `_write_log()`, `run_final_automation_once()` |

`app/api/rfq_lifecycle_api.py` also retains the earlier Python 3.9 annotation compatibility fix for `payload: Optional[Dict[str, Any]]`.

## Tests Added

- `tests/test_runtime_paths.py`
- `tests/test_acquisition_router_import_safety.py`

The tests verify:

- host project-root resolution;
- environment override behavior;
- idempotent explicit directory creation;
- import of all 14 router modules;
- no temporary runtime files or directories created merely by import;
- representative route path/method metadata is still exposed by each router.

## Validation Results

Commands run:

```bash
PYTHONPYCACHEPREFIX=/tmp/lmcp_pycache \
  .venv/bin/python -m compileall app scripts tests
```

Result: passed.

```bash
PYTHONPYCACHEPREFIX=/tmp/lmcp_pycache \
  .venv/bin/python -m pytest -q \
    tests/test_router_imports_python39.py \
    tests/test_acquisition_router_import_safety.py \
    tests/test_runtime_paths.py
```

Result: `5 passed, 6 warnings`.

```bash
.venv/bin/python scripts/audit_router_parity.py \
  --expected-loaded 67 \
  --output /Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation/router-parity-after-import-safety.json \
  --verbose
```

Result: 110 source routers loaded, 0 failed router imports, 2 duplicate route pairs.

```bash
.venv/bin/python scripts/compare_runtime_source_routes.py \
  --running-openapi /Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation/after-import-safety/running-openapi.json \
  --source-openapi /Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation/after-import-safety/source-openapi.json \
  --output-dir /Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation/after-import-safety \
  --matrix-output /Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation/after-import-safety/runtime_route_difference_matrix_after_import_safety.json \
  --verbose
```

Result: 20 running-only, 130 source-only, 3 different operation IDs.

## Runtime Store Safety

Before and after hashes and metadata matched:

| File | SHA-256 | Size | mtime |
| --- | --- | ---: | ---: |
| `runtime/live_rfqs.json` | `7d04a98c923a841cc129a7ffe87a32343a14aae2adb66f48c0e4ca55e1bb3cbc` | 566658 | 1783537040 |
| `runtime/rfq_lifecycle/rfqs.json` | `2b4b34146f1ac834ee2339ab01e97576a3c54a203961249731101eeb8dc2ac51` | 4889399 | 1783537048 |

Focused import-safety tests verified that imports did not create directories under a temporary runtime root.

## Route Parity Result

| Metric | Before repair | After repair |
| --- | ---: | ---: |
| Running paths | 351 | 351 |
| Running method/path pairs | 359 | 359 |
| Source paths | 406 | 462 |
| Source method/path pairs | 413 | 469 |
| Source loaded routers | 96 | 110 |
| Source failed routers | 14 | 0 |
| Duplicate route pairs | 0 | 2 |
| Running-only method/path pairs | 36 | 20 |
| Source-only method/path pairs | 90 | 130 |

The increase in source-only routes is expected: the repaired routers now register their routes instead of failing import.

## Remaining Restart Blockers

Restart remains `NOT_SAFE_TO_RESTART` because:

1. 20 running routes are absent from current source.
2. 130 source routes would become newly exposed.
3. Two duplicate `/sbd-intelligence` route pairs are now visible.
4. Three shared `/autonomous` operation IDs differ.
5. Source-only acquisition, portal, autonomous, upload, submission, pricing, and RFQ-processing routes require explicit operator review before activation.

## Rollback Procedure

Do not execute without operator approval.

```bash
git checkout -- app/services/smart_harvester_v31_service.py \
  app/services/real_rfq_harvester_v32_service.py \
  app/services/real_portal_rfq_extraction_v33_service.py \
  app/services/structured_rfq_extractor_v34_service.py \
  app/services/playwright_live_dom_extractor_v35_service.py \
  app/services/interactive_playwright_extractor_v36_service.py \
  app/services/deep_rfq_link_extractor_v37_service.py \
  app/services/interactive_click_deep_extraction_v38_service.py \
  app/services/true_navigation_extraction_v39_service.py \
  app/services/tender_form_intelligence_engine.py \
  app/services/csd_persistent_session_service.py \
  app/services/csd_monthly_refresh_service.py \
  app/services/final_automation_layer_service.py \
  scripts/compare_runtime_source_routes.py
```

Then manually remove untracked additions only after review:

- `app/core/runtime_paths.py`
- `tests/test_acquisition_router_import_safety.py`
- `tests/test_runtime_paths.py`
- this recovery documentation

Do not use broad cleanup commands.
