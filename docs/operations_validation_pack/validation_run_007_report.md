# Validation Run 007 Report

## Summary

Run 007 measured the live queue again after Sprint 1.3 metadata-recovery hardening.

| KPI | Run 006 Live Benchmark | Run 007 |
| --- | ---: | ---: |
| READY | 0 | 2 |
| NOT READY | 15 | 13 |
| Metadata / Completeness | 11 | 13 |
| Qualification Exclusion | 6 | 2 |
| Technical Validation Gate | 0 | 0 |
| Document Generation | 10 | 0 |
| Extraction | 10 | 0 |

## What Changed

- The first READY outcomes now appear on the live queue benchmark.
- Recovered closing dates and recovered source/detail URLs are sufficient to convert some records to READY.
- The live queue remains harsher than the curated validation inventory, but the recovery layer is now actively changing outcomes.

## Key Recovery Signals

| Signal | Count |
| --- | ---: |
| `boq` | 13 |
| `sbd_or_returnables` | 13 |
| `pricing_schedule` | 4 |
| `quote_pack` | 3 |

## Conclusion

Sprint 1.3 is partially effective: it does produce READY conversions on the live queue, but metadata/completeness remains the dominant blocker in the measured benchmark. The next step should remain metadata recovery hardening rather than Sprint 2.
