# Supervised-Live Expansion Triggers

These triggers define when the program may reopen a Tier 25 discussion or consider broader expansion. They are intentionally objective and evidence-based.

## Minimum Triggers

Expansion review may be reopened only after all of the following are true:

| Trigger | Threshold |
| --- | --- |
| Consecutive supervised-live RFQs completed | `10` |
| Governance failures | `0` |
| Audit failures | `0` |
| Proof-capture failures | `0` |
| Submission bypasses | `0` |
| Material postmortem findings | `0` |
| Unresolved remediation items affecting control integrity | `0` |

## Required Review Inputs

Any expansion review must reference:

- the RFQ performance ledger
- the consolidated evidence review
- the latest postmortems
- the current remediation status
- the operator review history

## Non-Triggers

The following do not justify expansion on their own:

- elapsed time
- successful completion of a single additional RFQ
- a clean dry-run only
- a clean approval only
- a clean proof capture only

## Current Position

- Tier 25: frozen
- Multi-RFQ expansion: not authorized
- Operating mode: continue RFQ-by-RFQ supervised-live only
- Monitoring layer: unchanged

## Review Rule

When the minimum triggers are met, Tier 25 should be reviewed as a separate formal decision. It should not be activated automatically.

