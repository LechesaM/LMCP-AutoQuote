# LMCP Archive Plan

Date: 2026-06-22
Scope: documentation only

## Purpose
This plan defines a safe archive strategy for duplicate, obsolete, experimental, or superseded LMCP assets without moving any files yet.

It is based on:

- [docs/REPO_AUDIT.md](/Users/cash/Documents/docs/REPO_AUDIT.md)
- [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md)
- [docs/PLATFORM_ARCHITECTURE.md](/Users/cash/Documents/docs/PLATFORM_ARCHITECTURE.md)
- [docs/MIGRATION_STRATEGY.md](/Users/cash/Documents/docs/MIGRATION_STRATEGY.md)
- [docs/DATABASE_SOURCE_OF_TRUTH.md](/Users/cash/Documents/docs/DATABASE_SOURCE_OF_TRUTH.md)
- [docs/STATE_TRANSITION_MODEL.md](/Users/cash/Documents/docs/STATE_TRANSITION_MODEL.md)
- [docs/SERVICE_BOUNDARIES.md](/Users/cash/Documents/docs/SERVICE_BOUNDARIES.md)
- [docs/SERVICE_DEPENDENCY_GRAPH.md](/Users/cash/Documents/docs/SERVICE_DEPENDENCY_GRAPH.md)

## Rules For This Plan

- no files move yet
- no files are deleted
- no imports change
- no runtime behavior changes
- archive candidates remain in place until dependency validation is complete

## 1. ACTIVE Assets That Must Not Be Moved

These assets are on the official or currently stabilized runtime path and must not be archived or relocated yet.

### Official backend/runtime spine

- [app](/Users/cash/Documents/app)
- [docker-compose.production.yml](/Users/cash/Documents/docker-compose.production.yml)
- [docker](/Users/cash/Documents/docker)
- [deploy](/Users/cash/Documents/deploy)
- [nginx](/Users/cash/Documents/nginx)
- [scripts](/Users/cash/Documents/scripts)
- [tests](/Users/cash/Documents/tests)

### Active runtime and storage roots

- [runtime](/Users/cash/Documents/runtime)
- [monthly_quotes](/Users/cash/Documents/monthly_quotes)
- [generated](/Users/cash/Documents/generated)
- [docs](/Users/cash/Documents/docs)

### Active service and model ownership

- [app/services](/Users/cash/Documents/app/services)
- [app/models](/Users/cash/Documents/app/models)
- [app/tasks](/Users/cash/Documents/app/tasks)
- [app/api](/Users/cash/Documents/app/api)
- [app/db](/Users/cash/Documents/app/db)

### Active frontend assets

Frontend authority is currently inconsistent across docs:

- [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md) names [frontend](/Users/cash/Documents/frontend) as official.
- later frontend stabilization work used [etenders_acquisition/lmcp-dashboard](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard) as the official frontend target.

Because of that conflict, neither frontend tree should be archived until frontend ownership is explicitly reconciled.

## 2. ARCHIVE_CANDIDATE Assets

These are the safest candidates for future archival once dependency checks pass.

### Top-level non-runtime material

- [Word Recovery](/Users/cash/Documents/Word Recovery)
- [backups](/Users/cash/Documents/backups)
- [.pycache](/Users/cash/Documents/.pycache)
- [.pytest_cache](/Users/cash/Documents/.pytest_cache)

### Backup and broken source variants

All `*.bak*`, `*.backup*`, `*.broken*`, `*.ignored`, and `*.FINAL_LOCK_*` variants that are not on the active import path are archive candidates.

Examples:

