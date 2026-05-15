# Backend Consolidation Audit

Audit date: 2026-05-14

Scope:
- Inspected `app/main.py`.
- Inspected router modules under `app/api/*.py`.
- Reviewed root-level routers referenced by `app/main.py` where they affect the active API surface.
- No backend execution behavior was changed.
- No routers were removed.
- No portal upload, email send, CAPTCHA bypass, or final submission path was enabled.

## Executive Summary

`app/main.py` currently runs a broad compatibility API surface. It directly registers a small set of core routers, then dynamically registers a long `OPTIONAL_ROUTERS` list that includes stable routers, domain-specific routers, and old versioned routers from v31 through v50.9. This preserves backward compatibility but makes the backend difficult to reason about because many route families overlap in responsibility.

The consolidation target should be a stable `/api/*` namespace with read-only/status wrappers first, followed later by controlled write wrappers. Existing routes should remain available until the frontend and tests are migrated.

Most safety-critical execution risks are concentrated in routers that touch email sending, portal/browser automation, upload, final submit, and autonomous loop execution. Several of these routers have default safety flags, but the endpoints themselves remain execution-capable and should be isolated from stable read-only frontend workspaces.

## Current `app/main.py` Shape

Active direct router registrations:
- `tender_pipeline_router`
- `quote_engine_router`
- `submission_pipeline_router`
- `email_router`
- `test_pricing_router`
- `tasks_router`
- `supplier_quotes_router`
- `email_ingestion_router`
- `csd_router`
- `opportunities_router`
- `system_control_router`
- `submission_history_recent_router`
- `submission_history_pipeline_sync_router`
- `proof_of_submission_router`
- `submission_history_proof_enrichment_router`
- `mission_control_compat_api.router` at the end of the file

Dynamic optional registration:
- `OPTIONAL_ROUTERS` imports a large compatibility set through `_safe_include_optional_router`.
- Import failures are captured in `failed_routers` rather than stopping startup.
- Duplicate detection uses `router_name:prefix:route_count`, so routers with the same prefix but different names or route counts can still load together.

Static mounts:
- `/downloads`
- `/runtime`
- `/proofs`
- `/portal-runtime`
- `/final-submission-runtime`
- `/proof-center-runtime`
- `/handwriting-runtime`
- `/tender-form-runtime`
- `/clickable-navigation-v40-runtime`

Base health/root payload advertises multiple legacy endpoints, including execution-sensitive endpoints such as `/portal-submission/auto-submit`.

## Domain Grouping

### rfq_engine

Current routers:
- `app.api.rfq_lifecycle_api` at `/rfq-lifecycle`
- `app.api.tender_pipeline_api` at `/tender-pipeline`
- `app.api.opportunities_api` at `/opportunities` currently present under `app/api`
- root `app.opportunities_api` at `/opportunities`, directly registered by `app/main.py`
- `app.api.supply_command_api` at `/supply-command`
- `app.api.smart_harvester_v31_api` at `/v31-smart-harvester`
- `app.api.real_rfq_harvester_v32_api` at `/v32-real-rfq-harvester`
- `app.api.real_portal_rfq_extraction_v33_api` at `/v33-real-portal-rfq`
- `app.api.structured_rfq_extractor_v34_api` at `/v34-structured-rfq`
- `app.api.playwright_live_dom_extractor_v35_api` at `/v35-playwright-rfq`
- `app.api.interactive_playwright_extractor_v36_api` at `/v36-interactive-rfq`
- `app.api.deep_rfq_link_extractor_v37_api` at `/v37-deep-rfq`
- `app.api.interactive_click_deep_extraction_v38_api` at `/v38-click-deep-rfq`
- `app.api.true_navigation_extraction_v39_api` at `/v39-true-navigation`
- `app.api.clickable_navigation_v40_api` at `/v40-clickable-navigation`
- `app.api.real_rfq_detail_navigation_v49_api` at `/v49-real-rfq-detail-navigation`
- `app.api.detail_page_follow_v49_1_api` at `/v49-1-detail-page-follow`
- v50 eTenders RFQ/detail/document discovery routers from `/v50-7-*` through `/v50-9-10-*`

