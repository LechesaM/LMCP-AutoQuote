resource "aws_sns_topic" "alerts" {
  count = var.enable_sns ? 1 : 0
  name  = "${local.name}-alerts"
  tags  = local.tags
}

resource "aws_sns_topic_subscription" "email" {
  for_each = var.enable_sns ? toset(var.alert_emails) : []

  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = each.value
}
