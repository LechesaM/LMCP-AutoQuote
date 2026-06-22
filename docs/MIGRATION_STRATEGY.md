# Migration Strategy

Date: 2026-06-22
Scope: gradual movement into `lmcp-core/` without breaking production

## Objective

Move the current LMCP runtime into the `lmcp-core/` platform structure gradually, without breaking:

- `app.main:app`
- `app.celery_app.celery_app`
- existing imports
- `docker-compose.production.yml`
- current runtime paths and operational scripts

## Current Constraints

- no active runtime files are moved yet
- no imports are changed yet
- no business logic is refactored yet
- no archive operations occur yet
- current production startup remains authoritative

## Migration Principles

1. Production remains the source of truth until each migration step is explicitly validated.
2. Structural preparation comes before code movement.
3. Domain ownership is defined before imports are redirected.
4. Runtime compatibility is preserved at every step.
5. One boundary is stabilized at a time to avoid broad regression risk.

## Phase 0: Platform Skeleton

Status:

- completed by creating `lmcp-core/` and platform documentation

Outcome:

- the target structure exists
- no runtime behavior changes

## Phase 1: Ownership Mapping

Goal:

- map current runtime modules to target platform domains without moving them

Activities:

- identify which current files belong to acquisition, intelligence, commercial, submission, and governance
- record authoritative owners for duplicated trees
- confirm which current frontend is official

Production safety:

- no file movement
- no import changes
- no compose changes

## Phase 2: Compatibility Shims Before Relocation

Goal:

- introduce migration-safe boundaries before moving source files

Activities:

- define future API, worker, and service ownership in docs
- identify where compatibility wrappers will be required later
- determine which root-level duplicate trees must remain read-only during migration

Production safety:

- startup entrypoints remain `app.main:app` and `app.celery_app.celery_app`
- compose paths remain unchanged

## Phase 3: Domain-by-Domain Source Promotion

Goal:

- move code into `lmcp-core/` one domain at a time after explicit validation

Recommended order:

1. governance
2. intelligence
3. commercial
4. acquisition
5. submission

Reasoning:

- governance establishes safety rails first
- intelligence and commercial are easier to separate than full submission execution
- submission should move later because it carries the highest operational risk

Production safety:

- each move must preserve a working compatibility surface
- imports should only change when the replacement path is validated

## Phase 4: API and Worker Realignment

Goal:

- align transport and background execution with the new platform layout

Activities:

- gradually map router ownership into `lmcp-core/api/`
- gradually map queue and task ownership into `lmcp-core/workers/`
- keep current entrypoints loading compatible modules until final cutover

Production safety:

- `app.main:app` remains the official backend entrypoint during transition
- `app.celery_app.celery_app` remains the official worker entrypoint during transition

## Phase 5: Runtime and Storage Boundary Cleanup

Goal:

- formalize future platform-owned runtime and storage boundaries

Activities:

- document which runtime directories remain legacy versus platform-owned
- define storage ownership and retention rules
- move only after runtime compatibility and observability are confirmed

Production safety:

- repository-root `runtime/` remains active until replacement paths are verified
- no docker-compose production path breakage is allowed

## Phase 6: Final Runtime Cutover

Goal:

- promote `lmcp-core/` from structural destination to active platform root

Prerequisites:

- domain ownership completed
- compatibility verified
- duplicate trees retired from active ownership
- frontend runtime path clarified
- compose and launcher references validated end-to-end

Production safety:

- final cutover must be staged and reversible
- no cutover should happen until health, worker readiness, and operational telemetry remain stable

## Non-Negotiable Safety Rules

- do not change `docker-compose.production.yml` until the replacement runtime is proven
- do not change `app.main:app` as the official backend entrypoint until the final cutover phase
- do not change `app.celery_app.celery_app` as the official worker entrypoint until the final cutover phase
- do not move runtime artifacts into `lmcp-core/archive/` yet
- do not collapse duplicate trees by deletion until authoritative replacements are validated

## Immediate Next Steps After This Skeleton

The next stabilization-safe action should be documentation and mapping only:

1. map current modules into the five service domains
2. identify authoritative modules where duplicates exist
3. identify compatibility points required before any source relocation
4. confirm frontend runtime ownership before touching launch scripts

## Success Condition

The migration is successful only when:

- the platform structure under `lmcp-core/` becomes authoritative
- production startup remains intact throughout the transition
- runtime behavior is preserved
- domain boundaries are clearer than in the current mixed structure
- duplicate ownership is eliminated without breaking operations