Stable destination:
- `/api/rfq/*`

Notes:
- This is the largest overlap area. RFQ discovery, detail navigation, document acquisition, eTenders JSON parsing, and RFQ lifecycle advancement are spread across many legacy versioned routers.

### quote_engine

Current routers:
- `app.api.quote_engine_api` at `/quote-engine`
- `app.api.quote_pack_api` at `/quote-pack`
- `app.api.quote_pack_v44_api` at `/v44-quote-pack`
- `app.api.auto_pricing_v43_api` at `/v43-auto-pricing`
- `app.api.pricing_table_extraction_v42_api` at `/v42-pricing-table-extraction`
- `app.api.real_profit_pricing_api` at `/real-profit-pricing`
- root `app.quote_pack_api` at `/quote-packs`
- root `app.quote_api` with `/quote/*`
- root `app.quotes_api` at `/quotes`
- `app.api.supplier_quotes_api` at `/supplier-quotes`

Stable destination:
- `/api/quotes/*`

Notes:
- Quote generation, quote pack generation, pricing extraction, profit pricing, supplier quote ingestion, and older quote pack workflows overlap.
- `app.api.quote_pack_api /run-autoquote` is risky because it calls a pipeline service that can attempt email sending when configured.

### submission_engine

Current routers:
- `app.api.submission_pipeline_api` at `/submission-pipeline`
- `app.api.submission_pack_v45_api` at `/v45-submission-pack`
- `app.api.auto_submission_v46_api` at `/v46-auto-submission`
- `app.api.submission_retry_api` at `/submission-retry`
- `app.api.submission_scheduler_api` at `/submission-scheduler`
- `app.api.submission_analytics_api` at `/submission-analytics`
- `app.api.submission_history` at `/submission-history`
- `app.api.submission_history_recent_api` at `/submission-history`
- `app.api.submission_history_pipeline_sync_api` at `/submission-history`
- `app.api.submission_history_proof_enrichment_api` at `/submission-history`
- `app.api.tender_submission_pipeline_api` at `/tender-submission`
- root `app.submission_api` with `/submission-pack/{quote_id}`
- root `app.email_api` at `/email-submissions`

Stable destination:
- `/api/submissions/*`

Notes:
- `/submission-history` is intentionally split across multiple routers, but this creates prefix-level duplication risk.
- Email submission endpoints belong here operationally, but should be isolated behind explicit safe wrappers and policy checks.

### proof_engine

Current routers:
- `app.api.proof_of_submission_api` at `/submission-proof`
- `app.api.proof_center_api` at `/proof-center`
- `app.api.deep_verification_v47_7_api` at `/v47-deep-verification`
- `app.api.sbd_completion_api` at `/sbd-completion`
- `app.api.sbd_intelligence_api` at `/sbd-intelligence`
- `app.api.tender_form_intelligence_api` also at `/sbd-intelligence`
- `app.api.sbd_version_detector_api` at `/sbd-version`
- handwriting/form routers:
  - `/handwriting-simulation`
  - `/handwriting-form`
  - `/handwriting-glyph`
  - `/handwriting-field-detector`
  - `/handwriting-full-auto`
  - `/clean-ink-v3`
  - `/forms`

Stable destination:
- `/api/proofs/*`

Notes:
- Proof generation and proof-center scan/download are active and useful.
- SBD/form completion overlaps with compliance and quote/submission readiness.
- Duplicate `/sbd-intelligence` prefixes should be resolved under a stable proof/compliance boundary later.

### portal_engine

