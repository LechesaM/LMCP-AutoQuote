# SYNC-001 — Authoritative Local State Synchronisation Checklist

This checklist is intentionally conservative. Its purpose is to move the current local LMCP working state into a reviewable GitHub branch **without losing work and without overwriting `release/v1.1`**.

## Stop immediately if

- the directory is not the intended LMCP repository;
- `git status` reports work you do not recognise;
- the remote points to a different repository;
- a command proposes a reset, clean, destructive checkout, force-push, or history rewrite;
- secret-sensitive files appear staged for publication and their safety is unknown.

## 1. Inventory only — no mutation

Run from the authoritative LMCP project directory:

```bash
pwd
printf '\n=== STATUS ===\n'
git status --short --branch
printf '\n=== BRANCH ===\n'
git branch --show-current
printf '\n=== REMOTES ===\n'
git remote -v
printf '\n=== RECENT COMMITS ===\n'
git log --oneline --decorate -20
printf '\n=== WORKTREES ===\n'
git worktree list
printf '\n=== LOCAL BRANCHES ===\n'
git branch -vv
```

Do not continue until this inventory has been reviewed.

## 2. Preserve uncommitted work

If the authoritative state contains uncommitted changes, do **not** run `git reset --hard`, `git clean`, or switch branches destructively.

The preferred path is to make an intentional checkpoint commit on the existing development branch after reviewing what belongs in the repository. Generated files, credentials and local runtime artifacts must not be blindly included.

If a checkpoint commit is inappropriate, create a complete external backup before any branch manipulation.

## 3. Fetch remote state

After the inventory and local changes are safe:

```bash
git fetch --all --prune
```

Then inspect divergence:

```bash
printf '\n=== RELEASE DIVERGENCE ===\n'
git rev-list --left-right --count origin/release/v1.1...HEAD
printf '\n=== COMMITS LOCAL ONLY ===\n'
git log --oneline origin/release/v1.1..HEAD
printf '\n=== COMMITS RELEASE ONLY ===\n'
git log --oneline HEAD..origin/release/v1.1
```

Do not interpret a large count as permission to merge automatically.

## 4. Create a non-destructive sync branch

From the authoritative local state:

```bash
git switch -c sync/authoritative-2026-08-18
```

If that branch name already exists, stop and inspect it rather than deleting it.

## 5. Inspect publish surface

Before pushing:

```bash
printf '\n=== CHANGED PATHS VS RELEASE ===\n'
git diff --name-status origin/release/v1.1...HEAD
printf '\n=== TRACKED ENV-LIKE FILES ===\n'
git ls-files | grep -E '(^|/)(\.env($|\.)|.*secret.*|.*credential.*|.*private.*key.*)' || true
```

Review any environment, credential, key, database, runtime export, procurement evidence or personal-data paths before publication.

## 6. Push only the sync branch

```bash
git push -u origin sync/authoritative-2026-08-18
```

**Never use `--force` for this synchronisation.**

## 7. Reconciliation gate

After the branch is visible on GitHub:

- compare it with `release/v1.1`;
- open a draft PR only;
- run the Phase 65 engineering audit against the sync branch;
- inspect secrets and generated artifacts;
- determine which release-branch commits must be preserved;
- resolve conflicts deliberately;
- merge only after human review.

## Completion evidence

SYNC-001 is complete only when:

- the authoritative local state is safely backed up/preserved;
- a non-destructive sync branch exists on GitHub;
- release/local divergence is documented;
- no known secret or local-only artifact has been accidentally published;
- a draft reconciliation PR is available for audit;
- `release/v1.1` has not been force-rewritten.
