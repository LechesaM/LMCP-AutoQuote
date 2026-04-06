# GitHub Secrets Setup (Copy/Paste)

After `terraform apply`, run:

```bash
./scripts/print_github_secrets.sh
```

Paste the printed values into GitHub repo **Settings → Secrets and variables → Actions**.

Required secrets for Blue/Green workflow:
- AWS_ROLE_ARN
- CODEDEPLOY_BUCKET
- CODEDEPLOY_APP_NAME
- CODEDEPLOY_DG_NAME
- ECS_EXEC_ROLE_ARN
- ECS_TASK_ROLE_ARN
- SSM_DB_URL_ARN
- SSM_JWT_ARN
- SSM_MFA_ARN
- SSM_REDIS_ARN

## GitHub OIDC Role (no long-lived AWS keys)
This repo can create the GitHub OIDC role automatically.

In `prod.tfvars` set:
- enable_github_oidc=true
- github_org="YOUR_GITHUB_ORG_OR_USERNAME"
- github_repo="YOUR_REPO_NAME"
- github_branch="main"

After `terraform apply`, get:
- `github_actions_role_arn` (set GitHub secret `AWS_ROLE_ARN`)

## CodeDeploy bucket (auto-created)
Terraform can create the S3 bucket for revision bundles.

Output:
- `codedeploy_bucket_name` → set GitHub secret `CODEDEPLOY_BUCKET`


## Staging secrets (recommended)
For staging deployments, this repo includes:
- `.github/workflows/deploy-staging-bluegreen.yml`

Use the same outputs, but store them in GitHub Secrets with a `_STAGING` suffix, e.g.:
- `AWS_ROLE_ARN_STAGING`
- `CODEDEPLOY_BUCKET_STAGING`
- `CODEDEPLOY_APP_NAME_STAGING`
- `CODEDEPLOY_DG_NAME_STAGING`
- `ECS_EXEC_ROLE_ARN_STAGING`, etc.
