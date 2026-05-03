# Define the Terraform configuration
terraform {
  # We require a recent version of Terraform for stability
  required_version = ">= 1.5.0"

  # Define the providers we need to interact with AWS and Kubernetes
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0" # Use version 5.x for latest features
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }

  # REMOTE STATE STORAGE (Industry Standard)
  # This saves the infrastructure state to S3 so multiple engineers can work safely.
  # Note: You must create this bucket manually once before running terraform init.
  backend "s3" {
    bucket         = "scalable-rag-platform-terraform-state-prod-001" # Unique bucket name
    key            = "platform/terraform.tfstate"                     # Path inside bucket
    region         = "us-east-1"                                      # AWS Region
    encrypt        = true                                             # Encrypt state at rest
    use_lockfile   = true                                             # Prevents concurrent writes
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  # Apply default tags to ALL resources for cost tracking (FinOps)
  default_tags {
    tags = {
      Project     = "Enterprise-RAG"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}