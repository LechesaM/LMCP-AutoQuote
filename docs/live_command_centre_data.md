# Live Command Centre Data

This branch upgrades the Command Centre dashboard from static mock values to read-only telemetry backed by existing LMCP runtime and persistence services.

## Live telemetry sources

- `GET /telemetry/dashboard`
- `GET /telemetry/source-health`
- `GET /telemetry/review-queue`
- `GET /telemetry/qualification`
- `GET /telemetry/operational-health`

The backend reads from existing runtime and persistence services, including:

- dashboard summaries
- workflow summaries
- queue summaries and history
- source registry and source health records
- pilot readiness and operational reports
- qualification summaries
- pricing confidence summaries
- persistence health snapshots

## `data_source` meanings

- `runtime`: the response was assembled from live runtime services
- `persistence`: the response was assembled from persisted operational records
- `mixed`: both runtime and persistence inputs were used
- `fallback`: no dependable runtime data was available, so safe zero/default values were returned

## Fallback behavior

- The frontend keeps the last known telemetry if a request fails
- Missing or malformed API responses are normalized into safe fallback values
- No telemetry endpoint mutates workflow state
- No endpoint triggers quote generation, submission, or approval actions

## Stale and refresh behavior

- The frontend polls telemetry every 30 seconds
- Stale data is visibly marked in the dashboard and operational health panel
- Refresh errors remain non-blocking and preserve the last known state

## Operator capacity assumptions

- Team size: 10 operators
- Maximum review capacity per operator: 100 RFQs per day
- Total review capacity: 1,000 RFQs per day

These values are advisory telemetry defaults and are not used to bypass governance controls.

## Frontend display behavior

- The dashboard shows a live-vs-fallback badge
- The dashboard shows last updated time and stale/refreshing state
- The operational health panel shows the telemetry source and fallback mode when applicable
- Metric cards remain read-only and reflect backend values only

## Governance preservation

- Manual approval remains mandatory
- `review_ready` remains mandatory
- Proof capture remains mandatory
- Final submission remains manual-only
- No autonomous workflow transition was introduced
- No workflow transition rule was changed
- No pricing threshold was changed

