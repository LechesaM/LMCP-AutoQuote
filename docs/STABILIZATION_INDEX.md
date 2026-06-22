# Stabilization Index

Date: 2026-06-22
Scope: Phase 1 stabilization index for the current controlled LMCP state

## Current Controlled Status

LMCP is currently in documentation-first stabilization.

- official backend authority is defined
- official worker authority is defined
- service landing zones have been created under `lmcp-core/services/*`
- runtime behavior remains on the legacy active runtime under `app/` and repository-root `runtime/`
- source relocation has not started
- frontend authority is documented but not fully reconciled across all stabilization documents and compose references

## Official Runtime

Primary runtime definition: [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md)

- official production launcher: `docker-compose.production.yml`
- official backend entrypoint: `app.main:app`
- official worker entrypoint: `app.celery_app.celery_app`

## Official Frontend

Frontend authority decision: [docs/FRONTEND_AUTHORITY_DECISION.md](/Users/cash/Documents/docs/FRONTEND_AUTHORITY_DECISION.md)

- recommended official frontend: `etenders_acquisition/lmcp-dashboard`
- status:
  - this is the recommended controlled frontend
  - [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md) still names `frontend/` as official
  - compose and startup references to `frontend/command-centre` are still unresolved

## Official Backend

- backend entrypoint: `app.main:app`
- backend runtime doc: [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md)
- backend health/status stabilization:
  - `GET /health`
  - `GET /status`

## Official Worker Entrypoint

- worker entrypoint: `app.celery_app.celery_app`
- worker runtime doc: [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md)

## Completed Stabilization Milestones

- repository audit completed: [docs/REPO_AUDIT.md](/Users/cash/Documents/docs/REPO_AUDIT.md)
- official runtime baseline documented: [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md)
- platform target structure documented: [docs/PLATFORM_ARCHITECTURE.md](/Users/cash/Documents/docs/PLATFORM_ARCHITECTURE.md)
- migration strategy documented: [docs/MIGRATION_STRATEGY.md](/Users/cash/Documents/docs/MIGRATION_STRATEGY.md)
- database source-of-truth baseline documented: [docs/DATABASE_SOURCE_OF_TRUTH.md](/Users/cash/Documents/docs/DATABASE_SOURCE_OF_TRUTH.md)
- state transition model documented: [docs/STATE_TRANSITION_MODEL.md](/Users/cash/Documents/docs/STATE_TRANSITION_MODEL.md)
- service boundaries documented: [docs/SERVICE_BOUNDARIES.md](/Users/cash/Documents/docs/SERVICE_BOUNDARIES.md)
- service dependency graph documented: [docs/SERVICE_DEPENDENCY_GRAPH.md](/Users/cash/Documents/docs/SERVICE_DEPENDENCY_GRAPH.md)
- archive planning documented: [docs/ARCHIVE_PLAN.md](/Users/cash/Documents/docs/ARCHIVE_PLAN.md)
- frontend authority decision documented: [docs/FRONTEND_AUTHORITY_DECISION.md](/Users/cash/Documents/docs/FRONTEND_AUTHORITY_DECISION.md)
- backend `/health` and `/status` surface stabilized and verified by tests
- controlled service landing zones created for governance, acquisition, intelligence, commercial, and submission

## Service Landing Zones Completed

- governance:
  - [lmcp-core/services/governance/README.md](/Users/cash/Documents/lmcp-core/services/governance/README.md)
  - [docs/GOVERNANCE_MIGRATION_REPORT.md](/Users/cash/Documents/docs/GOVERNANCE_MIGRATION_REPORT.md)
- acquisition:
  - [lmcp-core/services/acquisition/README.md](/Users/cash/Documents/lmcp-core/services/acquisition/README.md)
  - [docs/ACQUISITION_MIGRATION_REPORT.md](/Users/cash/Documents/docs/ACQUISITION_MIGRATION_REPORT.md)
- intelligence:
  - [lmcp-core/services/intelligence/README.md](/Users/cash/Documents/lmcp-core/services/intelligence/README.md)
  - [docs/INTELLIGENCE_MIGRATION_REPORT.md](/Users/cash/Documents/docs/INTELLIGENCE_MIGRATION_REPORT.md)
- commercial:
  - [lmcp-core/services/commercial/README.md](/Users/cash/Documents/lmcp-core/services/commercial/README.md)
  - [docs/COMMERCIAL_MIGRATION_REPORT.md](/Users/cash/Documents/docs/COMMERCIAL_MIGRATION_REPORT.md)
