# Audit Defensibility

LMCP audit defensibility is built around append-only events, evidence continuity, and export-safe summaries.

## Audit chain validation
- Checks for missing event fields.
- Checks timestamp continuity.
- Detects duplicate identifiers.
- Flags orphaned operator actions.

## Evidence continuity
- Evidence-linked audit events are tracked separately from operational noise.
- Missing references are surfaced as review items, not deleted.

## Operator attribution
- Governance actions and operator actions retain operator identity where available.
- No audit record is silently mutated.

## Export readiness
- Audit export packs are JSON-safe and CSV-safe.
- No tokens, credentials, or secrets are included.

