# Local Handoff Commands — SYNC-001 Inventory

Run these commands only from the authoritative LMCP checkout. They are read-only except for `git fetch`; they do not reset, clean, commit, switch branches, push, or modify application files.

```bash
pwd
printf '\n=== STATUS ===\n'
git status --short --branch
printf '\n=== CURRENT BRANCH ===\n'
git branch --show-current
printf '\n=== REMOTES ===\n'
git remote -v
printf '\n=== RECENT COMMITS ===\n'
git log --oneline --decorate -20
printf '\n=== WORKTREES ===\n'
git worktree list
printf '\n=== BRANCHES ===\n'
git branch -vv
printf '\n=== FETCH REMOTES ===\n'
git fetch --all --prune
printf '\n=== RELEASE DIVERGENCE (release | local) ===\n'
git rev-list --left-right --count origin/release/v1.1...HEAD
printf '\n=== LOCAL-ONLY COMMITS ===\n'
git log --oneline origin/release/v1.1..HEAD
printf '\n=== RELEASE-ONLY COMMITS ===\n'
git log --oneline HEAD..origin/release/v1.1
printf '\n=== CHANGED PATHS VS RELEASE ===\n'
git diff --name-status origin/release/v1.1...HEAD
printf '\n=== TRACKED ENV/SECRET-LIKE PATHS ===\n'
git ls-files | grep -Ei '(^|/)(\.env($|\.)|.*secret.*|.*credential.*|.*private.*key.*)' || true
```

After reviewing the output, the next mutation step is intentionally separate: create and push a new `sync/authoritative-2026-08-18` branch. Do not combine the inventory and push into one blind script.
