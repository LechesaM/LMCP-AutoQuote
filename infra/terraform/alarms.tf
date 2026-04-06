# ALB 5xx + latency
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${local.name}-alb-5xx-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10

  dimensions = {
    LoadBalancer = aws_lb.alb.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }

  alarm_actions = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
  ok_actions    = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
}

resource "aws_cloudwatch_metric_alarm" "alb_latency" {
  alarm_name          = "${local.name}-alb-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 1.5

  dimensions = {
    LoadBalancer = aws_lb.alb.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }

  alarm_actions = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
  ok_actions    = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
}

# RDS CPU + storage
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.name}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.id
  }

  alarm_actions = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
  ok_actions    = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
}

resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${local.name}-rds-free-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5e9

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.id
  }

  alarm_actions = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
  ok_actions    = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
}

# Redis CPU
resource "aws_cloudwatch_metric_alarm" "redis_cpu_high" {
  alarm_name          = "${local.name}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    CacheClusterId = aws_elasticache_cluster.redis.id
  }

  alarm_actions = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
  ok_actions    = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
}

# App custom metrics (published by your app)
resource "aws_cloudwatch_metric_alarm" "send_failed_spike" {
  alarm_name          = "${local.name}-send-failed-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "SendFailedCount"
  namespace           = "AutoQuote"
  period              = 300
  statistic           = "Sum"
  threshold           = 3

  alarm_actions = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
  ok_actions    = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
}

resource "aws_cloudwatch_metric_alarm" "send_blocked_spike" {
  alarm_name          = "${local.name}-send-blocked-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "SendBlockedCount"
  namespace           = "AutoQuote"
  period              = 300
  statistic           = "Sum"
  threshold           = 20

  alarm_actions = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
  ok_actions    = var.enable_sns ? [aws_sns_topic.alerts[0].arn] : []
}
