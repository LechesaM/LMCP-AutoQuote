# Production Runtime Baseline

This document defines the unified runtime and configuration baseline for `branch-b-unified-config-runtime`.

## Official runtime structure

The runtime and filesystem layout is centralized in `app/core/runtime_paths.py`.

- Runtime root: `LMCP_RUNTIME_DIR` or `<project>/runtime`
- Logs: `runtime/logs`
- Downloads: `LMCP_MONTHLY_QUOTES_DIR` or `<project>/monthly_quotes`
- Submission proofs: `runtime/submission_proofs`
- Portal submission workspace: `runtime/portal_submission`
- Final submission workspace: `runtime/final_submission_v47_5`
- Proof center: `runtime/proof_center`
- Manual production: `runtime/manual_production`
- Temporary files: `runtime/tmp`
- Exports: `runtime/exports`
- Operator auth: `runtime/operator_auth`
- Audit trail: `runtime/audit_trail`
- Submission history: `runtime/submission_history`
- Health and locks: `runtime/health`, `runtime/locks`

Required directories are created through the shared runtime path layer. Production code should not introduce new ad hoc `Path("runtime")` joins when an existing shared path already covers the use case.

## Official production modes

Production modes are centralized in `app/core/production_modes.py`.

- `development`
- `staging`
- `manual_production`
- `semi_autonomous`
- `locked_production`

Rules:

- Mode selection is environment-driven through `LMCP_PRODUCTION_MODE`.
- Invalid or missing values fail safely to `manual_production`.
- Manual-production enforcement remains enabled for all non-development runtime modes.
- Legacy routers are never enabled by default in any mode.

## Runtime safety rules

- Final submission remains manual-only.
- Manual-production workflows remain human-approved.
- Runtime directories must be created through the shared runtime path layer.
- No parallel configuration system should bypass `app/core/runtime_config.py`.
- No startup path may silently re-enable legacy routers by default.

## Logging policy

- Logging bootstrap is centralized in `app/core/runtime_config.py`.
- Application logs are written under the shared logs directory.
- `app/main.py` must use the shared logging bootstrap instead of maintaining its own logging setup.
- Runtime log placement remains centralized and filesystem-safe.

## Environment loading policy

- `.env` loading is centralized in `app/core/runtime_config.py`.
- Shared environment helpers (`env`, `env_bool`, `env_csv`) should be reused instead of duplicating ad hoc parsing logic in startup/runtime configuration code.
- Runtime configuration must expose:
  - `LMCP_ENABLE_LEGACY_ROUTERS`
  - production mode selection
  - degraded startup flag
  - runtime safety flags

## Manual-production enforcement policy

- `manual_production` is the safe fallback mode.
- Manual review, manual approval, submission review, and proof capture continue to use the shared `runtime/manual_production` workspace.
- Final submission stays manual-only unless explicitly unlocked by a future controlled change.
