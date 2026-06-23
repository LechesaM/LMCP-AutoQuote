# Staging and Pilot Enablement Plan

## Purpose
Define how LMCP should be enabled for staging and pilot use before any broader production rollout. This plan is operational guidance only and does not change runtime behavior.

## Staging rollout sequence
1. Stand up staging with the same runtime topology as production.
2. Enable read-only telemetry and health visibility first.
3. Validate dry-run acquisition, extraction, pricing, and submission handoffs.
4. Run shadow submission execution against non-production targets or no-op targets.
5. Validate operator review and escalation workflows.
6. Promote only after telemetry, rollback, and audit review criteria are met.

## Dry-run workflow execution model
- Dry-run should exercise the workflow contract end to end without triggering irreversible actions.
- Dry-run outputs should include correlation IDs, stage transitions, and approval checkpoints.
- Dry-run should be clearly labeled and separated from live operational state.

## Shadow submission execution model
- Shadow submission should mirror submission packaging and orchestration without transmitting live portal submissions.
- Shadow execution should capture proof, receipt, and telemetry surfaces for comparison.
- Shadow outcomes should never be interpreted as live completion.

## Operator review workflow
- Operators review telemetry, workflow state, DLQ state, and submission readiness before approval.
- Operator review should be mandatory for any step that can affect an irreversible action.
- Review outcomes should be captured in audit records and visible in operational reports.

## Telemetry dashboard requirements
- RFQ lifecycle progress.
- Queue depth, retry backlog, and DLQ counts.
- Worker heartbeat and stale-worker visibility.
- Submission readiness and go-live guard status.
- Last safe snapshot and stale-data warnings.
- Correlation-aware event history for the active pilot window.

## Pilot procurement category selection
- Choose categories with low submission risk and clear approval rules.
- Prefer categories with stable document formats and predictable portal behavior.
- Avoid categories with ambiguous approval chains or highly variable submission requirements.

## Approval and escalation workflow
- Approval should be required before any irreversible or externally visible submission action.
- Escalation should occur when telemetry indicates stale data, queue blockage, DLQ growth, or worker instability.
- Operator escalation should be visible before the system retries an unsafe action.

## Pilot rollback strategy
- Rollback should return the environment to the last known safe deployment and runtime snapshot.
- Rollback should not delete proof, audit, or queue evidence.
- Rollback should disable live submission while preserving investigative visibility.

## Operational audit review cadence
- Daily review during pilot warm-up.
- Immediate review after any failed submission, DLQ spike, or worker degradation.
- Weekly review of telemetry trends, retry behavior, and approval outcomes.

## Success metrics for pilot rollout
- Low or declining failure rate across acquisition, extraction, pricing, and submission.
- Stable queue depth and worker heartbeat behavior.
- High correlation completeness across telemetry and audit records.
- No unauthorized irreversible submission events.

## Acceptable failure thresholds
- Minor transient retries are acceptable if they remain visible and bounded.
- Any unexplained submission failure or approval bypass is not acceptable.
- DLQ growth and stale-worker events must remain below agreed operational thresholds.

## Operator intervention thresholds
- Queue congestion beyond normal operating capacity.
- Repeated retry failures for the same RFQ or workflow stage.
- Any stale-data warning on a workflow approaching submission.
- Any ambiguity around approval, receipt, or portal submission outcome.

## Submission approval checkpoints
- Extraction confidence review.
- Pricing validation review.
- Approval/go-live guard verification.
- Submission packaging review.
- Final human sign-off before live portal execution.

## Safest initial pilot size
- Start with a very small number of RFQs or a single low-risk procurement category.
- Prefer pilot scope that can be supervised end to end by the operator team.

## Safest user/operator group
- A small, experienced operations group with direct access to telemetry and approval controls.
- Operators should already understand queue recovery, DLQ handling, and submission review.

## Safest rollout progression model
1. Shadow mode.
2. Dry-run staging.
3. Limited pilot with human supervision.
4. Expand only after metrics remain stable and rollback criteria are confirmed.

## Constraint
- This plan is documentation only. It does not change orchestration, queue topology, or workflow behavior.

