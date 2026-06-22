# Frontend Authority Decision

Date: 2026-06-22
Scope: documentation only

## Purpose
This document resolves the current frontend authority conflict so archival and migration planning can proceed safely without modifying frontend code.

Sources used:

- [docs/REPO_AUDIT.md](/Users/cash/Documents/docs/REPO_AUDIT.md)
- [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md)
- [docs/ARCHIVE_PLAN.md](/Users/cash/Documents/docs/ARCHIVE_PLAN.md)
- [etenders_acquisition/lmcp-dashboard](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard)
- compose files and startup scripts currently in the repository

## Repository `package.json` Inventory

Repository-owned `package.json` files:

1. [frontend/package.json](/Users/cash/Documents/frontend/package.json)
2. [etenders_acquisition/lmcp-dashboard/package.json](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard/package.json)

Notes:

- `frontend/command-centre/` has no `package.json`.
- this inventory excludes `node_modules/**/package.json`, which are dependency artifacts rather than repository-owned app manifests

## Frontend App Inventory

## 1. `etenders_acquisition/lmcp-dashboard`

- Path: [etenders_acquisition/lmcp-dashboard](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard)
- Framework: Next.js 16 + React 19
- Startup command: `cd etenders_acquisition/lmcp-dashboard && npm run dev`
- Port: `3000`
- Current purpose:
  - thin dashboard shell
  - uses `/dashboard`, `/refresh/all`, and `/health`
  - exposes backend connectivity and environment indicators
- Referenced by docs or compose:
  - yes, in its own [README.md](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard/README.md)
  - yes, indirectly in newer service-boundary docs that describe it as the official frontend surface
  - no, not referenced by current compose files
- Status: `ACTIVE`
- Assessment:
  - this is the only frontend with an explicit stabilized runtime contract
  - it has a fixed documented port and environment-based API configuration
  - it matches the most recent stabilization work

## 2. `frontend`

- Path: [frontend](/Users/cash/Documents/frontend)
- Framework: Vite + React 19
- Startup command: `cd frontend && npm run dev`
- Port: default Vite dev port, effectively `5173` unless overridden
- Current purpose:
  - large legacy command-centre/operations UI surface
  - contains many service-specific panels and API integrations
  - appears broader than the current stabilized dashboard requirement
- Referenced by docs or compose:
  - yes, named as official in [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md)
  - no, not referenced as the build target in current compose files
- Status: `DUPLICATE`
- Assessment:
  - this is a substantial frontend, but it does not currently have the cleanest authority signal
  - its README is still generic Vite boilerplate
  - its runtime surface is much broader and more tightly coupled to legacy/internal APIs than the stabilized dashboard

## 3. `frontend/command-centre`

- Path: [frontend/command-centre](/Users/cash/Documents/frontend/command-centre)
- Framework: incomplete TypeScript frontend subtree; framework cannot be fully established from repo metadata because there is no manifest
- Startup command: none safely documented from local app metadata
- Port: unknown from local app metadata
- Current purpose:
  - partial command-centre frontend source tree
  - used as a reference path by scripts and compose
- Referenced by docs or compose:
  - yes, current [docker-compose.yml](/Users/cash/Documents/docker-compose.yml) and [docker-compose.production.yml](/Users/cash/Documents/docker-compose.production.yml) point frontend builds at `frontend/command-centre/Dockerfile`
  - yes, multiple scripts reference `frontend/command-centre`
  - no repository-local `package.json` or `Dockerfile` was found in this folder during the audit
- Status: `UNKNOWN`
- Assessment:
  - this is the highest-risk authority conflict point
  - it is referenced operationally, but the audited tree is incomplete as an independently runnable frontend app
  - until its missing manifest/build assets are explained, it cannot be the authoritative frontend

## 4. Other frontend-like subtrees

### `frontend/src/frontend`