- [app/main.py.backup_v50_7](/Users/cash/Documents/app/main.py.backup_v50_7)
- [app/main.py.bak_mission_control_compat](/Users/cash/Documents/app/main.py.bak_mission_control_compat)
- [services/tender_pipeline.py.bak](/Users/cash/Documents/services/tender_pipeline.py.bak)
- [services/tender_pipeline.py.backup](/Users/cash/Documents/services/tender_pipeline.py.backup)
- [services/tender_pipeline.py.broken_indent_20260503_102133](/Users/cash/Documents/services/tender_pipeline.py.broken_indent_20260503_102133)
- [services/tender_pipeline.py.FINAL_LOCK_OK](/Users/cash/Documents/services/tender_pipeline.py.FINAL_LOCK_OK)
- [services/quote_pack_service_broken_20260326.py](/Users/cash/Documents/services/quote_pack_service_broken_20260326.py)

### Root-level duplicate trees

- [models](/Users/cash/Documents/models)
- [services](/Users/cash/Documents/services)

These were already classified as duplicates in the audit and should eventually archive after import-path validation confirms runtime never resolves to them instead of `app/models` and `app/services`.

### Experimental alternate stack

- [etenders_acquisition](/Users/cash/Documents/etenders_acquisition)

This is a large archive candidate as a unit, but it is high-risk and must move last because it currently includes:

- a separate API
- a separate DB lineage
- a separate frontend
- many alternate acquisition, extraction, pricing, and submission engines

### Partial frontend subtree

- [frontend/command-centre](/Users/cash/Documents/frontend/command-centre)

The audit found no `package.json` or `Dockerfile` here even though compose references `frontend/command-centre/Dockerfile`. It is a likely archive candidate, but only after compose/build references are cleaned up or replaced.

## 3. UNKNOWN Assets Requiring Manual Review

These assets should not be archived until ownership is manually confirmed.

### Data roots

- [data](/Users/cash/Documents/data)
- [app/data](/Users/cash/Documents/app/data)

Reason:

- audit classified `data/` as `UNKNOWN`
- some `app/data` material looks like seed/config/reference data, not pure generated output

### Frontend authority

- [frontend](/Users/cash/Documents/frontend)
- [etenders_acquisition/lmcp-dashboard](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard)

Reason:

- official frontend ownership is inconsistent between docs and later stabilization work

### Manual-production runtime subtrees

- [runtime/manual_production](/Users/cash/Documents/runtime/manual_production)
- [runtime/tender_submission_pipeline](/Users/cash/Documents/runtime/tender_submission_pipeline)

Reason:

- they contain both generated artifacts and active operational evidence/state
- some subtrees are likely archival evidence, others are still supporting current workflows

### Local SQLite stores

- [runtime/manual_production/lmcp_operations.db](/Users/cash/Documents/runtime/manual_production/lmcp_operations.db)
- [runtime/operator_auth/operator_auth.sqlite3](/Users/cash/Documents/runtime/operator_auth/operator_auth.sqlite3)
- [runtime/harvest.db](/Users/cash/Documents/runtime/harvest.db)
- [etenders_acquisition/etenders.db](/Users/cash/Documents/etenders_acquisition/etenders.db)

Reason:

- these are persistence-risk items, not simple artifacts
- they may still be consulted by active services

## 4. Duplicate Frontend/Dashboard Assets

### Current duplicates or overlaps

- [frontend](/Users/cash/Documents/frontend)
- [frontend/command-centre](/Users/cash/Documents/frontend/command-centre)
- [etenders_acquisition/lmcp-dashboard](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard)

### Archive guidance

- do not archive any frontend asset until one official frontend is explicitly ratified
- once ratified, move non-official frontend trees under `lmcp-core/archive/frontend/`

### Proposed archive destinations

- `lmcp-core/archive/frontend/command-centre/`
- `lmcp-core/archive/frontend/etenders-dashboard/`
- if `frontend/` loses authority instead, then `lmcp-core/archive/frontend/vite-frontend/`

## 5. Duplicate Backend/API Assets

### Current duplicates or alternates

