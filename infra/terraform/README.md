# Terraform — Full Base Stack + Scaling Add-ons

This folder now includes the full base stack:
- VPC (public/private/db subnets) + NAT
- ALB (HTTP + optional HTTPS)
- ECS (API + worker + beat) with Container Insights
- RDS Postgres 16 (private) + hardened parameter group
- Redis (private)
- S3 buckets (docs/packs/portal/evidence)
- SSM parameters for secrets
- WAF + SNS alerts + alarms + dashboard

Plus the scaling add-ons already included in this repo:
- stage queues, all-stage worker pools, schedules, Athena/Glue scaffolding, read replica

## Use
1) Copy `prod.tfvars.example` → `prod.tfvars` and fill it in (do not commit).
2) Run:
   - `make tf-init`
   - `make tf-plan`
   - `make tf-apply`

## Blue/Green deployments
If you want ECS blue/green, set:
- `enable_bluegreen=true`
and add the blue/green Terraform file from our earlier blueprint into this folder (or ask me and I’ll insert it here too).

## Blue/Green (CodeDeploy) — included
This repo includes `bluegreen_codedeploy.tf`.

Enable by setting in `prod.tfvars`:
- enable_bluegreen=true
- prod_listener_port=80 (or 443 if using ACM)
- test_listener_port=9000

GitHub secrets required for `.github/workflows/deploy-bluegreen.yml`:
- AWS_ROLE_ARN
- CODEDEPLOY_BUCKET
- CODEDEPLOY_APP_NAME (terraform output `codedeploy_app_name`)
- CODEDEPLOY_DG_NAME  (terraform output `codedeploy_deployment_group`)
- ECS_EXEC_ROLE_ARN, ECS_TASK_ROLE_ARN
- SSM_DB_URL_ARN, SSM_JWT_ARN, SSM_MFA_ARN, SSM_REDIS_ARN


## Staging
Use `staging.tfvars.example` to create `staging.tfvars` and apply with `-var-file=staging.tfvars`.
