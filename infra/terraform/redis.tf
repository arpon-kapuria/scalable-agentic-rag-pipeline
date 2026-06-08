resource "aws_elasticache_subnet_group" "redis_subnet" {
  name       = "${var.cluster_name}-redis-subnet"
  subnet_ids = module.vpc.database_subnets
}

resource "aws_security_group" "redis_sg" {
  name   = "${var.cluster_name}-redis-sg"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
}

resource "aws_elasticache_cluster" "redis" {
  # CHANGED: replication_group → single cluster node
  # t4g.medium with replica = ~$50/month
  # t3.micro single node = ~$12/month

  cluster_id      = "rag-redis-dev"
  engine          = "redis"
  node_type       = "cache.t3.micro"   # ← cheapest available
  num_cache_nodes = 1                  # ← no replica, single node
  port            = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis_subnet.name
  security_group_ids = [aws_security_group.redis_sg.id]

  # REMOVED: at_rest_encryption and transit_encryption
  # These require paid instance types on some regions
  # Add back when upgrading to prod
}