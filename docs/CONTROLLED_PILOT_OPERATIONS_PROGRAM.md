# Controlled Pilot Operations Program

This document defines the supervised, controlled, real-world pilot operations program for LMCP AutoQuote. It is documentation only. It does not enable autonomous live submissions, remove dry-run protections, redesign orchestration, or introduce production connectivity.

## Purpose

The goal of the controlled pilot operations program is to permit carefully supervised pilot execution in staging-governed conditions while keeping all irreversible actions behind operator control and existing submission locks.

The program is built on the current staging evidence model:

- `runtime/staging/pilot-cycles/`
- `runtime/staging/governance-exports/`
- `docs/PILOT_OPERATIONAL_REVIEW_BOARD_REPORT.md`
- `docs/SCHEDULED_PILOT_CADENCE_REPORT.md`
- `docs/PILOT_GO_NO_GO_FRAMEWORK.md`

## Supervised pilot execution model

- Every pilot cycle is initiated and observed under a named operator lead.
- Pilot execution is limited to the approved scope recorded in the latest governance export and review-board outputs.
- Pilot activity must remain dry-run aware and submission-lock aware at every checkpoint.
- Operators must be able to halt, rollback, or defer the pilot at any point before an irreversible action.
- Review-board oversight is required before, during, and after each pilot session.

## Operator supervision responsibilities

- Confirm the latest review-board status is current and read-only.
- Confirm the latest cadence report shows the pilot and governance review windows are current.
- Confirm readiness score, stability score, and evidence pack status are within approval thresholds.
- Confirm submission locks, dry-run protections, and NO-GO checks are PASS before allowing the pilot to proceed.
- Observe queue, worker, telemetry, retry, and dead-letter surfaces while the pilot is active.
- Pause the pilot if any warning threshold is exceeded or if telemetry becomes stale.
- Record operator observations, exceptions, and intervention decisions in the staging evidence trail.
- Trigger rollback or halt workflows when required by the go/no-go framework.

## Governance-board operational cadence

- Governance review must occur on the same recurring cadence reflected in the staging evidence.
- Review-board sessions must be scheduled at least as frequently as the latest approved cadence window.
- Readiness scoring checkpoints must be validated before any pilot session starts.
- Stability trend checkpoints must be reviewed before pilot activation and after each pilot cycle.
- If cadence slips or review sessions are overdue, the pilot must not be expanded.

## Escalation workflow

1. Detect warning conditions from review-board, cadence, stability, queue, worker, telemetry, or lock surfaces.
2. Classify the condition as advisory, warning, halt, or rollback-triggering.
3. Notify the operator lead and the governance reviewer immediately.
4. Freeze pilot progression if the issue cannot be confirmed as read-only or staging-only.
5. Escalate to rollback if the condition could obscure workflow state, endanger isolation, or imply a live-capable action path.
6. Record the escalation outcome in the staging evidence trail.

## Rollback activation workflow

- Rollback may be activated only by an operator who can verify the affected pilot cycle is still reversible.
- Rollback must preserve evidence packs, governance exports, and review-board history.
- Rollback must not use production credentials, production queues, or production databases.
- Rollback must return the staging pilot state to the last known safe dry-run or rehearsal state.
- If rollback cannot be verified as safe, the pilot must remain halted.

## Operational halt workflow

- Any operator may request an operational halt when risk increases.
- A halt freezes pilot progression and prevents further expansion.
- Halt conditions include stale telemetry, queue instability, worker instability, unresolved exceptions, missing submission locks, or NO-GO indicators.
- The halt state remains in effect until the operator lead and governance reviewer both agree the issue is resolved.

## Pilot-scope expansion rules

- Scope may only expand after a completed pilot cycle has a clean evidence pack, clean review-board status, and clean cadence validation.
- Scope expansion must be incremental and must never jump from a small supervised batch to an unattended broad rollout.
- Any new category or portal behavior must be treated as a new pilot scope and re-reviewed.
- Scope cannot expand if there are unresolved exceptions, warnings, or review-board items.

## Pilot RFQ category restrictions

- Start only with the safest categories already proven in rehearsal and review.
- Exclude categories with fragile portal behavior, ambiguous approval paths, or complex document formats.
- Exclude any category that requires production credentials or live portal assumptions.
- Any category not covered by the approved rehearsal and evidence artifacts remains out of scope.

## Controlled concurrency limits

- Concurrency must remain low and bounded.
- The initial pilot envelope should use single-cycle supervision.
- Queue and worker concurrency may only increase after repeated review-board and stability approval.
- Concurrency changes require governance review before use.

## Operational review cadence

- Conduct an operational review before the pilot window begins.
- Conduct a review after each pilot cycle completes.
- Conduct an additional review if any warning threshold is crossed.
- Review-board sessions should not be skipped to accelerate the pilot.

## Stability review cadence

- Review stability checkpoints at the same cadence as the operational review board.
- Compare readiness drift, cadence drift, queue stability, worker stability, telemetry health, retry frequency, DLQ frequency, and operator intervention trends.
- Any drift warning must be surfaced before the next pilot cycle begins.

## Telemetry review cadence

- Telemetry must be checked before pilot start, during execution, and after completion.
- Missing or stale telemetry is a halt condition.
- Telemetry review must include queue depth, worker heartbeats, retry activity, dead-letter visibility, and lock state.

## Evidence retention policy

- Retain pilot-cycle evidence, governance exports, review-board summaries, cadence history, and stability snapshots in staging-safe storage.
- Preserve operator acknowledgements, NO-GO summaries, rollback evidence, and escalation records.
- Do not purge evidence required for governance review or audit.
- Evidence retention must make it possible to reconstruct why a pilot proceeded, halted, or rolled back.

## Explicit pilot termination conditions

- Any live submission control becomes reachable.
- Submission locks fail or become unverifiable.
- Dry-run protections fail or become ambiguous.
- Telemetry becomes stale or fails to explain workflow state.
- Queue backlog, dead-letter growth, or worker instability exceeds the approved bounds.
- An unresolved operational exception or NO-GO indicator persists.
- The operator lead or governance reviewer requests termination.

## Explicit NO-GO escalation triggers

- A production database, queue host, or credential path appears anywhere in the pilot evidence chain.
- A live portal destination is detected.
- The review-board report shows unresolved exceptions.
- Cadence is overdue or missing.
- Readiness or stability trends fall below the approved threshold.
- Rollback safety cannot be confirmed.

## Operational anomaly response model

- Treat anomalies as operator-visible events first, not automatic control actions.
- Confirm whether the anomaly is advisory, warning, halt-worthy, or rollback-worthy.
- Preserve evidence and avoid destructive response actions.
- Prefer halting over trying to continue through unclear state.

## Governance override rules

- Governance override exists to protect the pilot, not to bypass safety checks.
- An override may only relax a non-destructive advisory recommendation after review.
- No override may bypass submission locks, dry-run protections, or production isolation.
- Any override must be recorded in the review-board evidence trail.

## Recommended starting posture

- Safest initial pilot scope: the smallest approved batch already proven in rehearsal.
- Safest operator staffing model: one operator lead plus one independent reviewer.
- Safest pilot duration: a short, bounded window that covers one complete supervised cycle.
- Safest rollout progression: rehearsal, shadow, controlled pilot, then measured expansion only after repeated clean reviews.

## Constraint

This program is a governance framework only. It does not change runtime behavior, queue topology, workflow orchestration, or submission authority.
