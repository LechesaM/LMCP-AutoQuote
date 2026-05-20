# Observability and Runtime Monitoring

LMCP AutoQuote now exposes a read-only observability layer for supervised-live operations.

## Architecture

- Prometheus-style metrics export
- Grafana dashboard definitions
- Optional Sentry runtime exception capture
- SLA monitoring for queue, telemetry, backup and source freshness
- Runtime anomaly detection
- Alert routing summaries
- Structured log aggregation
- Uptime and performance monitoring

## Operational Use

- All observability endpoints are read-only.
- All outputs are JSON-safe except the Prometheus text export.
- Missing runtime data falls back safely to seeded or empty summaries.
- Monitoring surfaces advisory signals only.

## Governance

- No autonomous procurement execution is introduced.
- No workflow transition, submission or approval behavior is modified.
- Manual operator governance remains intact.
