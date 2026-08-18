# AI Development Factory Status

**Current state:** Gate 0 — source-of-truth synchronisation required.

| Work ID | Priority | State | Dependency |
|---|---:|---|---|
| SYNC-001 | P0 | BLOCKING / READY TO EXECUTE LOCALLY | none |
| AUDIT-002 | P0 | BLOCKED | SYNC-001 |
| GOV-003 | P0 | BLOCKED | AUDIT-002 |
| CAP-004 | P0 | BLOCKED | AUDIT-002 |
| CI-005 | P0 | BLOCKED | AUDIT-002 |
| SEC-006 | P0 | BLOCKED | SYNC-001 + AUDIT-002 |
| HA-007 | P1 | BLOCKED | AUDIT-002 + applicable P0 remediation |
| LOAD-008 | P1 | BLOCKED | CAP-004 + HA-007 + CI-005 |
| REVIEW-009 | P1 | CONTROL TO ADOPT | governance factory adoption |
| FACTORY-010 | P1 | PENDING | governance factory adoption |

Do not move a blocked item to implementation merely to increase parallel utilisation. The purpose of the factory is controlled throughput, not maximum simultaneous edits.
