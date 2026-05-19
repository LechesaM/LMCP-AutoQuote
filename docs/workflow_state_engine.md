# Workflow State Engine

## Purpose

The workflow state engine is the single source of truth for LMCP AutoQuote workflow progression in manual production.

It records workflow events and current-state snapshots in append-only JSONL files under `runtime/manual_production` and supplements, rather than replaces, the existing manual approval, submission review, and proof logs.

## Stages

The engine recognizes these stages:

- `discovered`
- `extracted`
- `evaluated`
- `priced`
- `quote_generated`
- `approval_required`
- `approved`
- `review_ready`
- `proof_recorded`
- `refused`
- `archived`

## Allowed Transitions

Forward transitions:

- `discovered -> extracted`
- `extracted -> evaluated`
- `evaluated -> priced`
- `priced -> quote_generated`
- `quote_generated -> approval_required`
- `approval_required -> approved`
- `approved -> review_ready`
- `review_ready -> proof_recorded`

Controlled exit transitions:

- any active stage -> `refused`
- `refused -> archived`
- `proof_recorded -> archived`

Disallowed transitions include:

- backwards movement outside the refusal/archive path
- `review_ready` without first being `approved`
- `proof_recorded` without first being `review_ready`
- `quote_generated` without first being `priced`
- any autonomous final-submission stage or handoff

## Manual-Production Workflow

Manual production remains human governed:

- approval is still explicit
- submission review still depends on approval
- proof capture still depends on review readiness
- final submission remains manual-only

The workflow engine supplements the existing JSONL logs:

- `approvals.jsonl`
- `submission_reviews.jsonl`
- `submission_proofs.jsonl`

It does not replace them yet.

## Refusal And Archive Behavior

`refuse_workflow()` records a terminal refusal for any active stage.

`archive_workflow()` is only valid after `refused` or `proof_recorded`.

This keeps the workflow history append-only while still allowing closed-out records to be marked as archived.

## Audit And Event Logging

Every recorded workflow transition appends:

- a workflow event row
- a workflow state snapshot row

When available, the engine also emits an audit-trail event using the existing audit format so downstream observability stays compatible.

## No Autonomous Final Submission

This branch does not enable autonomous final submission.

The engine models the manual production handoff only, and no transition in this state machine bypasses human approval or manual submission handling.
