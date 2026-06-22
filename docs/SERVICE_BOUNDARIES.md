# LMCP Service Boundaries

## Purpose
This document maps the current LMCP runtime into formal enterprise service boundaries without changing runtime behavior. It is based on the active backend entrypoint, registered routers, service modules under [app/services](/Users/cash/Documents/app/services), Celery configuration in [app/celery_app.py](/Users/cash/Documents/app/celery_app.py), task definitions in [app/tasks.py](/Users/cash/Documents/app/tasks.py), scheduler tasks in [app/tasks/submission_scheduler_tasks.py](/Users/cash/Documents/app/tasks/submission_scheduler_tasks.py), the official frontend in [etenders_acquisition/lmcp-dashboard](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard), and the current persistence split documented in [docs/DATABASE_SOURCE_OF_TRUTH.md](/Users/cash/Documents/docs/DATABASE_SOURCE_OF_TRUTH.md).

## Runtime Shape

The current runtime is not yet cleanly separated into domain services. It behaves as one monolith with these characteristics:

- router composition is centralized in [app/api/router_registry.py](/Users/cash/Documents/app/api/router_registry.py)
- orchestration mixes API routes, Celery tasks, JSON stores, SQLite stores, and SQLAlchemy models
- major workflows cross service boundaries through direct imports rather than stable contracts
- the official frontend currently uses a narrow surface, mainly `/dashboard`, `/refresh/all`, and `/health`
- many additional frontend surfaces exist in the legacy `frontend/` tree and consume broad operational APIs

The six target enterprise boundaries below are therefore logical boundaries over the current code, not isolated deployable units yet.

## 1. Acquisition Service

### Ownership
Owns discovery, harvesting, qualification, document acquisition, and RFQ lifecycle ingress.

### Responsibilities

- source discovery and radar cycles
- tender harvesting across eTenders and other portals
- source health and portal fitness tracking
- buyer pack acquisition and document download
- RFQ intake normalization and promotion into lifecycle tracking

### Primary modules

- [app/services/tender_harvester.py](/Users/cash/Documents/app/services/tender_harvester.py)
- [app/services/harvest_scheduler_service.py](/Users/cash/Documents/app/services/harvest_scheduler_service.py)
- [app/services/local_harvest_service.py](/Users/cash/Documents/app/services/local_harvest_service.py)
- [app/services/harvester_adapter.py](/Users/cash/Documents/app/services/harvester_adapter.py)
- [app/services/rfq_lifecycle_service.py](/Users/cash/Documents/app/services/rfq_lifecycle_service.py)
- [app/services/rfq_document_acquisition_engine.py](/Users/cash/Documents/app/services/rfq_document_acquisition_engine.py)
- [app/services/harvest_source_registry_service.py](/Users/cash/Documents/app/services/harvest_source_registry_service.py)
- [app/services/source_parser_routing_service.py](/Users/cash/Documents/app/services/source_parser_routing_service.py)
- versioned eTenders navigators and download services under [app/services](/Users/cash/Documents/app/services)

### APIs consumed

- system control checks from [app/services/system_control_service.py](/Users/cash/Documents/app/services/system_control_service.py)
- lifecycle recovery/state store from [app/services/rfq_state_store.py](/Users/cash/Documents/app/services/rfq_state_store.py)
- document intelligence hooks from [app/services/rfq_document_intelligence.py](/Users/cash/Documents/app/services/rfq_document_intelligence.py)
- pricing readiness checks from [app/services/validation_readiness_service.py](/Users/cash/Documents/app/services/validation_readiness_service.py)

### APIs exposed

- `/rfq-lifecycle/*` via [app/api/rfq_lifecycle_api.py](/Users/cash/Documents/app/api/rfq_lifecycle_api.py)
- `/tasks/*` harvest triggers via [app/tasks_api.py](/Users/cash/Documents/app/tasks_api.py)
- `/opportunities/*` and harvest-related routes via [app/api/opportunities_api.py](/Users/cash/Documents/app/api/opportunities_api.py)
- many versioned eTenders APIs under [app/api](/Users/cash/Documents/app/api)

### Database entities owned

Canonical target ownership:

- tender master records
- source document metadata
- acquisition attempts
- lifecycle transition records for discovery through document acquisition

Current actual ownership is split across:

- `opportunities` in [app/models/core.py](/Users/cash/Documents/app/models/core.py)
- acquisition-side SQLite models in [etenders_acquisition/app/db/models.py](/Users/cash/Documents/etenders_acquisition/app/db/models.py)
- RFQ lifecycle JSON state in [app/services/rfq_state_store.py](/Users/cash/Documents/app/services/rfq_state_store.py)

### Celery queues/tasks involved

- `acquisition_queue`
- `retry_queue`
- `app.tasks.run_harvest_only`
- `app.tasks.run_harvest_pipeline`
- `app.tasks.run_scheduled_tender_harvest_task`
- `app.tasks.rfq_lifecycle_acquisition_task`
- `app.tasks.run_rfq_lifecycle_golden_cycle`

### Runtime dependencies

- Redis/Celery transport
- portal HTTP access
- lifecycle state JSON
- source registry and source health files

### Filesystem dependencies

- `runtime/live_rfqs.json`
- `runtime/rfq_lifecycle/*`
- `runtime/harvest_runs/*`
- `runtime/source_health.json`
- `runtime/multi_portal_discovery/*`
- `runtime/opportunity_extraction/*`
- `runtime/downloaded_tender_documents/*`

### External integrations

- eTenders
- buyer/portal web endpoints
- Playwright/browser automation surfaces

### Frontend surfaces

- dashboard summaries from `/dashboard`
- RFQ operations and workflow views in the legacy `frontend/` app
- lifecycle and portal status screens through `/rfq-lifecycle/*`

## 2. Intelligence Service

### Ownership
Owns document understanding, BOQ/returnables extraction, buyer intelligence, province/category normalization, and decision support inputs.

### Responsibilities

- document role classification
- BOQ extraction and normalization
- pricing schedule detection and buyer form intelligence
- buyer profiling and procurement signals
- scoring and recommendation support for operators and mission control

### Primary modules

- [app/services/document_ingestion_service.py](/Users/cash/Documents/app/services/document_ingestion_service.py)
- [app/services/rfq_document_intelligence.py](/Users/cash/Documents/app/services/rfq_document_intelligence.py)
- [app/services/rfq_docx_main_document_intelligence.py](/Users/cash/Documents/app/services/rfq_docx_main_document_intelligence.py)
- [app/services/rfq_zip_content_extraction_engine.py](/Users/cash/Documents/app/services/rfq_zip_content_extraction_engine.py)
- [app/services/final_boq_row_normalization_engine.py](/Users/cash/Documents/app/services/final_boq_row_normalization_engine.py)
- [app/services/amount_quantity_integrity_validation_engine.py](/Users/cash/Documents/app/services/amount_quantity_integrity_validation_engine.py)
- [app/services/tender_form_intelligence_engine.py](/Users/cash/Documents/app/services/tender_form_intelligence_engine.py)
- [app/services/decision_intelligence_service.py](/Users/cash/Documents/app/services/decision_intelligence_service.py)
- [app/services/mission_control_ai_scoring_service.py](/Users/cash/Documents/app/services/mission_control_ai_scoring_service.py)
- procurement intelligence package under [app/services/procurement_intelligence](/Users/cash/Documents/app/services/procurement_intelligence)

### APIs consumed

- lifecycle items and live RFQ records
- quote/pricing artifacts from Commercial Service
- submission gate evaluation from Submission/Governance surfaces

### APIs exposed

- `/decision-intelligence/*`
- `/tender-form-intelligence/*`
- `/backend-intelligence/*`
- `/mission-control/*`
- several document/parsing versioned APIs

### Database entities owned

Canonical target ownership:

- procurement signals
- buyer events
- buyer profiles
- document intelligence results
- BOQ extraction jobs and normalized BOQ rows

Current actual ownership is split across:

- `buyer_events`, `buyer_profiles`, `procurement_signals` in [app/models](/Users/cash/Documents/app/models)
- acquisition-side `boq_extractions` and `boq_items` in [etenders_acquisition/app/db/models.py](/Users/cash/Documents/etenders_acquisition/app/db/models.py)
- large JSON outputs in `runtime/document_intelligence`, `runtime/boq_intelligence`, and `runtime/buyer_intelligence`

### Celery queues/tasks involved

- `parsing_queue`
- `pricing_queue`
- `app.tasks.rfq_lifecycle_parsing_task`
- `app.tasks.rfq_lifecycle_pricing_task`

### Runtime dependencies