Current routers:
- `app.api.portal_submission_api` at `/portal-submission`
- `app.api.portal_submission_v47_api` at `/v47-portal-submission`
- `app.api.portal_form_autofill_v47_1_api` at `/v47-portal-autofill`
- `app.api.assisted_browser_v47_2_api` at `/v47-assisted-browser`
- `app.api.live_browser_attach_v47_3_api` at `/v47-live-browser`
- `app.api.v47_live_browser_api` exists with the same `/v47-live-browser` prefix but is not listed in `app/main.py`
- `app.api.smart_upload_v47_4_api` at `/v47-smart-upload`
- `app.api.final_submission_v47_5_api` at `/v47-final-submit`
- `app.api.etenders_session_api` at `/etenders-session`
- v50 eTenders browser/download/interceptor routers:
  - `/v50-9-document-download`
  - `/v50-9-1-tenderdetails-json`
  - `/v50-9-2-support-document-download`
  - `/v50-9-3-browser-download-interceptor`
  - `/v50-9-4-dom-modal-autoclick`
  - `/v50-9-5-dom-trigger-forced-click`
  - `/v50-9-6-hidden-api-discovery`
  - `/v50-9-7-document-mapping-resolver`
  - `/v50-9-8-download-replay-reconstruction`
  - `/v50-9-9-runtime-download-interceptor`
  - `/v50-9-10-tender-download-correlation`

Stable destination:
- `/api/portal/*`

Notes:
- Portal monitoring, classification, session readiness, document discovery, browser attachment, upload, and final submit are mixed across this domain.
- Stable `/api/portal/*` should start read-only: status, classification, readiness, worker/session health, and dry-run results only.

### compliance_engine

Current routers:
- root `app.compliance_api` at `/compliance`
- root `app.sbd_api` at `/sbd`
- `app.api.production_lock_api` at `/production-lock`
- `app.api.go_live_guard_api` at `/go-live-guards`
- `app.api.pipeline_enforcement_api` at `/pipeline-enforcement`
- `app.api.security_api` at `/security`
- `app.api.csd_api` at `/csd`
- `app.api.csd_monthly_refresh_api` at `/csd-monthly-refresh`
- `app.api.csd_persistent_session_api` at `/csd-persistent-session`

Stable destination:
- `/api/compliance/*`

Notes:
- Production locks and go-live guards are safety-critical and should stay active.
- Compliance document upload endpoints are mutating but not submission-execution endpoints.
- CSD session endpoints can involve browser/session state and should be labeled separately under stable compliance/session wrappers.

### orchestration_engine

Current routers:
- root `app.autonomous_api` at `/autonomous`
- `app.api.autonomous_api` exists at `/autonomous` but is not the router listed in `app/main.py`
- `app.api.full_autonomous_cycle_api` at `/full-autonomous-cycle`
- `app.api.full_autonomous_v48_api` at `/v48-autonomous`
- `app.api.final_automation_layer_api` at `/final-automation`
- `app.api.safe_autonomous_scheduler_api` at `/safe-autonomous-scheduler`
- `app.api.operator_actions_api` at `/operator-actions`
- `app.api.decision_intelligence_api` at `/decision-intelligence`
- `app.api.backend_intelligence_api` at `/backend-intelligence`
- `app.api.supervisor` at `/supervisor`
- `app.api.self_healing_harvester` at `/self-healing-harvester`

Stable destination:
- `/api/orchestration/*`

Notes:
- This domain currently mixes read-only status, policy changes, autonomous run commands, scheduler loops, and final automation.
- Stable orchestration should first expose status, queue, health, decisions, and dry-run simulation only.

### system_health

Current routers:
- `app/main.py` root `/` and `/health`
- `app.api.system` at `/system`
- `app.api.system_control` at `/system/control`
- `app.api.system_stability_api` at `/system-stability`
- `app.api.stability` at `/system` exists but is not listed in `app/main.py`
- root `app.system_guard_api` at `/system-guard`
- root `app.tasks_api` at `/tasks`
- `app.api.ws_live` with `/ws/status` and websocket paths
- `app.api.mission_control_compat_api` with radar/portal-health compatibility paths

