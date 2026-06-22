# Validation Run 007

Post-Sprint 1.3 live-queue measurement against the frozen live-benchmark sample.

## Run Metadata

- Run ID: `VALIDATION_RUN_007`
- Baseline: `Run 006 live-queue benchmark`
- Sprint State: `Sprint 1.3 implemented`
- Status: `completed`
- Objective: measure whether Sprint 1.3 increased READY outcomes and reduced metadata-completeness failures on the live queue
- Measured RFQs: `15`

## Baseline to Beat

| Failure Class | Run 006 Live Benchmark |
| --- | ---: |
| READY | 0 |
| NOT READY | 15 |
| Metadata / Completeness | 11 |
| Qualification Exclusion | 6 |
| Technical Validation Gate | 0 |
| Document Generation | 10 |
| Extraction | 10 |

## Execution Summary

| KPI | Run 006 Live Benchmark | Run 007 Result |
| --- | ---: | ---: |
| READY | 0 | 2 |
| NOT READY | 15 | 13 |
| Metadata / Completeness | 11 | 13 |
| Qualification Exclusion | 6 | 2 |
| Technical Validation Gate | 0 | 0 |
| Document Generation | 10 | 0 |
| Extraction | 10 | 0 |

## Review Snapshot

The first live records produced by the Sprint 1.3 validator now recover the key metadata fields when evidence exists:

- `RFQ-XYZ` remains `NOT_READY` because the queue does not expose enough recoverable metadata.
- `FIN-SCM-TEN-0236` becomes `READY` after recovering closing date and source/detail URL evidence.
- `FIN-SCM-TEN-0235` becomes `READY` after recovering closing date and source/detail URL evidence.
- The remaining records are still dominated by `closing_date_passed`, business-rule, or qualification blocks.

## Recovery Signals

| Signal | Count |
| --- | ---: |
| `boq` | 13 |
| `sbd_or_returnables` | 13 |
| `pricing_schedule` | 4 |
| `quote_pack` | 3 |

## Closeout Interpretation

- Sprint 1.3 produced the first `READY` outcomes on the live queue benchmark.
- Metadata recovery is now converting some queue records from `NOT_READY` to `READY`.
- The live queue is still harsher than the curated validation fixtures, but the recovery path is now measurably active.
- The run supports continuing metadata recovery hardening before moving to Sprint 2.