- [app/main.py](/Users/cash/Documents/app/main.py) is active
- [app/recovery_main.py](/Users/cash/Documents/app/recovery_main.py) is alternate/experimental
- [etenders_acquisition/api/main.py](/Users/cash/Documents/etenders_acquisition/api/main.py) is separate experimental FastAPI stack
- multiple `app/main.py.bak*` and `backup*` files
- router duplication exists between stable APIs and many versioned legacy APIs under [app/api](/Users/cash/Documents/app/api)

### Archive guidance

- archive backup entrypoints first
- archive alternate experimental API trees only after verifying nothing in production launcher, tests, or scripts calls them

### Proposed archive destinations

- `lmcp-core/archive/backend/entrypoint-backups/`
- `lmcp-core/archive/backend/recovery-runtime/`
- `lmcp-core/archive/backend/experimental-etenders-api/`
- `lmcp-core/archive/backend/legacy-versioned-apis/` for later selective versioned API retirement, not immediate bulk movement

## 6. Duplicate Worker/Orchestration Assets

### Current duplicates or overlaps

- [app/celery_app.py](/Users/cash/Documents/app/celery_app.py) and [app/tasks.py](/Users/cash/Documents/app/tasks.py) are active
- [services](/Users/cash/Documents/services) mirrors [app/services](/Users/cash/Documents/app/services)
- [etenders_acquisition/orchestrator.py](/Users/cash/Documents/etenders_acquisition/orchestrator.py) and worker scripts in `etenders_acquisition/` duplicate acquisition/orchestration ideas
- runtime contains many generation-specific worker outputs under versioned folders such as `runtime/v31_smart_harvester`, `runtime/v35_playwright_live_dom`, `runtime/v36_interactive_playwright`, `runtime/v37_deep_rfq_link_extractor`

### Archive guidance

- root `services/` duplicate tree is a major archive candidate
- experimental orchestrators under `etenders_acquisition/` should archive only after no scripts or tests depend on them

### Proposed archive destinations

- `lmcp-core/archive/workers/root-services-duplicate-tree/`
- `lmcp-core/archive/workers/experimental-etenders-workers/`
- `lmcp-core/archive/workers/versioned-runtime-worker-experiments/`

## 7. Duplicate Extraction/Pricing/Submission Engines

These are the highest-value archive candidates after runtime dependency mapping.

### Extraction duplicates

- document and BOQ extraction families in [app/services](/Users/cash/Documents/app/services)
- alternate BOQ/document extractors in [etenders_acquisition](/Users/cash/Documents/etenders_acquisition)
- versioned extraction APIs and services under `v31` through `v50_9_10`

### Pricing duplicates

- [app/services/pricing_engine.py](/Users/cash/Documents/app/services/pricing_engine.py)
- [app/services/pricing_engine_v2_realistic.py](/Users/cash/Documents/app/services/pricing_engine_v2_realistic.py)
- [app/services/real_profit_pricing_service.py](/Users/cash/Documents/app/services/real_profit_pricing_service.py)
- alternate pricing engines under [etenders_acquisition](/Users/cash/Documents/etenders_acquisition)

### Submission duplicates

- [app/services/submission_pipeline.py](/Users/cash/Documents/app/services/submission_pipeline.py)
- [app/services/tender_submission_pipeline.py](/Users/cash/Documents/app/services/tender_submission_pipeline.py)
- [app/services/portal_submission_service.py](/Users/cash/Documents/app/services/portal_submission_service.py)
- [app/services/portal_submission_v47_service.py](/Users/cash/Documents/app/services/portal_submission_v47_service.py)
- alternate submission compilers and pack generators under [etenders_acquisition](/Users/cash/Documents/etenders_acquisition)

### Proposed archive destinations

- `lmcp-core/archive/services/acquisition/legacy-extractors/`
- `lmcp-core/archive/services/commercial/legacy-pricing-engines/`
- `lmcp-core/archive/services/submission/legacy-submission-engines/`
- `lmcp-core/archive/services/experimental-etenders-stack/`