Stable destination:
- `/api/system/*`

Notes:
- System health is split between `/health`, `/system/*`, `/system/control/*`, `/system-stability/*`, websocket status, and Mission Control compatibility routes.
- Stable `/api/system/*` should become the canonical source for health, metrics, telemetry, safety policy, router inventory, and websocket status.

### frontend_support

Current routers:
- `app.api.dashboard` at `/dashboard`
- root `app.dashboard_api` at `/dashboard` exists but is not listed in `app/main.py`
- `app.api.revenue_dashboard_api` at `/revenue-dashboard`
- `app.api.mission_control_compat_api` for radar and portal-health compatibility paths
- `app.api.ws_live` for websocket feeds
- root UI routers exist (`app.ui`, `app.ui_routes`) but are not included by `app/main.py`

Stable destination:
- No separate long-term backend domain recommended. Frontend support should consume `/api/system/*`, `/api/rfq/*`, `/api/quotes/*`, `/api/submissions/*`, `/api/proofs/*`, `/api/portal/*`, and `/api/orchestration/*`.

## Duplicate and Overlapping Routers

High priority overlaps:
- `/submission-history` is split across:
  - `submission_history`
  - `submission_history_recent_api`
  - `submission_history_pipeline_sync_api`
  - `submission_history_proof_enrichment_api`
- `/sbd-intelligence` is used by both:
  - `sbd_intelligence_api`
  - `tender_form_intelligence_api`
- `/v47-live-browser` exists in both:
  - `live_browser_attach_v47_3_api`
  - `v47_live_browser_api`
- `/dashboard` exists in:
  - `app.api.dashboard`
  - root `app.dashboard_api`
- `/opportunities` exists in:
  - root `app.opportunities_api`
  - `app.api.opportunities_api`
- `/system` exists in:
  - `app.api.system`
  - `app.api.stability`
- `/autonomous` exists in:
  - root `app.autonomous_api`
  - `app.api.autonomous_api`

Functional overlaps:
- RFQ harvest/discovery is spread across `/tender-pipeline`, `/supply-command`, `/opportunities`, `/v31-smart-harvester`, `/v32-real-rfq-harvester`, `/v33-real-portal-rfq`, `/v34-structured-rfq`, `/v35-playwright-rfq`, `/v36-interactive-rfq`, `/v37-deep-rfq`, `/v38-click-deep-rfq`, `/v39-true-navigation`, `/v40-clickable-navigation`, `/v49-*`, and `/v50-*`.
- Quote/pricing work is spread across `/quote-engine`, `/quote-pack`, `/quote-packs`, `/quotes`, `/quote/*`, `/v42-pricing-table-extraction`, `/v43-auto-pricing`, `/v44-quote-pack`, and `/real-profit-pricing`.
- Submission execution and history are spread across `/submission-pipeline`, `/submission-history`, `/submission-retry`, `/submission-scheduler`, `/v45-submission-pack`, `/v46-auto-submission`, `/portal-submission`, `/v47-portal-submission`, `/v47-smart-upload`, `/v47-final-submit`, `/v48-autonomous`, `/full-autonomous-cycle`, and `/final-automation`.
- Proof/audit is split across `/submission-proof`, `/proof-center`, `/submission-history/proof-sync`, `/submission-history/recent-with-proofs`, `/v47-deep-verification`, and SBD/form completion routers.

Non-imported backup/stale files present in `app/api`:
- `proof_of_submission_api.py.backup`
- `rfq_lifecycle_api.py.bak_upload_dry_run`
- `etenders_browser_download_interceptor_v50_9_3_api.py.backup`
- `etenders_local_filter_v50_8_5_api.py.backup_v50_8_5`

These are not regular `*.py` modules, but they increase audit noise and should eventually be archived outside `app/api` after tests and operator approval.

## Old Versioned Routers to Eventually Merge

