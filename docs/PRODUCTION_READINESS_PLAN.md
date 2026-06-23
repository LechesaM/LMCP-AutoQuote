# Production Readiness Plan

## Purpose
Define the controlled staging and production deployment strategy for LMCP before any future orchestration isolation or service migration. This document is operational guidance only and does not change runtime behavior.

## Environment architecture

### Staging environment architecture
- Mirrors the production runtime shape as closely as possible without exposing real submission targets.
- Uses the same service boundaries, queue surfaces, and telemetry contracts as production.
- Runs against non-production credentials, sandbox portals, or dry-run submission endpoints where possible.
- Preserves runtime snapshots, queue state, and telemetry so validation can compare staging behavior against production expectations.

### Production environment architecture
- Uses the official runtime with the documented backend, frontend, worker, queue, telemetry, and database contracts.
- Treats PostgreSQL as the canonical state store where already established, while preserving file-backed runtime artifacts for operational visibility.
- Keeps irreversible submission actions behind approval and go-live guards.

## Deployment topology
- Backend API, worker processes, and telemetry helpers should remain separately observable even if co-located in the same deployment stack.
- Database, broker, runtime filesystem, and portal credentials must be isolated from the application container boundary.
- Frontend should point at the official backend only and must not bypass runtime governance surfaces.

## Secrets management approach
- Secrets should be injected via environment configuration or secret manager, never committed to the repository.
- Portal credentials, database credentials, broker credentials, and any signing or receipt credentials must be environment-scoped.
- Dry-run and staging secrets must be clearly separated from production secrets.

## Backup and recovery strategy
- Maintain runtime snapshots for queue state, DLQ state, telemetry last-safe snapshots, and audit trails.
- Backups should be recoverable without mutating business state automatically.
- Recovery should favor explicit operator action over automatic replay when the action could affect submission or approval outcomes.

## Rollback strategy
- Rollback should revert deployment artifacts and runtime configuration without deleting audit evidence.
- Rollback must not auto-resubmit, repricing, or re-trigger irreversible submission steps.
- Any failed production change should be reversible to the last known safe runtime and telemetry state.

## Container and runtime isolation
- Separate API, worker, and support processes at the runtime boundary where possible.
- Keep queue and telemetry helpers available to all runtime roles but not as mutation owners across domains.
- Preserve file-system isolation between operational runtime artifacts and source-controlled assets.

## Operator access model
- Operators should have role-based access to health, status, queue, telemetry, and recovery surfaces.
- Submission and approval-related actions should remain restricted and reviewable.
- Production access should be auditable and limited to the minimum operational surface required.

## Audit retention model
- Retain workflow transitions, submission proofs, receipts, queue transitions, DLQ records, and recovery actions.
- Audit records should be append-only where feasible.
- Do not purge evidence needed to reconstruct a failed or partial workflow.

## Dry-run submission mode
- Dry-run mode should simulate submission contracts without transmitting live portal submissions.
- It should exercise approval checks, packaging, telemetry, and correlation tracking.
- Dry-run results should be explicitly labeled and never conflated with live completion.

## Shadow-mode execution strategy
- Shadow mode should compare real runtime state with a read-only validation view.
- It should not mutate queue, workflow, or submission state.
- Shadow mode should be used to validate orchestration visibility, telemetry, and contract stability before live changes.

## Production readiness gates
- Health and status endpoints are available and stable.
- Queue, worker, DLQ, and stale-data telemetry are visible.
- Correlation IDs are present in logs and operational reports.
- Submission dry-run and shadow-mode validation pass.
- Backups and recovery paths are verified.
- Operator intervention paths are documented and accessible.

## Go-live checklist
- Confirm staging validation matches expected workflow and telemetry behavior.
- Confirm secrets are correctly scoped and not shared between staging and production.
- Confirm operator access is limited and auditable.
- Confirm rollback paths are known and tested.
- Confirm approval and go-live guards are active for any irreversible action.
- Confirm DLQ and queue recovery reporting works before production rollout.

## Operational escalation model
- Transient operational issues should be handled through retry and observation.
- Persistent queue, worker, or telemetry issues should escalate to operator intervention.
- Submission-side ambiguity or irreversible failure should escalate immediately.
- DLQ growth or stale-state drift should trigger governance visibility and support review.

## Support and on-call model
- Support should cover backend health, queue visibility, worker supervision, and submission readiness.
- On-call responders should be able to inspect telemetry, retry artifacts, and recovery reports without modifying business data.
- Escalation should be documented by severity and ownership domain.

## Deployment approval workflow
- Changes should pass staging validation and shadow-mode checks before production approval.
- A production deployment should require explicit approval from the operational owner or equivalent authority.
- Deployment approval should be blocked when telemetry, backup, or rollback readiness is incomplete.

## Safest pilot rollout strategy
1. Start with shadow-mode and dry-run validation only.
2. Enable staging with non-production credentials and non-irrevocable workflows.
3. Roll out production to the safest low-risk operational slices first.
4. Expand only after queue health, telemetry, and rollback behavior are stable.

## Safest procurement categories for initial rollout
- Low-risk procurement categories with clear approval paths and limited submission complexity.
- Categories where dry-run validation closely matches live submission behavior.
- Categories where operator oversight can be maintained throughout the initial rollout.

## Human oversight requirements
- Human approval is required for irreversible submission steps.
- Human review is required when extraction confidence, pricing validation, or submission readiness is ambiguous.
- Human intervention is required for DLQ recovery decisions and any rollback that could affect final outcomes.

## Constraint
- This plan defines deployment and readiness strategy only. It does not alter orchestration, service boundaries, or workflow behavior.

