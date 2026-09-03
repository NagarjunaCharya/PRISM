resource "aws_security_group" "redis_sg" {
  name        = "siih2026-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }
}

resource "aws_elasticache_subnet_group" "redis_subnet_group" {
  name       = "siih2026-redis-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id          = "siih2026-redis-${var.environment}"
  description                   = "Redis cluster for PRISM caching and rate limiting"
  node_type                     = "cache.r6g.large" # 13GB RAM
  port                          = 6379
  parameter_group_name          = "default.redis7.cluster.on"
  automatic_failover_enabled    = true
  
  subnet_group_name             = aws_elasticache_subnet_group.redis_subnet_group.name
  security_group_ids            = [aws_security_group.redis_sg.id]

  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true

  num_node_groups         = 1
  replicas_per_node_group = 1 # Primary + 1 replica
}
