# Runtime Recovery Validation

This validator performs controlled, staging-only recovery validation against the existing runtime governance artifacts.

## Recovery Targets
- Redis interruption
- Backend degradation
- Worker interruption
- Observability interruption
- Escalation degradation
- Continuity instability

## Governance Verifications
- Governance stability restoration
- Remediation closure tracking
- Continuity recovery
- Escalation readiness restoration
- Observability restoration
- Supervision continuity
- Governance index recovery
- Unresolved blockers remain visible when recovery is incomplete

## Recovery State Model
- `recovered`
- `degraded-but-recovering`
- `unresolved-blocked`

`PASS` is only allowed for `recovered`. Partial recovery states must retain warnings, blocker sources, and rationale in the emitted evidence.

## Evidence Contract
- `recovery_state`
- `recovery_state_history`
- `unresolved_blockers`
- `recovery_rationale`
- `blocker_sources`
- `score_impact`

Incomplete recovery must aggregate unresolved blockers from:
- rollout recovery snapshot
- continuity recovery snapshot
- escalation recovery snapshot
- remediation recovery snapshot

## Markdown Expectations
- final recovery state
- unresolved blockers
- recovery rationale
- score impact

## Outputs
- `runtime/staging/runtime-recovery-validations/`
- `latest_runtime_recovery_validation.json`
- `latest_runtime_recovery_validation.md`

## Safety Boundary
The validator does not enable autonomous procurement authority, live submission enablement, irreversible actions, or real production credentials. It only emits simulated recovery evidence from staged governance data.
