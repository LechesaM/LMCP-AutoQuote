resource "aws_elasticache_subnet_group" "redis_subnet" {
  name       = "${local.name}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
  tags = local.tags
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.name}-redis"
  engine               = "redis"
  node_type            = "cache.t4g.small"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name    = aws_elasticache_subnet_group.redis_subnet.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = local.tags
}