RFQ/discovery chain:
- v31 smart harvester
- v32 real RFQ harvester
- v33 real portal RFQ extraction
- v34 structured RFQ extractor
- v35 Playwright live DOM extractor
- v36 interactive Playwright extractor
- v37 deep RFQ link extractor
- v38 interactive click extraction
- v39 true navigation extraction
- v40 clickable navigation
- v49 real RFQ detail navigation
- v49.1 detail page follow
- v50.7 through v50.9.10 eTenders detail/navigation/document/download routers

Quote/submission chain:
- v42 pricing table extraction
- v43 auto pricing
- v44 quote pack
- v45 submission pack
- v46 auto submission
- v47 portal submission/autofill/browser/upload/final submit/deep verification
- v48 full autonomous

Recommendation:
- Keep these routes live during Phase A/B.
- Add stable wrappers that delegate to the newest safe service implementations.
- Deprecate only after frontend workspaces and backend tests use the stable wrappers.

## Active Safe Routers

Generally safe read-only/status routes:
- `GET /health`
- `GET /`
- `GET /dashboard/*`
- `GET /rfq-lifecycle/status`
- `GET /rfq-lifecycle/mission-control`
- `GET /rfq-lifecycle/analytics`
- `GET /rfq-lifecycle/telemetry`
- `GET /submission-history/*`
- `GET /submission-proof/status`
- `POST /submission-proof/latest`, `/generate`, `/generate-all` are proof generation, not real portal/email execution.
- `GET /proof-center/*`
- `POST /proof-center/scan` scans local proof artifacts.
- `GET /portal-submission/status`
- `POST /portal-submission/classify`
- `POST /portal-submission/route`
- `GET /portal-submission/health`
- `GET /production-lock/status`
- `GET /production-lock/policy`
- `POST /production-lock/evaluate`
- `POST /production-lock/assert`
- `GET /go-live-guards/summary`
- `POST /go-live-guards/evaluate`
- `GET /system/*`
- `GET /system-stability/*`
- `GET /security/status`
- `GET /ws/status`
- `GET /etenders-session/status`
- `GET /v48-autonomous/status`
- `GET /full-autonomous-cycle/status`
- `GET /v50-7-etenders-navigation/status`
- `GET /v50-7-promotion-gate/status`

Safe but mutating/control routes that should stay behind operator access:
- `POST /system/control/*`
- `POST /go-live-guards/submission-lock`
- `POST /go-live-guards/clear-submission-lock`
- `POST /production-lock/policy`
- `POST /operator-actions/*`

## Risky Routers Touching Execution

Email execution:
- root `app.email_api` at `/email-submissions/send` calls email submission logic.
- `app.api.auto_submission_v46_api` can send email if `dry_run=False` and `allow_send=True`.
- `app.api.quote_pack_api /run-autoquote` calls `AutoQuotePipelineService`, which contains SMTP send logic.
- root `app.quote_pack_api` has workflow routes including submit/mark sent semantics.

Portal upload/final submit/browser execution:
- `app.api.portal_submission_api`
  - `/auto-submit` and `/submit` call `auto_submit_portal`; the service currently reports final submit blocked, but endpoint naming and routing are execution-sensitive.
- `app.api.smart_upload_v47_4_api`
  - `/attach-and-upload` defaults to `execute_uploads=False` and `stop_before_submit=True`, but it is upload-capable by design.
- `app.api.final_submission_v47_5_api`
  - `/guarded-submit` defaults to `execute_final_submit=False`, but the service contains browser upload and final submit code paths behind policy/flags.
- `app.api.full_autonomous_cycle_api`
  - `/run` has `dry_run: bool = False`; this is a high-priority stabilization risk.
- `app.api.full_autonomous_v48_api`
  - `/policy` can alter `allow_email_send`, `allow_portal_upload`, and `allow_portal_final_submit`.
  - `/run-from-pdf` and `/run-from-v45-workspace` run autonomous orchestration.
