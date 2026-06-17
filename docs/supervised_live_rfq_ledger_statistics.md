# Supervised-Live RFQ Ledger Statistics

This is a static summary document derived from the current RFQ performance ledger. It is read-only and does not introduce a live reporting tool or any new workflow.

## Evidence Basis

- Source ledger: `Documents/docs/supervised_live_rfq_performance_ledger.md`
- RFQs included: `REAL-PILOT-001`, `RFQ_004`, `RFQ_005`
- Population basis: the existing three supervised-live ledger rows only

## Outcome Summary

| Metric | Count |
| --- | ---: |
| Total supervised-live RFQs | 3 |
| `PASS` | 0 |
| `PASS WITH OBSERVATIONS` | 3 |
| `HOLD` | 0 |
| Approval issues recorded | 0 |
| Proof issues recorded | 3 |

## Submission Method Breakdown

| Submission Method | Count |
| --- | ---: |
| Portal with email fallback | 2 |
| Courier / hand delivery | 1 |
| Email-only | 0 |

## Issue Summary

| Issue Type | Count | Notes |
| --- | ---: | --- |
| Approval issues | 0 | No governed approval-step failures recorded |
| Proof corrections required | 3 | Each RFQ required proof or proof-entry correction before the active proof record was valid |
| Unresolved proof failures | 0 | Current ledger state records valid active proof entries for all three RFQs |

## Recurring Observations

| Observation | Count | Status |
| --- | ---: | --- |
| Proof correction required after initial capture | 3 | Recurring trend to monitor |
| Physical submission-route confirmation required for courier / hand-delivery RFQs | 1 | Route-specific observation |
| Quote-comparison enrichment observation | 2 | Historical observation; remediation completed successfully |

## RFQ-Level Summary

| RFQ | Outcome | Submission Method | Approval Issues | Proof Issues | Observation Focus |
| --- | --- | --- | --- | --- | --- |
| `REAL-PILOT-001` | `PASS WITH OBSERVATIONS` | Portal with email fallback | None recorded | Placeholder proof corrected; active proof entry valid | Quote-comparison enrichment initially thin |
| `RFQ_004` | `PASS WITH OBSERVATIONS` | Portal with email fallback | None recorded | Placeholder / invalid proof entries corrected; active proof entry valid | Quote-comparison enrichment remained the standing observation |
| `RFQ_005` | `PASS WITH OBSERVATIONS` | Courier / hand delivery | None recorded | Literal proof-path entry corrected; active proof entry valid | Physical submission-route verification and proof-of-delivery handling required explicit confirmation |

## Expansion Readiness

The current ledger history does not meet the documented minimum trigger for reopening expansion review.

| Trigger | Threshold | Current Static Position |
| --- | --- | --- |
| Consecutive supervised-live RFQs completed | `10` | `3 of 10` |
| Governance failures | `0` | `0` recorded in the ledger |
| Audit failures | `0` | `0` recorded in this summary set |
| Proof-capture failures | `0` | `0` unresolved failures, but `3` correction events were observed |
| Submission bypasses | `0` | `0` recorded |
| Material postmortem findings | `0` | Not cleared by this document |
| Unresolved remediation items affecting control integrity | `0` | Not cleared by this document |

## Interpretation

- All three recorded supervised-live RFQs currently sit in `PASS WITH OBSERVATIONS`.
- The dominant repeated pattern is not approval failure; it is proof correction after initial capture.
- Portal with fallback is the most common route in the current three-RFQ set.
- Courier / hand-delivery handling appears only once so far, and should be treated as a route-specific monitoring point rather than a cross-RFQ trend.
- Quote-comparison enrichment appeared in two of the three ledger rows, but it should be read as a historical observation rather than a currently open remediation signal.
- The evidence remains too small and too observation-heavy to support any claim that expansion triggers have been crossed.

## Relationship To Existing Controls

- Tier 25 remains frozen.
- Track A remains `WAIT`.
- Track B remains `MONITOR`.
- Regression Run #2 remains untouched.
- Multi-RFQ expansion remains not authorized unless the documented expansion triggers are met through separate review.

## Next RFQ Update Checklist

Use this checklist after each additional supervised-live RFQ, starting with RFQ `#4`:

- Update the `Evidence Basis` RFQ list to include the new RFQ.
- Increase total supervised-live RFQ count by one.
- Recalculate outcome counts for `PASS`, `PASS WITH OBSERVATIONS`, and `HOLD`.
- Recalculate approval-issue and proof-issue counts from the ledger state.
- Update the submission-method breakdown.
- Update recurring observations only when the new RFQ adds repeated evidence or closes a prior pattern.
- Update expansion readiness progress against the `10` consecutive supervised-live RFQ threshold.
- Reconfirm that Tier 25, multi-RFQ authorization, Track A, Track B, and Regression Run #2 remain unchanged unless a separate formal decision says otherwise.
