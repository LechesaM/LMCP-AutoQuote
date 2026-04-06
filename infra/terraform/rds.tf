resource "aws_db_subnet_group" "dbsubnet" {
  name       = "${local.name}-dbsubnet"
  subnet_ids = aws_subnet.db[*].id
  tags = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier             = "${local.name}-pg"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.small"
  allocated_storage      = 50
  storage_type           = "gp3"
  db_name                = var.db_name
  username               = var.db_user
  password               = var.db_pass

  parameter_group_name   = aws_db_parameter_group.pg16_hardened.name

  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.dbsubnet.name

  backup_retention_period = 7
  deletion_protection     = true
  skip_final_snapshot     = false

  tags = local.tags
}
