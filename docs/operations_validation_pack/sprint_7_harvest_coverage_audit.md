# Sprint 7 Harvest Coverage Audit

## Purpose

Identify where the source pipeline drops off:

- sources attempted
- sources reachable
- sources parsed successfully
- sources producing RFQs
- sources producing qualified RFQs
- sources producing submission candidates

This audit is based on observed runtime evidence, not assumptions.

## Evidence Sources

- `runtime/source_health.json`
- `runtime/multi_portal_discovery/source_health_report.json`
- `runtime/multi_portal_discovery/yield_summary.json`
- `runtime/multi_portal_discovery/source_yield_rankings.json`
- `runtime/live_rfqs.json`

## Coverage Funnel

| Metric | Observed Count | Notes |
| --- | ---: | --- |
| Registry sources | 1040 | Expanded live registry baseline |
| Source-health records | 71 | Sources with recorded health telemetry |
| Sources attempted | 60 | `scan_total > 0` in `runtime/source_health.json` |
| Sources reachable / healthy | 4 | Sources with observed productive/healthy status in the telemetry snapshot |
| Sources parsed successfully | 4 | Sources with `candidate_total > 0` |
| Sources producing RFQs | 4 | Same observed set as parsed successfully |
| Sources producing qualified RFQs | 4 | Sources with `qualified_candidate_total > 0` |
| Sources producing submission candidates | 3 | Sources with `document_candidate_total > 0` |

## Where The Drop-Off Occurs

Observed failure modes in `runtime/source_health.json`:

| Acquisition Status | Count |
| --- | ---: |
| `no_candidates` | 30 |
| `dns_failed` | 23 |
| `timeout` | 3 |
| `http_failed` | 1 |
| `success` | 3 |

The largest drop-off is before parsing and qualification:

- DNS failures
- no-candidate pages
- timeouts
- HTTP failures

## Top Producers Observed

| Rank | Source | Category | RFQs Produced | Qualified RFQs | Submission Candidates | Notes |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | National Treasury eTenders | Aggregator | 429 | 321 | 429 | Strongest observed real portal producer. |
| 2 | Browser Source | Internal / test | 24 | 24 | 0 | Productive test source, not a real procurement portal. |
| 3 | Healthy Source | Internal / test | 24 | 18 | 24 | Productive test source, not a real procurement portal. |
| 4 | Department of Higher Education and Training | National department | 2 | 1 | 2 | Real portal with low but non-zero yield. |
| 5 | DNS Source | Internal / test | 0 | 0 | 0 | No productive output in the current sample. |
| 6 | Broken Source | Internal / test | 0 | 0 | 0 | No productive output in the current sample. |
| 7 | Empty Source | Internal / test | 0 | 0 | 0 | No productive output in the current sample. |
| 8 | Dihlabeng Local Municipality | Municipality | 0 | 0 | 0 | No productive output in the current sample. |
| 9 | Kopanong Local Municipality | Municipality | 0 | 0 | 0 | No productive output in the current sample. |
| 10 | Mafube Local Municipality | Municipality | 0 | 0 | 0 | No productive output in the current sample. |

## Non-Productive Sources In The Current Sample

Representative zero-yield sources from the observed source-health snapshot include:

- `Airports Company South Africa`
- `Bloem Water`
- `Buffalo City Metropolitan Municipality`
- `City of Cape Town`
- `City of Ekurhuleni`
- `City of Johannesburg`
- `City of Tshwane`
- `DBSA`
- `Denel`
- `Department of Agriculture`
- `Department of Basic Education`

These are not proven dead. They are simply non-productive in the current observed sample.

## Interpretation

The current bottleneck is source effectiveness, not registry size.

The audit shows:

- only 4 sources have produced any observed RFQs in the runtime health snapshot
- only 3 sources have produced submission candidates
- most failures happen before qualification, primarily at the acquisition / reachability layer

## Reference Sources

Treat these as the current reference set for harvest behavior:

- National Treasury eTenders
- Department of Higher Education and Training
- Browser Source
- Healthy Source

## Recommendation

- Keep Sprint 7 frozen.
- Keep harvesting the existing source set.
- Improve reachability and parsing coverage before adding more sources.
- Prioritize source effectiveness work over further registry growth until the attempted-to-productive gap narrows materially.
## Harvest Effectiveness Run - 2026-06-19T20:18:07.537196+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Awards | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | 0 | 0 | 0 |
| Airports Company South Africa - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T20:22:27.704116+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 20 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| harvest_coverage_percent | 1.92 |
| rfq_producing_source_percent | 5.0 |

