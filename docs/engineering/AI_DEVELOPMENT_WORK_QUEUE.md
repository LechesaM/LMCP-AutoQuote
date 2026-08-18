# LMCP AutoQuote — AI Development Factory Work Queue

**Queue version:** 1.0  
**Created:** 2026-08-18  
**Control branch:** `governance/ai-development-factory-v1`  
**Default/release branch:** `release/v1.1`

## Operating rule

No item below may bypass its dependency gate. Parallelism begins only where file ownership and behavioural contracts are sufficiently independent.

## Gate 0 — Source-of-truth synchronisation

### SYNC-001 — Synchronise authoritative August local checkout to GitHub

**Priority:** P0 / BLOCKER  
**Owner role:** Lead implementation/operator  
**Parallel-safe:** No — all downstream work waits for this gate.

**Objective**

Capture the current authoritative local LMCP working state on a new GitHub branch without destructive history rewriting and reconcile it against `release/v1.1`.

**Required procedure**

1. From the authoritative local LMCP checkout, capture:
   - repository root;
   - `git status --short --branch`;
   - current branch;
   - remote URLs;
   - latest 20 commits;
   - local vs remote ahead/behind state;
   - untracked and modified files;
   - existing worktrees.
2. Do not discard, clean, reset, force-push or rebase uncommitted work.
3. If uncommitted changes exist, preserve them intentionally before synchronisation.
4. Fetch remote refs.
5. Create a new sync branch from the authoritative local state, e.g. `sync/authoritative-2026-08-18`.
6. Push only that new branch.
7. Compare it to `release/v1.1`.
8. Open a draft reconciliation PR; do not merge automatically.
9. Audit secrets, generated artifacts and local-only files before any merge.

**Acceptance criteria**

- No force-push to `release/v1.1`.
- No local work is lost.
- GitHub contains a reviewable branch representing the current local source state.
- Divergence from `release/v1.1` is quantified and reviewable.
- Secret-sensitive files are identified before merge.

---

## Gate 1 — Re-establish engineering truth

### AUDIT-002 — Re-run Phase 65 implementation audit on synchronised branch

**Priority:** P0  
**Depends on:** SYNC-001  
**Owner role:** ChatGPT/control + independent reviewer  
**Parallel-safe:** Limited, read-only audit tasks may run in parallel.

**Objective**

Classify each remaining Phase 65 capability as implemented, partial, scaffold, placeholder-risk, or absent using the synchronised code rather than roadmap memory.

**Required outputs**

- implementation matrix;
- test/evidence matrix;
- unresolved blockers;
- dependency graph;
- exact closure path into Phase 66;
- explicit list of work that must not be reopened.

---

## Gate 2 — P0 remediation packages

These may execute in parallel only after AUDIT-002 confirms they remain applicable and assigns non-overlapping file ownership.

### GOV-003 — Replace synthetic production-readiness declarations with evidence-backed gates

**Priority:** P0  
**Depends on:** AUDIT-002  
**Suggested primary agent:** Codex  
**Independent review:** Required

**Scope candidates**

- operational runbook readiness;
- production hardening readiness;
- production cutover readiness;
- evidence provenance/status semantics;
- negative-path tests for absent/stale/failed evidence.

**Acceptance criteria**

- `ready=true` cannot arise solely from hardcoded/static category defaults where empirical evidence is required;
- stale, placeholder or absent evidence cannot be represented as exercised operational capability;
- safety controls remain conservative;
- readiness output explains evidence source, timestamp/status and blockers.

### CAP-004 — Make autoscaling readiness evidence-based

**Priority:** P0  
**Depends on:** AUDIT-002  
**Suggested primary agent:** Codex/performance specialist  
**Independent review:** Required

**Acceptance criteria**

- placeholder strings/manifests cannot satisfy production autoscaling readiness;
- configuration-readiness and exercised-capability are distinct states;
- queue-depth/worker scaling uses measured evidence where production-readiness is claimed;
- tests cover placeholder, stale, failed and measured-success paths.

### CI-005 — Expand ordinary PR CI to backend regression validation

**Priority:** P0  
**Depends on:** AUDIT-002  
**Suggested primary agent:** CI/test specialist

