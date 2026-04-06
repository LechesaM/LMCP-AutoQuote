resource "aws_ecs_cluster" "cluster" {
  name = "${local.name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name  = "api"
    image = var.api_image
    essential = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name="POLICY_PATH", value="config/policy.json" },
      { name="MFA_ISSUER", value="AutoQuoteTenderDesk" }
    ]
    secrets = [
      { name="DATABASE_URL", valueFrom=aws_ssm_parameter.db_url.arn },
      { name="JWT_SECRET", valueFrom=aws_ssm_parameter.jwt.arn },
      { name="MFA_SECRET_KEY", valueFrom=aws_ssm_parameter.mfa.arn },
      { name="REDIS_URL", valueFrom=aws_ssm_parameter.redis_url.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        awslogs-group = aws_cloudwatch_log_group.api.name,
        awslogs-region = var.aws_region,
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name  = "worker"
    image = var.worker_image
    essential = true
    command = ["celery","-A","app.celery_app.celery","worker","--loglevel=INFO"]
    secrets = [
      { name="DATABASE_URL", valueFrom=aws_ssm_parameter.db_url.arn },
      { name="JWT_SECRET", valueFrom=aws_ssm_parameter.jwt.arn },
      { name="MFA_SECRET_KEY", valueFrom=aws_ssm_parameter.mfa.arn },
      { name="REDIS_URL", valueFrom=aws_ssm_parameter.redis_url.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        awslogs-group = aws_cloudwatch_log_group.worker.name,
        awslogs-region = var.aws_region,
        awslogs-stream-prefix = "worker"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${local.name}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name  = "beat"
    image = var.beat_image
    essential = true
    command = ["celery","-A","app.celery_app.celery","beat","--loglevel=INFO"]
    secrets = [
      { name="DATABASE_URL", valueFrom=aws_ssm_parameter.db_url.arn },
      { name="REDIS_URL", valueFrom=aws_ssm_parameter.redis_url.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        awslogs-group = aws_cloudwatch_log_group.beat.name,
        awslogs-region = var.aws_region,
        awslogs-stream-prefix = "beat"
      }
    }
  }])
}

# API service (disabled when blue/green enabled)
resource "aws_ecs_service" "api" {
  count           = var.enable_bluegreen ? 0 : 1
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
  tags = local.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name}-worker"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  tags = local.tags
}

resource "aws_ecs_service" "beat" {
  name            = "${local.name}-beat"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  tags = local.tags
}
