# Operator Onboarding and Certification Program

## Purpose

This program defines the minimum supervised onboarding and certification expectations for operators participating in controlled production rollout governance.

## Eligibility

Operators must be able to demonstrate:

- active supervision responsibility
- escalation-chain awareness
- readiness evidence review capability
- rollback awareness
- dry-run and safety boundary understanding

## Certification Checks

Operator readiness is assessed against:

- supervision coverage
- operator availability
- escalation-chain readiness
- acknowledgment of unresolved blockers
- review of current release authorization

## Certification Statuses

- `READY`
- `WATCH`
- `BLOCKED`

Only `READY` operators may participate in supervised rollout review sessions.

## Required Review Topics

- release authority and read-only governance
- rollout readiness evidence
- deployment health and tenant isolation
- observability and escalation chains
- rollback and halt expectations

## Safety Constraints

- No autonomous deployment authority.
- No autonomous submission authority.
- No production credentials beyond supervised access controls.
- No irreversible operational actions.

## Continuous Re-Certification

Operator certification must be revisited whenever:

- rollout readiness changes materially
- escalation conditions are triggered
- governance history indicates drift
- supervision coverage falls below threshold