## 8. Runtime/Generated Folders That Should Remain File-Based

These should remain file-based even after archive cleanup because the source-of-truth plan explicitly treats them as artifacts, caches, or evidence rather than canonical database rows.

### Runtime artifact and evidence folders

- [runtime/downloaded_tender_documents](/Users/cash/Documents/runtime/downloaded_tender_documents)
- [runtime/proof_center](/Users/cash/Documents/runtime/proof_center)
- [runtime/locks/immutable_submission](/Users/cash/Documents/runtime/locks/immutable_submission)
- [runtime/portal_submission](/Users/cash/Documents/runtime/portal_submission)
- [runtime/final_submission_v47_5](/Users/cash/Documents/runtime/final_submission_v47_5)
- [runtime/submission_pack](/Users/cash/Documents/runtime/submission_pack)
- [runtime/support_document_resolution/documents](/Users/cash/Documents/runtime/support_document_resolution/documents)
- [monthly_quotes](/Users/cash/Documents/monthly_quotes)
- [generated/quotation_packs](/Users/cash/Documents/generated/quotation_packs)

### Runtime derived cache or report folders

- `runtime/pricing_summaries`
- `runtime/document_intelligence`
- `runtime/boq_intelligence`
- `runtime/buyer_intelligence`
- `runtime/mission_control`
- `runtime/harvest_runs`

These may later be pruned or regenerated, but they should remain file-based rather than moved into the database.

## 9. Runtime/Generated Folders That Should Be Excluded From Git

These are generated, mutable, local, or evidence-heavy and should not be tracked as source.

### Already broadly covered by `.gitignore`

- [runtime](/Users/cash/Documents/runtime)
- [generated](/Users/cash/Documents/generated)
- `__pycache__/`
- `.pytest_cache/`

### Specific generated/runtime families that should remain excluded

- `runtime/manual_production/**`
- `runtime/tmp_*`
- `runtime/e2e_fixtures/**`
- `runtime/playwright_profiles/**`
- `runtime/chrome-profile/**`
- `runtime/v31_*`
- `runtime/v33_*`
- `runtime/v35_*`
- `runtime/v36_*`
- `runtime/v37_*`
- `runtime/tender_submission_pipeline/**`
- `monthly_quotes/**`
- `generated/quotation_packs/**`

## 10. Dependency Risks Before Archiving

### Frontend ownership conflict

- `docs/OFFICIAL_RUNTIME.md` says `frontend/` is official
- later stabilized frontend work treated `etenders_acquisition/lmcp-dashboard` as official

No frontend archival should proceed before that is resolved.

### Duplicate import-path risk

- root [services](/Users/cash/Documents/services) and [models](/Users/cash/Documents/models) are duplicates, but scripts or ad hoc tooling may still import them directly

### Compose/build reference risk

- `frontend/command-centre/` is referenced by compose material but lacks a complete app definition in the audit

### Persistence risk

- JSON and SQLite stores still hold active runtime state
- archive actions must not sweep up files that services still read at runtime

### Experimental stack coupling risk

- `etenders_acquisition/` contains alternate implementations for acquisition, extraction, pricing, workers, and frontend
- some knowledge may not yet be promoted into `app/`

### Evidence retention risk

- proof and submission artifacts may have audit or operational value even if they are old

## 11. Exact Proposed Archive Destination Paths Under `lmcp-core/archive/`

### Repository-level duplicates and backups

- `lmcp-core/archive/repo-root/word-recovery/`
- `lmcp-core/archive/repo-root/backups/`
- `lmcp-core/archive/repo-root/pycache/`
- `lmcp-core/archive/repo-root/pytest-cache/`
- `lmcp-core/archive/repo-root/root-models-duplicate-tree/`
- `lmcp-core/archive/repo-root/root-services-duplicate-tree/`

### Backend/API

