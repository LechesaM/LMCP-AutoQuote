# Queue Orchestration Baseline

## Purpose
This document describes the queue orchestration layer for LMCP AutoQuote in manual-production mode. It exists to coordinate bounded background work, retries, recovery, and operator-visible queue state without enabling autonomous procurement execution.

## Architecture
- Queue jobs are append-only records stored in JSONL and SQLite.
- Workflow state remains governed by `app/core/workflow_state_engine.py`.
- Monitoring and dashboard services read queue state but do not mutate it.
- Recovery actions are explicit and operator-governed.

## Job Types
- `rfq_extraction`
- `pricing`
- `quote_generation`
- `approval_tracking`
- `submission_review`
- `proof_capture`
- `workflow_recovery`
- `integrity_check`

## Queue Statuses
- `queued`
- `running`
- `completed`
- `failed`
- `retry_pending`
- `blocked`
- `archived`

## Retry Philosophy
- Retries are bounded.
- Infinite retries are not allowed.
- Approval, review, and proof jobs remain governed.
- Final submission jobs are not part of the queue orchestration model.
- Retryable failures are classified conservatively.

## Blocked Job Handling
- Blocked jobs are visible to operators.
- Blocked jobs must not auto-retry.
- Blocked jobs may be archived or retried only through operator-approved recovery actions.

## Recovery Process
- Recovery starts with queue and workflow scans.
- Stuck jobs are surfaced for human review.
- Workflow recovery never skips stages.
- Recovery never enables final submission automation.

## Operator Responsibilities
- Review stalled, failed, and blocked jobs.
- Decide whether a job should be retried, blocked, or archived.
- Confirm workflow recovery actions explicitly.
- Preserve append-only history and audit evidence.

## Safeguards
- No autonomous final submission.
- No bypass of manual approvals.
- No bypass of review-ready or proof-capture governance.
- No uncontrolled concurrency.
- No destructive cleanup.

