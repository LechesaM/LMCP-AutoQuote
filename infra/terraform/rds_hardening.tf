resource "aws_db_parameter_group" "pg16_hardened" {
  name   = "${local.name}-pg16-hardened"
  family = "postgres16"
  tags   = local.tags

  parameter { name = "log_connections" value = "1" }
  parameter { name = "log_disconnections" value = "1" }
  parameter { name = "log_checkpoints" value = "1" }
  parameter { name = "log_lock_waits" value = "1" }
  parameter { name = "log_min_duration_statement" value = "250" }
  parameter { name = "log_statement" value = "none" }
  parameter { name = "ssl" value = "1" }
}
