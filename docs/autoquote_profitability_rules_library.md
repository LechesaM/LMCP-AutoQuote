# Profitability Rules Library

## Purpose
This library documents the current profitability standards used for screening and review.

## Governance Boundaries
- These are operating standards, not automated workflow overrides.
- No rule here authorizes autonomous submission.
- No rule here bypasses manual review.

## Current Standards
- Minimum profit target: R30,000
- Minimum margin assumption: 25%
- Supply-only preferred
- No briefing session tenders unless explicitly reviewed
- All provinces in scope unless category evidence suggests otherwise

## Profitability Filters
Screen tenders using these checks:
- estimated gross profit
- margin percentage
- delivery cost burden
- supplier availability confidence
- quote freshness
- province complexity
- compliance cost burden
- packaging and proof overhead

## Preferred Decision Outcomes
- `GO` when expected profit and evidence quality are strong
- `REVIEW` when profit is acceptable but evidence is incomplete
- `HOLD` when key assumptions are unstable
- `NO_GO` when profit or evidence quality is below standard

## Rule Notes
- A high revenue tender is not automatically profitable.
- Delivery-heavy tenders need explicit cost treatment.
- Low-confidence pricing should reduce trust in profitability estimates.
- Profitability should be evaluated together with category fit and supplier coverage.

## Recordkeeping Fields
Record each rule application with:
- RFQ identifier
- category
- profit estimate
- margin estimate
- delivery assumption
- pricing confidence
- supplier evidence confidence
- final advisory outcome
