# Live Submission Promotion Rule

Supervised live submission remains blocked until the evidence registry shows all of the following for 4 consecutive weekly dry-dispatch cycles:

| Metric | Requirement |
| --- | --- |
| Pass Rate | `>= 90%` |
| Confidence Score | `>= 85%` |
| Gate Score | `>= 85%` |
| Rollback Rate | `< 2%` |
| Critical Failures | `0` |
| Production Ready Status | Stable for 4 weeks |

## Decision Rule
- If every weekly cycle meets the threshold, the gate status is `eligible_for_supervised_live`.
- Otherwise the gate status remains `hold`.

## Scope Constraint
- This rule is evidence-based only.
- It does not authorize Track A or Track B changes.
- It does not introduce new workflow layers or monitoring logic.
