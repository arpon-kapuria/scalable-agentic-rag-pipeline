module "aurora" {
  source  = "terraform-aws-modules/rds-aurora/aws"
  version = "8.3.0"

  name           = "${var.cluster_name}-postgres"
  engine         = "aurora-postgresql"
  engine_version = "15.3"
  
  # SERVERLESS V2: Scales Compute (ACU) up/down based on load
  instance_class = "db.serverless" 
  
  instances = {
    one = {}
    two = {} # High Availability (2 instances)
  }

  # High Budget -> High Performance config
  serverlessv2_scaling_configuration = {
    min_capacity = 2   # Baseline
    max_capacity = 64  # Scale up during peak chat traffic
  }

  vpc_id               = module.vpc.vpc_id
  db_subnet_group_name = module.vpc.database_subnet_group_name
  security_group_rules = {
    vpc_ingress = {
      cidr_blocks = [module.vpc.vpc_cidr_block] # Allow only internal VPC access
    }
  }

  master_username = "ragadmin"
  master_password = var.db_password
  
  skip_final_snapshot = false # Always snapshot before deleting
}