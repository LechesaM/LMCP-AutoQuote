# Multiple worker pools pinned to stage queues.
# This assumes you are using Fargate and environment variables to select Celery queues.

variable "worker_min_ingest"  { type = number default = 1 }
variable "worker_min_extract" { type = number default = 1 }
variable "worker_min_pricing" { type = number default = 1 }
variable "worker_min_pack"    { type = number default = 1 }
variable "worker_min_send"    { type = number default = 1 }

variable "worker_max_ingest"  { type = number default = 5 }
variable "worker_max_extract" { type = number default = 10 }
variable "worker_max_pricing" { type = number default = 6 }
variable "worker_max_pack"    { type = number default = 6 }
variable "worker_max_send"    { type = number default = 3 }

# You can reuse the same task definition image for each pool.
# If you have distinct images, swap var.worker_image_*.

locals {
  stage_env = [
    { name="CELERY_BROKER", value=aws_ssm_parameter.redis_url.arn },
  ]
}

# --- Example: Extract pool (copy pattern for others) ---

resource "aws_ecs_task_definition" "worker_extract" {
  family                   = "${local.name}-worker-extract"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name  = "worker_extract"
    image = var.worker_image
    essential = true
    command = ["celery","-A","app.celery_app.celery","worker","--loglevel=INFO","-Q","extract","--concurrency=2"]
    secrets = [
      { name="DATABASE_URL", valueFrom=aws_ssm_parameter.db_url.arn },
      { name="JWT_SECRET", valueFrom=aws_ssm_parameter.jwt.arn },
      { name="MFA_SECRET_KEY", valueFrom=aws_ssm_parameter.mfa.arn },
      { name="REDIS_URL", valueFrom=aws_ssm_parameter.redis_url.arn }
    ]
    environment = [
      { name="CELERY_QUEUE_NAME", value="extract" }
    ]
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        awslogs-group = aws_cloudwatch_log_group.worker.name,
        awslogs-region = var.aws_region,
        awslogs-stream-prefix = "worker_extract"
      }
    }
  }])
}

resource "aws_ecs_service" "worker_extract" {
  name            = "${local.name}-worker-extract"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.worker_extract.arn
  desired_count   = var.worker_min_extract
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  tags = local.tags
}

# Autoscaling target + policy (queue depth metric per stage) — reuse your custom metrics publisher,
# but add Dimension QueueName=extract and publish QueueDepthPerWorker per queue.
resource "aws_appautoscaling_target" "worker_extract" {
  max_capacity       = var.worker_max_extract
  min_capacity       = var.worker_min_extract
  resource_id        = "service/${aws_ecs_cluster.cluster.name}/${aws_ecs_service.worker_extract.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "worker_extract_queue" {
  name               = "${local.name}-worker-extract-queue"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker_extract.resource_id
  scalable_dimension = aws_appautoscaling_target.worker_extract.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker_extract.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 15
    customized_metric_specification {
      metric_name = "QueueDepthPerWorker"
      namespace   = "AutoQuote"
      statistic   = "Average"
      unit        = "Count"
      dimensions  = { QueueName = "extract" }
    }
    scale_in_cooldown  = 180
    scale_out_cooldown = 60
  }
}
