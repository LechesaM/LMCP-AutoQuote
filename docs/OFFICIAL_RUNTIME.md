# Official Runtime

Date: 2026-06-22
Source: `docs/REPO_AUDIT.md`
Scope: runtime definition only; no code changes

## Official Runtime Definition

1. Official backend entrypoint: `app.main:app`
2. Official worker entrypoint: `app.celery_app.celery_app`
3. Official production launcher: `docker-compose.production.yml`

## Frontend Apps

Frontend apps discovered in the audit:

- `frontend/`
  - Classification: `ACTIVE`
  - Stack: Vite + React
  - Evidence: `frontend/package.json`, `frontend/index.html`, `frontend/vite.config.js`
- `frontend/command-centre/`
  - Classification: `EXPERIMENTAL`
  - Evidence: partial TypeScript subtree exists, but audit found no `package.json` or `Dockerfile`
- `etenders_acquisition/lmcp-dashboard/`
  - Classification: `EXPERIMENTAL`
  - Stack: Next.js
  - Belongs to the separate `etenders_acquisition/` stack

Official frontend for stabilization:

- Treat `frontend/` as the official frontend app.
- Do not treat `frontend/command-centre/` or `etenders_acquisition/lmcp-dashboard/` as official runtime targets.

## Required Environment Variables

These are the required runtime variables derived from the audit, `app/config.py`, `.env.example`, and `.env.production.example`.

### Core runtime

- `LMCP_APP_ENTRYPOINT=app.main:app`
- `LMCP_ENV`
- `LMCP_PRODUCTION_MODE`
- `LMCP_DEPLOYMENT_PROFILE`
- `LMCP_PROJECT_ROOT`
- `LMCP_RUNTIME_DIR`
- `LMCP_SECRET_KEY`

### Backend and database

- `LMCP_DB_BACKEND`
- `LMCP_DATABASE_URL`
- `DATABASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DB_HOST`
- `DB_DOCKER_HOST`
- `DB_LOCAL_HOST`
- `DB_PORT`

### Broker and workers

- `LMCP_QUEUE_BACKEND`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `QUEUE_WORKER_COUNT`
- `WORKER_CONCURRENCY`
- `MAX_TASKS_PER_CHILD`
- `PREFETCH_MULTIPLIER`
- `OPERATIONS_CONCURRENCY`
- `OPERATIONS_WORKER_READY_TIMEOUT_SECONDS`
- `OPERATIONS_WORKER_READY_POLL_INTERVAL_SECONDS`
- `REQUIRE_OPERATIONS_WORKER_READY`

### Runtime paths

- `LMCP_MANUAL_PRODUCTION_DIR`
- `LMCP_MANUAL_PRODUCTION_DB_PATH`
- `LMCP_BACKUPS_DIR`
- `LMCP_HEALTH_DIR`
- `LMCP_LOG_DIR`
- `LMCP_EXPORTS_DIR`
- `LMCP_TLS_CERT_DIR`

### Auth and web runtime

- `LMCP_CORS_ORIGINS`
- `LMCP_OPERATOR_SESSION_COOKIE_SECURE`
- `LMCP_OPERATOR_SESSION_TIMEOUT_SECONDS`
- `LMCP_AUTH_REQUIRED`
- `LMCP_AUTH_ALLOW_DEMO_USERS`

### Production safety and observability

- `STRICT_PRODUCTION_STARTUP`
- `LMCP_ALLOW_DEGRADED_STARTUP`
- `LMCP_ENABLE_LEGACY_ROUTERS`
- `LMCP_RUNTIME_SAFETY_ENABLED`
- `LMCP_DEPLOYMENT_HARDENING_ENABLED`
- `LMCP_OBSERVABILITY_ENABLED`
- `LMCP_TELEMETRY_FALLBACK_ENABLED`
- `LMCP_LOG_LEVEL`
- `LMCP_DEBUG`
- `LMCP_ENABLE_SENTRY`
- `LMCP_SENTRY_DSN`

### Defaults by mode

Local development defaults from `.env.example`:

- `LMCP_DB_BACKEND=sqlite`
- `LMCP_QUEUE_BACKEND=local`
- `LMCP_APP_ENTRYPOINT=app.main:app`

Production defaults from `.env.production.example`:

