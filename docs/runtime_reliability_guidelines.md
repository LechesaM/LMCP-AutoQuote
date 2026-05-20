# Runtime Reliability Guidelines

## Expectations

- Keep telemetry fresh
- Reduce alert noise without hiding critical alerts
- Prefer graceful fallback over hard failure
- Surface degraded states early

## Degraded-state handling

- Treat fallback activation as advisory
- Investigate stale telemetry quickly
- Rebalance workload when fatigue signals rise
- Preserve manual governance at all times

