# Read replica for reporting (optional but recommended at scale)
# Use for dashboards, analytics, and heavy read queries.

variable "enable_read_replica" { type = bool default = true }

resource "aws_db_instance" "postgres_replica" {
  count                   = var.enable_read_replica ? 1 : 0
  identifier              = "${local.name}-pg-replica"
  replicate_source_db     = aws_db_instance.postgres.id
  instance_class          = "db.t4g.small"
  publicly_accessible     = false
  vpc_security_group_ids  = [aws_security_group.db.id]
  db_subnet_group_name    = aws_db_subnet_group.dbsubnet.name
  deletion_protection     = true
  skip_final_snapshot     = false
  tags = local.tags
}
