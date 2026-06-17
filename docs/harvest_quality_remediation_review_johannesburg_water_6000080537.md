# Harvest Quality Remediation Review: Johannesburg Water 6000080537

## Test Case

- ID: `HARVEST-REMEDIATION-001`
- Reference Opportunity: `6000080537`
- Buyer: `Johannesburg Water`
- Title: `Electrical Components`
- Closing Date: `19 June 2026`

## Outcome

- Status: `PASS`
- Scope: harvest-quality investigation only
- Governance impact: `None`

## Trace Matrix

| Stage | Result | Pass/Fail |
| --- | --- | --- |
| URL harvest | Opportunity visible in live store | PASS |
| Metadata extraction | Buyer, title, closing date, and document URL available | PASS |
| PDF discovery | Acquisition returned a downloaded PDF path | PASS |
| PDF download | Downloaded artifact recorded | PASS |
| PDF parse | Text extraction and parser intelligence returned | PASS |
| Specification detection | No spec signal detected from parsed content | FAIL |
| Returnables detection | No SBD/returnables detected | FAIL |
| Qualification | Blocked | FAIL |

## Root Cause

- `rfq_spec_document_not_detected`

## Rejection Reason

- The parser trace did not produce enough spec signals to classify the document as the technical specification source for the opportunity.
- Returnables evidence was also absent, so the lifecycle service kept the item in review.

## Remediation Category

- Improve specification-file classification
- Improve returnables detection
- Improve rejection evidence logging

## Notes

- No thresholds were changed.
- No approval gates were changed.
- No submission behavior was changed.
- No supervised-live controls were changed.
- Evidence artifacts:
  - [Fixture](../tests/fixtures/qualification_rfqs/rfq_006_johannesburg_water_electrical_components.json)
  - [Test](../tests/test_harvest_quality_remediation_johannesburg_water.py)