- submission:
  - [lmcp-core/services/submission/README.md](/Users/cash/Documents/lmcp-core/services/submission/README.md)
  - [docs/SUBMISSION_MIGRATION_REPORT.md](/Users/cash/Documents/docs/SUBMISSION_MIGRATION_REPORT.md)

## Migration Reports Completed

- [docs/GOVERNANCE_MIGRATION_REPORT.md](/Users/cash/Documents/docs/GOVERNANCE_MIGRATION_REPORT.md)
- [docs/ACQUISITION_MIGRATION_REPORT.md](/Users/cash/Documents/docs/ACQUISITION_MIGRATION_REPORT.md)
- [docs/INTELLIGENCE_MIGRATION_REPORT.md](/Users/cash/Documents/docs/INTELLIGENCE_MIGRATION_REPORT.md)
- [docs/COMMERCIAL_MIGRATION_REPORT.md](/Users/cash/Documents/docs/COMMERCIAL_MIGRATION_REPORT.md)
- [docs/SUBMISSION_MIGRATION_REPORT.md](/Users/cash/Documents/docs/SUBMISSION_MIGRATION_REPORT.md)

## Current Blockers

- frontend authority is not fully reconciled:
  - [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md) names `frontend/`
  - [docs/FRONTEND_AUTHORITY_DECISION.md](/Users/cash/Documents/docs/FRONTEND_AUTHORITY_DECISION.md) recommends `etenders_acquisition/lmcp-dashboard`
  - compose and scripts still reference `frontend/command-centre`
- PostgreSQL is the intended canonical state store, but live runtime state is still split across PostgreSQL-adjacent models, SQLite, JSON, and runtime folders:
  - [docs/DATABASE_SOURCE_OF_TRUTH.md](/Users/cash/Documents/docs/DATABASE_SOURCE_OF_TRUTH.md)
- lifecycle orchestration remains monolithic in `app/services/rfq_lifecycle_service.py`
- service ownership is documented, but queue ownership, runtime paths, and persistence boundaries are not yet isolated
- no compatibility shims exist yet for source relocation into `lmcp-core`

## What Must Not Be Changed Yet

- do not change `app.main:app` as the official backend entrypoint
- do not change `app.celery_app.celery_app` as the official worker entrypoint
- do not break `docker-compose.production.yml`
- do not move live runtime code out of `app/` yet without compatibility validation
- do not change imports for active runtime modules yet
- do not archive duplicate trees yet
- do not move repository-root `runtime/` artifacts yet
- do not enable real autonomous final submission

Reference: [docs/MIGRATION_STRATEGY.md](/Users/cash/Documents/docs/MIGRATION_STRATEGY.md), [docs/SUBMISSION_MIGRATION_REPORT.md](/Users/cash/Documents/docs/SUBMISSION_MIGRATION_REPORT.md)

## Next Recommended Milestones

1. Reconcile official frontend authority across runtime docs, compose references, and launch scripts without changing runtime behavior unexpectedly.
2. Define compatibility-shim strategy for the first real source promotion from `app/` into `lmcp-core/services/*`.
3. Formalize runtime path adapters for governance, acquisition, intelligence, commercial, and submission artifacts.
4. Define canonical database ownership transitions for lifecycle, quote, submission, audit, and operator state.
5. Prepare API and worker realignment planning for `lmcp-core/api/` and `lmcp-core/workers/`.

Reference: [docs/MIGRATION_STRATEGY.md](/Users/cash/Documents/docs/MIGRATION_STRATEGY.md), [docs/SERVICE_DEPENDENCY_GRAPH.md](/Users/cash/Documents/docs/SERVICE_DEPENDENCY_GRAPH.md)

## Verification Commands

Backend compile:

```bash
python3 -m py_compile app/main.py
```

Backend route tests:

```bash
.venv/bin/pytest tests/test_main_health_status_routes.py
.venv/bin/pytest tests/test_main_runtime_surface.py
```

Backend health checks:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/status
```

## Definition Of Done For Phase 1 Stabilization

Phase 1 Stabilization is done when all of the following are true:

- official backend, worker, and frontend authority are explicitly documented with no unresolved contradiction
- repository audit, runtime definition, migration strategy, database state model, service boundaries, and dependency graph are complete
- all five service landing zones exist under `lmcp-core/services/*`
- each service has a completed migration report
- backend `/health` and `/status` are stable and verified
- no production entrypoint, import surface, or runtime behavior has been broken during the documentation-first phase
- the repository is ready to begin compatibility-shim work before any live source relocation