### Top Failure Types

- dns_failed: 20

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| CSD | 0 | 0 | 0 |
| CSD - Archive | 0 | 0 | 0 |
| CSD - Awards | 0 | 0 | 0 |
| CSD - Bidboard | 0 | 0 | 0 |
| CSD - Contracts | 0 | 0 | 0 |
| CSD - Current Tenders | 0 | 0 | 0 |
| CSD - Documents | 0 | 0 | 0 |
| CSD - Downloads | 0 | 0 | 0 |
| CSD - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T20:26:28.661296+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 20 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| harvest_coverage_percent | 1.92 |
| rfq_producing_source_percent | 5.0 |

### Top Failure Types

- dns_failed: 20

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| CSD | 0 | 0 | 0 |
| CSD - Archive | 0 | 0 | 0 |
| CSD - Awards | 0 | 0 | 0 |
| CSD - Bidboard | 0 | 0 | 0 |
| CSD - Contracts | 0 | 0 | 0 |
| CSD - Current Tenders | 0 | 0 | 0 |
| CSD - Documents | 0 | 0 | 0 |
| CSD - Downloads | 0 | 0 | 0 |
| CSD - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T20:26:33.692655+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Awards | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | 0 | 0 | 0 |
| Airports Company South Africa - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Awards | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | dns_failed | dns_failed | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T20:31:43.325869+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 20 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 1.92 |
| rfq_producing_source_percent | 5.0 |

### Top Failure Types

- dns_failed: 20

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| CSD | 0 | 0 | 0 |
| CSD - Archive | 0 | 0 | 0 |
| CSD - Awards | 0 | 0 | 0 |
| CSD - Bidboard | 0 | 0 | 0 |
| CSD - Contracts | 0 | 0 | 0 |
| CSD - Current Tenders | 0 | 0 | 0 |
| CSD - Documents | 0 | 0 | 0 |
| CSD - Downloads | 0 | 0 | 0 |
| CSD - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | dns_runtime_suspected | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T20:31:51.868626+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Awards | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | 0 | 0 | 0 |
| Airports Company South Africa - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | dns_runtime_suspected | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T20:35:34.421240+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Awards | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | 0 | 0 | 0 |
| Airports Company South Africa - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | dns_runtime_suspected | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T20:56:56.373246+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- http_error: 106
- no_candidates: 75
- timeout: 18
- unknown_error: 1

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Awards | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | 0 | 0 | 0 |
| Airports Company South Africa - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Archive | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Awards | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Bidboard | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Contracts | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Current Tenders | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Documents | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Downloads | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Notices | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Opportunities | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Procurement | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Procurement Tenders | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Quote | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Rfq | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Supplier Portal | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Tenders | timeout | timeout |  | 0 | 0 | 0 |
| National Treasury eTenders | ok | unknown_error |  | 429 | 321 | 429 |
| National Treasury eTenders - Archive | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Awards | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Documents | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Notices | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Quote | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| Airports Company South Africa | no_candidates | no_candidates |  | 0 | 0 | 0 |
| Airports Company South Africa - Archive | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Awards | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Documents | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | http_failed | http_error |  | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T21:12:25.893587+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- http_error: 105
- no_candidates: 76
- timeout: 18
- unknown_error: 1

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Awards | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | 0 | 0 | 0 |
| Airports Company South Africa - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Archive | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Awards | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Bidboard | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Contracts | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Current Tenders | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Documents | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Downloads | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Notices | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Opportunities | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Procurement | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Procurement Tenders | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Quote | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Rfq | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Supplier Portal | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Tenders | http_failed | http_error |  | 0 | 0 | 0 |
| National Treasury eTenders | ok | unknown_error |  | 429 | 321 | 429 |
| National Treasury eTenders - Archive | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Awards | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Documents | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Notices | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Quote | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| Airports Company South Africa | no_candidates | no_candidates |  | 0 | 0 | 0 |
| Airports Company South Africa - Archive | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Awards | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Documents | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | http_failed | http_error |  | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T21:15:40.650800+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1040 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- http_error: 115
- no_candidates: 76
- timeout: 8
- unknown_error: 1

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Awards | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | 0 | 0 | 0 |
| Airports Company South Africa - Notices | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Archive | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Awards | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Bidboard | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Contracts | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Current Tenders | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Documents | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Downloads | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Notices | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Opportunities | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Procurement | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Procurement Tenders | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Quote | http_failed | http_error |  | 0 | 0 | 0 |
| CSD - Rfq | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Supplier Portal | timeout | timeout |  | 0 | 0 | 0 |
| CSD - Tenders | http_failed | http_error |  | 0 | 0 | 0 |
| National Treasury eTenders | ok | unknown_error |  | 429 | 321 | 429 |
| National Treasury eTenders - Archive | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Awards | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Documents | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Notices | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Quote | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | no_candidates | no_candidates |  | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | no_candidates | no_candidates |  | 0 | 0 | 0 |
| Airports Company South Africa | no_candidates | no_candidates |  | 0 | 0 | 0 |
| Airports Company South Africa - Archive | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Awards | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Bidboard | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Contracts | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Current Tenders | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Documents | http_failed | http_error |  | 0 | 0 | 0 |
| Airports Company South Africa - Downloads | http_failed | http_error |  | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T21:34:59.969372+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1022 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200
- duplicate_url: 18

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Bloem Water | 0 | 0 | 0 |
| Bloem Water - Archive | 0 | 0 | 0 |
| Bloem Water - Downloads | 0 | 0 | 0 |
| Bloem Water - Notices | 0 | 0 | 0 |
| Bloem Water - Opportunities | 0 | 0 | 0 |
| Bloem Water - Procurement | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | dns_runtime_suspected | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T21:39:18.644246+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1004 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200
- duplicate_url: 36

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Bloem Water | 0 | 0 | 0 |
| Bloem Water - Archive | 0 | 0 | 0 |
| Bloem Water - Quote | 0 | 0 | 0 |
| CSD | 0 | 0 | 0 |
| CSD - Archive | 0 | 0 | 0 |
| CSD - Awards | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | dns_runtime_suspected | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T21:40:51.345528+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1004 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200
- duplicate_url: 36

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Bloem Water | 0 | 0 | 0 |
| Bloem Water - Archive | 0 | 0 | 0 |
| Bloem Water - Quote | 0 | 0 | 0 |
| CSD | 0 | 0 | 0 |
| CSD - Archive | 0 | 0 | 0 |
| CSD - Awards | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | dns_runtime_suspected | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |

