# Staging Runtime Bootstrap Report

## What was added
- `.env.staging.example`
- `docker-compose.staging.yml`

## Staging isolation model
- Dedicated staging PostgreSQL, Redis, runtime filesystem, queue state, logs, proofs, and telemetry volumes.
- Backend, workers, frontend, Prometheus, and Grafana are all wired to staging-only dependencies.
- Submission safety is preserved by default with `LMCP_ALLOW_FINAL_AUTOMATION=false` and portal isolation enabled.

## Protections against production access
- No production database host or credentials are referenced.
- No production queue host is referenced.
- Live portal submission remains disabled by default.
- Runtime paths are isolated under `/app/runtime/staging`.
- Portal isolation state is staging-specific.

## Startup instructions
1. Adjust `.env.staging.example` values if you want custom staging secrets or host ports.
2. Start the stack:
   `docker compose -f docker-compose.staging.yml up --build`
3. Confirm the backend, worker, frontend, PostgreSQL, Redis, Prometheus, and Grafana services are healthy.

## Validation commands
- `curl -fsS http://127.0.0.1:${LMCP_BACKEND_HOST_PORT:-8012}/health`
- `curl -fsS http://127.0.0.1:${LMCP_BACKEND_HOST_PORT:-8012}/status`
- `curl -fsS http://127.0.0.1:${LMCP_FRONTEND_HOST_PORT:-4175}/`
- `curl -fsS http://127.0.0.1:${LMCP_PROMETHEUS_HOST_PORT:-9091}/-/ready`
- `curl -fsS http://127.0.0.1:${LMCP_GRAFANA_HOST_PORT:-3001}/api/health`

## Health verification
- Backend `health` and `status` respond.
- Worker heartbeats appear in telemetry.
- Queue depth, retry, and DLQ views are visible.
- PostgreSQL and Redis are isolated to staging.
- Frontend resolves the staging backend only.

## Telemetry verification checklist
- Structured logs include request and worker context.
- Correlation IDs flow through API and worker activity.
- Queue and DLQ visibility are present.
- Stale-data guards have a last-safe snapshot path.
- Prometheus and Grafana start against staging-only data.

## Rollback procedure
- Stop the staging stack.
- Preserve runtime artifacts and telemetry logs.
- Revert to the previous staging image or manifest version.
- Re-run health and dry-run checks before resuming validation.

## Safest rollout notes
- Start with low-risk RFQs only.
- Keep data volume minimal for the first staging cycle.
- Require operator review for every dry-run and any submission-adjacent step.

## Result
- This bootstrap prepares an isolated staging runtime without enabling live production submissions or changing workflow behavior.
