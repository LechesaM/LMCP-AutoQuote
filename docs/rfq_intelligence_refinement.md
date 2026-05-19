# RFQ Intelligence Refinement

## Purpose
This layer refines RFQ qualification decisions using real tender language patterns.
It improves advisory decision quality only.

## Language Intelligence Rules
The language intelligence layer detects and scores:
- compulsory briefing session
- non-compulsory briefing
- mandatory site inspection
- functionality scoring
- minimum functionality threshold
- CIDB requirement
- local content requirement
- subcontracting requirement
- OEM or accreditation requirement
- sample requirement
- warranty requirement
- delivery deadline
- contract duration
- disqualification clauses
- late submission clauses
- pricing schedule requirement
- company letterhead requirement
- e-submission requirement
- email submission requirement
- physical/dropbox submission requirement

Outputs include:
- detected patterns
- risk flags
- manual-review triggers
- disqualification triggers
- confidence
- evidence phrases

## Readiness States
Submission readiness states are:
- `READY`
- `MISSING_DOCS`
- `HIGH_RISK`
- `MANUAL_ONLY`
- `BLOCKED`

Rules:
- physical, courier, or dropbox submission -> `MANUAL_ONLY`
- missing mandatory compliance documents -> `MISSING_DOCS`
- functionality-heavy RFQ -> `HIGH_RISK`
- excluded category -> `BLOCKED`
- email plus complete documents plus clear pricing plus low risk -> `READY`

## Supplier Match Intelligence
Supplier match intelligence scores:
- supplier domain confidence
- stock availability risk
- delivery feasibility
- logistics complexity
- specialization requirement
- local supplier advantage
- supplier evidence required

This is advisory only and does not call any live supplier API.

## Pricing Evidence Integration
Pricing evidence strengthens advisory qualification without changing workflow governance.
It can surface:
- supplier evidence completeness
- pricing defensibility
- pricing validation warnings
- quote aging risk
- pricing confidence
- traceability summaries

These signals remain advisory only and do not authorize submission or bypass manual controls.

## Risk Engine
The risk engine scores:
- technical risk
- operational risk
- pricing risk
- compliance risk
- delivery risk
- adjudication risk
- submission risk
- overall risk

Risk levels:
- low
- medium
- high
- blocked

Manual-review triggers include:
- functionality threshold
- technical fabrication
- physical submission
- sample requirement
- OEM or accreditation requirement
- unclear pricing schedule
- missing closing date
- ambiguous submission method

## Next Operator Action
The next operator action is derived from the readiness and risk signals.
It remains advisory only and never authorizes autonomous submission.

## Governance Preservation
- No autonomous final submission
- No bypass of manual approval
- No bypass of review_ready
- No bypass of proof capture
- No legacy router reactivation
- No new router versions