- lifecycle records from Acquisition Service
- SQLAlchemy models for buyer intelligence
- heavy local processing of files under runtime

### Filesystem dependencies

- `runtime/document_intelligence/*`
- `runtime/boq_intelligence/*`
- `runtime/buyer_intelligence/*`
- `runtime/tender_form_intelligence/*`
- downloaded buyer packs and extracted local text

### External integrations

- source documents from portals
- local parsers for PDF, DOCX, XLSX, ZIP

### Frontend surfaces

- mission control AI scoring
- RFQ operations intelligence views
- quote review extraction/debug surfaces

## 3. Commercial Service

### Ownership
Owns pricing, quote construction, supplier comparison, quote pack generation, and commercial review.

### Responsibilities

- build priced line items from extracted RFQs
- run pricing engines and profit/margin logic
- compare supplier quotes and recommend awards
- generate quote packs and manage quote review workflow
- maintain commercial state needed before submission

### Primary modules

- [app/services/pricing_engine.py](/Users/cash/Documents/app/services/pricing_engine.py)
- [app/services/pricing_engine_v2_realistic.py](/Users/cash/Documents/app/services/pricing_engine_v2_realistic.py)
- [app/services/real_profit_pricing_service.py](/Users/cash/Documents/app/services/real_profit_pricing_service.py)
- [app/services/quote_engine.py](/Users/cash/Documents/app/services/quote_engine.py)
- [app/services/quote_pack_service.py](/Users/cash/Documents/app/services/quote_pack_service.py)
- [app/services/quote_pack_builder_service.py](/Users/cash/Documents/app/services/quote_pack_builder_service.py)
- [app/services/quote_compilation_service.py](/Users/cash/Documents/app/services/quote_compilation_service.py)
- [app/services/quote_review_service.py](/Users/cash/Documents/app/services/quote_review_service.py)
- [app/services/supplier_quote_ingestion_service.py](/Users/cash/Documents/app/services/supplier_quote_ingestion_service.py)
- [app/services/supplier_quote_comparison_service.py](/Users/cash/Documents/app/services/supplier_quote_comparison_service.py)
- [app/services/supplier_award_execution_service.py](/Users/cash/Documents/app/services/supplier_award_execution_service.py)
- [app/services/tender_pipeline.py](/Users/cash/Documents/app/services/tender_pipeline.py)

### APIs consumed

- lifecycle and acquisition outputs from Acquisition Service
- document intelligence and BOQ outputs from Intelligence Service
- operator identity from Governance Service

### APIs exposed

- `/quote-engine/*`
- `/quote-pack/*`
- `/quote-compilation/*`
- `/dashboard/*` commercial aggregates
- tender pipeline routes and quote review routes

### Database entities owned

Canonical target ownership:

- quote drafts and line items
- quote packs and quote pack items
- quote review status history
- supplier/product/commercial comparison records

Current actual ownership:

- `quote_drafts`, `quote_line_items`, `supplier_items` in [app/models/core.py](/Users/cash/Documents/app/models/core.py)
- `quote_packs`, `quote_pack_items`, `quote_pack_status_history`, `quote_pack_edit_audit` in [app/quote_pack_models.py](/Users/cash/Documents/app/quote_pack_models.py)
- large commercial JSON outputs in runtime

### Celery queues/tasks involved

- `pricing_queue`
- `proof_queue`
- `app.tasks.rfq_lifecycle_pricing_task`
- downstream proof-stage transitions when quote packs become submission-ready

### Runtime dependencies

- SQLAlchemy database access
- quote review service performs schema mutation/startup work via `ensure_quote_pack_schema()`
- uses pricing, supplier, and quote assembly services directly

### Filesystem dependencies

- `monthly_quotes/*`
- `runtime/manual_review/*`
- `runtime/manual_production/*`
- `runtime/pricing_engine/*`
- `runtime/pricing_summaries/*`
- `runtime/commercial_intelligence/*`
- `runtime/supplier_quote_*/*`

### External integrations

- supplier quote ingestion inputs from email/files
- document artifacts from acquisition and submission packs

### Frontend surfaces

- dashboard top-line commercial metrics
- quote pack engine workspace in legacy frontend
- RFQ operations and quote review UI surfaces

## 4. Submission Service

### Ownership
Owns submission package assembly, route classification, email/portal dispatch, proof capture, and submission retry execution.

