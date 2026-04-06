############################################
# ECS BLUE/GREEN DEPLOYMENTS (CODEDEPLOY)
# Single ALB, two target groups (blue/green)
# Prod traffic: existing listener (HTTP or HTTPS)
# Test traffic: dedicated listener on test_listener_port
############################################

# IMPORTANT:
# - When enable_bluegreen=true, the standard ECS api service is disabled (see ecs.tf).
# - This creates a new ECS service with deployment_controller=CODE_DEPLOY.
# - Your CI/CD must trigger CodeDeploy with appspec.yaml + taskdef revision.

resource "aws_lb_target_group" "api_blue" {
  count       = var.enable_bluegreen ? 1 : 0
  name        = "${local.name}-tg-api-blue"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.vpc.id
  target_type = "ip"

  health_check {
    path    = "/health"
    matcher = "200"
  }

  tags = local.tags
}

resource "aws_lb_target_group" "api_green" {
  count       = var.enable_bluegreen ? 1 : 0
  name        = "${local.name}-tg-api-green"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.vpc.id
  target_type = "ip"

  health_check {
    path    = "/health"
    matcher = "200"
  }

  tags = local.tags
}

locals {
  prod_listener_arn = (
    var.prod_listener_port == 443 && length(aws_lb_listener.https) > 0
    ? aws_lb_listener.https[0].arn
    : aws_lb_listener.http.arn
  )
}

resource "aws_lb_listener_rule" "api_bg_rule" {
  count        = var.enable_bluegreen ? 1 : 0
  listener_arn = local.prod_listener_arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_blue[0].arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/health", "/docs*", "/openapi.json"]
    }
  }

  tags = local.tags
}

resource "aws_lb_listener" "test" {
  count             = var.enable_bluegreen ? 1 : 0
  load_balancer_arn = aws_lb.alb.arn
  port              = var.test_listener_port
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_green[0].arn
  }

  tags = local.tags
}

data "aws_iam_policy_document" "codedeploy_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codedeploy.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codedeploy" {
  count              = var.enable_bluegreen ? 1 : 0
  name               = "${local.name}-codedeploy-role"
  assume_role_policy = data.aws_iam_policy_document.codedeploy_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "codedeploy_attach" {
  count     = var.enable_bluegreen ? 1 : 0
  role      = aws_iam_role.codedeploy[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSCodeDeployRoleForECS"
}

resource "aws_codedeploy_app" "ecs" {
  count            = var.enable_bluegreen ? 1 : 0
  name             = "${local.name}-codedeploy"
  compute_platform = "ECS"
}

resource "aws_ecs_service" "api_bg" {
  count           = var.enable_bluegreen ? 1 : 0
  name            = "${local.name}-api-bg"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  deployment_controller {
    type = "CODE_DEPLOY"
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api_blue[0].arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener_rule.api_bg_rule
  ]

  tags = local.tags
}

resource "aws_codedeploy_deployment_group" "ecs" {
  count                 = var.enable_bluegreen ? 1 : 0
  app_name              = aws_codedeploy_app.ecs[0].name
  deployment_group_name = "${local.name}-dg"
  service_role_arn      = aws_iam_role.codedeploy[0].arn

  deployment_config_name = "CodeDeployDefault.ECSCanary10Percent5Minutes"

  ecs_service {
    cluster_name = aws_ecs_cluster.cluster.name
    service_name = aws_ecs_service.api_bg[0].name
  }

  load_balancer_info {
    target_group_pair_info {
      target_group { name = aws_lb_target_group.api_blue[0].name }
      target_group { name = aws_lb_target_group.api_green[0].name }

      prod_traffic_route { listener_arns = [local.prod_listener_arn] }
      test_traffic_route { listener_arns = [aws_lb_listener.test[0].arn] }
    }
  }

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM", "DEPLOYMENT_STOP_ON_REQUEST"]
  }

  blue_green_deployment_config {
    terminate_blue_instances_on_deployment_success {
      action                           = "TERMINATE"
      termination_wait_time_in_minutes = var.bluegreen_termination_wait_minutes
    }

    deployment_ready_option {
      action_on_timeout = "CONTINUE_DEPLOYMENT"
    }
  }

  tags = local.tags
}

output "codedeploy_app_name" {
  value       = var.enable_bluegreen ? aws_codedeploy_app.ecs[0].name : null
  description = "CodeDeploy app name for blue/green deployments"
}

output "codedeploy_deployment_group" {
  value       = var.enable_bluegreen ? aws_codedeploy_deployment_group.ecs[0].deployment_group_name : null
  description = "CodeDeploy deployment group name"
}
