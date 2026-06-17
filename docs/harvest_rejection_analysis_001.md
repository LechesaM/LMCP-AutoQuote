# HARVEST-REJECTION-ANALYSIS-001

## Scope

This review records the current rejection frequency profile for the active runtime RFQ ledger while remaining in Operational Hold State.

## Latest Scheduled Harvest Run

- Run: `scheduled_harvest_20260608T010000Z`
- Cycles completed: `4`
- Rejected opportunities in the scheduled run: `0`
- Blocked opportunities in the scheduled run: `0`
- Screened-out opportunities in the scheduled run: `0`

The latest scheduled harvest cycle did not produce rejection counts, so the frequency analysis below uses the live RFQ ledger currently stored in `runtime/rfq_lifecycle/rfqs.json`.

## Ledger Basis

- Source file: [runtime/rfq_lifecycle/rfqs.json](/Users/cash/Documents/runtime/rfq_lifecycle/rfqs.json)
- Ledger entries: `5`
- Blocked entries with a primary blocker: `4`
- Counting rule: one count per RFQ, using the primary blocker recorded on the RFQ item

## Rejection Frequency

| Rejection Reason | Count |
| --- | ---: |
| `missing_closing_date` | 2 |
| `below_minimum_profit` | 1 |
| `missing_source_or_detail_url` | 1 |

## Per-Opportunity Trace

| RFQ | Title | Buyer | Primary Rejection Reason |
| --- | --- | --- | --- |
| `022-REQUEST-FOR-QUOTATION-STATIONERY-PHOTOCOPY-PAPER-OCT` | Request for Quotation: Stationery - Photocopy paper Oct | LMCP | `below_minimum_profit` |
| `RFQ-123` | RFQ-123 | Metro Procurement Unit | `missing_source_or_detail_url` |
| `RFQ-12345` | RFQ 12345 Supply and delivery of office supplies for 12 months | Smoke Fixture eTenders | `missing_closing_date` |
| `RFQ-67890` | RFQ 67890 Supply and delivery of cleaning materials for 24 months | Smoke Fixture eTenders | `missing_closing_date` |

## Interpretation

- `missing_closing_date` is currently the most common blocker in the live ledger.
- `below_minimum_profit` appears once and is consistent with designed profitability gating.
- `missing_source_or_detail_url` appears once and points to intake completeness rather than qualification thresholds.

## Decision Guidance

- If the goal is to reduce avoidable misses, the next investigation should target closing-date capture and source/detail URL completeness before changing any qualification logic.
- If the goal is to preserve current behavior, no remediation is required for `below_minimum_profit`; it is behaving as designed.

## Governance Impact

- None.
- No thresholds changed.
- No submission rules changed.
- No supervised-live controls changed.
