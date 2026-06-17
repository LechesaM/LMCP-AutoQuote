# Supervised-Live RFQ Performance Ledger

This ledger records supervised-live RFQs as operational evidence. It is intentionally narrow: one row per RFQ, with outcome and issues captured in plain terms.

## Ledger

| RFQ | Outcome | Submission Method | Approval Issues | Proof Issues | Observations |
| --- | --- | --- | --- | --- | --- |
| `REAL-PILOT-001` | `PASS WITH OBSERVATIONS` | Portal with email fallback | None recorded | Placeholder proof corrected; active proof entry now valid | Quote-comparison enrichment was thin at first and required evidence correction |
| `RFQ_004` | `PASS WITH OBSERVATIONS` | Portal with email fallback | None recorded | Placeholder / invalid proof entries corrected; active proof entry now valid | Quote-comparison enrichment remained the only standing observation |
| `RFQ_005` | `PASS WITH OBSERVATIONS` | Courier / hand delivery | None recorded | Literal proof-path entry corrected; active proof entry now valid | Physical submission-route verification and proof-of-delivery handling still require explicit confirmation |

## Ledger Rules

- Add one row per supervised-live RFQ.
- Record the real submission method used.
- Record approval issues only when they affect the governed approval step.
- Record proof issues only when they affect proof capture or proof correction.
- Record operational observations separately from control failures.
- Do not retroactively rewrite outcomes; append corrections as governed evidence.

## Next RFQ Update Checklist

Use this checklist after each additional supervised-live RFQ, starting with RFQ `#4`:

- Add one new ledger row for the RFQ.
- Record the final outcome as `PASS`, `PASS WITH OBSERVATIONS`, or `HOLD`.
- Record the actual submission method used.
- Record approval issues only if the governed approval step was affected.
- Record proof issues only if proof capture or proof correction was affected.
- Record operational observations in plain language, separate from control failures.
- Confirm the entry reflects the final governed evidence state, not an intermediate draft state.

## Current Status

- Supervised-live RFQ tracking is operational.
- No autonomous submission behavior is recorded.
- Tier 25 remains frozen.
- Track A remains `WAIT`.
- Track B remains `MONITOR`.
- Regression Run #2 remains untouched.
