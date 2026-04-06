############################################
# EVENTBRIDGE SCHEDULES (THOUSANDS MODE)
############################################
# Triggers ECS RunTask jobs on a schedule:
# 1) poll_etenders (ingest)
# 2) export_audit_snapshots (Athena exports)
# 3) create_next_partitions (DB maintenance)

variable "enable_schedules" { type = bool default = true }
variable "poll_rate_expression" { type = string default = "rate(30 minutes)" }
variable "daily_export_cron" { type = string default = "cron(10 1 * * ? *)" }
variable "monthly_partition_cron" { type = string default = "cron(30 0 25 * ? *)" }

data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type = "Service" identifiers = ["events.amazonaws.com"] }
  }
}

resource "aws_iam_role" "events_run_ecs" {
  count              = var.enable_schedules ? 1 : 0
  name               = "${local.name}-events-run-ecs"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
  tags = local.tags
}

data "aws_iam_policy_document" "events_run_ecs_policy" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = ["*"]
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.task_exec.arn, aws_iam_role.task.arn]
  }
}

resource "aws_iam_policy" "events_run_ecs_policy" {
  count  = var.enable_schedules ? 1 : 0
  name   = "${local.name}-events-run-ecs-policy"
  policy = data.aws_iam_policy_document.events_run_ecs_policy.json
}

resource "aws_iam_role_policy_attachment" "events_run_ecs_attach" {
  count      = var.enable_schedules ? 1 : 0
  role       = aws_iam_role.events_run_ecs[0].name
  policy_arn = aws_iam_policy.events_run_ecs_policy[0].arn
}

resource "aws_ecs_task_definition" "job_runner" {
  count                    = var.enable_schedules ? 1 : 0
  family                   = "${local.name}-job-runner"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name       = "job"
    image      = var.worker_image
    essential  = true
    command    = ["python","-m","app.jobs","--help"]
    secrets = [
      { name="DATABASE_URL", valueFrom=aws_ssm_parameter.db_url.arn },
      { name="REDIS_URL", valueFrom=aws_ssm_parameter.redis_url.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        awslogs-group = aws_cloudwatch_log_group.worker.name,
        awslogs-region = var.aws_region,
        awslogs-stream-prefix = "job_runner"
      }
    }
  }])
}

resource "aws_cloudwatch_event_rule" "poll" {
  count               = var.enable_schedules ? 1 : 0
  name                = "${local.name}-poll-etenders"
  schedule_expression = var.poll_rate_expression
  tags = local.tags
}

resource "aws_cloudwatch_event_target" "poll_target" {
  count     = var.enable_schedules ? 1 : 0
  rule      = aws_cloudwatch_event_rule.poll[0].name
  target_id = "poll-etenders"
  arn       = aws_ecs_cluster.cluster.arn
  role_arn  = aws_iam_role.events_run_ecs[0].arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.job_runner[0].arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = aws_subnet.private[*].id
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }

  input = jsonencode({
    containerOverrides = [{
      name    = "job",
      command = ["python","-m","app.jobs","poll_etenders"]
    }]
  })
}

resource "aws_cloudwatch_event_rule" "daily_export" {
  count               = var.enable_schedules ? 1 : 0
  name                = "${local.name}-daily-export"
  schedule_expression = var.daily_export_cron
  tags = local.tags
}

resource "aws_cloudwatch_event_target" "daily_export_target" {
  count     = var.enable_schedules ? 1 : 0
  rule      = aws_cloudwatch_event_rule.daily_export[0].name
  target_id = "daily-export"
  arn       = aws_ecs_cluster.cluster.arn
  role_arn  = aws_iam_role.events_run_ecs[0].arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.job_runner[0].arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = aws_subnet.private[*].id
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }

  input = jsonencode({
    containerOverrides = [{
      name    = "job",
      command = ["python","-m","app.jobs","export_audit_snapshots"]
    }]
  })
}

resource "aws_cloudwatch_event_rule" "monthly_partition" {
  count               = var.enable_schedules ? 1 : 0
  name                = "${local.name}-monthly-partitions"
  schedule_expression = var.monthly_partition_cron
  tags = local.tags
}

resource "aws_cloudwatch_event_target" "monthly_partition_target" {
  count     = var.enable_schedules ? 1 : 0
  rule      = aws_cloudwatch_event_rule.monthly_partition[0].name
  target_id = "monthly-partitions"
  arn       = aws_ecs_cluster.cluster.arn
  role_arn  = aws_iam_role.events_run_ecs[0].arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.job_runner[0].arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = aws_subnet.private[*].id
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }

  input = jsonencode({
    containerOverrides = [{
      name    = "job",
      command = ["python","-m","app.jobs","create_next_partitions"]
    }]
  })
}
