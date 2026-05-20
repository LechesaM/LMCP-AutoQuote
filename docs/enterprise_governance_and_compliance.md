# Enterprise Governance and Compliance

LMCP governance is manual-first, audit-defensible, and retention-aware.

## Governance architecture
- Policy registry and policy versioning capture the active governance catalog.
- Compliance controls validate manual approval, review readiness, proof capture, attribution, and retention readiness.
- Audit validation and evidence-chain tracking keep the trail exportable and reviewable.
- Legal holds override routine retention enforcement where required.

## Compliance philosophy
- No autonomous procurement execution.
- No autonomous submission.
- No auto-approval.
- No bypass of `review_ready` or proof capture.
- Every governance action is explicit, attributable, and auditable.

## Audit defensibility
- Audit events remain append-only.
- Integrity monitoring checks event continuity, ordering, and attribution.
- Export packaging keeps the audit chain readable without secrets or tokens.

## Manual governance enforcement
- Governance actions require supervisor/admin/governance access.
- Destructive retention actions are dry-run by default.
- Legal holds are registered and released explicitly.

