# Test RFQ Library

## Purpose
This library defines a reusable set of RFQ scenarios for regression and manual testing without changing live workflow code.

## Scenario Types

### Small RFQs
Use these to validate basic flow handling:
- stationery top-up
- PPE replenishment
- cleaning chemical order
- office accessories order

Expected focus:
- simple pricing
- low delivery complexity
- quick review turnaround

### Medium RFQs
Use these to validate multi-item handling:
- office furniture plus stationery
- electrical consumables plus PPE
- cleaning chemicals plus janitorial supplies
- hardware plus safety signage

Expected focus:
- supplier matching
- multiple line items
- mixed margin profiles

### Large RFQs
Use these to validate heavier evidence loads:
- construction materials across multiple line items
- mixed supply-and-delivery procurement bundle
- multi-province delivery requirement

Expected focus:
- lead time handling
- delivery assumptions
- multi-supplier coverage

### Multi-Line-Item RFQs
Use these to validate aggregation:
- ten or more line items
- mixed unit types
- mixed price bands
- mixed supplier availability

Expected focus:
- line-item consistency
- total reconciliation
- quote package completeness

### Edge-Case RFQs
Use these to validate rejection and escalation handling:
- briefing session required
- missing delivery details
- unclear submission method
- stale supplier quote
- blocked category present
- inconsistent VAT treatment
- unrealistic delivery window
- province coverage gap

Expected focus:
- manual review triggers
- block reasons
- note capture
- refusal handling

## Test Metadata
Each RFQ scenario should record:
- scenario name
- size class
- category
- expected outcome
- required evidence
- known risk
- regression owner
- last run date

## Suggested Acceptance Checks
- Category screening works as expected.
- Pricing confidence is visible.
- Profitability filters are applied consistently.
- Blocked categories remain blocked.
- Review notes are preserved.
- No scenario changes runtime governance.
