# Go-Live Checklist

## Preflight Checks

- Confirm the correct branch and commit are in use
- Confirm the manual-production runtime directory is configured
- Confirm the database and JSONL compatibility layers are available
- Confirm workflow rules have not been altered

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