- `LMCP_DB_BACKEND=postgres`
- `LMCP_QUEUE_BACKEND=redis`
- `LMCP_APP_ENTRYPOINT=app.main:app`
- `REDIS_URL=redis://redis:6379/0`
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://redis:6379/0`

## Required Services

The official runtime requires these services:

- Backend API
  - Process: `uvicorn app.main:app`
- Database
  - Local/dev: SQLite is supported
  - Production: Postgres is required
- Broker
  - Production worker runtime expects Redis
- Workers
  - General Celery worker
  - Operations queue worker
  - Beat scheduler
- Frontend
  - Official target should be the app under `frontend/`

The production compose file includes:

- `backend`
- `worker`
- `operations-worker`
- `beat`
- `frontend`
- `postgres`
- `redis`
- `prometheus`
- `grafana`

## Local Development Commands

Python environment setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Backend only:

```bash
cd /Users/cash/Documents
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend only:

```bash
cd /Users/cash/Documents/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Local worker startup:

```bash
cd /Users/cash/Documents
bash scripts/start_production_workers.sh
```

Existing local helper script:

```bash
cd /Users/cash/Documents
bash scripts/start_local_manual_production.sh
```

Note: this helper currently launches `frontend/command-centre`, which does not match the official frontend decision from the audit.

Local compose runtime:

```bash
cd /Users/cash/Documents
docker compose -f docker-compose.yml up --build
```

## Production Startup Commands

Official production compose startup:

```bash
cd /Users/cash/Documents
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build --remove-orphans
```

Production backend launcher script:

```bash
cd /Users/cash/Documents
bash scripts/ops/production_start.sh
```

Production workers:

```bash
cd /Users/cash/Documents
bash scripts/start_production_workers.sh
```

`scripts/ops/production_start.sh` also supports:

```bash
LMCP_USE_DOCKER=1 bash scripts/ops/production_start.sh
```

## Health Check Commands

Backend health:

```bash
curl -fsS http://localhost:8000/health
```

Backend status:

```bash
curl -fsS http://localhost:8000/status
```

System health:

```bash
curl -fsS http://localhost:8000/health/system
```

Workflow health:

```bash
curl -fsS http://localhost:8000/health/workflows
```

Operational report:

```bash
curl -fsS http://localhost:8000/health/operational-report
```

Production readiness script:

```bash
cd /Users/cash/Documents
bash scripts/ops/production_readiness_check.sh
```

Operations worker readiness:

```bash
cd /Users/cash/Documents
python3 scripts/check_operations_worker_ready.py --queue operations_queue
```

Local runtime status snapshot:

```bash
cd /Users/cash/Documents
python3 scripts/check_local_system.py
```

## Known Risks

- `services/` is a duplicate mirror of `app/services/`. Stabilization work should treat `app/services/` as authoritative.
- `models/` is a duplicate mirror of `app/models/`. Stabilization work should treat `app/models/` as authoritative.
- `etenders_acquisition/` is a separate experimental stack with its own API, DB, compose file, and frontend. It is not part of the official LMCP runtime.
- `frontend/command-centre/` is not a valid official frontend target from the audit, but existing startup and compose references still point at it.
- Both `docker-compose.yml` and `docker-compose.production.yml` reference `frontend/command-centre/Dockerfile`, while the audit did not find that file.
- `app/recovery_main.py` exists as an alternate FastAPI app path but is not part of the official runtime.
- Multiple backup FastAPI entrypoints remain in `app/main.py.backup_*` and `app/main.py.bak_*`. They should not be treated as runtime sources.
- The repository contains large runtime and generated trees under `runtime/`, `generated/`, and `monthly_quotes/`, which increases the chance of mixing source with artifacts during stabilization work.

## Unresolved `UNKNOWN` Items From The Audit

- `data/`
  - Classification in the audit: `UNKNOWN`
  - Current status: present in the repo root, but not yet established as an authoritative runtime input or source-of-truth store
  - Stabilization rule: do not promote `data/` into the official runtime without explicit follow-up audit or runtime evidence

## Runtime Boundary For Stabilization

Until further audit changes this definition, treat the official runtime boundary as:

- Backend source: `app/`
- Worker source: `app/celery_app.py` and `app/tasks/`
- Frontend source: `frontend/`
- Runtime state: `runtime/`
- Generated output: `generated/`, `monthly_quotes/`
- Production orchestration: `docker-compose.production.yml`
