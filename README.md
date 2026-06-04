# AutoQuote Tender Desk — Production Repo Skeleton

This repo skeleton combines:
- Production MVP architecture + Terraform base (VPC/ECS/RDS/Redis/S3/WAF/alarms)
- Scale-to-thousands pipeline (stage queues, worker pools, ranking)
- Blue/Green (CodeDeploy) blueprint + deploy workflow guidance
- Final scaling layer (all-stage worker pools, EventBridge schedules, Athena/Glue scaffolding)

## Quick start
1) **Infra**
   - Copy Terraform from `infra/terraform/` into your infra repo (or keep here).
   - Set secrets in `prod.tfvars` (DO NOT COMMIT).
   - `make tf-init tf-plan tf-apply`

2) **App**
   - Implement the stubs in `app/` (jobs, tasks, extraction, pricing).
   - Build/push Docker image.
   - Deploy via GitHub Actions (OIDC) or `make deploy`.

## Safety gates (must keep)
- Policy engine blocks sending unless RFQ explicitly allows email responses
- SOE allowlists + admin approval + TOTP required to send
- Evidence packs + immutable send_events for audit

## Contents
- `infra/terraform/` — Infrastructure as code
- `app/` — Application skeleton (FastAPI + Celery routing + jobs)
- `db/migrations/` — Multi-tenant + ranking columns + index templates
- `docs/` — Ops cockpit, ranking spec, Athena queries
- `_reference_packs/` — Original generated packs for reference


## One-click GitHub Secrets (Blue/Green)
After `terraform apply`, run `./scripts/print_github_secrets.sh` and paste outputs into GitHub secrets.


## First deployment
See `docs/first_deployment_checklist.md`.


## Application (Prototype integrated)
The API now includes:
- `/docs` Swagger UI
- `/poll/run` to ingest eTenders OCDS releases
- `/opportunities` shortlist (SOE + supply/delivery filters)
- `/opportunities/{id}/extract` PDF extraction (best-effort)
- `/opportunities/{id}/draft` create a draft email in outbox
- `/ui` admin page to approve drafts and (optionally) send
- `/outbox/{id}/send` SAFE send endpoint (strict gates)

### Safe sending (default OFF)
Sending is **disabled by default** (`SEND_ENABLED=false`).
To enable safely, configure SMTP and set:
- `SEND_ENABLED=true`
- Keep `REQUIRE_RFP_EMAIL_ALLOWED=true` (recommended)
- Use `MAX_SENDS_PER_DAY` as a guardrail

See: `docs/safe_sending.md`

## Manual Review Pilot
Use the controlled Phase 5 pilot runner to process up to 10 RFQs under manual supervision.

Template:
- `app/templates/pilot_manifest_template.json`

Run:
```bash
python3 app/scripts/run_manual_review_pilot.py \
  --manifest /absolute/path/to/your_pilot_manifest.json \
  --operator-id pilot-admin \
  --operator-name "Pilot Admin" \
  --role admin \
  --limit 10
```

Workflow:
- Copy `app/templates/pilot_manifest_template.json` to a writable location.
- Replace the example `rfq_path` values with real absolute paths.
- Edit `pilot_name`, `human_notes`, and `rfq_data` as needed.
- Run the script and review the generated JSON/CSV outputs under `runtime/manual_review/pilot_runs/`.

## Controlled Shared-Runtime Proof
Use the one-command controlled proof wrapper to seed the runtime, boot the backend, verify controlled status, and run the local validate -> quote pack -> pricing schedule -> submission package chain.

Run:
```bash
make controlled-proof
```

To print only the saved summary later:
```bash
make controlled-proof-report
```

What it verifies:
- `GET /health`
- `GET /system/control/effective-status`
- `GET /health/workflows`
- controlled-only guardrails:
  - no portal upload
  - no email send
  - no autonomous final submit

Notes:
- The wrapper uses `LMCP_RUNTIME_DIR=/private/tmp/lmcp_runtime` by default in this environment.
- If the sandbox blocks `127.0.0.1:8000`, it falls back to `8011` here.
