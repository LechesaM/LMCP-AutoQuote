# Sprint 8 Candidate: eTender Harvest Coverage Audit

## Status

- Type: Backlog item
- Sprint: Future engineering sprint
- Current state: Not implemented
- Sprint 7 impact: None

## Objective

Determine what percentage of publicly visible National Treasury eTender opportunities are actually entering LMCP.

The question is not whether the system can process RFQs once they are discovered. That has already been demonstrated in Sprint 7.

The question is how much of the available eTender opportunity surface LMCP is seeing at all.

## Hypothesis

The largest performance gain for LMCP AutoQuote may be upstream harvest coverage rather than downstream acquisition conversion.

If LMCP is only ingesting a small fraction of publicly visible eTender opportunities, then improving harvest coverage could produce more impact than:

- adding more sources
- expanding source maintenance
- tuning downstream acquisition alone

## Success Metric

- `LMCP-discovered eTender opportunities / publicly visible eTender opportunities`
- Target: materially higher coverage than the current observed pilot baseline

## Key Questions

1. How many eTender opportunities are publicly visible today?
2. How many of those does LMCP discover today?
3. What percentage coverage is LMCP achieving?
4. Where is the loss happening?
   - source coverage
   - extractor coverage
   - URL discovery
   - genuine lack of qualifying opportunities

## Evidence Basis

Current Sprint 7 evidence shows:

- Harvesting works.
- Qualification works.
- Governance works.
- Manual submission works.
- eTender URL discovery is underperforming.

This investigation exists to answer whether the next larger win is improving upstream harvest coverage rather than only improving downstream URL conversion.

## Guardrails

- Do not change Sprint 7 governance.
- Do not change qualification rules.
- Do not change approval rules.
- Do not change submission logic.
- Do not enable autonomous submission.

## Expected Outcome

This investigation should identify whether LMCP is losing most opportunities:

- before they enter the registry
- during extraction
- during URL discovery
- or only because the available opportunity pool is genuinely small

If coverage is low, improving the harvest surface may yield more submission-ready opportunities than any downstream optimization alone.