- Path: [frontend/src/frontend](/Users/cash/Documents/frontend/src/frontend)
- Framework: unclear nested source subtree
- Startup command: none
- Port: none
- Current purpose: embedded/nested legacy source material
- Referenced by docs or compose: no direct runtime reference found
- Status: `OBSOLETE`

### `app/services/frontend` and `services/frontend`

- Paths:
  - [app/services/frontend](/Users/cash/Documents/app/services/frontend)
  - [services/frontend](/Users/cash/Documents/services/frontend)
- Framework: not standalone frontend apps; they are frontend-related source fragments
- Startup command: none
- Port: none
- Current purpose: source fragments duplicated inside service trees
- Referenced by docs or compose: no standalone frontend runtime reference found
- Status: `OBSOLETE`

### `lmcp-core/frontend`

- Path: [lmcp-core/frontend](/Users/cash/Documents/lmcp-core/frontend)
- Framework: none yet
- Startup command: none
- Port: none
- Current purpose: future platform destination only
- Referenced by docs or compose:
  - yes, as a target in [docs/PLATFORM_ARCHITECTURE.md](/Users/cash/Documents/docs/PLATFORM_ARCHITECTURE.md)
  - no, not an active runtime
- Status: `UNKNOWN`

## Decision

The recommended single official frontend is:

- [etenders_acquisition/lmcp-dashboard](/Users/cash/Documents/etenders_acquisition/lmcp-dashboard)

## Why This Frontend Wins

1. It is the only frontend with a current stabilization-specific runtime contract:
   - explicit startup instructions
   - fixed dev port `3000`
   - explicit API base URL configuration
   - explicit `/health` connectivity surface
2. It matches the most recent frontend stabilization work already performed in the repository.
3. It has the narrowest and safest backend dependency surface:
   - `/dashboard`
   - `/refresh/all`
   - `/health`
4. The competing candidates are either broader legacy surfaces or operationally referenced but incomplete trees.

## What This Means For The Other Frontends Later

### `frontend`

- treat as non-official legacy frontend
- keep in place for now
- later actions should be:
  - retain only if specific operator workflows still lack parity in the official frontend
  - otherwise classify for archive after explicit workflow migration

### `frontend/command-centre`

- treat as non-official and incomplete
- keep in place for now because compose and scripts still reference it
- later actions should be:
  - first resolve whether missing manifest/build files exist elsewhere or whether compose references are stale
  - then either restore it as a real build target or retire/archive it

### `frontend/src/frontend`

- treat as obsolete nested legacy source
- keep in place for now
- later actions should be:
  - archive after confirming no active imports or tooling depend on it

### `app/services/frontend` and `services/frontend`

- treat as duplicated frontend-related fragments, not authoritative apps
- keep in place for now
- later actions should be:
  - review whether they are dead fragments or still referenced
  - archive only after that dependency check

## Required Follow-Up After This Decision

This document resolves authority, but it does not change runtime references. The following must happen later in a controlled migration phase:

1. Update runtime documentation so [docs/OFFICIAL_RUNTIME.md](/Users/cash/Documents/docs/OFFICIAL_RUNTIME.md) no longer names `frontend/` as official.
2. Reconcile compose and startup scripts that still reference `frontend/command-centre`.
3. Decide whether legacy `frontend/` remains temporarily supported or becomes an archive candidate after workflow parity review.
4. Keep `lmcp-core/frontend/` as the long-term destination, not the current runtime.

## Final Classification Summary

| Frontend path | Classification | Authority decision |
| --- | --- | --- |
| `etenders_acquisition/lmcp-dashboard` | `ACTIVE` | Official frontend |
| `frontend` | `DUPLICATE` | Non-official legacy frontend |
| `frontend/command-centre` | `UNKNOWN` | Non-official, operationally referenced but incomplete |
| `frontend/src/frontend` | `OBSOLETE` | Non-official nested legacy source |
| `app/services/frontend` | `OBSOLETE` | Not a standalone frontend |
| `services/frontend` | `OBSOLETE` | Not a standalone frontend |
| `lmcp-core/frontend` | `UNKNOWN` | Future destination only |
