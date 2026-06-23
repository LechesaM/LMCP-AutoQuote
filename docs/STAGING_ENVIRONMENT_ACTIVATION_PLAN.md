# Staging Environment Activation Plan

## Purpose
Define the first controlled staging runtime for LMCP operational validation. This plan is documentation only and does not change orchestration behavior or enable live submissions.

## Staging runtime topology
- Backend API runs in a staging deployment identical in shape to production but pointed at isolated staging dependencies.
- Frontend dashboard connects only to the staging backend.
- Celery workers run against staging queues and staging broker settings only.
- PostgreSQL is staging-isolated and must not share data with production.
- Telemetry and logging remain enabled for staging so operators can validate behavior end to end.
- Object and document storage must be staging-isolated and non-production.

## Isolated database strategy
- Use a dedicated staging database instance or schema namespace.
- Seed only sanitized or synthetic data.
- Prevent staging from reading or writing production runtime state.
- Keep audit and queue artifacts isolated by environment.

## Isolated queue strategy
- Use staging queue names or a dedicated broker namespace.
- Prevent staging workers from consuming production jobs.
- Keep retry, DLQ, and recovery state isolated from production queues.

## Isolated storage and runtime paths
- Use staging-specific runtime directories for logs, queue snapshots, proofs, and temporary artifacts.
- Do not reuse production runtime paths.
- Keep staging object storage and document storage separate from production runtime evidence.

## Staging telemetry activation
- Enable structured logs, request correlation, worker heartbeats, queue telemetry, and DLQ visibility.
- Staging telemetry should be reviewed against the same operational expectations as production telemetry.
- Telemetry should clearly label staging-origin data.

## Dry-run execution controls
- Dry-run mode must prevent irreversible submission behavior.
- Dry-run should still validate the orchestration contract, approvals, packaging, and visibility surfaces.
- Dry-run outputs should be clearly marked and retained separately from live results.

## Submission safety locks
- Submission safety locks must prevent live portal submissions in staging.
- Approval gates and go-live guards should remain visible but not executable against real portals.
- Any staging submission attempt should fail closed if the environment is not explicitly dry-run.

## Operator access controls
- Limit access to authorized staging operators.
- Require visibility into health, status, queue, worker, and DLQ surfaces.
- Keep submission and approval actions reviewable even in staging.

## Staging secrets handling
- Use staging-only secrets and credentials.
- Never reuse production portal credentials.
- Store secrets outside the repository and rotate them independently from production.

## Required staging services
- Backend API.
- Frontend dashboard.
- Celery workers.
- Queue broker.
- PostgreSQL.
- Telemetry and logging surfaces.
- Object/document storage.

## Staging startup sequence
1. Provision isolated storage, database, broker, and runtime paths.
2. Start telemetry and logging surfaces.
3. Start PostgreSQL and confirm staging connectivity.
4. Start queue broker and workers.
5. Start the backend API.
6. Start the frontend dashboard.
7. Validate health, status, queue visibility, and dry-run protections.

## Staging validation checklist
- Health and status endpoints respond.
- Queue and worker telemetry are available.
- DLQ and recovery reporting are available.
- Dry-run mode is active and live submission is blocked.
- Portal isolation is confirmed.
- Logs and telemetry are tagged as staging.
- No production credentials are reachable from staging.

## Staging health criteria
- Backend, workers, and queue broker are reachable.
- PostgreSQL connectivity is healthy.
- Worker heartbeats are present.
- Queue depth and retry visibility are normal for staging load.
- No live submission path is available.

## Staging shutdown and recovery procedure
- Stop workers before stopping the broker if possible.
- Preserve queue snapshots, DLQ state, and logs before shutdown.
- On recovery, re-validate isolation, dry-run protection, and telemetry visibility before resuming validation.

## Explicit protections against live tender submission
- Use staging-only credentials and endpoints.
- Disable or guard live submission routes and execution paths in staging.
- Require dry-run enforcement and fail closed on any unexpected portal destination.

## Dry-run-only enforcement
- Dry-run mode must be explicit in configuration.
- Any attempt to execute a real submission in staging should be blocked and surfaced.
- Dry-run status should be observable in telemetry and logs.

## Portal isolation requirements
- Use sandbox portals or no-op portal targets for staging.
- Isolate browser automation from live portal accounts.
- Ensure portal navigation and upload flows cannot reach production submission endpoints.

## Safest first RFQ types
- Low-risk, low-volume RFQs with stable documents and clear approval paths.
- RFQs that can be fully exercised in dry-run without external side effects.

## Safest staging data volume
- Start with a very small data set sufficient to validate queue, telemetry, and workflow handoffs.
- Increase volume gradually only after stability and rollback behavior are confirmed.

## Safest operator workflow
- A small, experienced operator group with direct access to staging telemetry and review controls.
- Operators should supervise every dry-run and any step that approaches submission readiness.

## Constraint
- This plan defines staging activation only. It does not enable live production submissions or alter orchestration behavior.

