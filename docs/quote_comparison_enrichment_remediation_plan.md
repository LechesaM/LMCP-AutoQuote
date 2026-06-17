# Quote Comparison Enrichment Remediation Plan

## Purpose

Define the quote-comparison enrichment defect precisely, define what "fixed" means, and establish the evidence required before any new expansion decision is considered.

This remediation must be implemented outside the monitoring layer.

## Problem Statement

Across the supervised-live evidence reviewed in Wave 001 and Wave 002, quote-comparison enrichment remained incomplete relative to the supplier quote sources used in governed submission preparation.

Observed symptoms included:

- `supplier_quotes` missing or incomplete
- `recommended_supplier` placeholder-like or under-populated
- `quoted_total` fields empty or `0.0`
- traceability chains incomplete or empty

Observed impact to date:

- no evidence showed impact on approval controls
- no evidence showed impact on submission controls
- no evidence showed impact on proof controls
- no evidence showed impact on audit controls

This remains a data-quality and traceability defect, not a recorded governance-control failure.

## Scope

In scope:

- supplier quote comparison enrichment
- recommended supplier population
- runner-up supplier population when available
- quoted total population
- savings calculation population
- traceability chain population
- prevention of empty or placeholder comparison records

## Out Of Scope

- monitoring-only fixes
- dashboard-only normalization
- telemetry-only workarounds
- governance outcome rewrites for Wave 001 or Wave 002
- changes to Track A
- changes to Track B
- changes to Regression Run #2

## Success Criteria

Remediation is considered technically complete only if all of the following are true for the evaluated evidence set:

- supplier quotes are populated from the real supplier quote sources
- recommended supplier is populated
- quoted totals are populated
- runner-up supplier is populated when available
- savings calculation is populated when available
- traceability chain is populated
- empty comparison records are prevented
- placeholder values are prevented

## Evidence Requirements

Required evidence:

- before/after outputs for Wave 001-related data
- before/after outputs for Wave 002-related data
- completed objective validation checklist
- formal remediation review outcome

Evidence should be concrete and inspectable, not narrative-only.

## Expansion-Decision Dependency

Further expansion remains deferred pending remediation review.

No decision on any of the following should be made until the remediation review is complete:

- `RFQ_005` activation
- limited Tier 25 pilot
- limited multi-RFQ pilot
- any wider supervised-live expansion
