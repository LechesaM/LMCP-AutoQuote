# Go-Live Checklist

## Preflight Checks

- Confirm the correct branch and commit are in use
- Confirm the manual-production runtime directory is configured
- Confirm the database and JSONL compatibility layers are available
- Confirm workflow rules have not been altered
- Confirm the supervised-live pilot pack is present for the 10-RFQ controlled pilot
- Confirm final submission remains manual-only

## Tests to Run

- Runtime config tests
- Router registry tests
- Domain schema tests
- Workflow state engine tests
- Service registry tests
- Persistence layer tests
- Monitoring tests
- Operator dashboard tests
- RFQ harness tests
- Review and proof record tests

## Validation Checks

- Run the end-to-end RFQ harness
- Review the readiness report
- Confirm health endpoints are acceptable
- Confirm dashboard queues match expectations
- Confirm supervised-live governance summary is advisory only
- Confirm proof capture and review_ready gating are intact

## Sample Pilot Checks

- Validate one known-good RFQ
- Validate refusal cases for excluded and below-margin RFQs
- Validate missing-source handling

## Backup Checks

- Confirm logs are being written
- Confirm durable persistence is available
- Confirm recovery procedures are documented

## Sign-Off Checklist

- Manual production safety confirmed
- No autonomous submission enabled
- Workflow governance intact
- Operator readiness confirmed