## Harvest Effectiveness Run - 2026-06-19T21:43:05.254165+00:00

### Coverage Metrics

| Metric | Value |
| --- | ---: |
| configured_sources | 1040 |
| enabled_sources | 1040 |
| unique_urls | 1004 |
| attempted_sources | 200 |
| reachable_sources | 0 |
| rfq_producing_sources | 1 |
| qualified_rfq_sources | 1 |
| submission_candidate_sources | 1 |
| dns_runtime_suspected_sources | 0 |
| harvest_coverage_percent | 19.23 |
| rfq_producing_source_percent | 0.5 |

### Top Failure Types

- dns_failed: 200
- duplicate_url: 36

### Top Producers

| Source | RFQs | Qualified | Submission Candidates |
| --- | ---: | ---: | ---: |
| National Treasury eTenders | 429 | 321 | 429 |
| Airports Company South Africa | 0 | 0 | 0 |
| Airports Company South Africa - Archive | 0 | 0 | 0 |
| Airports Company South Africa - Documents | 0 | 0 | 0 |
| Bloem Water | 0 | 0 | 0 |
| Bloem Water - Archive | 0 | 0 | 0 |
| Bloem Water - Quote | 0 | 0 | 0 |
| CSD | 0 | 0 | 0 |
| CSD - Archive | 0 | 0 | 0 |
| CSD - Awards | 0 | 0 | 0 |

### Attempted Sources

| Source | Status | Failure Type | Marker | RFQs | Qualified | Submission Candidates |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CSD | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| CSD - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders | dns_failed | dns_failed | dns_runtime_suspected | 429 | 321 | 429 |
| National Treasury eTenders - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Current Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Downloads | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Notices | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Opportunities | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Procurement Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Quote | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Rfq | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Supplier Portal | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| National Treasury eTenders - Tenders | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Airports Company South Africa - Documents | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Archive | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Awards | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Bidboard | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |
| Denel - Contracts | dns_failed | dns_failed | dns_runtime_suspected | 0 | 0 | 0 |

