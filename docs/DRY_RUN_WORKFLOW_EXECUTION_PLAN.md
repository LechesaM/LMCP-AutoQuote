# Dry-Run Workflow Execution Plan

## Purpose
Define the first controlled dry-run workflow execution procedure for staging validation. This plan is documentation only and does not change orchestration behavior.

## First dry-run RFQ workflow sequence
1. Ingest a small set of low-risk RFQs into staging.
2. Validate acquisition and source metadata.
3. Run extraction and normalization.
4. Run pricing and review preparation.
5. Build submission-ready artifacts without performing a live submission.
6. Verify telemetry, queue state, audit events, and rollback visibility.

## Safest RFQ categories
- Low-risk RFQs with stable documents and predictable structures.
- Categories with simple approval paths and no ambiguous submission requirements.
- Categories that can be exercised without portal side effects.

## Ingestion validation steps
- Confirm source metadata is complete.
- Confirm correlation IDs are present.
- Confirm the RFQ enters the expected acquisition or queue state.
- Confirm no downstream pricing or submission state is advanced prematurely.

## Extraction validation steps
- Confirm documents are normalized successfully.
- Confirm BOQ or structured extraction outputs are produced.
- Confirm extraction confidence and warnings are visible.
- Confirm extraction failures stay within retry/review boundaries.

## Pricing validation steps
- Confirm pricing input is derived from extracted data only.
- Confirm validation and review state are visible.
- Confirm pricing outputs do not trigger live submission.
- Confirm any pricing warning produces an operator-visible checkpoint.

## Queue telemetry expectations
- Queue depth remains small and readable.
- Running, retry pending, blocked, failed, completed, and DLQ counts are visible.
- No unexpected backlog growth or hidden queue transitions.

## Worker telemetry expectations
- Worker heartbeat events are visible.
- Stale worker detection remains quiet under normal dry-run load.
- Worker logs carry correlation IDs and workflow stage context.

## Retry and recovery expectations
- Retry should be bounded and visible.
- Recovery actions must preserve correlation and audit evidence.
- DLQ movement should occur only when retry limits are exceeded or a step is explicitly unsafe.

## Rollback expectations
- Rollback should preserve audit, proof, and queue evidence.
- Rollback must not auto-reprocess to a live submission.
- Rollback should return the workflow to the last safe dry-run state.

## Operator checkpoints
- After ingestion.
- After extraction.
- After pricing.
- Before any submission-packaging step.
- Before any action that would normally precede portal submission.

## Manual approval points
- Approval of the dry-run start.
- Approval of each stage transition if the workflow exposes ambiguous state.
- Approval before any submission-ready artifact is generated.

## Escalation triggers
- Missing or stale telemetry.
- Queue congestion or retry storms.
- Worker heartbeat loss.
- Extraction confidence collapse.
- Any ambiguous submission-readiness result.

## Dry-run termination conditions
- Any attempt to use live portal submission.
- Any attempt to use live credentials.
- Any irreversible submission action.
- Any unsupported state transition or telemetry failure that hides workflow progress.

## Expected telemetry events
- `rfq_discovered`
- `rfq_extracted`
- `rfq_priced`
- `queue_transition`
- `worker_heartbeat`
- `retry_scheduled`
- `retry_executed`
- `dry_run_ready`
- `dry_run_blocked`
- `operator_checkpoint`
- `workflow_state_transition`

## Expected state transitions
- Acquisition to extraction handoff.
- Extraction to pricing handoff.
- Pricing to review-ready or blocked state.
- Dry-run completion without live submission.

## Expected queue behavior
- Jobs should move predictably through pending, running, retry pending, completed, or failed states.
- DLQ entries should appear only when retry limits are reached or an unsafe condition is detected.
- No queue should implicitly trigger live submission work.

## Expected audit events
- Dry-run start and end.
- Stage transition records.
- Operator checkpoint and approval records.
- Retry and recovery records.
- Rollback or termination records.

## Safest initial dry-run scale
- Start with a very small batch of RFQs, ideally one or a few items.
- Expand only after telemetry and rollback behavior are stable.

## Safest concurrency limits
- Keep concurrency low during initial validation.
- Prefer one worker or a very small worker set until the dry-run path is proven.

## Safest worker counts
- One backend worker and one operations-oriented worker at most for the first run.
- Increase only if queue visibility and retry behavior remain stable.

## Safest execution cadence
- Run dry-runs manually and infrequently at first.
- Increase cadence only after the operator review loop and rollback path are proven safe.

## Explicit prohibitions
- No live portal submission.
- No live credential usage.
- No irreversible submission actions.

## Constraint
- This plan is documentation only. It does not change orchestration, queue topology, or business logic.

