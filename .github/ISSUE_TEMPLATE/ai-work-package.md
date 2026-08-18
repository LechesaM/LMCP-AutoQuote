---
name: AI Work Package
description: Bounded implementation or audit task for controlled multi-agent development
title: "[WORK-ID] "
labels: []
assignees: []
---

## Work package ID

`WORK-ID`

## Roadmap / phase reference

State the governing phase/subphase or `cross-cutting governance`.

## Objective

One outcome only. Describe what must become true.

## Why this is needed

State the defect, capability gap, evidence gap, or approved requirement. Do not use feature enthusiasm as justification.

## Dependencies / gates

- [ ] Required predecessor work is complete.
- [ ] This package is permitted by the current phase gate.
- [ ] Authoritative source branch/ref is identified.

Dependencies:

## In scope

- 

## Explicitly out of scope

- 

## File / component ownership

Primary owned paths/components:

- 

Do not edit these shared/governed areas without an explicit handoff:

- 

## Agent assignment

**Primary implementation agent:**  
**Independent reviewer:**  
**Human decision authority:** `@LechesaM`

## Current behaviour / baseline

Document existing behaviour and the baseline checks run before editing.

## Acceptance criteria

- [ ] 
- [ ] 
- [ ] 

## Required negative / failure paths

- [ ] Missing/invalid input is handled safely.
- [ ] Unauthorized/forbidden behaviour is tested where applicable.
- [ ] Stale/absent/failed evidence cannot become a false readiness/compliance claim where applicable.
- [ ] Retry/failure/idempotency behaviour is considered for asynchronous work where applicable.

Additional package-specific negative paths:

- 

## Security / privacy / tenancy impact

State impact and required tests. Use `none identified` only after inspection.

## Data / migration impact

State schema/data migration requirements and recovery/rollback approach.

## Procurement governance impact

Confirm whether the change affects submission, supplier interaction, buyer forms, evidence validity, pricing, approvals, audit records, or procurement commitments.

## Validation commands / checks

```text
<exact commands/checks>
```

## Evidence required in PR

- [ ] Acceptance criteria mapped to implementation/tests.
- [ ] Exact validation outcomes reported.
- [ ] Changed configuration/migrations documented.
- [ ] Security/privacy/tenant impact reported.
- [ ] Known risks and remaining work reported.
- [ ] Independent review status reported.

## Stop conditions

Stop and escalate rather than improvising if:

- the work conflicts with a repository invariant;
- destructive migration/data loss risk is discovered;
- credentials/secrets appear exposed;
- implementation requires reopening or changing a separately governed phase;
- a material unrelated regression appears;
- scope begins overlapping another active agent branch.
