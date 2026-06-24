# Backup, Restore & Data Durability Governance Report

## Scope
This package defines a read-only, staging-only governance scaffold for backup, restore, and data durability topology.
It does not add live external backup storage credentials, autonomous submission authority, or a production execution path.

## Readiness Signals
The governance slice tracks:
- PostgreSQL backup readiness
- Redis persistence readiness
- restore rehearsal readiness
- backup retention governance
- encrypted backup placeholder governance
- tenant-aware backup boundaries
- RPO visibility
- RTO visibility
- backup degradation indicators
- restore blocker indicators
- backup governance history

## Package Controls
The base package includes placeholders for:
- PostgreSQL backup CronJob
- Redis persistence
- backup storage secret placeholder
- restore rehearsal job
- backup retention policy

The existing tenant governance scaffolding is reused to keep backup boundaries tenant-aware.
The production overlay remains locked to:
- `LMCP_ALLOW_FINAL_AUTOMATION=false`
- `LMCP_DRY_RUN_MODE=true`
- `LMCP_REQUIRE_HUMAN_SUPERVISION=true`

## Governance Model
The service classifies each snapshot into one of three explicit states:
- `recovered`
- `degraded-but-recovering`
- `unresolved-blocked`

Scoring is conservative:
- `PASS` is only emitted when the governance state is `recovered`
- degraded states reduce score
- unresolved blockers reduce score further
- warnings and blockers are always surfaced

## Evidence Artifacts
The runtime evidence exposes:
- `recovery_state`
- `recovery_state_history`
- `unresolved_blockers`
- `recovery_rationale`
- `blocker_sources`

## Validation
The package validator checks:
- PostgreSQL backup placeholder
- Redis persistence placeholder
- backup storage secret placeholder-only content
- restore rehearsal job representation
- backup retention policy representation
- RPO and RTO representation
- tenant-aware backup boundaries
- dry-run enforcement
- supervision mandatory
- no live external backup credentials

## Operating Rule
This scaffold is for governance validation only.
It is not an execution path for live backup jobs, live restore actions, or production credentials.
