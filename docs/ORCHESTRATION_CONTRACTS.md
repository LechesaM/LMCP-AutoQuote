# Orchestration Contracts

## Purpose
Define the ownership, boundaries, and handoff contracts for LMCP orchestration before any future isolation or refactor. This document is intentionally descriptive and does not change runtime behavior.

## Ownership model

### RFQ lifecycle ownership
- Acquisition owns discovery and harvest initiation.
- Intelligence owns document parsing, normalization, and structured extraction.
- Commercial owns pricing, adjudication, and approval preparation.
- Submission owns portal automation, submission packaging, and receipt capture.
- Governance owns telemetry, recovery, supervision, retry visibility, and operational control surfaces.

### Queue ownership
- Acquisition queues own ingestion and harvest-related work.
- Intelligence queues own extraction and document-processing work.
- Commercial queues own pricing and review work.
- Submission queues own packaging, upload, and submission work.
- Governance queues own operational recovery, supervision, and dead-letter oversight.

### Retry ownership
- Retry policy is a governance concern, but retry execution belongs to the owning workflow domain.
- Acquisition retries must not mutate commercial or submission state.
- Intelligence retries must not trigger submission.
- Commercial retries must not auto-submit.
- Submission retries must never bypass approval or go-live guards.

### Dead-letter ownership
- Dead-letter queues are governed operational artifacts.
- The domain that produced the failure owns the business context of the item.
- Governance owns visibility, archive state, and recovery reporting.
- Dead-letter recovery must not silently change business outcomes.

### Failure escalation ownership
- Domain failures are first owned by the producing service.
- Governance owns escalation visibility and operational intervention surfaces.
- Manual intervention requirements belong to the domain that controls the irreversible step.

### State transition authority
- Acquisition is authoritative for discovery and harvest state.
- Intelligence is authoritative for extraction and normalization state.
- Commercial is authoritative for pricing and adjudication state.
- Submission is authoritative for submission and receipt state.
- Governance is authoritative for operational state, not business state.

### Workflow completion authority
- Business completion authority belongs to the last domain that can safely prove completion of its work.
- Submission owns final completion when a portal submission or equivalent irreversible action is completed.
- Governance may report operational completion, but it does not author business completion.

## Service contracts

### Acquisition → Intelligence
#### Contract
- Acquisition produces discovered tender records, source metadata, and raw document references.
- Intelligence consumes those artifacts and returns normalized document and extraction outputs.

#### Required payload fields
- `tender_id`
- `source_id`
- `discovered_at`
- `source_url`
- `document_refs`
- `correlation_id`

#### Rules
- Payloads must be idempotent.
- Missing source metadata must fail closed.
- Acquisition must not embed pricing or submission decisions in the handoff.

### Intelligence → Commercial
#### Contract
- Intelligence produces structured BOQ, normalized documents, and extraction confidence signals.
- Commercial consumes those artifacts to price, validate, and prepare approval material.

#### Required payload fields
- `tender_id`
- `correlation_id`
- `extraction_status`
- `normalized_documents`
- `boq_rows`
- `confidence_scores`
- `validation_warnings`

#### Rules
- Commercial must not assume extraction completeness unless explicitly flagged.
- Low-confidence extraction must remain visible in the payload.
- Intelligence must not initiate commercial approval or submission.

### Commercial → Submission
#### Contract
- Commercial produces pricing decisions, review outcomes, and approval-ready quote material.
- Submission consumes only approved or explicitly go-live-authorized artifacts.

#### Required payload fields
- `tender_id`
- `correlation_id`
- `pricing_status`
- `approval_status`
- `quote_pack_refs`
- `submission_readiness`
- `go_live_guard`

#### Rules
- Submission must fail closed when approval or go-live guards are missing.
- Commercial must not auto-trigger portal submission.
- Pricing decisions must remain auditable and traceable.

