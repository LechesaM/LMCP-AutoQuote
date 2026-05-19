# Supervised-Live Daily Checklist

## Startup Checks
- Confirm supervised-live pilot mode is active
- Confirm runtime directories are writable
- Confirm manual-production database is reachable
- Confirm audit trail and submission history directories exist

## Runtime Health Checks
- Confirm monitoring reports are generating
- Confirm workflow state persistence is healthy
- Confirm no unexpected workflow failures are present

## Dashboard Checks
- Confirm dashboard summary loads
- Confirm pending approval counts are visible
- Confirm review_ready queue counts are visible
- Confirm proof capture queue counts are visible

## Queue Checks
- Confirm RFQ queue backlog is understood
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

## Approval Checks
- Confirm manual approval is recorded
- Confirm no autonomous approval path is used
- Confirm approval evidence is captured

## Review Checks
- Confirm review_ready is recorded before proof capture
- Confirm submission review remains manual
- Confirm review evidence is captured

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
