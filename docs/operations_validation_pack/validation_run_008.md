# Validation Run 008

Post-Sprint 2 live-queue measurement against the frozen live benchmark.

## Run Metadata

- Run ID: `VALIDATION_RUN_008`
- Baseline: `Run 007 live-queue benchmark`
- Sprint State: `Sprint 2 implemented`
- Status: `completed`
- Objective: measure whether Sprint 2 reduced document-generation-caused `NOT_READY` outcomes on the live queue
- Measured RFQs: `15`

## Baseline to Beat

| KPI | Run 007 Live Benchmark |
| --- | ---: |
| READY | 2 |
| NOT READY | 13 |
| Metadata / Completeness | 13 |
| Qualification Exclusion | 2 |
| Technical Validation Gate | 0 |
| Document Generation | 0 |
| Extraction | 0 |

## Midpoint Snapshot

The first 10 executable live-queue records currently available in `runtime/live_rfqs.json` were measured as the Run 008 midpoint evidence set.

| KPI | Run 007 Live Benchmark | Run 008 Midpoint |
| --- | ---: | ---: |
| READY | 2 | 0 |
| NOT READY | 13 | 10 |
| Metadata / Completeness | 13 | 7 |
| Qualification Exclusion | 2 | 5 |
| Technical Validation Gate | 0 | 0 |
| Document Generation | 0 | 7 |
| Extraction | 0 | 7 |

## Midpoint Interpretation

- No READY outcomes appeared in the first 10 live-queue records.
- Sprint 2 did produce generated quote-pack evidence on a subset of records, but those records were still blocked by qualification or expiry conditions.
- Document-generation and extraction-related gaps remain visible in the live queue.
- No delivery or audit-trace regressions were introduced by Sprint 2 in the measured midpoint queue.

## Live Queue Signals

| Signal | Count |
| --- | ---: |
| `quote_pack_generated = true` | 3 |
| `pricing_schedule_status = detected` | 3 |
| `returnables_status = detected` | 3 |
| `boq_status = detected` | 3 |

The three quote-pack-generated records were:

- `FIN-SCM-TEN-0236`
- `FIN-SCM-TEN-0235`
- `FIN-SCM-TEN-0227`

They remained `NOT_READY` because they were still blocked by qualification or expiry conditions, not by delivery or audit issues.

## Final Closeout

The live queue benchmark was closed against the current evidence store.

| KPI | Run 007 Live Benchmark | Run 008 Closeout |
| --- | ---: | ---: |
| READY | 2 | 0 |
| NOT READY | 13 | 15 |
| Metadata / Completeness | 13 | 11 |
| Qualification Exclusion | 2 | 6 |
| Technical Validation Gate | 0 | 0 |
| Document Generation | 0 | 10 |
| Extraction | 0 | 10 |

## Final Interpretation

- Sprint 2 did not produce READY outcomes on the live queue benchmark.
- The document-generation path now emits quote-pack evidence for a small subset of records, but that was not enough to convert any RFQs to READY.
- Document-generation, extraction, and metadata-completeness blockers remain present in the live queue.
- Delivery and audit remained stable with no observed regressions.
- Sprint 2 is therefore only partially effective at the current benchmark level and does not yet meet the success gate.
