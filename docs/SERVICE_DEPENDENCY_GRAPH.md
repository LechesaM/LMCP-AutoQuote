# LMCP Service Dependency Graph

## Purpose
This document describes the current upstream/downstream relationships in LMCP, including event flow, queue ownership, and database boundaries. It is a logical graph over the current monolith.

## Top-Level Graph

```text
Acquisition
  -> Intelligence
  -> Commercial
  -> Governance
  -> Unified Command Centre

Intelligence
  -> Commercial
  -> Submission
  -> Unified Command Centre

Commercial
  -> Submission
  -> Governance
  -> Unified Command Centre

Submission
  -> Governance
  -> Unified Command Centre

Governance
  -> Acquisition
  -> Commercial
  -> Submission
  -> Unified Command Centre

Unified Command Centre
  -> no canonical downstream ownership
  -> aggregates all services
```

## Upstream and Downstream Relationships

### Acquisition Service

- Upstream:
  - Governance for system-control and pause/lock decisions
  - external portals and eTenders
- Downstream:
  - Intelligence via document packs and lifecycle items
  - Commercial via qualified/live RFQs
  - Unified Command Centre via lifecycle and health summaries

### Intelligence Service

- Upstream:
  - Acquisition for lifecycle items and source documents
- Downstream:
  - Commercial via BOQ, pricing schedule, returnables, and buyer intelligence
  - Submission via submission gate/readiness inputs
  - Unified Command Centre via AI scoring and trends

### Commercial Service

- Upstream:
  - Acquisition for candidate RFQs
  - Intelligence for extracted structures and buyer/pricing insight
  - Governance for operator access and approval policy
- Downstream:
  - Submission via approved quote packs and submission package inputs
  - Unified Command Centre via commercial summaries and quote review metrics

### Submission Service

- Upstream:
  - Commercial for quote packs and pricing outputs
  - Governance for go-live guard, production lock, and operator approval
- Downstream:
  - Unified Command Centre via submission history, proof, and health views

### Governance Service

- Upstream:
  - all services emit actions requiring policy/audit treatment
- Downstream:
  - Acquisition via pause/reject/source control
  - Commercial via approval and operator auth
  - Submission via release gates and locks
  - Unified Command Centre via mode, status, and audit visibility

### Unified Command Centre

- Upstream:
  - all services
- Downstream:
  - operator dashboards and websocket clients only

## Event Flow

### Primary runtime flow

```text
Portal source discovered
  -> Harvest run
  -> RFQ normalized
  -> RFQ lifecycle item created
  -> Acquisition queue
  -> Document acquisition
  -> Parsing queue
  -> Document/BOQ intelligence
  -> Pricing queue
  -> Quote/pricing/commercial review
  -> Proof queue
  -> Submission prep and execution
  -> Retry queue when blocked/failed
  -> Submission history + proof capture
  -> Dashboard / mission control aggregation
```

### Current implementation anchors

- lifecycle state machine: [app/services/rfq_lifecycle_service.py](/Users/cash/Documents/app/services/rfq_lifecycle_service.py)
- queue routing: [app/celery_app.py](/Users/cash/Documents/app/celery_app.py)
- Celery tasks: [app/tasks.py](/Users/cash/Documents/app/tasks.py)
- retry scheduler: [app/tasks/submission_scheduler_tasks.py](/Users/cash/Documents/app/tasks/submission_scheduler_tasks.py)
- dashboard/websocket fan-out: [app/api/dashboard.py](/Users/cash/Documents/app/api/dashboard.py), [app/api/ws_live.py](/Users/cash/Documents/app/api/ws_live.py), [app/services/websocket_broker.py](/Users/cash/Documents/app/services/websocket_broker.py)

## Queue Ownership

### `default`

- Current use:
  - general Celery tasks and health checks
- Recommended owner:
  - platform/common operational tasks only

### `acquisition_queue`

- Current use:
  - `app.tasks.rfq_lifecycle_acquisition_task`
- Recommended owner:
  - Acquisition Service

### `parsing_queue`

- Current use:
  - `app.tasks.rfq_lifecycle_parsing_task`
- Recommended owner:
  - Intelligence Service

### `pricing_queue`

- Current use:
  - `app.tasks.rfq_lifecycle_pricing_task`
- Recommended owner:
  - Commercial Service

### `proof_queue`

- Current use:
  - `app.tasks.rfq_lifecycle_proof_task`
- Recommended owner:
  - Submission Service

### `retry_queue`

- Current use:
  - `app.tasks.rfq_lifecycle_retry_task`
  - `app.tasks.run_rfq_lifecycle_golden_cycle`
  - scheduled harvest task and retry-style orchestration
