---
name: AI Agent Work Package
about: Create a bounded, reviewable LMCP AutoQuote implementation task
labels: agent-work
---

# Work package

## Identity

- Work ID:
- Roadmap phase/sub-phase:
- Human owner: Lechesa Manaba
- Primary implementation agent:
- Independent review agent:
- Proposed branch: `agent/<work-id>-<short-description>`

## Problem / objective

State the operational problem and the exact outcome required. Avoid solution sprawl.

## Current-state evidence

- Relevant files/components:
- Existing tests/validators:
- Known baseline behaviour:
- Related issues/PRs/evidence:

## In scope

- 

## Out of scope

- 

## File ownership for parallel work

| Agent / role | Allowed paths/components | Must not edit |
|---|---|---|
| Primary | | |
| Specialist (optional) | | |
| Reviewer | Read-only first | All until review findings are issued |

## Acceptance criteria

- [ ] AC-1:
- [ ] AC-2:
- [ ] AC-3:

## Required negative / failure cases

- [ ] Unauthorized/forbidden path where applicable
- [ ] Invalid or incomplete input
- [ ] Dependency/external-service failure where applicable
- [ ] Retry/idempotency where applicable
- [ ] Tenant-boundary failure where applicable

## Governance invariants

- [ ] Human submission control must remain intact
- [ ] Supplier automation must not be silently enabled
- [ ] Evidence provenance/auditability must remain intact
- [ ] Expired evidence must not be treated as current/valid
- [ ] Uncertainty must not become a false compliance claim
- [ ] No weakening of auth/security/tenant isolation

## Required validation

List exact expected checks before implementation begins where possible.

```text
<backend tests>
<frontend tests/build>
<governance validators>
<migration/recovery checks>
```

## Evidence required for completion

- [ ] Diff mapped to acceptance criteria
- [ ] Exact test/check outputs recorded
- [ ] Migration/config impact documented
- [ ] Security/privacy/tenant impact assessed
- [ ] Rollback/recovery path documented where applicable
- [ ] Independent review completed
- [ ] BLOCKER/HIGH findings resolved or accepted by human authority

## Stop / escalation conditions

Stop and report instead of improvising if the work requires destructive migration without recovery, conflicts with governed behaviour, exposes credentials, bypasses human submission control, weakens security controls, or requires reopening a separately closed phase.
