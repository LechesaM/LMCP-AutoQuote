resource "aws_ssm_parameter" "db_url" {
  name  = "/${local.name}/DATABASE_URL"
  type  = "SecureString"
  value = "postgresql+psycopg2://${var.db_user}:${var.db_pass}@${aws_db_instance.postgres.address}:5432/${var.db_name}"
}

resource "aws_ssm_parameter" "jwt" {
  name  = "/${local.name}/JWT_SECRET"
  type  = "SecureString"
  value = var.jwt_secret
}

resource "aws_ssm_parameter" "mfa" {
  name  = "/${local.name}/MFA_SECRET_KEY"
  type  = "SecureString"
  value = var.mfa_secret_key
}

resource "aws_ssm_parameter" "redis_url" {
  name  = "/${local.name}/REDIS_URL"
  type  = "SecureString"
  value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
}
