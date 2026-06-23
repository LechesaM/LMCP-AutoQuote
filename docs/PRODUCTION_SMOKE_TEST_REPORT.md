# Production Smoke Test Report

This document defines the production-safe smoke testing layer for the Docker production package.

## Smoke Test Scope
- Compose config parsing
- Required service presence
- Safe production defaults
- Backend health route expectation
- Submission lock enforcement
- Placeholder-only credentials
- Final automation disabled
- Dry-run enabled
- Human supervision required

## Required Services
The smoke test expects the production package to define:
- backend
- frontend
- postgres
- redis
- worker
- prometheus
- grafana

## Safety Boundary
The smoke test is static validation only. It does not:
- start production containers
- enable autonomous live submissions
- add real production credentials
- weaken supervision boundaries
- redesign orchestration

## Output Artifacts
Smoke test evidence is written under:
- `runtime/staging/production-smoke-tests/`

Latest artifacts:
- `latest_production_smoke_test.json`
- `latest_production_smoke_test.md`

## Validation Contract
The smoke runner checks:
- `docker-compose.production.example.yml` parses via `docker compose config`
- required services are present
- env defaults remain safe
- backend `/health` route is expected
- submission locks are present or documented
- no live credentials appear
- final automation stays disabled
- dry-run stays enabled
- human supervision remains required
