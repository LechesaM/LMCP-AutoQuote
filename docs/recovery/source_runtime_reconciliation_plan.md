# Source/Runtime Reconciliation Plan

Audit date: 2026-07-16
Status: stop for operator review before any API restart.

## Root Cause

The container bind-mounts the repository to `/app`, and the files currently visible inside the container match the host repository. The running API process, however, started before the current recovered source was written to the bind mount. Its `/health` response and OpenAPI therefore reflect modules imported into process memory from an earlier source state.

The checked-out source reports `2.5.3-v50.7-etenders-promotion-gate`; the running process reports `2.6.0-manual-production`. The `2.6.0-manual-production` string was not found in the current mounted source sample, which supports `PROCESS_NOT_RELOADED` rather than an active file mismatch.

## Changes Applied

- Add `scripts/audit_router_parity.py` for read-only router/source/OpenAPI comparison.
- Add `tests/test_router_imports_python39.py` for the Python 3.9 RFQ lifecycle router annotation fix.
- Patch only `app/api/rfq_lifecycle_api.py` to remove the evaluated `dict | None` annotation.
- Add this recovery documentation and safe-test inventory.

## Changes Not Applied

- No Docker restart, stop, recreate, rebuild, or compose command.
- No runtime-store mutation.
- No frontend source change.
- No broad router-registry rewrite.
- No optional-router failure suppression.
- No copy or replacement of older enterprise services.

## Validation Plan

Run:

```bash
PYTHONPYCACHEPREFIX=/tmp/lmcp_pycache .venv/bin/python -m compileall app scripts
.venv/bin/python scripts/audit_router_parity.py \
  --expected-loaded 67 \
  --output /Users/Shared/LMCP-Recovery-2026-07-15/source-runtime-parity/router-parity.json \
  --verbose
PYTHONPYCACHEPREFIX=/tmp/lmcp_pycache .venv/bin/python -m pytest -q tests/test_router_imports_python39.py
```

Expected result:

- Compile succeeds.
- RFQ lifecycle router no longer fails under Python 3.9.
- Direct host import may still show the fourteen `/app` import-context failures until those routers are validated inside the same container path context or patched to avoid import-time absolute `/app` access.

## Controlled Restart Plan

Do not execute during this audit. For operator review only:

```bash
docker compose ps
docker compose restart api
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/openapi.json -o /tmp/lmcp_openapi_after_restart.json
```

If the service name is not `api`, identify it first with:

```bash
docker compose ps
```

## Rollback Plan

Do not execute during this audit. If the source patch must be rolled back before a restart:

```bash
git diff -- app/api/rfq_lifecycle_api.py
git checkout -- app/api/rfq_lifecycle_api.py
```

If a restart is later performed and router registration regresses, restore the previous source state from Git or the reviewed patch, then restart the API container again under operator control.

## Prohibited Commands During Recovery

```bash
docker compose down
docker compose up --build
docker compose build
docker compose pull
docker compose rm
docker stop lmcp-api
docker restart lmcp-api
docker kill lmcp-api
docker rm lmcp-api
git reset --hard
git clean -fd
git merge
git rebase
git cherry-pick
```
