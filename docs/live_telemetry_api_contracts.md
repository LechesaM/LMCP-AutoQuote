# Live Telemetry API Contracts

## Purpose

The live telemetry API exposes read-only runtime summaries for the LMCP AutoQuote command centre. It is designed to support the production dashboard, operational health panel, review queue, and qualification views without changing workflow state.

## Endpoints

- `GET /telemetry/dashboard`
- `GET /telemetry/source-health`
- `GET /telemetry/review-queue`
- `GET /telemetry/qualification`
- `GET /telemetry/operational-health`

## Response Schemas

### Dashboard Telemetry

- `total_harvested_rfqs`
- `eligible_rfqs`
- `total_estimated_value`
- `high_profit_rfqs`
- `avg_estimated_profit`
- `avg_margin`
- `eligible_rate`
- `province_distribution`
- `opportunity_breakdown`
- `top_high_profit_rfqs`
- `recent_alerts`
- `generated_at`
- `data_source`

### Source Health Telemetry

- `total_sources`
- `active_sources`
- `healthy_sources`
- `degraded_sources`
- `failing_sources`
- `disabled_sources`
- `parser_failure_rate`
- `average_response_time_ms`
- `recent_source_failures`
- `generated_at`
- `data_source`

### Review Queue Telemetry

- `pending_reviews`
- `approved_today`
- `manual_review_required`
- `blocked_reviews`
- `overdue_reviews`
- `operator_capacity`
- `operator_capacity_used`
- `operator_capacity_remaining`
- `queue_lag_minutes`
- `generated_at`
- `data_source`

### Qualification Telemetry

- `go_count`
- `manual_review_count`
- `reject_count`
- `low_confidence_count`
- `top_rejection_reasons`
- `top_manual_review_triggers`
- `avg_qualification_score`
- `avg_risk_score`
- `generated_at`
- `data_source`

### Operational Health Telemetry

- `source_failures`
- `parser_failures`
- `queue_lag`
- `operator_capacity`
- `rfq_aging`
- `stale_evidence`
- `workflow_failures`
- `persistence_failures`
- `audit_failures`
- `status`
- `generated_at`
- `data_source`

## Fallback Behavior

- If `VITE_LMCP_API_BASE_URL` is not configured, the frontend stays on local seed data.
- If a request fails, the frontend keeps the last known values and marks the panel stale rather than breaking the UI.
- If the backend response is incomplete or malformed, the frontend normalizer falls back to the local seed contract.
- Runtime builders also return safe zero/default payloads when the live runtime data is unavailable.

## Frontend Contract

- Environment variable: `VITE_LMCP_API_BASE_URL`
- Polling interval: 30 seconds by default
- Websocket transport is available in the refresh layer, but polling remains the primary mechanism

## Governance

- The telemetry API is read-only.
- It does not transition workflow state.
- It does not generate quotes.
- It does not submit tenders.
- It does not bypass manual approval, `review_ready`, or proof capture.
- It does not weaken refusal rules or pricing thresholds.

## Notes

- All response payloads are JSON-safe.
- All responses include `generated_at` and `data_source` or `status`.
- The telemetry endpoints are advisory only and are safe to consume from the dashboard.
