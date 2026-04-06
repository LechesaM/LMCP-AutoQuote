# Staging setup (separate from production)

## 1) Terraform apply (staging)
From repo root:

```bash
cd infra/terraform
terraform init
terraform apply -var-file=staging.tfvars
```

> Tip: keep staging and prod state separate:
- Use **Terraform workspaces** (`terraform workspace new staging`) OR
- Use separate folders / separate backends.

## 2) Print staging outputs for GitHub secrets
After the staging apply, run:

```bash
./scripts/print_github_secrets.sh
```

This prints values from the **currently selected Terraform state**.

## 3) Add GitHub secrets (staging)
Add these secrets for the `staging` branch workflow:

- AWS_ROLE_ARN_STAGING   (Terraform output: github_actions_role_arn)
- CODEDEPLOY_BUCKET_STAGING (output: codedeploy_bucket_name)
- CODEDEPLOY_APP_NAME_STAGING (output: codedeploy_app_name)
- CODEDEPLOY_DG_NAME_STAGING  (output: codedeploy_deployment_group)

- ECS_EXEC_ROLE_ARN_STAGING (output: cicd_ecs_exec_role_arn)
- ECS_TASK_ROLE_ARN_STAGING (output: cicd_ecs_task_role_arn)
- SSM_DB_URL_ARN_STAGING (output: cicd_ssm_db_url_arn)
- SSM_JWT_ARN_STAGING (output: cicd_ssm_jwt_arn)
- SSM_MFA_ARN_STAGING (output: cicd_ssm_mfa_arn)
- SSM_REDIS_ARN_STAGING (output: cicd_ssm_redis_arn)

## 4) Deploy to staging
Push commits to the `staging` branch.
GitHub Actions will run:
- `.github/workflows/deploy-staging-bluegreen.yml`
