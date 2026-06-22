# Sprint 7A - Harvest Effectiveness Optimization

## Purpose

Improve harvest coverage and source effectiveness under frozen Sprint 7 governance.

This phase does not change qualification, approval, submission, audit, or pilot rules.

## Governance Locks

- Portal Submission = DISABLED
- Human Approval = REQUIRED
- Audit Trail = AUTHORITATIVE
- Approval Bypasses = 0 tolerance
- Duplicate Audit Events = 0 tolerance
- Orphaned Audit Events = 0 tolerance
- State Drift = 0 tolerance

## Current Baseline

| Metric | Value |
| --- | ---: |
| Configured sources | 1040 |
| Attempted sources | 60 |
| Harvest coverage | 5.8% |
| RFQ-producing source rate | 6.7% |
| Live RFQ observed sources | 3 |
| Manual submission candidates | 1 |

## Coverage KPI

Weekly track:

| KPI | Formula | Current |
| --- | --- | ---: |
| Harvest Coverage % | Attempted Sources / Configured Sources | 5.8% |
| RFQ-Producing Source % | RFQ-Producing Sources / Attempted Sources | 6.7% |

## Coverage Classes

| Class | Meaning | Action |
| --- | --- | --- |
| Reachable + Producing | Source is useful | Keep |
| Reachable + No Candidates | Source may need parser/filtering review | Review |
| Timeout | Source may need retry strategy | Retry |
| DNS Failed | Source maintenance issue | Maintain / repair |
| Disabled / Dead | Source is not contributing | Quarantine or remove |

## Observed Producer Leaderboard

### Source-Health Producers

| Rank | Source | Category | RFQs Produced | Qualified RFQs | Submission Candidates | Notes |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | National Treasury eTenders | Aggregator | 429 | 321 | 429 | Highest-yield real portal in the observed health corpus. |
| 2 | Browser Source | Internal / test | 24 | 24 | 0 | Useful for parser validation, not a real procurement portal. |
| 3 | Healthy Source | Internal / test | 24 | 18 | 24 | Useful for controlled positive-path testing. |
| 4 | Department of Higher Education and Training | National department | 2 | 1 | 2 | Real portal with low but non-zero yield. |

### Live Pilot Evidence Producers

| Rank | Source | Category | Live RFQs Produced | Qualified RFQs | Submission Candidates | Notes |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | NECSA | SOE | 2 | 0 observed in the source-productivity corpus | 0 observed in the source-productivity corpus | Live-harvested pilot evidence in the Sprint 7 queue. |
| 2 | manual_production | Internal / pilot evidence | 1 | 0 observed in the source-productivity corpus | 0 observed in the source-productivity corpus | Controlled pilot evidence path. |

## Non-Productive Observations

Sources that have produced no observed RFQs in the current source-health snapshot should be treated as unproven, not permanently dead.

Representative examples:

- Airports Company South Africa
- Bloem Water
- Buffalo City Metropolitan Municipality
- City of Cape Town
- City of Ekurhuleni
- City of Johannesburg
- City of Tshwane
- DBSA
- Denel
- Department of Agriculture
- Department of Basic Education

## Recommended Operating Sequence

1. Continue toward the 15-RFQ checkpoint under unchanged governance.
2. Keep scheduled harvest refreshes running.
3. Monitor the top 10 RFQ-producing sources separately.
4. Classify the 60 attempted sources by coverage outcome.
5. Review parser, reachability, and timeout failures before adding more sources.

## Decision Rule

Do not add more sources until harvest coverage and source effectiveness improve materially.

The next improvement target is coverage growth from 5.8% toward 20-25% using the existing registry.

## Latest Decision Memo

- [Sprint 7 Harvest Effectiveness Decision Memo](./sprint_7_harvest_effectiveness_decision_memo.md)
- [Sprint 7 Source Coverage Decision Memo](./sprint_7_source_coverage_decision_memo.md)
- [Sprint 7 HTTP Failure Analysis](./sprint_7_http_failure_analysis.md)
- [Sprint 7 Source Maintenance Decision Memo](./sprint_7_source_maintenance_decision_memo.md)
