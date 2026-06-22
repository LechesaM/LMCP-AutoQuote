# Platform Architecture

Date: 2026-06-22
Scope: target platform skeleton only

## Purpose

This document defines the foundational target architecture for the LMCP enterprise platform without changing the current production runtime.

The current official runtime remains:

- backend entrypoint: `app.main:app`
- worker entrypoint: `app.celery_app.celery_app`
- production launcher: `docker-compose.production.yml`

The new `lmcp-core/` tree is a structural destination for future migration, not an active replacement yet.

## Acquisition Layer

The Acquisition Layer owns all inbound opportunity capture from external procurement sources.

Primary responsibilities:

- source registry ownership
- portal crawling and fetch execution
- tender and RFQ harvesting
- document acquisition
- source health telemetry
- acquisition diagnostics and recovery flows

Target home:

- `lmcp-core/services/acquisition/`

Expected interfaces:

- acquisition APIs under `lmcp-core/api/`
- acquisition workers under `lmcp-core/workers/`
- orchestration hooks under `lmcp-core/orchestration/`

## Intelligence Layer

The Intelligence Layer interprets acquired data and converts raw intake into platform decisions and operational signals.

Primary responsibilities:

- RFQ qualification
- buyer and supplier signal enrichment
- source productivity analysis
- workflow stage intelligence
- telemetry interpretation
- recommendation generation for downstream domains

Target home:

- `lmcp-core/services/intelligence/`

Expected interfaces:

- read from acquisition outputs
- publish scored and enriched records to commercial and governance consumers

## Commercial Layer

The Commercial Layer owns pricing, profitability, and quote-construction logic.

Primary responsibilities:

- pricing engine execution
- margin rules
- quote pack assembly
- quote comparison support
- commercial readiness checks
- profitability validation

Target home:

- `lmcp-core/services/commercial/`

Expected interfaces:

- consume qualified RFQs and enriched buyer context
- produce commercial decisions and quote artifacts for submission workflows

## Submission Layer

The Submission Layer owns the controlled preparation and execution of outbound submission work.

Primary responsibilities:

- submission package assembly
- portal upload workflows
- proof generation
- submission scheduling
- retry handling
- submission history updates

Target home:

- `lmcp-core/services/submission/`

Expected interfaces:

- consume commercial outputs approved for progression
- emit proof, status, and operational feedback into governance and command-centre surfaces

## Governance Layer

The Governance Layer owns safety, controls, auditability, and production enforcement.

Primary responsibilities:

- policy enforcement
- approval gates
- production lock controls
- audit trails
- runtime safety checks
- operational compliance decisions

Target home:

- `lmcp-core/services/governance/`

Expected interfaces:

- evaluate whether work may proceed between layers
- provide hard-stop and soft-warning decisions to orchestration and UI layers

## Unified Command Centre

The Unified Command Centre is the future operator-facing platform surface.

Primary responsibilities:

- monitor acquisition health
- review intelligence outputs
- supervise commercial readiness
- control submission workflows
- inspect governance state and audit evidence

Target homes:

- frontend application: `lmcp-core/frontend/`
- API transport layer: `lmcp-core/api/`

Design intent:

- present a single operational surface across all layers
- avoid separate disconnected dashboards per domain
- keep operator control compatible with the current guarded production model

## Platform Relationship Model

The target platform relationship is:

1. Acquisition captures external data.
2. Intelligence qualifies and enriches that data.
3. Commercial decides whether the opportunity is economically viable.
4. Submission prepares and executes controlled outbound delivery.
5. Governance supervises and constrains all prior layers.
6. The Unified Command Centre presents the cross-layer operational view.

## Structural Rules

- `lmcp-core/` defines the target platform structure only.
- Existing runtime code remains authoritative until explicitly migrated.
- No imports should be redirected to `lmcp-core/` until migration steps are planned and validated.
- No runtime ownership is considered moved simply because a target folder exists.

