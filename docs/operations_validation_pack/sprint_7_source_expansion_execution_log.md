# Sprint 7 Source Expansion Execution Log

## Purpose

Track source growth during Sprint 7 so we can identify which municipalities and SOEs actually produce live RFQs and which sources are dead weight.

## Expansion Baseline

| Field | Value |
| --- | ---: |
| Baseline Registry Sources | 1040 |
| Baseline Unique Source URLs | 1040 |
| Baseline Duplicate URL Groups | 0 |
| Baseline Enabled Sources | 1040 |

## Source Tracking Table

Add one row per new source as it is added and validated.

| Date | Source | Category | Added | First Harvest | RFQs Produced | Qualified RFQs Produced | Notes |
| --- | --- | --- | --- | --- | ---: | ---: | --- |

## Batch Plan

Add sources in 20-source batches.

| Batch | Planned Additions | Status | Date Started | Date Completed | Notes |
| --- | ---: | --- | --- | --- | --- |
| Batch 1 | 20 | Pending |  |  | Municipal and SOE sources preferred. |
| Batch 2 | 20 | Pending |  |  | Municipal and SOE sources preferred. |
| Batch 3 | 20 | Pending |  |  | Municipal and SOE sources preferred. |

## Recording Rules

- Record a source only after it has been added to the live registry.
- Set `First Harvest` to the first date on which the source produced a valid harvest result.
- Leave `First Harvest` blank until the first success is observed.
- Count only live, non-fixture RFQs in `RFQs Produced`.
- Count only RFQs that pass qualification in `Qualified RFQs Produced`.
- Use the notes column to mark dead weight, duplicates, or sources that remain silent after repeated harvest cycles.

## Review Use

This log should be used to answer:

- Which municipalities generate opportunities consistently?
- Which SOEs generate opportunities consistently?
- Which sources are dead weight?
- Which sources should be de-prioritized in future harvest cycles?

## Governance

Keep the existing Sprint 7 controls unchanged while source expansion is being measured:

- Portal submission remains disabled
- Human approval remains required
- Audit trail remains authoritative
- Approval bypass tolerance remains zero
- Duplicate audit event tolerance remains zero
- Orphaned audit event tolerance remains zero
- State drift tolerance remains zero

## Current Operating Note

The source network has already been expanded to 1,040 active sources. This log is the execution trail for measuring which of those sources produce live RFQs over time.

## Batch Review Rule

After each 20-source batch, record:

- RFQs harvested per day
- Open RFQs
- Qualified RFQs
- Submission candidates

## Productivity Audit Reference

The first source productivity audit is recorded in:

- `sprint_7_source_productivity_audit.md`

Current observed live-harvested producers:

- `NECSA` - 2 live RFQs
- `manual_production` - 1 live RFQ

Current observed non-productive live-harvested sources:

- `TENDER FOR`
- `19/06`
- `022_Request_for_Quotation_Stationery_-_Photocopy_paper_Oct`

## Harvest Coverage Audit Reference

The harvest coverage audit is recorded in:

- `sprint_7_harvest_coverage_audit.md`

Use that report to measure:

- sources attempted
- sources reachable
- sources parsed successfully
- sources producing RFQs
- sources producing qualified RFQs
- sources producing submission candidates

## Sprint 7A Reference

The harvest effectiveness optimization phase is recorded in:

- `sprint_7a_harvest_effectiveness_optimization.md`

Current KPI baseline:

- Harvest Coverage %: 5.8%
- RFQ-Producing Source %: 6.7%

Current observed producers:

- `National Treasury eTenders`
- `Browser Source`
- `Healthy Source`
- `Department of Higher Education and Training`
- `NECSA`
- `manual_production`
