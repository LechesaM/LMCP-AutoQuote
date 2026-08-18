# LMCP AutoQuote Agent Operating Contract

This repository uses controlled multi-agent development. This file is authoritative for AI coding agents unless a narrower, explicitly approved task packet states otherwise.

## 1. Prime directive

Ship the smallest change that satisfies the approved work package without weakening procurement governance, security, auditability, evidence integrity, tenant isolation, manual submission control, or existing tested behaviour.

Do not expand scope because an adjacent improvement appears attractive. Record adjacent work separately.

## 2. Human authority

Lechesa Manaba is the human decision authority for roadmap changes, production-governance exceptions, submission automation, supplier automation, security exceptions, and phase closure.

AI agents may propose. They must not silently redefine product policy or certify a phase complete.

## 3. Branch and worktree isolation

- Never develop directly on the repository default/release branch.
- One bounded work package per branch/worktree.
- One primary implementation agent owns a branch at a time.
- Parallel agents must have non-overlapping file ownership unless an explicit handoff is documented.
- Do not rebase, force-push, merge, or rewrite another agent's active branch without explicit instruction.
- Prefer branches named `agent/<work-id>-<short-description>`.

## 4. Agent roles

### Lead implementation agent

Default: Codex.

Responsibilities:
- read the work package and affected code before editing;
- establish a baseline using the relevant existing tests/checks;
- implement only the approved scope;
- add or update tests for changed behaviour;
- document migrations, configuration changes, and operational consequences;
- produce an evidence summary in the pull request.

### Independent review agent

Default: Claude Code or another separately assigned frontier coding agent.

Review mode is read-only first. The reviewer must inspect the diff, surrounding implementation, tests, security boundaries, regressions, failure modes, and acceptance criteria before proposing edits.

The reviewer must classify findings as:
- BLOCKER
- HIGH
- MEDIUM
- LOW
- OBSERVATION

The reviewer does not approve its own remediation work.

### Specialist agents

Frontend, tests, documentation, performance, security, or migration specialists may run in parallel only when their file ownership and acceptance criteria are explicitly bounded in the work package.

## 5. Required implementation loop

For every material change:

1. Read the work package.
2. Identify affected files, data flows, APIs, permissions, migrations, tests, and operational controls.
3. Run the narrowest meaningful baseline checks before editing where feasible.
4. Implement the minimum approved change.
5. Add/update automated tests.
6. Run relevant tests, lint/build/type checks, and governance validators.
7. Self-review the diff for accidental scope expansion and unsafe defaults.
8. Open a draft pull request using the repository template.
9. Obtain independent review for material backend, security, data, workflow, compliance, or production changes.
10. Remediate findings on the implementation branch.
11. Re-run validation after remediation.
12. Human authority decides merge and phase closure.

## 6. Definition of done

A work package is not complete merely because code exists or a test passes. Completion requires, as applicable:

- acceptance criteria are demonstrably satisfied;
- affected tests pass;
- regression risk is addressed;
- frontend build passes for frontend-impacting changes;
- database migrations are reversible or have a documented recovery path;
- security/privacy/tenant-boundary impact is assessed;
- audit/evidence behaviour is preserved;
- operational/configuration changes are documented;
- no real secrets or credentials are committed;
- the pull request contains reproducible validation evidence;
- independent review blockers/high findings are resolved or explicitly accepted by the human authority.

## 7. Procurement and safety invariants

Unless a later explicit human instruction supersedes them:

- tender/RFQ submission remains human-controlled; agents must not introduce autonomous submission;
- supplier automation must not be enabled silently;
- expired compliance evidence may be retained and linked but must not be represented as valid/current evidence;
- uncertainty must not be converted into a false compliance claim;
- generated or inferred values must retain provenance where the workflow requires evidentiary support;
- audit records must remain append-only in intent and must not be silently suppressed to make tests pass.

## 8. Security rules

- Never commit real secrets, tokens, private keys, production passwords, or live credentials.
- Treat `.env.production` and equivalent runtime configuration as sensitive configuration even when values are placeholders.
- Do not weaken authentication, authorization, tenant isolation, rate limiting, logging, TLS, secrets handling, or production guards to unblock a feature.
- New external calls require explicit timeout, failure handling, provenance, and least-privilege consideration.
- Security-sensitive changes require independent review before merge.

## 9. Testing rules

- Do not delete or relax a failing test merely to obtain green CI unless the work package explicitly changes the tested contract.
- New behaviour requires positive and negative-path tests where practical.
- Authorization changes require unauthorized/forbidden-path tests.
- Data migrations require migration/rollback or recovery validation where applicable.
- Queue/worker changes require idempotency and failure/retry consideration.
- If a required test cannot run, state exactly why in the PR; do not claim it passed.

## 10. Evidence standard

Every draft PR must state:

- work-package/phase identifier;
- scope and out-of-scope items;
- files or components changed;
- acceptance criteria mapping;
- exact validation commands/checks and outcomes;
- migrations/configuration changes;
- security/privacy/tenant impact;
- known risks and remaining work;
- independent review status.

Do not use phrases such as `fully complete`, `production ready`, `certified`, or `zero risk` unless the relevant formal gate has actually been executed and evidenced.

## 11. Parallelisation rules

Good parallel work:
- backend endpoint vs isolated frontend consumer;
- independent test expansion;
- documentation/evidence assembly;
- performance harness work isolated from feature implementation;
- read-only security/review audit.

Bad parallel work:
- two agents editing the same service simultaneously;
- independent schema redesigns for the same feature;
- multiple agents changing authentication/authorization in parallel;
- implementation and reviewer sharing the same assumptions without an independent read of the code;
- starting the next roadmap phase before the current closure gate permits it.

## 12. Stop conditions

Stop implementation and surface the issue when:

- requirements conflict with repository invariants;
- a migration risks destructive data loss without an approved recovery plan;
- credentials/secrets appear exposed;
- requested behaviour would bypass human submission control or material security controls;
- the work package cannot be completed without changing a separately governed phase or contract;
- test failures reveal an unrelated but material regression.

Record the blocker; do not improvise around it.
