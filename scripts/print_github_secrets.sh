#!/usr/bin/env bash
set -euo pipefail

# Prints the Terraform outputs you should paste into GitHub secrets.
# Run from repo root after terraform apply:
#   ./scripts/print_github_secrets.sh

TF_DIR="infra/terraform"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform not found on PATH"
  exit 1
fi

pushd "$TF_DIR" >/dev/null

echo "=== GitHub Secrets (copy/paste) ==="
echo ""

# Safe fetch helper
get() {
  terraform output -raw "$1" 2>/dev/null || true
}

CODEDEPLOY_APP=$(get codedeploy_app_name)
CODEDEPLOY_DG=$(get codedeploy_deployment_group)

echo "ECS_EXEC_ROLE_ARN=$(get cicd_ecs_exec_role_arn)"
echo "ECS_TASK_ROLE_ARN=$(get cicd_ecs_task_role_arn)"
echo "SSM_DB_URL_ARN=$(get cicd_ssm_db_url_arn)"
echo "SSM_JWT_ARN=$(get cicd_ssm_jwt_arn)"
echo "SSM_MFA_ARN=$(get cicd_ssm_mfa_arn)"
echo "SSM_REDIS_ARN=$(get cicd_ssm_redis_arn)"

if [ -n "$CODEDEPLOY_APP" ]; then
  echo "CODEDEPLOY_APP_NAME=$CODEDEPLOY_APP"
fi
if [ -n "$CODEDEPLOY_DG" ]; then
  echo "CODEDEPLOY_DG_NAME=$CODEDEPLOY_DG"
fi

echo ""
AWS_ROLE=$(get github_actions_role_arn)
if [ -n "$AWS_ROLE" ]; then
  echo "AWS_ROLE_ARN=$AWS_ROLE"
fi

echo "NOTE: You must also set:"
echo "  AWS_ROLE_ARN (OIDC role for GitHub)"
echo "  CODEDEPLOY_BUCKET (S3 bucket for revision.zip uploads)"
echo ""
BUCKET=$(get codedeploy_bucket_name)
if [ -n "$BUCKET" ]; then
  echo "CODEDEPLOY_BUCKET=$BUCKET"
else
  echo "Suggested bucket name: $(get cicd_codedeploy_bucket_hint)"
fi
echo ""
popd >/dev/null