### Responsibilities

- determine email vs portal submission route
- prepare submission packs
- execute portal and email submissions
- capture proof and receipt artifacts
- maintain submission history and scheduler/retry behavior

### Primary modules

- [app/services/submission_pipeline.py](/Users/cash/Documents/app/services/submission_pipeline.py)
- [app/services/tender_submission_pipeline.py](/Users/cash/Documents/app/services/tender_submission_pipeline.py)
- [app/services/portal_submission_service.py](/Users/cash/Documents/app/services/portal_submission_service.py)
- [app/services/portal_submission_v47_service.py](/Users/cash/Documents/app/services/portal_submission_v47_service.py)
- [app/services/email_submission_service.py](/Users/cash/Documents/app/services/email_submission_service.py)
- [app/services/email_submission_preparation_service.py](/Users/cash/Documents/app/services/email_submission_preparation_service.py)
- [app/services/submission_history_service.py](/Users/cash/Documents/app/services/submission_history_service.py)
- [app/services/submission_retry_service.py](/Users/cash/Documents/app/services/submission_retry_service.py)
- [app/services/submission_scheduler_service.py](/Users/cash/Documents/app/services/submission_scheduler_service.py)
- [app/services/submission_proof_service.py](/Users/cash/Documents/app/services/submission_proof_service.py)
- [app/services/proof_center_service.py](/Users/cash/Documents/app/services/proof_center_service.py)
- [app/services/submission_package_service.py](/Users/cash/Documents/app/services/submission_package_service.py)

### APIs consumed

- quote packs and approved commercial outputs from Commercial Service
- governance gates from Governance Service
- lifecycle and live RFQ records from Acquisition Service

### APIs exposed

- `/submission-pipeline/run`
- `/portal-submission/*`
- `/submission-scheduler/*`
- `/submission-history/*`
- `/proof-center/*`
- `/proof-of-submission/*`

### Database entities owned

Canonical target ownership:

- submission master record
- submission attempt history
- proof metadata
- dispatch route and execution logs

Current actual ownership is split across:

- `submission_records` in [app/models/core.py](/Users/cash/Documents/app/models/core.py)
- JSON history in [app/services/submission_history_service.py](/Users/cash/Documents/app/services/submission_history_service.py)
- proof and review rows in manual production SQLite through `app.persistence.db`

### Celery queues/tasks involved

- `proof_queue`
- `retry_queue`
- `app.tasks.rfq_lifecycle_proof_task`
- `app.tasks.rfq_lifecycle_retry_task`
- `app.tasks.submission_scheduler_tasks.run_autonomous_submission_loop_task`

### Runtime dependencies

- Redis/Celery for retries and scheduler execution
- submission history JSON store
- proof and portal runtime folders

### Filesystem dependencies

- `runtime/submission_history/*`
- `runtime/portal_submission/*`
- `runtime/final_submission_v47_5/*`
- `runtime/proof_center/*`
- `runtime/locks/immutable_submission/*`
- `runtime/submission_pack/*`
- `runtime/tender_submission_pipeline/*`

### External integrations

- SMTP/email
- portal/browser automation
- buyer submission portals

### Frontend surfaces

- portal workers workspace
- submission centre workspace
- proof audit centre workspace
- dashboard submission summaries

## 5. Governance Service

### Ownership
Owns operator identity, system control, production guardrails, audit, lock enforcement, and release policy.

### Responsibilities

- operator authentication and RBAC
- system on/off, pause, emergency stop, and control state
- production lock and go-live guard evaluation
- pipeline enforcement before quote/submission execution
- audit trail and operator action broadcasting
- submission lock and controlled/manual release rules

### Primary modules

- [app/services/operator_auth_service.py](/Users/cash/Documents/app/services/operator_auth_service.py)
- [app/services/system_state_service.py](/Users/cash/Documents/app/services/system_state_service.py)
- [app/services/system_control_service.py](/Users/cash/Documents/app/services/system_control_service.py)
- [app/services/production_lock_service.py](/Users/cash/Documents/app/services/production_lock_service.py)
- [app/services/go_live_guard_service.py](/Users/cash/Documents/app/services/go_live_guard_service.py)
- [app/services/pipeline_enforcement_service.py](/Users/cash/Documents/app/services/pipeline_enforcement_service.py)
- [app/services/immutable_submission_lock_service.py](/Users/cash/Documents/app/services/immutable_submission_lock_service.py)
- [app/services/audit_trail_service.py](/Users/cash/Documents/app/services/audit_trail_service.py)
- [app/services/operator_action_service.py](/Users/cash/Documents/app/services/operator_action_service.py)

