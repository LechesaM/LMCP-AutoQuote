# Safe Parallelism Rules

Parallel AI work is permitted only when all of the following are true:

1. The authoritative source branch is known and current.
2. Each work package has one primary implementation owner.
3. File/component ownership does not overlap, or an explicit handoff exists.
4. Acceptance criteria and negative paths are defined before editing.
5. Shared schemas, authentication, tenant boundaries and core procurement workflow are not being independently redesigned by competing agents.
6. Each branch can be validated independently before integration.
7. An integration gate exists after parallel branches converge.
8. Material changes receive independent review.
9. Human authority controls final merge and phase closure.

Until SYNC-001 is complete, only read-only analysis and governance preparation are parallel-safe.
