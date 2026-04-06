resource "aws_cloudwatch_log_group" "api" {
  name              = "/${local.name}/api"
  retention_in_days = 30
  tags = local.tags
}
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/${local.name}/worker"
  retention_in_days = 30
  tags = local.tags
}
resource "aws_cloudwatch_log_group" "beat" {
  name              = "/${local.name}/beat"
  retention_in_days = 30
  tags = local.tags
}
