module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.32" # Use stable K8s version

  # Networking: Connect to the VPC we just created
  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true # Allow developer access from internet (secured by IAM)

  # OIDC Provider is REQUIRED for Service Accounts (IRSA)
  # This allows a specific Pod to assume an AWS IAM Role
  enable_irsa = true

  # NODE GROUPS (The "Always On" Baseline)
  eks_managed_node_groups = {
    # System Node Group: Runs CoreDNS, Karpenter, Ingress Controller
    system = {
      name           = "system-nodes"
      instance_types = ["m6i.large"] # Modern Intel generation
      min_size       = 2
      max_size       = 5
      desired_size   = 2
      
      # Taints prevent App pods from scheduling here accidentally
      taints = [
        {
          key    = "CriticalAddonsOnly"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }

  # Prepare security groups
  node_security_group_tags = {
    "karpenter.sh/discovery" = var.cluster_name
  }
}

# Export the Cluster Endpoint
output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}