**Acceptance criteria**

- relevant backend pytest suite runs for ordinary PRs;
- frontend/library checks remain;
- production-governance validators remain available;
- CI avoids silently skipping material backend changes;
- test partitioning may be used for speed but must preserve meaningful coverage.

### SEC-006 — Production environment and secret hygiene

**Priority:** P0  
**Depends on:** SYNC-001, AUDIT-002  
**Suggested primary agent:** security specialist  
**Independent review:** Required

**Acceptance criteria**

- determine whether `.env.production` should remain tracked; prefer safe example/template separation;
- inspect history for accidental real credentials/secrets;
- identify any credentials that require rotation because they were live or reused;
- prevent future secret commits through repository controls/scanning where practical;
- production configuration does not rely on default placeholder passwords/secrets.

---

## Gate 3 — Production proof packages

### HA-007 — Revalidate HA and distributed runtime against real infrastructure

**Priority:** P1  
**Depends on:** AUDIT-002 and relevant P0 remediation

**Evidence required**

- multi-instance application behaviour;
- session continuity/distributed session backend;
- database primary/replica or equivalent topology and failover behaviour;
- Redis/cache/broker availability and degradation behaviour;
- worker failover/recovery and idempotency;
- no hidden local-storage/shared-process assumptions.

### LOAD-008 — Capacity and concurrency certification harness

**Priority:** P1  
**Depends on:** CAP-004, HA-007, CI-005

**Objective**

Replace declarative capacity readiness with reproducible measured workload evidence under realistic procurement activity.

**Required outputs**

- workload model;
- concurrency levels and ramp strategy;
- latency/error/throughput/queue/database metrics;
- resource saturation and autoscaling observations;
- failure/recovery scenarios;
- evidence bundle and repeatable commands/configuration;
- explicit certified envelope rather than aspirational capacity.

### REVIEW-009 — Independent second-agent audit gate

**Priority:** P1 / recurring control  
**Depends on:** governance factory adoption

For material backend, security, workflow, compliance, data or production PRs, a second agent performs a read-only-first review and classifies findings as BLOCKER/HIGH/MEDIUM/LOW/OBSERVATION. The implementation agent may remediate findings, but cannot independently certify its own remediation.

### FACTORY-010 — Enforce protected release workflow

**Priority:** P1  
**Depends on:** governance factory adoption

**Objective**

Configure GitHub repository protection/rulesets so the documented process is enforceable rather than voluntary.

**Target controls**

- no direct routine pushes to `release/v1.1`;
- required CI checks;
- code-owner/human review for governed surfaces;
- resolved review conversations before merge where appropriate;
- prevent force pushes/deletion of protected release branch;
- preserve human merge/phase-closure authority.

## Parallel execution model after Gate 1

```text
                         AUDIT-002
                            |
          +-----------------+-----------------+
          |                 |                 |
       GOV-003           CAP-004           CI-005
          |                 |                 |
          +--------+--------+                 |
                   |                          |
                SEC-006 <---------------------+
                   |
              integration gate
                   |
              independent review
                   |
          +--------+--------+
          |                 |
       HA-007            REVIEW-009
          |
       LOAD-008
          |
       Phase gate evidence
```

This graph is provisional until the authoritative August branch is synchronised and audited.

## Agent allocation

- **ChatGPT/control:** task decomposition, dependency control, acceptance criteria, repository/PR audit, review synthesis, closure recommendations.
- **Codex:** default implementation agent for bounded work packages.
- **Independent reviewer:** Claude Code or another separately instructed capable coding agent; read-only first.
- **Human authority:** approves roadmap exceptions, merges governed changes, accepts material risk and closes formal phase gates.

## Prohibited shortcuts

- Do not begin Phase 66/67 implementation merely because a readiness service reports `GO`.
- Do not treat unit-test success as production-capacity certification.
- Do not allow placeholder configuration to satisfy exercised production capability.
- Do not merge the stale GitHub branch over newer local work.
- Do not run multiple implementation agents against overlapping authentication, schema, tenancy or core workflow code.
- Do not relax tests/security controls to obtain a green build.