- `app.api.final_automation_layer_api`
  - `/run-once` touches final automation service.
- `app.api.safe_autonomous_scheduler_api`
  - `/start-loop`, `/enable`, `/run-once`, and `enable_submit` option should be treated as execution-sensitive.
- `app.api.assisted_browser_v47_2_api`
  - Browser automation from plans; default includes `stop_before_submit=True`.
- `app.api.live_browser_attach_v47_3_api` and dormant `v47_live_browser_api`
  - Live browser attach and document attach.
- v50 eTenders DOM/browser/download capture routers
  - These can manipulate browser DOM, capture downloads, reconstruct/replay download behavior, or trigger clicks.
- `app.api.csd_persistent_session_api`
  - Manual login/session control should be considered browser/session-sensitive.

Destructive/local mutation risk:
- `POST /rfq-lifecycle/cleanup-runtime` can delete runtime artifacts depending on payload flags.
- `POST /supply-command/live-rfqs/clear` clears live RFQ records.

## Missing Stable Domain Endpoints

No stable `/api/*` namespace exists yet. Missing stable endpoints by target domain:

`/api/rfq/*`
- `GET /api/rfq/status`
- `GET /api/rfq/recent`
- `GET /api/rfq/{rfq_id}`
- `GET /api/rfq/{rfq_id}/timeline`
- `GET /api/rfq/readiness`
- `POST /api/rfq/ingest` wrapper, later only after Phase A read-only wrappers are stable

`/api/quotes/*`
- `GET /api/quotes/status`
- `GET /api/quotes/queue`
- `GET /api/quotes/{quote_id}`
- `GET /api/quotes/{quote_id}/pack`
- `POST /api/quotes/build` wrapper, later controlled

`/api/submissions/*`
- `GET /api/submissions/status`
- `GET /api/submissions/history`
- `GET /api/submissions/readiness`
- `GET /api/submissions/dry-runs/latest`
- `POST /api/submissions/dry-runs/run` wrapper only for controlled dry-run

`/api/proofs/*`
- `GET /api/proofs/status`
- `GET /api/proofs/latest`
- `GET /api/proofs/files`
- `GET /api/proofs/{proof_id}`
- `POST /api/proofs/scan` wrapper for proof center scan

`/api/portal/*`
- `GET /api/portal/status`
- `GET /api/portal/session`
- `GET /api/portal/workers`
- `GET /api/portal/compatibility`
- `POST /api/portal/classify`
- `POST /api/portal/readiness`
- No stable `/api/portal/submit` or `/api/portal/upload` until later explicit safety review.

`/api/compliance/*`
- `GET /api/compliance/status`
- `GET /api/compliance/documents`
- `GET /api/compliance/requirements/{rfq_id}`
- `GET /api/compliance/sbd/status`
- `POST /api/compliance/evaluate`

`/api/orchestration/*`
- `GET /api/orchestration/status`
- `GET /api/orchestration/workflows`
- `GET /api/orchestration/workflows/{rfq_id}`
- `GET /api/orchestration/retry-pressure`
- `GET /api/orchestration/escalations`
- `POST /api/orchestration/simulate` only local/dry-run backend simulation, not live execution

`/api/system/*`
- `GET /api/system/health`
- `GET /api/system/metrics`
- `GET /api/system/telemetry`
- `GET /api/system/routes`
- `GET /api/system/safety`
- `GET /api/system/policy`
- `GET /api/system/websocket-status`

## Proposed Stable API Surface

Phase A should add wrappers only. Existing routes remain unchanged.

