# Log Aggregation Strategy

## Sources

- Auth logs
- Operator action logs
- Runtime alerts
- Queue events
- Deployment events
- Incident logs

## Rules

- Summaries remain JSON-safe.
- Secrets, tokens and passwords are redacted.
- Aggregation is read-only.
