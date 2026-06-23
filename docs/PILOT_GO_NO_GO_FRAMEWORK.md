# Pilot Go/No-Go Framework

## Purpose
Define the formal operational go/no-go framework for any controlled pilot operations. This document is documentation only and does not enable live submissions, remove dry-run protections, use production credentials, or redesign orchestration.

## Mandatory readiness criteria
- Dry-run protections remain enforced in the official runtime and staging runtime.
- Submission locks and go-live guards are active and observable.
- Shadow-mode and rehearsal programs have completed successfully for the target workflow path.
- The staging environment is isolated from production database, queue, storage, and credentials.
- Backend health and status endpoints are reachable and stable.
- Command Centre visibility surfaces are functioning and read-only.
- Recovery and rollback procedures are documented, tested, and available to operators.

## Telemetry readiness requirements
- Structured logging is active for request, worker, RFQ lifecycle, and operational events.
- RFQ correlation IDs are present across request, task, and workflow traces.
- Queue depth, worker heartbeat, retry, and dead-letter visibility are available.
- Telemetry is fresh enough to detect stale worker or stale workflow conditions.
- Operational dashboards surface staging status, warnings, and lock state.
- Missing or stale telemetry must fail closed for pilot approval.

## Queue health requirements
- Queue backlog must remain below the documented warning threshold.
- No unexplained queue growth may exist in pending, retry, or dead-letter states.
- Queue transitions must remain visible and attributable.
- Recovery and retry behavior must be bounded and auditable.
- Queue isolation from production must be confirmed before pilot approval.

## Worker stability requirements
- Worker heartbeats must be present and fresh.
- Worker restart and crash counts must remain within acceptable rehearsal bounds.
- No worker queue starvation or persistent stalled task condition may exist.
- Worker concurrency must remain within the approved pilot envelope.
- Any worker instability beyond the rehearsal baseline is a no-go.

## Rollback readiness requirements
- Rollback steps must be known, tested, and available to operators.
- The last safe dry-run or rehearsal state must be recoverable.
- Proof, audit, and guard evidence must be preserved during rollback.
- Rollback must not depend on production credentials or live portal actions.
- If rollback cannot be completed safely, the pilot is a no-go.

## Operator staffing requirements
- A named operator lead must be available for the pilot window.
- At least one additional reviewer should be available for approval and escalation.
- Operators must have access to telemetry, guard, audit, and queue surfaces.
- Operators must be able to halt the pilot immediately if risk increases.
- Staffing gaps or unclear responsibility are a no-go.

## Escalation readiness requirements
- Escalation paths for queue congestion, worker loss, telemetry outages, and dead-letter growth must be defined.
- Operators must know when to pause, rollback, or halt the pilot.
- Emergency contacts and responsibilities must be documented and current.
- Escalation tooling or surfaces must be reachable before the pilot begins.
- Missing escalation readiness is a no-go.

## Audit readiness requirements
- Rehearsal records, approvals, rollbacks, and warnings must be retained.
- Pilot-related state transitions must be auditable end-to-end.
- Evidence artifacts must be retained in staging-safe storage.
- Audit trails must clearly distinguish rehearsal, shadow, and pilot activity.
- Incomplete audit readiness is a no-go.

## Explicit NO-GO conditions
- Any live submission control is exposed or can be reached.
- Any production credential, production queue host, or production database reference is present.
- Submission locks or go-live guards are missing, bypassed, or unverifiable.
- Telemetry is stale, missing, ambiguous, or partially unavailable in a way that hides workflow state.
- Queue backlog, dead-letter growth, or worker instability exceeds documented thresholds.
- Rollback cannot be performed safely and predictably.
- Operator staffing or escalation coverage is insufficient.