### APIs consumed

- database connectivity checks
- submission gate data and quote review actions
- websocket broker for operator event fan-out

### APIs exposed

- `/system-control/*`
- `/operator-auth/*`
- `/operator-actions/*`
- `/audit-trail/*`
- `/production-lock/*`
- `/pipeline-enforcement/*`
- health/go-live routes and mission control policy views

### Database entities owned

Canonical target ownership:

- operator identities and sessions
- audit events
- control-state changes
- governance decisions
- submission lock records

Current actual ownership is split across:

- operator auth SQLite in [app/services/operator_auth_service.py](/Users/cash/Documents/app/services/operator_auth_service.py)
- runtime JSON in `runtime/system_state`, `runtime/production_lock`, `runtime/pipeline_enforcement`, `runtime/audit_trail`
- manual production SQLite via [app/persistence/db.py](/Users/cash/Documents/app/persistence/db.py)
- lightweight SQLAlchemy `audit_logs` table in [app/models/audit_log.py](/Users/cash/Documents/app/models/audit_log.py)

### Celery queues/tasks involved

- indirectly all queues, because guards block or allow execution
- submission retry scheduling and autonomous cycles depend on governance checks

### Runtime dependencies

- SQLite operator auth database
- runtime JSON lock/policy files
- websocket broker for event propagation

### Filesystem dependencies

- `runtime/system_state/*`
- `runtime/production_lock/*`
- `runtime/pipeline_enforcement/*`
- `runtime/audit_trail/*`
- `runtime/locks/*`
- `runtime/operator_auth/*`

### External integrations

- none as a primary business integration
- indirectly governs all external submission and portal automation

### Frontend surfaces

- system control panels
- operator auth workflows
- audit/proof/governance dashboards
- mission control readiness and mode indicators

## 6. Unified Command Centre

### Ownership
Owns cross-service observability, operator dashboards, mission control snapshots, and websocket fan-out. It should not own domain state.

### Responsibilities

- aggregate lifecycle, submission, portal, and health views
- publish dashboard and websocket updates
- present mission control recommendations and trends
- expose command surfaces for supervisors/operators

### Primary modules

- [app/api/dashboard.py](/Users/cash/Documents/app/api/dashboard.py)
- [app/api/mission_control_snapshot_api.py](/Users/cash/Documents/app/api/mission_control_snapshot_api.py)
- [app/api/ws_live.py](/Users/cash/Documents/app/api/ws_live.py)
- [app/services/websocket_broker.py](/Users/cash/Documents/app/services/websocket_broker.py)
- [app/services/mission_control_history_service.py](/Users/cash/Documents/app/services/mission_control_history_service.py)
- [app/services/mission_control_recommendations_service.py](/Users/cash/Documents/app/services/mission_control_recommendations_service.py)

### APIs consumed

- `/rfq-lifecycle/*`
- `/portal-submission/*`
- `/submission-history/*`
- `/health`, `/status`
- mission control AI and recommendation builders

### APIs exposed

- `/dashboard/*`
- `/mission-control/*`
- `/ws`, `/ws/live`, `/ws/dashboard`, `/ws/tenders`

### Database entities owned

- none should be canonical here

Current persistence used:

- mission control history JSON in `runtime/mission_control`
- transient in-memory websocket connection state

### Celery queues/tasks involved

- none owned directly
- consumes outputs from all queues through aggregate status views

### Runtime dependencies

- all service APIs and read models
- websocket connection manager

### Filesystem dependencies

- `runtime/mission_control/*`
- read-only access to many other runtime summaries

### External integrations

- browser websocket clients

### Frontend surfaces

- official frontend [etenders_acquisition/lmcp-dashboard/app/page.tsx](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard/app/page.tsx)
- legacy `frontend/` command-centre and mission-control workspaces

## Overlapping Responsibilities

### Acquisition overlap

- `tender_harvester`, `local_harvest_service`, `autonomous_engine`, and `harvest_scheduler_service` all coordinate harvesting
- `rfq_lifecycle_service` both tracks state and performs orchestration actions
- many versioned eTenders services overlap on navigation, download, and detail resolution

