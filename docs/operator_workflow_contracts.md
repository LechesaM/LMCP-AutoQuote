# Operator Workflow Contracts

## Purpose

The operator workflow surface provides read-only operational visibility for:

- RFQ workflow rows and detail views
- qualification insights
- pricing evidence
- source health detail

These contracts are intended for the Command Centre frontend and for operator review only.

## Endpoints

- `GET /operations/rfqs`
- `GET /operations/rfqs/{tender_id}`
- `GET /operations/qualification-insights`
- `GET /operations/pricing-evidence`
- `GET /operations/source-health-details`

## Read-Only Guarantee

The endpoints are read-only.

They do not:

- create jobs
- change workflow state
- generate quotes
- submit tenders
- bypass approval gates
- bypass `review_ready`
- bypass proof capture

## Telemetry Sources

The contract layer reads from existing runtime sources where available:

- workflow repository
- dashboard summaries
- qualification engine summaries
- pricing evidence and traceability reports
- source registry and source health
- queue and monitoring summaries
- pilot readiness reporting

## Fallback Behavior

If runtime data is missing or incomplete, the contracts return safe fallback responses with:

- JSON-safe values
- zero/default counts
- `data_source = "fallback"`

The frontend should keep the last known state visible and show fallback mode when live data is unavailable.

## Governance Preservation

The operator workflow surface remains advisory and controlled.

Manual approval, `review_ready`, proof capture and final submission remain human-governed.

## Operational Limits

- No autonomous final submission
- No workflow transition changes
- No pricing threshold changes
- No duplicate routers
- No write actions from the Command Centre frontend
