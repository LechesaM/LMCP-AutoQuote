############################################
# GitHub Actions OIDC -> AWS IAM Role
# Produces AWS_ROLE_ARN for GitHub secrets
############################################

# GitHub OIDC provider (one per AWS account typically)
resource "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_oidc ? 1 : 0

  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub's root CA thumbprint for token.actions.githubusercontent.com
  # If this ever changes, update it (AWS docs).
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
  tags = local.tags
}

data "aws_iam_policy_document" "github_assume_role" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Restrict to a specific repo + branch
    # sub format: repo:<org>/<repo>:ref:refs/heads/<branch>
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:ref:refs/heads/${var.github_branch}"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  count              = var.enable_github_oidc ? 1 : 0
  name               = "${local.name}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_assume_role[0].json
  tags               = local.tags
}

# Permissions needed by the workflow:
# - ECR: login + push images
# - ECS: register task definition
# - CodeDeploy: create deployment
# - S3: upload revision bundle
data "aws_iam_policy_document" "github_actions_policy" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = ["*"]
  }

  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:DescribeRepositories",
      "ecr:CreateRepository"
    ]
    resources = ["*"]
  }

  statement {
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition"
    ]
    resources = ["*"]
  }

  statement {
    actions = [
      "codedeploy:CreateDeployment",
      "codedeploy:GetDeployment",
      "codedeploy:GetDeploymentGroup",
      "codedeploy:GetApplication",
      "codedeploy:RegisterApplicationRevision"
    ]
    resources = ["*"]
  }

  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:CreateBucket"
    ]
    resources = ["*"]
  }

  statement {
    actions = [
      "iam:PassRole"
    ]
    resources = [
      aws_iam_role.task_exec.arn,
      aws_iam_role.task.arn
    ]
  }
}

resource "aws_iam_policy" "github_actions" {
  count  = var.enable_github_oidc ? 1 : 0
  name   = "${local.name}-github-actions-policy"
  policy = data.aws_iam_policy_document.github_actions_policy[0].json
}

resource "aws_iam_role_policy_attachment" "github_actions_attach" {
  count      = var.enable_github_oidc ? 1 : 0
  role       = aws_iam_role.github_actions[0].name
  policy_arn = aws_iam_policy.github_actions[0].arn
}

output "github_actions_role_arn" {
  value       = var.enable_github_oidc ? aws_iam_role.github_actions[0].arn : null
  description = "Set GitHub secret AWS_ROLE_ARN to this"
}
