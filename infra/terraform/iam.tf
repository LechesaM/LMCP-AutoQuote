data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type = "Service" identifiers = ["ecs-tasks.amazonaws.com"] }
  }
}

resource "aws_iam_role" "task_exec" {
  name               = "${local.name}-ecs-task-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "task_exec_attach" {
  role       = aws_iam_role.task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags = local.tags
}

data "aws_iam_policy_document" "task_policy_doc" {
  statement {
    actions = ["ssm:GetParameter","ssm:GetParameters","ssm:GetParametersByPath"]
    resources = ["*"]
  }
  statement {
    actions = ["cloudwatch:PutMetricData"]
    resources = ["*"]
  }
  statement {
    actions = ["s3:PutObject","s3:GetObject","s3:ListBucket"]
    resources = concat(
      [for b in aws_s3_bucket.b : b.arn],
      [for b in aws_s3_bucket.b : "${b.arn}/*"]
    )
  }
}

resource "aws_iam_policy" "task_policy" {
  name   = "${local.name}-task-policy"
  policy = data.aws_iam_policy_document.task_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "task_policy_attach" {
  role       = aws_iam_role.task.name
  policy_arn = aws_iam_policy.task_policy.arn
}
