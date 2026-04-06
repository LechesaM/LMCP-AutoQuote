# First Deployment Checklist (Production)

This checklist assumes you are deploying to **AWS af-south-1** using:
- Terraform base stack
- Optional ECS Blue/Green via CodeDeploy
- GitHub Actions OIDC (no AWS keys)

---

## 0) Local prerequisites
Install:
- Terraform >= 1.6
- AWS CLI v2
- Docker
- GNU Make

---

## 1) Prepare `prod.tfvars`
1. Copy:
   - `infra/terraform/prod.tfvars.example` → `infra/terraform/prod.tfvars`
2. Fill in:
   - `db_pass`, `jwt_secret`, `mfa_secret_key`
   - `api_image`, `worker_image`, `beat_image` (any placeholder is OK for first apply if you will deploy later)
3. GitHub OIDC (recommended):
   - `enable_github_oidc=true`
   - `github_org="YOUR_GITHUB_ORG_OR_USERNAME"`
   - `github_repo="YOUR_REPO_NAME"`
   - `github_branch="main"`
4. Blue/Green (recommended):
   - `enable_bluegreen=true`
   - `prod_listener_port=80` (or 443 if ACM enabled)
   - `test_listener_port=9000`

---

## 2) Terraform apply
From repo root:

```bash
make tf-init
make tf-plan
make tf-apply
```

After apply, note these outputs:
- `alb_dns_name`
- `codedeploy_app_name` and `codedeploy_deployment_group` (if blue/green enabled)
- `github_actions_role_arn` (OIDC role)
- `codedeploy_bucket_name`

---

## 3) Print GitHub secrets (copy/paste)
After terraform apply:

```bash
./scripts/print_github_secrets.sh
```

In GitHub repo:
- Settings → Secrets and variables → Actions → New repository secret

Paste:
- `AWS_ROLE_ARN` (from output/script)
- `CODEDEPLOY_BUCKET`
- `CODEDEPLOY_APP_NAME`
- `CODEDEPLOY_DG_NAME`
- `ECS_EXEC_ROLE_ARN`, `ECS_TASK_ROLE_ARN`
- `SSM_DB_URL_ARN`, `SSM_JWT_ARN`, `SSM_MFA_ARN`, `SSM_REDIS_ARN`

---

## 4) Create ECR repository (if not already)
Your workflow tries to create it if permissions allow. If you prefer to create it manually:

```bash
aws ecr create-repository --repository-name autoquote-tender-desk --region af-south-1
```

---

## 5) Deploy (Blue/Green)
1. Push to `main` (or your configured branch).
2. GitHub Actions runs: `.github/workflows/deploy-bluegreen.yml`
3. CodeDeploy will:
   - Register the new task definition
   - Shift traffic canary (10% for 5 minutes) then full, with rollback on failure

---

## 6) Smoke tests
When the workflow finishes, test:

```bash
curl -s http://<ALB_DNS>/health
```

Expected:
```json
{"ok": true}
```

---

## 7) Database migrations (first time)
This repo contains SQL migrations in `db/migrations/`.

Minimum manual approach (run inside your VPC via bastion/VPN or SSM Session Manager):

1) Get DB endpoint from Terraform output `db_endpoint`
2) Connect with psql and run migrations in order.

Recommended production approach:
- Add a “migrate” ECS RunTask job (same job runner pattern as schedules).

---

## 8) Turn on schedules (optional)
EventBridge schedules run:
- `poll_etenders`
- `export_audit_snapshots`
- `create_next_partitions`

To enable:
- Ensure `enable_schedules=true`
- Ensure your image implements `app/jobs.py` behavior (currently stubbed)

---

## 9) Verify safety gates before sending email
Before enabling real email sending:
- Policy engine blocks sends unless RFQ explicitly allows email responses
- Require admin approval + MFA (TOTP)
- Log immutable `send_events` and store evidence packs to S3

---

## 10) Operational “day-2” checks
- CloudWatch alarms green
- WAF attached to ALB
- S3 public access blocks enabled
- RDS backups running

---

## Common first-deploy issues
- **No traffic shifting:** check `enable_bluegreen=true` and CodeDeploy outputs exist
- **Workflow cannot assume role:** check `github_org/github_repo/github_branch` in tfvars
- **ECR push denied:** confirm GitHub OIDC role policy includes ECR actions
- **Health check failing:** ensure `/health` returns HTTP 200 quickly
