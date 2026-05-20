# Restore Validation Runbook

## Purpose
Validate that the latest backup can be read without mutating runtime state.

## Steps
1. Locate the latest backup manifest.
2. Verify the manifest lists required files.
3. Confirm the database file exists and can be opened.
4. Confirm audit and workflow records remain readable.
5. Record blockers if any check fails.

## Non-Destructive Guarantee
- Validation is read-only.
- No restore writeback occurs in this branch.

## Escalation
- If blockers exist, operators must review and decide whether to restore manually.