```text
/api/rfq/status
/api/rfq/recent
/api/rfq/items
/api/rfq/items/{rfq_id}
/api/rfq/{rfq_id}/audit
/api/rfq/readiness

/api/quotes/status
/api/quotes/drafts
/api/quotes/queue
/api/quotes/packs
/api/quotes/packs/{quote_id}

/api/submissions/status
/api/submissions/history
/api/submissions/history/recent
/api/submissions/readiness
/api/submissions/dry-runs/latest
/api/submissions/dry-runs/run

/api/proofs/status
/api/proofs/latest
/api/proofs/files
/api/proofs/scan
/api/proofs/{proof_id}

/api/portal/status
/api/portal/classify
/api/portal/session/status
/api/portal/workers/status
/api/portal/compatibility
/api/portal/readiness

/api/compliance/status
/api/compliance/documents
/api/compliance/requirements/{rfq_id}
/api/compliance/sbd/status
/api/compliance/locks

/api/orchestration/status
/api/orchestration/workflows
/api/orchestration/workflows/{rfq_id}
/api/orchestration/retry-pressure
/api/orchestration/escalations
/api/orchestration/simulate

/api/system/health
/api/system/metrics
/api/system/telemetry
/api/system/routes
/api/system/safety
/api/system/policy
/api/system/websocket-status
```

Important stable API rule:
- Read-only wrappers first.
- Mutating wrappers must be explicitly named for dry-run/review/simulation.
- No stable route should expose final submit, email send, CAPTCHA bypass, or portal upload until a separate safety review approves it.

## Migration Plan

### Phase A: Add Stable Wrapper Endpoints

Add `/api/*` routers that delegate to existing services/routes without changing old behavior.

Constraints:
- Keep all legacy routes live.
- Start with read-only wrappers and dry-run-only wrappers.
- Add a route inventory endpoint under `/api/system/routes`.
- Add a safety summary endpoint under `/api/system/safety`.
- Ensure wrappers return normalized shapes for frontend workspaces.

### Phase B: Update Frontend to Stable Endpoints

Move frontend probes from mixed legacy endpoints to stable wrappers:
- Dashboard: `/api/system/*`, `/api/rfq/*`
- RFQ Operations: `/api/rfq/*`
- Quote Pack Engine: `/api/quotes/*`
- Submission Centre: `/api/submissions/*`, `/api/proofs/*`, `/api/portal/*`
- Proof & Audit Centre: `/api/proofs/*`
- Portal Workers: `/api/portal/workers/status`, `/api/portal/session/status`
- Workflow Orchestrator: `/api/orchestration/*`

Keep fallback probes to legacy endpoints temporarily during migration.

### Phase C: Deprecate Old v47-v50 Routes

After frontend and tests use `/api/*`, add deprecation metadata to old versioned routes:
- Response header: `Deprecation: true`
- Optional header: `Link: </api/...>; rel="successor-version"`
- Log usage of old routes.
- Do not remove routes yet.

### Phase D: Remove Duplicates Only After Tests Pass

Only after tests and production observation pass:
- Remove or archive duplicate prefixes.
- Merge split `/submission-history` routers.
- Consolidate SBD/form routers.
- Move backup files out of `app/api`.
- Remove old v31-v50 routes in small batches, starting with inactive/dormant routers.

## Compile Results

Requested commands:

```bash
python3 -m py_compile app/main.py
find app -name "*.py" -maxdepth 4 -print0 | xargs -0 python3 -m py_compile
```

Observed result for both requested commands:
- Both failed in this sandbox because `py_compile` tried to write bytecode under `/Users/cash/Library/Caches/com.apple.python/...`, which is outside the writable workspace.
- This was an environment/cache write failure, not evidence that `app/main.py` has syntax errors.

Workaround checks run with workspace-local bytecode cache:

```bash
PYTHONPYCACHEPREFIX=runtime/pycache python3 -m py_compile app/main.py
find app -name "*.py" -maxdepth 4 -print0 | xargs -0 env PYTHONPYCACHEPREFIX=runtime/pycache python3 -m py_compile
```

