# AUDIT-002 — Post-Synchronisation Audit Scope

Once `sync/authoritative-2026-08-18` (or the intentionally chosen equivalent) is on GitHub, audit the synchronised branch against the current release branch and the approved roadmap.

Minimum scope:

- repository topology and application entrypoints;
- current backend routes/services and frontend workspaces;
- database/schema/migrations;
- authentication/authorization/tenant isolation;
- intake and ACTIVE_RFQ governance;
- pricing/profit controls;
- supplier/submission automation safety boundaries;
- production hardening and cutover readiness;
- HA/distributed sessions;
- queue/worker/autoscaling governance;
- DR/BCP;
- observability/runbooks;
- production deployment controls;
- generic and specialised CI coverage;
- secret/environment hygiene;
- real evidence versus placeholder/scaffold status;
- Phase 65 closure blockers and exact transition prerequisites.

The audit must not infer implementation from roadmap text. Every completion claim must point to code plus appropriate validation/evidence.
