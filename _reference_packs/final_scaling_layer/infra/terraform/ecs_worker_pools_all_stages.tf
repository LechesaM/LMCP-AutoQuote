############################################
# ECS WORKER POOLS — ALL STAGES (THOUSANDS MODE)
############################################

# Requirements:
# - Your Celery app routes tasks to queues: ingest, extract, pricing, pack, send
# - You publish custom CW metric: AutoQuote/QueueDepthPerWorker with Dimension QueueName

variable "worker_image" { type = string }

variable "worker_min_ingest"  { type = number default = 1 }
variable "worker_min_extract" { type = number default = 1 }
variable "worker_min_pricing" { type = number default = 1 }
variable "worker_min_pack"    { type = number default = 1 }
variable "worker_min_send"    { type = number default = 1 }

variable "worker_max_ingest"  { type = number default = 5 }
variable "worker_max_extract" { type = number default = 12 }
variable "worker_max_pricing" { type = number default = 8 }
variable "worker_max_pack"    { type = number default = 8 }
variable "worker_max_send"    { type = number default = 3 }

# CPU/memory per pool (tune)
variable "ingest_cpu"  { type = number default = 512 }
variable "ingest_mem"  { type = number default = 1024 }
variable "extract_cpu" { type = number default = 1024 }
variable "extract_mem" { type = number default = 2048 }
variable "pricing_cpu" { type = number default = 512 }
variable "pricing_mem" { type = number default = 1024 }
variable "pack_cpu"    { type = number default = 1024 }
variable "pack_mem"    { type = number default = 2048 }
variable "send_cpu"    { type = number default = 256 }
variable "send_mem"    { type = number default = 512 }

locals {
  queues = {
    ingest  = { cpu=var.ingest_cpu,  mem=var.ingest_mem,  min=var.worker_min_ingest,  max=var.worker_max_ingest,  target=20, concurrency=2 },
    extract = { cpu=var.extract_cpu, mem=var.extract_mem, min=var.worker_min_extract, max=var.worker_max_extract, target=15, concurrency=2 },
    pricing = { cpu=var.pricing_cpu, mem=var.pricing_mem, min=var.worker_min_pricing, max=var.worker_max_pricing, target=25, concurrency=2 },
    pack    = { cpu=var.pack_cpu,    mem=var.pack_mem,    min=var.worker_min_pack,    max=var.worker_max_pack,    target=15, concurrency=2 },
    send    = { cpu=var.send_cpu,    mem=var.send_mem,    min=var.worker_min_send,    max=var.worker_max_send,    target=10, concurrency=1 }
  }
}

resource "aws_ecs_task_definition" "worker_stage" {
  for_each                 = local.queues
  family                   = "${local.name}-worker-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(each.value.cpu)
  memory                   = tostring(each.value.mem)
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "worker_${each.key}"
    image     = var.worker_image
    essential = true
    command   = ["celery","-A","app.celery_app.celery","worker","--loglevel=INFO","-Q","${each.key}","--concurrency=${each.value.concurrency}"]
    secrets = [
      { name="DATABASE_URL", valueFrom=aws_ssm_parameter.db_url.arn },
      { name="JWT_SECRET", valueFrom=aws_ssm_parameter.jwt.arn },
      { name="MFA_SECRET_KEY", valueFrom=aws_ssm_parameter.mfa.arn },
      { name="REDIS_URL", valueFrom=aws_ssm_parameter.redis_url.arn }
    ]
    environment = [
      { name="CELERY_QUEUE_NAME", value="${each.key}" }
    ]
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        awslogs-group = aws_cloudwatch_log_group.worker.name,
        awslogs-region = var.aws_region,
        awslogs-stream-prefix = "worker_${each.key}"
      }
    }
  }])
}

resource "aws_ecs_service" "worker_stage" {
  for_each        = local.queues
  name            = "${local.name}-worker-${each.key}"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.worker_stage[each.key].arn
  desired_count   = each.value.min
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  tags = local.tags
}

resource "aws_appautoscaling_target" "worker_stage" {
  for_each           = local.queues
  max_capacity       = each.value.max
  min_capacity       = each.value.min
  resource_id        = "service/${aws_ecs_cluster.cluster.name}/${aws_ecs_service.worker_stage[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "worker_stage_queue" {
  for_each           = local.queues
  name               = "${local.name}-worker-${each.key}-queue"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker_stage[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.worker_stage[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker_stage[each.key].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = each.value.target
    customized_metric_specification {
      metric_name = "QueueDepthPerWorker"
      namespace   = "AutoQuote"
      statistic   = "Average"
      unit        = "Count"
      dimensions  = { QueueName = each.key }
    }
    scale_in_cooldown  = 180
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_policy" "worker_stage_cpu" {
  for_each           = local.queues
  name               = "${local.name}-worker-${each.key}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker_stage[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.worker_stage[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker_stage[each.key].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 55
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 240
    scale_out_cooldown = 60
  }
}