- Recommended owner:
  - shared operational queue governed by Governance + owning domain service

## Database Ownership Boundaries

## Canonical target

### Acquisition-owned entities

- tender master/lifecycle records
- source documents
- acquisition attempts

### Intelligence-owned entities

- document intelligence results
- BOQ extractions and normalized rows
- buyer events, buyer profiles, procurement signals

### Commercial-owned entities

- quote drafts
- quote packs
- commercial comparison records
- supplier pricing/award decisions

### Submission-owned entities

- submission master records
- submission attempts
- proof metadata

### Governance-owned entities

- operators and sessions
- audit events
- control state changes
- production lock and release decisions

### Unified Command Centre

- owns no canonical business entities
- may own derived aggregate snapshots only

## Current actual boundary violations

- RFQ lifecycle state is JSON-owned rather than database-owned
- submission history is JSON-owned alongside `submission_records`
- operator auth is SQLite-owned outside PostgreSQL
- governance audit is split across SQLAlchemy table, JSON files, and manual-production SQLite
- acquisition-side tenders/documents/BOQ models exist in a separate SQLite lineage

## Hidden Orchestration Coupling

### Lifecycle service as orchestrator + read model + cleanup manager

[app/services/rfq_lifecycle_service.py](/Users/cash/Documents/app/services/rfq_lifecycle_service.py) currently combines:

- lifecycle state management
- queue assignment
- acquisition advancement
- recovery/retry behavior
- mission-control style summaries
- cleanup/runtime maintenance

This is the clearest hidden platform orchestrator in the current runtime.

### Tender pipeline as commercial + supplier + submission bridge

[app/services/tender_pipeline.py](/Users/cash/Documents/app/services/tender_pipeline.py) currently combines:

- classification
- pricing
- quote generation
- supplier quote request/ingestion
- award execution
- storage and logging

This is a cross-domain orchestration hub rather than a pure commercial service.

### Submission path fragmentation

Submission logic is spread across:

- [app/services/submission_pipeline.py](/Users/cash/Documents/app/services/submission_pipeline.py)
- [app/services/tender_submission_pipeline.py](/Users/cash/Documents/app/services/tender_submission_pipeline.py)
- [app/services/portal_submission_service.py](/Users/cash/Documents/app/services/portal_submission_service.py)
- [app/services/email_submission_service.py](/Users/cash/Documents/app/services/email_submission_service.py)
- [app/services/submission_retry_service.py](/Users/cash/Documents/app/services/submission_retry_service.py)

This is the main reason Submission Service should be extracted late.

## Duplicated Logic Hotspots

- supply-and-delivery filtering appears in Acquisition, Commercial, and Submission flows
- margin/profit policy appears in lifecycle, pricing, and governance code
- quote readiness is derived in lifecycle JSON, live RFQ store, and commercial pack services
- proof/submission completion is tracked in multiple JSON histories and proof folders

## Frontend Dependency Graph

### Official frontend

[etenders_acquisition/lmcp-dashboard/app/page.tsx](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard/app/page.tsx) depends on:

- `GET /dashboard`
- `POST /refresh/all`
- `GET /health`

This makes the official frontend a thin Unified Command Centre shell today.

### Legacy frontend

The `frontend/` tree depends on many service-specific APIs including:

- `/rfq-lifecycle/status`
- `/portal-submission/status`
- `/submission-proof/status`
- `/autonomous/status`
- `/mission-control/*`
- `/system/control/status`

This means the legacy frontend is tightly coupled to internal service boundaries and fallback operational APIs.

## Future Extraction Order

### Recommended order

1. Governance Service
2. Acquisition Service
3. Intelligence Service
4. Commercial Service
5. Submission Service
6. Unified Command Centre last as contract consumer cleanup

### Why this order is safest

- Governance has clear policy and control semantics and the smallest external integration surface.
- Acquisition already has explicit queue ownership and a central lifecycle controller.
- Intelligence can be separated once acquisition output contracts are stable.
- Commercial depends heavily on intelligence outputs and review schemas, so it should follow.
- Submission is last because it is the most fragmented and touches the most production-risk integrations.

## Safest Migration Sequence

1. Freeze contracts around queue payloads, lifecycle DTOs, and status responses.
2. Move governance read/write functions behind stable interfaces without changing storage yet.
3. Split acquisition orchestration from lifecycle read models.
4. Introduce intelligence-only processors that consume acquisition records and publish normalized outputs.
5. Consolidate commercial pipelines into one quote/pricing aggregate owner.
6. Consolidate submission behind one orchestrator with email and portal adapters.
7. Reduce Unified Command Centre to a pure aggregation layer over stable service APIs.
