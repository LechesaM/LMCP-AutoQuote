# LMCP v2 Operational Route Baseline

Audit date: 2026-07-16
Manifest: `config/lmcp_v2_operational_route_baseline.json`

## Purpose

This baseline defines the route surface that may be exposed by default after a controlled API restart. It separates required operational routes from high-risk source-only route families that must not activate silently after recovery.

## Baseline Decision

Required and compatibility families remain enabled:

- health and workflow health;
- system control;
- RFQ lifecycle and manual pricing;
- Live RFQ/tender pipeline reads and controlled operator commands;
- quote compilation and supplier quote review;
- dashboard/revenue visibility;
- approval, operator action, proof, submission history, and audit routes;
- SBD and buyer-form intelligence;
- go-live guard checks;
- current autonomous status/control routes with autonomous state disabled by default.

High-risk source-only families are disabled by default:

- acquisition and browser automation V31-V40;
- local quote/submission artifact generation V43-V45;
- auto-submission, portal upload, final submit, and autonomous V46-V48;
- eTenders V50 acquisition/download/browser interception;
- CSD persistent session/monthly refresh automation;
- final automation and safe autonomous scheduler;
- handwriting/document processing routes that are source-only in this recovery comparison.

## Activation Control

Default-deny routing is implemented in `app/core/router_activation.py`.

Opt-in controls:

- `LMCP_ENABLE_HIGH_RISK_ROUTERS=true` enables all default-denied high-risk route families.
- `LMCP_ENABLE_ROUTER_FAMILIES=<router_name>[,<router_name>...]` enables only named families.

The gate runs before optional router import, so disabled families do not register routes and do not execute module import-time filesystem initialization.

## Current Controlled Source Surface

With default settings:

- loaded routers: 54;
- failed routers: 0;
- disabled routers: 56;
- duplicate method/path pairs: 0;
- source method/path pairs: 303.

The baseline verifier reports all required route families present and all high-risk route families controlled.

## Import-Safety Fix

`import app.main` and in-process OpenAPI generation no longer create persistent directories or files. Directory creation previously happened in `app.main` and module constructors/imports for runtime helpers. It now occurs only in explicit startup initialization or operational write paths.

## Restart Implication

The route surface after restart will intentionally differ from the stale running process:

- retained compatibility: `/health/workflows`, `/system/control/effective-status`, RFQ lifecycle/manual-pricing routes;
- waived/superseded: legacy autonomous health/run-sync;
- operator decision still available: historical dashboard manual-review and go-live pilot/report routes;
- source-only high-risk families: disabled by default.

This supports `SAFE_TO_RESTART_WITH_KNOWN_ROUTE_CHANGES` if validation passes and runtime stores remain unchanged.
