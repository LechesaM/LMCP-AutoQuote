# Tier 25 Entry Criteria

Tier 25 remains frozen until this gate is reviewed and explicitly reopened by a separate formal decision.

## Purpose

Define the minimum evidence required before Tier 25 can be considered for a pilot, without activating it automatically.

## Required Minimum Evidence

| Criterion | Minimum |
| --- | --- |
| Supervised-live RFQs completed | `10` consecutive |
| Approval failures | `0` |
| Submission review failures | `0` |
| Proof-capture failures | `0` |
| Audit failures | `0` |
| Autonomous submission events | `0` |
| Unresolved material postmortem findings | `0` |
| Unresolved control-integrity remediation items | `0` |

## Required Review Inputs

Any Tier 25 review must reference:

- the RFQ performance ledger
- the consolidated evidence review
- the expansion review after Wave 003
- the latest postmortems
- the current remediation status

## Disqualifiers

Tier 25 must not be considered ready if any of the following are true:

- any autonomous submission was observed
- any governance bypass was observed
- any proof-capture failure remains unresolved
- any audit-preservation issue remains unresolved
- any active remediation item affects control integrity

## Operating Constraint

- Tier 25 is not activated by elapsed time.
- Tier 25 is not activated by a clean dry run alone.
- Tier 25 is not activated by a single good RFQ.
- Tier 25 is not activated automatically after Wave 003.

## Current Status

- Tier 25: frozen
- Track A: `WAIT`
- Track B: `MONITOR`
- Regression Run #2: untouched

## Review Rule

If the minimum evidence is met, Tier 25 should be treated as a separate formal decision with its own pilot plan, operator assignment, and proof-capture requirements.

