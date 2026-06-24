# Autoscaling and Resource Governance Report

## Scope
This package defines a read-only, staging-only governance scaffold for future distributed production autoscaling.
It does not enable live scaling authority, autonomous submission, external alert delivery, or real production credentials.

## Readiness Signals
The governance slice tracks:
- HPA readiness
- worker autoscaling readiness
- backend autoscaling readiness
- frontend autoscaling readiness
- CPU and memory request governance
- CPU and memory limit governance
- queue-depth scaling readiness
- tenant-aware scaling boundaries
- scale-up governance
- scale-down governance
- saturation indicators
- autoscaling degradation indicators
- autoscaling governance history

## Package Controls
The base package includes placeholders for:
- backend HPA
- frontend HPA
- worker HPA
- resource quota
- limit range
- queue-depth scaling

The existing tenant isolation scaffolding is reused to keep autoscaling boundaries tenant-aware.
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
- required manifest directories
- required workload manifests
- HPA placeholders
- resource requests and limits
- namespace resource quotas
- limit ranges
- queue-depth scaling
- tenant-aware scaling boundaries
- dry-run enforcement
- supervision mandatory
- no autonomous production authority
- external alert delivery disabled

## Operating Rule
This scaffold is for governance validation only.
It is not an execution path for live autoscaling, live tenant onboarding, or production authority.