- `lmcp-core/archive/backend/entrypoint-backups/`
- `lmcp-core/archive/backend/recovery-runtime/`
- `lmcp-core/archive/backend/experimental-etenders-api/`
- `lmcp-core/archive/backend/legacy-versioned-apis/`

### Frontend

- `lmcp-core/archive/frontend/command-centre/`
- `lmcp-core/archive/frontend/etenders-dashboard/`
- `lmcp-core/archive/frontend/vite-frontend/`

Only one of the last two should eventually be used, depending on the final frontend decision.

### Experimental stack

- `lmcp-core/archive/experimental/etenders-acquisition-stack/`
- `lmcp-core/archive/experimental/etenders-runtime/`
- `lmcp-core/archive/experimental/etenders-tests/`

### Service-level duplicate engines

- `lmcp-core/archive/services/acquisition/legacy-extractors/`
- `lmcp-core/archive/services/acquisition/versioned-navigation-engines/`
- `lmcp-core/archive/services/intelligence/legacy-document-intelligence/`
- `lmcp-core/archive/services/commercial/legacy-pricing-engines/`
- `lmcp-core/archive/services/commercial/legacy-award-engines/`
- `lmcp-core/archive/services/submission/legacy-submission-engines/`
- `lmcp-core/archive/services/governance/legacy-lock-and-guard-variants/`

### Runtime snapshots and evidence

- `lmcp-core/archive/runtime/manual-production-snapshots/`
- `lmcp-core/archive/runtime/e2e-fixtures/`
- `lmcp-core/archive/runtime/versioned-worker-output/`
- `lmcp-core/archive/runtime/legacy-debug-outputs/`

## 12. Safe Archive Sequence

### Phase 1: No-risk generated and backup material

1. archive `.pycache`, `.pytest_cache`, and obvious backup/broken variants
2. archive Word Recovery and top-level non-runtime recovery material
3. archive repo-level backup directories not referenced by runtime

### Phase 2: Entry-point and duplicate-tree validation

1. confirm only `app.main:app` and `app.celery_app.celery_app` are used
2. confirm no tests/scripts import root `services/` or `models/`
3. archive root duplicate trees only after that validation

### Phase 3: Frontend ownership resolution

1. ratify one official frontend
2. validate build/start commands for the chosen frontend
3. archive the non-official frontend trees

### Phase 4: Experimental stack isolation

1. catalog `etenders_acquisition/` modules already superseded by `app/`
2. preserve any unique reference docs, configs, or learnings
3. archive the experimental stack as a whole only after reference extraction

### Phase 5: Service-family cleanup

1. identify versioned engine families with no active router/task/runtime dependency
2. archive superseded acquisition/intelligence/commercial/submission variants
3. leave active runtime versions in place until explicit cutover

### Phase 6: Runtime archival snapshots

1. snapshot old manual-production and E2E runtime outputs
2. archive only stale, non-active evidence directories
3. never archive the current live `runtime/` root wholesale

## 13. Rollback Procedure

If a future archive move causes any regression:

1. stop the move immediately and do not continue to later phases
2. restore the archived path back to its original repository location from `lmcp-core/archive/`
3. rerun the official runtime checks:
   - backend import/start for `app.main:app`
   - worker import/start for `app.celery_app.celery_app`
   - official frontend startup
   - `/health`
   - `/status`
4. rerun targeted tests for the affected area
5. diff the restored files against the archived copy to confirm byte-for-byte restoration
6. mark the asset as `UNKNOWN` rather than `ARCHIVE_CANDIDATE` until dependency mapping is improved

## Archive Decision Summary

- archive obvious backups and generated cache material first
- delay duplicate-tree archival until import usage is proven
- delay frontend archival until official frontend ownership is reconciled
- delay `etenders_acquisition/` archival until its remaining unique value is explicitly extracted
- keep runtime artifact and evidence folders file-based and git-excluded