Results:
- `app/main.py` compiled successfully with `PYTHONPYCACHEPREFIX=runtime/pycache`.
- Full app compile failed with real source issues:
  - `app/classify.py`, line 31: `SyntaxError: 'return' outside function`
  - `app/services/source_parser_routing_service.py`, line 192: `SyntaxError: invalid character '✅' (U+2705)` from `accept ✅`
  - `app/services/~$nder_pipeline.py`: contains null bytes and cannot be compiled

## Import Risks

Compile checks do not import modules, so they do not validate runtime dependency availability or startup import side effects.

Observed import/startup risks from `app/main.py`:
- Direct imports happen before optional router loading; failures in directly imported routers can prevent startup.
- Optional router import failures are swallowed into `failed_routers`, so the API can start with missing routers unless `/health` or logs are checked.
- Duplicate router detection is too weak for route-level conflicts because it keys by `router_name:prefix:route_count`.
- Several routers import browser automation, SMTP/email, and portal execution services at module import time.
- Multiple Pydantic styles may coexist; for example `model_dump()` assumes Pydantic v2 semantics in some routers.
- Non-Python backup files in `app/api` increase maintenance risk even if not imported.

## Router Duplication Risks

Highest risk:
- Multiple routers share the same prefix and could create route shadowing, confusing OpenAPI output, or ambiguous ownership.
- Legacy versioned routes are often newer experiments rather than stable replacements.
- Execution-sensitive endpoints are discoverable from root/health payloads even when safety flags default to safe values.

Operational impact:
- Frontend code must probe many possible endpoints.
- Developers cannot tell which router is canonical without inspecting `app/main.py`.
- Tests for one router family may miss another overlapping endpoint that performs similar work.
- Safety review is harder because portal upload/final submit/email actions are spread across several routers.

## Recommended First Safe Backend Change

First safe change should be non-execution and low blast radius:

1. Fix compile-only source blockers without changing runtime behavior:
   - Move the stray `return` statements in `app/classify.py` into a proper function or remove the corrupted appended fragment after confirming intended logic.
   - Replace `accept ✅` in `app/services/source_parser_routing_service.py` with valid Python logic or a comment.
   - Quarantine `app/services/~$nder_pipeline.py` outside compile scope after operator approval; do not delete it in-place without approval.

2. Add a read-only stable system wrapper router:
   - `/api/system/health`
   - `/api/system/routes`
   - `/api/system/safety`
   - `/api/system/telemetry`

3. Register that wrapper through the existing optional router pattern.

This gives the frontend a stable, safe starting point and improves observability before touching any execution-sensitive domain.

## Phase 2 Stable System Wrappers

Added after the initial audit:
- `app.api.system_stable_api` registered as `system_stable_router`.
- Read-only stable endpoints added at `/api/system/health`, `/api/system/routes`, `/api/system/runtime`, `/api/system/safety`, and `/api/system/summary`.
- Legacy `/`, `/health`, and existing router registrations remain retained.
- The stable wrappers expose observability and safety state only; they do not trigger email sending, portal uploads, CAPTCHA bypass, or final submission execution.

## Phase 3 Stable RFQ Wrappers

Added after Phase 2:
- `app.api.rfq_stable_api` registered as `rfq_stable_router`.
- Read-only stable endpoints added at `/api/rfq/health`, `/api/rfq/status`, `/api/rfq/recent`, and `/api/rfq/summary`.
- Runtime JSON fallback is used for RFQ visibility because legacy RFQ lifecycle routes include execution endpoints and import risks.
- Legacy RFQ routes remain retained; no router removal or execution behavior changes were made.

## Phase 4 Stable Quote Wrappers

Added after Phase 3:
- `app.api.quotes_stable_api` registered as `quotes_stable_router`.
- Read-only stable endpoints added at `/api/quotes/health`, `/api/quotes/status`, `/api/quotes/recent`, and `/api/quotes/summary`.
- Quote visibility is derived from generated quote artifact metadata first, with RFQ lifecycle JSON used only for enrichment or fallback candidates.
- Legacy quote routes remain retained; no quote generation, file mutation, router removal, or execution behavior changes were made.
