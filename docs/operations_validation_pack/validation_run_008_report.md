# Validation Run 008 Report

## Summary

Run 008 measured the live queue again after Sprint 2 document-generation hardening.

| KPI | Run 007 Live Benchmark | Run 008 |
| --- | ---: | ---: |
| READY | 2 | 0 |
| NOT READY | 13 | 15 |
| Metadata / Completeness | 13 | 11 |
| Qualification Exclusion | 2 | 6 |
| Technical Validation Gate | 0 | 0 |
| Document Generation | 0 | 10 |
| Extraction | 0 | 10 |

## What Changed

- No READY outcomes appeared in the measured live queue.
- Three records now generate quote-pack evidence, pricing schedules, returnables, and BOQ detection, but they remain non-ready because of qualification or closing-date blockers.
- Document-generation and extraction gaps remain visible in the live queue.
- No delivery or audit regressions were introduced by Sprint 2 in the measured evidence set.

## Key Document-Generation Signals

| Signal | Count |
| --- | ---: |
| `quote_pack_generated = true` | 3 |
| `pricing_schedule_status = detected` | 3 |
| `returnables_status = detected` | 3 |
| `boq_status = detected` | 3 |

## Conclusion

Sprint 2 is partially effective at pack generation, but it did not reduce the live-queue READY blocker enough to beat the Run 007 benchmark. The live queue remains dominated by metadata-completeness, qualification-exclusion, and document-quality issues, and no NOT_READY-to-READY conversions were produced by the Sprint 2 changes.