## Explicit pilot halt conditions
- A live portal destination is detected or becomes reachable.
- A submission-lock state changes unexpectedly.
- Worker heartbeats disappear or become stale beyond the threshold.
- Queue depth grows beyond the warning threshold and does not stabilize.
- A dead-letter item appears without a documented recovery path.
- Telemetry can no longer explain workflow state or queue state.
- Any operator requests a halt for risk containment.

## Emergency rollback conditions
- A submission-related action cannot be clearly verified as dry-run or shadow-mode only.
- A portal upload or submission path appears to be live-capable.
- Any external side effect cannot be guaranteed to remain non-production.
- A catastrophic telemetry or queue failure obscures workflow state.
- A live submission lock or go-live guard is compromised.

## Telemetry failure thresholds
- Any missing critical telemetry surface for the pilot workflow is a no-go.
- A stale worker heartbeat beyond the documented freshness window is a halt condition.
- A stale queue or dead-letter feed that obscures active risk is a halt condition.
- If telemetry cannot distinguish dry-run, shadow, and pilot state, the pilot must stop.

## Retry storm thresholds
- Repeated retries that exceed the documented rehearsal baseline are a halt condition.
- Retry growth that threatens queue stability or hides the root cause is a no-go.
- Retry behavior must stay bounded, visible, and attributable.
- Any unbounded retry loop is an emergency rollback condition.

## Dead-letter thresholds
- Any dead-letter growth beyond the rehearsal baseline is a no-go until reviewed.
- Dead-letter items must remain visible and attributable.
- Dead-letter handling must not be destructive or auto-purging.
- Unexplained dead-letter movement is a halt condition.

## Final approval workflow
1. Confirm mandatory readiness criteria are met.
2. Confirm telemetry, queue, worker, rollback, operator, escalation, and audit requirements are satisfied.
3. Review rehearsal evidence and sign off on the pilot scope.
4. Record the final approval decision and the named approvers.
5. If any gate fails, record a NO-GO and halt the pilot.

## Operational sign-off responsibilities
- Operator lead signs off on the operational readiness of the rehearsal and pilot window.
- Governance owner signs off on telemetry, guard, and audit sufficiency.
- Platform owner signs off on runtime isolation, rollback, and worker stability.
- No single person should override all sign-off responsibilities without escalation.

## Rehearsal completion requirements
- Dry-run, shadow-mode, and controlled rehearsal plans are complete for the intended workflow.
- Recovery, rollback, and halt drills have been exercised.
- Evidence artifacts for rehearsal execution and operator review are retained.
- Any unresolved rehearsal defect blocks pilot approval.

## Required evidence artifacts
- Dry-run execution harness report.
- Operational visibility surfaces report.
- Shadow-mode submission rehearsal plan and rehearsal records.
- Controlled operational rehearsal program record.
- Telemetry snapshots showing worker, queue, and lifecycle health.
- Guard summary proving locks and go-live protections remain active.
- Rollback and escalation evidence from rehearsal runs.

## Safest first live pilot scope
- Start with the smallest possible pilot batch.
- Use RFQs in the safest procurement categories already proven in rehearsal.
- Restrict the pilot to low-risk, stable document structures.
- Keep the scope small enough for manual operator review of every item.

## Safest procurement categories
- Supply-and-delivery RFQs with simple documentation and no ambiguous portal behavior.
- Categories already exercised successfully in dry-run and shadow-mode rehearsal.
- Avoid categories that introduce complex portal flows, unclear approvals, or fragile document formats.

## Safest concurrency limits
- Start with a single RFQ or a very small batch.
- Keep worker concurrency low and bounded.
- Increase concurrency only after queue and worker stability are proven.

## Safest operator supervision model
- Use a named operator lead and a second reviewer for the pilot window.
- Keep the pilot under active human supervision with explicit halt authority.
- Require immediate access to telemetry, guards, audit, queue, and rollback surfaces.
- Do not allow unattended execution for the first pilot scope.

## Constraint
This framework is documentation only. It does not change orchestration, queue topology, runtime behavior, or submission authority.
