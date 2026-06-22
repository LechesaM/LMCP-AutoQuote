# Sprint 7 Source Coverage Decision Memo

## Purpose

Classify source coverage outcomes after the 20-source Sprint 7 harvest-effectiveness probe and the follow-up DNS/runtime checks.

## Probe Summary

Command run:

- `python3 scripts/run_harvest_effectiveness_sprint7.py --limit 20 --timeout 20`

Observed result:

| Metric | Value |
| --- | ---: |
| Configured sources | 1040 |
| Enabled sources | 1040 |
| Unique URLs | 1040 |
| Attempted sources | 20 |
| Reachable sources | 0 |
| RFQ-producing sources | 1 |
| Qualified RFQ sources | 1 |
| Submission-candidate sources | 1 |
| Harvest coverage | 1.92% |
| RFQ-producing source rate | 5.0% |
| Top failure type | `dns_failed` (`20`) |

## Manual Investigation

Checked representative failed hosts from the attempted set:

- `secure.csd.gov.za`
- `www.etenders.gov.za`

Results:

- `curl --max-time 10 -I https://secure.csd.gov.za/` returned `HTTP/1.1 200 OK`
- `curl --max-time 10 -I https://www.etenders.gov.za/` returned `HTTP/1.1 200 OK`
- `python3 -c 'socket.getaddrinfo(...)'` failed for both hosts with `gaierror: [Errno 8] nodename nor servname provided, or not known`
- `nslookup` in this sandbox failed with `bind: Operation not permitted`

## Interpretation

This is not a clean source-specific DNS failure.

The evidence points to a runtime/DNS path problem in the Python preflight layer used by the Sprint 7 effectiveness script:

- `curl` can resolve and reach the hosts
- Python socket resolution fails in this execution environment
- the script’s current preflight classifier reports `dns_failed` for the attempted sources

## Classification

### Promote

- `National Treasury eTenders`

It remains the only clear producer in the harvest-effectiveness leaderboard.

### Retry

- The attempted source set after fixing or bypassing the Python DNS/runtime path

Reason: the current `dns_failed` sample is not sufficient to quarantine the source registry. Re-run after the runtime path is corrected.

### Quarantine

- None at this time

Reason: there is no evidence yet that the attempted sources themselves are bad URLs. The failure pattern is environment-linked.

### Investigate DNS/runtime

- Python preflight DNS resolution in `scripts/run_harvest_effectiveness_sprint7.py`
- The local DNS/runtime path used by `socket.getaddrinfo`

### Immediate Investigation

- Why the Python socket path fails while `curl` succeeds
- Whether the effectiveness script should use the same network path as the rest of the runtime stack
- Whether the sandbox/local runtime is blocking Python socket DNS differently from curl

## Decision Rule Application

Applied conservatively:

- If `80%+` of attempted sources fail DNS, do not add more sources
- Investigate DNS/runtime/network configuration first

That rule is triggered here, but the follow-up manual checks show the problem is likely environmental rather than source-specific.

## Recommendation

1. Keep Sprint 7 governance frozen.
2. Do not add more sources until the Python DNS/runtime path is understood.
3. Treat the current `dns_failed` result as a runtime investigation item, not a quarantine signal.
4. Keep `National Treasury eTenders` as the reference producer.
5. Re-run the harvest-effectiveness command after the DNS/runtime path is corrected.
6. Continue toward the `15` live-RFQ checkpoint unchanged.

## Guardrails

- Portal submission remains disabled.
- Human approval remains required.
- No autonomous submission.
- No approval injection.
- No qualification threshold changes.
- No governance rule changes.
- No submission execution.
