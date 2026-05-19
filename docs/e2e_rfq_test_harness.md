# E2E RFQ Test Harness

## Purpose

This harness validates that LMCP AutoQuote can move a real or simulated RFQ through the governed manual-production lifecycle without changing procurement execution logic.

It is a validation layer only. It does not enable autonomous submission, does not bypass approval controls, and does not change tender filtering or pricing thresholds.

## Fixture Format

Fixtures are JSON files under `tests/fixtures/rfqs/`.

Supported fields:

- `tender_id`
- `title`
- `buyer_name`
- `province`
- `category`
- `closing_date`
- `source_files`
- `line_items`
- `expected_exclusion_status`
- `expected_minimum_profit_result`
- `expected_submission_ready`

Fixture folders may also contain referenced source documents such as PDFs or pricing schedules.

## Lifecycle Validation

The harness exercises the governed lifecycle:

- `discovered`
- `extracted`
- `evaluated`
- `priced`
- `quote_generated`
- `approval_required`
- `approved`
- `review_ready`
- `proof_recorded`

It also validates refusal and archive paths where the RFQ is blocked.

## Refusal Validation

RFQs are refused when the harness detects:

- excluded tender categories
- missing source documents
- pricing below the configured thresholds

Refusal is recorded through the workflow engine and remains append-only.

## Failure Injection

The harness includes failure injection helpers for:

- missing source file
- missing pricing file
- DB write unavailable
- malformed JSON fixture
- invalid workflow transition
- interrupted lifecycle
- missing quote pack

Failure injection is diagnostic only. It must not bypass manual approval or corrupt workflow state.

## Readiness Report

The readiness report summarizes:

- total fixtures
- passed fixtures
- refused fixtures
- failed fixtures
- workflow correctness rate
- persistence verification rate
- audit verification rate
- common blockers
- manual-production safety status

It returns JSON-safe data and a human-readable text summary.

## Running Tests

Run the harness test directly with:

```bash
python3 -m pytest tests/test_e2e_rfq_harness.py
```

The branch validation sweep also reruns the runtime, workflow, service, persistence, monitoring, and dashboard tests.

## Adding Real RFQ Fixtures

To add a real RFQ fixture:

1. Add a JSON fixture to `tests/fixtures/rfqs/`.
2. Add any source document references relative to the fixture file.
3. Keep the fixture aligned with the governed manual-production lifecycle.
4. Do not add fixtures that enable autonomous submission.

## Governance Rule

The harness must never enable autonomous submission.

Manual-production governance remains authoritative, and the harness only verifies that the system still behaves correctly under that governance.
