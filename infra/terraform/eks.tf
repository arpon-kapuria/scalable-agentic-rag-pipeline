module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.33"

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true
  enable_irsa                    = true

  # ← disable KMS encryption entirely for dev setup
  create_kms_key            = false
  cluster_encryption_config = {}

  eks_managed_node_groups = {
    system = {
      name           = "system-nodes"
      instance_types = ["t3.medium"]  # ← cheapest EKS-compatible, free-tier eligible

      min_size     = 1   # ← reduced from 2 (saves ~$30/month)
      max_size     = 3
      desired_size = 1

      # REMOVED taints — with only 1 node, app pods must also run here
      # In prod: system node is tainted to prevent app pods scheduling there
      # In dev: we can't afford a dedicated system node
    }
  }

  node_security_group_tags = {
    "karpenter.sh/discovery" = var.cluster_name
  }
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}