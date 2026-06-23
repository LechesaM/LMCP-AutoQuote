# Controlled Activation Governance Report

## Scope
This report documents the read-only activation governance surface introduced for controlled tenant and operator activation on the staging rollout path.

## Source Artifacts
- `runtime/staging/production-rollout-validations/*/production_rollout_validation.json`
- `runtime/staging/production-rollout-validations/latest_production_rollout_validation.json`
- `runtime/staging/release-certifications/latest_executive_release_evidence.json`
- `runtime/staging/release-certifications/*/executive_release_evidence.json`

## Governance Contract
The activation surface derives institutional readiness from staged production rollout validation evidence only. It does not mutate runtime state, authorize production submissions, or bypass supervision layers.

## Tracked Readiness Domains
- Tenant activation readiness
- Operator certification readiness
- Supervision assignment readiness
- Staged rollout segmentation
- Throughput expansion readiness
- Rollout freeze indicators
- Escalation readiness
- Operator saturation indicators
- Supervision coverage indicators
- Rollout expansion history

## Safety Guarantees
- Read-only APIs only
- Staging-only evidence source
- No autonomous procurement authority
- No irreversible actions
- No production submission enablement
- Human supervision remains mandatory
- Dry-run protections remain active

## Operational Interpretation
- `GO` indicates the staged activation evidence is ready for supervised rollout expansion.
- `WATCH` indicates the evidence is usable but should remain under review.
- `NO_GO` indicates a blocker or freeze condition that prevents supervised rollout expansion.

## Runtime Surfaces
- `GET /rfq-lifecycle/activation-governance`
- `GET /rfq-lifecycle/activation-governance/latest`
- `GET /rfq-lifecycle/activation-governance/history`