### Commercial overlap

- `pricing_engine`, `pricing_engine_v2_realistic`, and `real_profit_pricing_service` all participate in pricing decisions
- `quote_engine`, `quote_pack_service`, `quote_pack_builder_service`, and `quote_compilation_service` overlap on quote package assembly
- `quote_review_service` mixes review workflow, extraction, validation, and schema management

### Submission overlap

- `submission_pipeline`, `tender_submission_pipeline`, `portal_submission_service`, and `email_submission_service` all model submission execution
- `submission_retry_service`, `submission_scheduler_service`, and `autonomous_submission_loop_service` overlap on retry orchestration
- proof capture exists in multiple services and runtime folders

### Governance overlap

- `system_state_service` and `system_control_service` both participate in control-state handling
- `production_lock_service`, `go_live_guard_service`, and `pipeline_enforcement_service` all enforce release policy

## Circular Dependencies and Hidden Coupling

### Hidden orchestration coupling

- [app/tasks.py](/Users/cash/Documents/app/tasks.py) resolves orchestration dynamically from `app.autonomous_engine` and `app.services.tender_pipeline`
- [app/api/router_registry.py](/Users/cash/Documents/app/api/router_registry.py) mixes production and legacy routers in one registry, so runtime exposure is centrally coupled
- [app/services/rfq_lifecycle_service.py](/Users/cash/Documents/app/services/rfq_lifecycle_service.py) combines state machine, queue mapping, acquisition retry, mission control metrics, and cleanup behavior

### Unsafe cross-service imports

- [app/services/document_ingestion_service.py](/Users/cash/Documents/app/services/document_ingestion_service.py) imports a wide chain of downstream pricing, form filling, submission prep, SMTP, and proof services
- [app/services/tender_pipeline.py](/Users/cash/Documents/app/services/tender_pipeline.py) imports classification, pricing, supplier quote ingestion, award execution, quote generation, CSD refresh, and storage in one flow
- [app/services/quote_review_service.py](/Users/cash/Documents/app/services/quote_review_service.py) imports pricing and document intelligence while also mutating database schema on startup
- [app/services/audit_trail_service.py](/Users/cash/Documents/app/services/audit_trail_service.py) crosses governance, persistence, and websocket/eventing

### Direct persistence coupling

- services write straight to JSON files under `runtime/*`
- some services write to manual-production SQLite via `app.persistence.db`
- some services use SQLAlchemy/PostgreSQL models
- the same business domain is often represented in all three

## Duplicated Logic

- supply/delivery qualification appears in harvester, lifecycle, tender pipeline, and submission pipeline layers
- profit/margin thresholds appear in lifecycle, production lock, pricing, and submission filtering
- submission readiness exists in lifecycle state, submission gate logic, proof services, and portal submission status
- route/control state exists in both JSON control files and service-level checks

## Boundary Recommendation

### Future extraction order into `lmcp-core/services/*`

1. `governance`
2. `acquisition`
3. `intelligence`
4. `commercial`
5. `submission`

Rationale:

- Governance is the safest first extraction because it is mostly policy, control, and audit coordination.
- Acquisition already has clear queue boundaries and a lifecycle controller, even though it is too broad.
- Intelligence can then separate parsing/analysis from acquisition side effects.
- Commercial extraction should follow once document and lifecycle contracts are stable.
- Submission should move last because it currently has the highest runtime coupling and production risk.

### Safest migration sequence

1. Extract read-only contracts first: DTOs, status payloads, and audit/event schemas.
2. Move governance policy and audit surfaces behind stable interfaces without changing execution paths.
3. Introduce acquisition service contracts around RFQ intake, source health, and lifecycle transitions.
4. Split intelligence processors from document acquisition and quote review orchestration.
5. Consolidate commercial ownership around one pricing pipeline and one quote-pack aggregate.
6. Consolidate submission execution behind one orchestrator with explicit email/portal adapters.
7. Leave Unified Command Centre as an aggregate shell consuming service contracts rather than owning business logic.

## Boundary Summary

- Acquisition should own discovery and lifecycle ingress.
- Intelligence should own understanding and scoring.
- Commercial should own pricing and quote state.
- Submission should own dispatch and proof.
- Governance should own control, policy, and audit.
- Unified Command Centre should aggregate all of the above and own no canonical domain state.
