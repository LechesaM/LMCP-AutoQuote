# Core Domain Schemas

This document defines the central domain contract layer introduced on `branch-c-core-domain-schemas`.

## Purpose

The domain layer provides stable typed contracts for RFQ, supplier, pricing, quote, submission, workflow, and audit data.

It is intended to:

- normalize payload shape expectations
- reduce ad hoc dictionary contracts
- preserve current business behavior while preparing service-layer refactoring
- keep manual-production governance explicit

This layer is contract-focused only. It does not introduce new business features or change existing workflow policy.

## Core schemas

- `app/domain/base.py`
  - `StrictBaseModel`
  - UTC datetime helper
  - safe string normalization helper
  - amount normalization helper
  - JSON-serializable dump helper
- `app/domain/rfq.py`
  - `RFQDocument`
  - `RFQLineItem`
  - `RFQEvaluation`
  - `RFQRecord`
- `app/domain/supplier.py`
  - `SupplierRecord`
  - `SupplierQuote`
  - `SupplierQuoteLine`
- `app/domain/pricing.py`
  - `PricingLineItem`
  - `PricingSchedule`
  - `PricingDecision`
- `app/domain/quote.py`
  - `QuotePackArtifact`
  - `QuotePack`
  - `BuyerPricingScheduleCompletion`
- `app/domain/submission.py`
  - `ApprovalRecord`
  - `SubmissionReview`
  - `SubmissionPack`
  - `SubmissionProof`
- `app/domain/workflow.py`
  - `WorkflowEvent`
  - `WorkflowStage`
  - `WorkflowState`
  - `WorkflowTransition`
- `app/domain/audit.py`
  - `AuditActor`
  - `AuditEvent`
  - `AuditSeverity`

## Manual-production workflow contract

The submission contracts preserve the current human-governed flow:

- manual approval must remain explicit
- `manual_approval_recorded` and `approved_by_operator` remain separate fields
- `submission_ready` is distinct from `submission_review_ready`
- `final_submission_attempted` remains false through the manual approval, review, and proof-capture stages by default
- `manual_submission_recorded` is only represented after proof capture succeeds

## Pricing rule contract

`PricingDecision` preserves the current pricing thresholds:

- minimum profit requirement: `R30,000`
- minimum supply margin ratio: `25%`
- refusal reasons are represented explicitly in `refusal_blocker_reasons`

These contracts do not change the existing pricing policy. They only formalize the payload shape.

## Submission governance contract

- final submission remains manual-only
- legacy routers remain disabled by default
- manual-production workflow state remains explicit and serializable
- services should validate or serialize through domain contracts when touching submission governance state

## Guidance going forward

- Services should use these schemas as the source of truth for payload shape.
- New service-layer refactors should prefer typed validation over ad hoc dictionary contracts.
- Business behavior must remain anchored in the existing production-safe workflow and router/runtime baselines.
