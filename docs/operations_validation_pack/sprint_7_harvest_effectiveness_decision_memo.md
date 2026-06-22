# Sprint 7 Harvest Effectiveness Decision Memo

## Run Summary

Harvest effectiveness command:

- `python3 scripts/run_harvest_effectiveness_sprint7.py --limit 200 --timeout 20`

Observed coverage metrics:

| Metric | Value |
| --- | ---: |
| Configured sources | 1040 |
| Enabled sources | 1040 |
| Unique URLs | 1040 |
| Attempted sources | 200 |
| Reachable sources | 0 |
| RFQ-producing sources | 1 |
| Qualified RFQ sources | 1 |
| Submission-candidate sources | 1 |
| Harvest coverage | 19.23% |
| RFQ-producing source rate | 0.5% |

Observed top failure type:

- `dns_failed`: `200`

## Decision

### Promote

- `National Treasury eTenders`

This is the only source in the current harvest-effectiveness evidence set with substantive RFQ production. Keep it as the reference producer for yield comparisons.

### Retry

- The 200 attempted enabled sources in the current run

Reason: every attempted source failed at the acquisition layer with `dns_failed`. That is a transport/reachability issue, not a qualification or governance issue. Retry is appropriate after reachability / DNS / host routing is reviewed.

### Quarantine

- None based on this run alone

Reason: a single DNS-failed effectiveness run is not enough to mark sources dead. The current evidence supports retry and maintenance review, not removal.

## Interpretation

The current limiter is source effectiveness and transport reachability, not registry size.

This run shows:

- coverage improved to `19.23%`
- the registry stayed unchanged at `1,040` enabled sources
- the productive source set remains extremely small
- the acquisition layer is the dominant failure point in this sample

## Recommended Next Action

1. Keep Sprint 7 governance frozen.
2. Retry the attempted source set after transport / DNS review.
3. Keep `National Treasury eTenders` as the primary reference producer.
4. Continue toward the `15` live-RFQ checkpoint without changing qualification, approval, audit, or submission rules.
5. Reassess quarantine decisions only after repeated failed harvest cycles.

## Guardrails

- Portal submission remains disabled.
- Human approval remains required.
- No autonomous submission.
- No approval injection.
- No qualification threshold changes.
- No governance rule changes.
- No submission execution.