### Submission → Governance
#### Contract
- Submission emits portal execution state, proof artifacts, receipts, and failure outcomes.
- Governance consumes those signals for health, audit, recovery, and operational visibility.

#### Required payload fields
- `tender_id`
- `correlation_id`
- `submission_status`
- `receipt_refs`
- `proof_refs`
- `failure_reason`
- `operator_action_required`

#### Rules
- Governance must not mutate submission outcomes.
- Submission failures that are irreversible must be surfaced as such.
- Governance may recommend recovery actions but does not perform business completion.

## Event payload contracts
- Every orchestration event should include `correlation_id`, `tender_id`, `source_domain`, `event_type`, `event_at`, and `status`.
- Failure events should include `failure_category`, `retry_eligible`, and `operator_action_required`.
- Handoff events should include `from_state`, `to_state`, and `handoff_result`.
- DLQ events should include `dlq_id`, `source_job_id`, and `archive_status`.

## Boundary rules
- A service may read the next service’s outputs only through the documented handoff contract.
- A service may not write another service’s authoritative state directly.
- Operational telemetry may aggregate across services, but operational helpers must not become business-process owners.
- Shared runtime state should be read-only from the perspective of downstream consumers unless a contract explicitly allows mutation.

## Idempotency requirements
- Handoff payloads must be replay-safe.
- Queue jobs must be idempotent by explicit idempotency key where supported.
- Retry actions must not duplicate irreversible operations.
- Recovery actions must be safe to re-run without changing business meaning.

## Retry semantics
- Retry should be bounded by attempt limits and explicit retry policies.
- Retry should preserve correlation IDs and original failure reasons.
- Retry should not skip approval, validation, or go-live guards.

## Timeout semantics
- Timeouts should be advisory for orchestration monitoring but strict for irreversible operations.
- A timeout must not silently convert a failed irreversible step into success.
- Timeout behavior should surface to governance as a recoverable or terminal condition.

## Escalation semantics
- Escalation should move from automatic retry to operator review, then to dead-letter retention if needed.
- Escalation must be explicit in telemetry and not hidden inside a retry loop.
- Manual intervention should be required for submission-side irreversible failures and approval bypass risks.

## Risk analysis

### Unsafe shared ownership
- Queue helpers that are used by multiple domains without explicit ownership.
- Telemetry helpers that also mutate operational state.
- Retry helpers that are shared across business workflows and governance surfaces.

### Orchestration ambiguity
- Overlapping ownership between queue state and workflow state.
- Retry actions that can be interpreted as both operational recovery and business re-execution.
- DLQ items that are not clearly labeled as operational artifacts.

### Hidden state mutation risks
- File-backed snapshots that are also used as live operational truth.
- Shared helpers that append audit or queue records as side effects.
- Workflow recovery helpers that mutate state during read paths.

### Circular orchestration dependencies
- Dashboard services depending on workflow queue helpers that also depend on dashboard-visible state.
- Telemetry helpers importing workflow execution helpers.
- Recovery helpers depending on monitoring helpers that in turn depend on queue state.

## Recommended future path

### Orchestration extraction sequence
1. Extract read-only orchestration tracing and reporting helpers.
2. Separate queue telemetry from queue mutation helpers.
3. Separate retry policy from retry execution.
4. Separate dead-letter reporting from dead-letter mutation.
5. Only then isolate orchestration control-plane execution.

### Event-driven evolution strategy
- Emit canonical orchestration events at each queue transition and workflow handoff.
- Build downstream dashboards and recovery tools from events rather than direct mutation helpers.
- Keep event payloads append-only and correlation-safe.

### Safe queue partitioning strategy
- Partition queues by domain ownership first, then by workflow stage.
- Keep governance-only queues read-heavy and mutation-light.
- Avoid splitting a queue before its owner service has an explicit contract for retries and recovery.

## Constraint
- This document defines contracts only. No runtime behavior, queue semantics, or service ownership changes are made here.

