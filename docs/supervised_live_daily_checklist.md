# Supervised-Live Daily Checklist

For the mandatory morning ritual review, see [production_cutover/daily_operational_rituals.md](production_cutover/daily_operational_rituals.md).

## Startup Checks
- Confirm supervised-live pilot mode is active
- Confirm runtime directories are writable
- Confirm manual-production database is reachable
- Confirm audit trail and submission history directories exist
- Run `make morning-ritual` to execute the readiness check, live queue status, and fresh-only daily loop together
- Confirm `make morning-ritual` prints the live queue status before the daily loop starts and stops immediately if the queue is empty
- Confirm the morning ritual does not try to seed fresh work on its own; use `make queue-refresh` for the National Treasury eTenders source or `make fresh-intake` for fallback recovery
- Confirm AO tooling is opened before operator work begins
- Confirm stabilization pages are visible
- Confirm operational health and observability panels are visible
- Confirm governance dashboards are visible
- Confirm workload balancing and fatigue monitoring are visible
- Confirm runtime resilience panels are visible

## Runtime Health Checks
- Confirm monitoring reports are generating
- Confirm workflow state persistence is healthy
- Confirm no unexpected workflow failures are present
- Confirm runtime alerts are reviewed for unresolved items
- Confirm stale evidence age is understood
- Confirm source failures and parser issues are visible
- Confirm anomaly reports are reviewed
- Confirm degraded-state fallback usage is understood
- Confirm SLA warnings are reviewed
- Confirm AO tooling is used daily, not only during incidents

## Dashboard Checks
- Confirm dashboard summary loads
- Confirm pending approval counts are visible
- Confirm review_ready queue counts are visible
- Confirm proof capture queue counts are visible

## Queue Checks
- Confirm RFQ queue backlog is understood
- Run `make live-queue-status` when you want a one-line view of queue freshness and runnable work
- Confirm refused RFQs are separated from active work
- Confirm archived items remain archived

## Backup Checks
- Confirm log files are being written
- Confirm proof artifacts are retained
- Confirm recovery notes are available for the day

## RFQ Processing Checks
- Confirm each RFQ is valid before processing
- Confirm exclusions and pricing thresholds are respected
- Confirm quote-pack readiness is only used for eligible RFQs
- Run `make queue-refresh` if the live queue has no fresh candidates and you want to seed the queue from the National Treasury eTenders source
- Run `make fresh-intake` if the live queue has no fresh candidates and you need fallback recovery
- Run `make daily-pilot-loop` for the current runnable RFQ and review the concise operator report
- Confirm `runtime/manual_production/daily_pilot_loop_report.json` is written after the loop completes

## Approval Checks
- Confirm manual approval is recorded
- Confirm no autonomous approval path is used
- Confirm approval evidence is captured

## Review Checks
- Confirm review_ready is recorded before proof capture
- Confirm submission review remains manual
- Confirm review evidence is captured
- Confirm operator attribution is complete
- Confirm escalations are reasonable
- Confirm stale reviews are minimized

## Proof Checks
- Confirm proof capture occurs after review_ready
- Confirm proof artifacts are retained
- Confirm proof evidence is captured

## End-of-Day Checks
- Confirm all RFQs are accounted for
- Confirm incidents are logged
- Confirm blockers are escalated
- Confirm daily report is completed

## Shutdown Checks
- Confirm active work is closed out
- Confirm logs are flushed
- Confirm manual-production workspace is left in a recoverable state
