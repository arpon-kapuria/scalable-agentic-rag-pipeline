# CHANGED: Aurora Serverless → standard RDS PostgreSQL
# Aurora Serverless v2 requires paid account and minimum 0.5 ACU
# RDS t3.micro is free-tier eligible and costs ~$12/month after free tier

resource "aws_db_subnet_group" "postgres" {
  name       = "${var.cluster_name}-postgres-subnet"
  subnet_ids = module.vpc.database_subnets
}

resource "aws_security_group" "postgres_sg" {
  name   = "${var.cluster_name}-postgres-sg"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
}

resource "aws_db_instance" "postgres" {
  identifier        = "${var.cluster_name}-postgres"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.t3.micro"   # ← free tier eligible
  allocated_storage = 20              # ← free tier gives 20GB

  db_name  = "ragdb"
  username = "ragadmin"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres_sg.id]

  backup_retention_period = 1          # ← free tier max
  skip_final_snapshot     = true       # ← set true for dev to avoid errors on destroy
  publicly_accessible     = false      # ← internal only

  # NO multi-az — costs double
  multi_az = false
}