# Runtime Observability

Runtime observability provides read-only operational telemetry for supervised-live usage.

## Metrics

- RFQs harvested per hour
- Review throughput
- Queue lag
- Operator utilization
- Parser failure rate
- Source availability
- Telemetry freshness
- Workflow failures
- Persistence failures
- Auth failures
- Rate-limit events
- API latency

## Alerts

- Queue overload
- Source outage
- Stale telemetry
- High parser failure rate
- Auth anomaly
- Deployment degradation
- High overdue review count

## Snapshots

- Health snapshots are append-only.
- Snapshot data is JSON-safe and may be fallback-backed when runtime data is missing.

## Logging

- Structured logs are JSON-safe.
- Request IDs are preserved where available.
- Secrets, tokens, and passwords are excluded.

