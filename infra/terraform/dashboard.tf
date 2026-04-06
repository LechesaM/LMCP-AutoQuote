resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name}-ops"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric",
        x = 0, y = 0, width = 12, height = 6,
        properties = {
          metrics = [
            ["AWS/ApplicationELB","HTTPCode_Target_5XX_Count","LoadBalancer", aws_lb.alb.arn_suffix, "TargetGroup", aws_lb_target_group.api.arn_suffix],
            [".","TargetResponseTime",".",".",".","."]
          ],
          view = "timeSeries",
          region = var.aws_region,
          title = "ALB 5XX + Latency"
        }
      },
      {
        type = "metric",
        x = 12, y = 0, width = 12, height = 6,
        properties = {
          metrics = [
            ["AWS/RDS","CPUUtilization","DBInstanceIdentifier", aws_db_instance.postgres.id],
            [".","FreeStorageSpace",".","."]
          ],
          view = "timeSeries",
          region = var.aws_region,
          title = "RDS Health"
        }
      },
      {
        type = "metric",
        x = 0, y = 6, width = 12, height = 6,
        properties = {
          metrics = [
            ["AutoQuote","QueueDepthPerWorker","QueueName","celery"],
            [".","SendFailedCount"],
            [".","SendBlockedCount"]
          ],
          view = "timeSeries",
          region = var.aws_region,
          title = "App Custom Metrics"
        }
      }
    ]
  })
}
