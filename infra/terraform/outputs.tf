output "eks_cluster_name" {
  description = "The name of the EKS cluster."
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "The endpoint for the EKS cluster's API server."
  value       = module.eks.cluster_endpoint
}

output "postgres_db_endpoint" {
  description = "The RDS PostgreSQL endpoint."
  value       = aws_db_instance.postgres.endpoint  # ← changed from aurora
}

output "redis_endpoint" {
  description = "The ElastiCache Redis endpoint."
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address  # ← changed
}

output "s3_documents_bucket_name" {
  description = "The name of the S3 bucket for document storage."
  value       = aws_s3_bucket.documents.id
}

output "ecr_api_url" {
  value = aws_ecr_repository.rag_api.repository_url
}

output "ecr_models_url" {
  value = aws_ecr_repository.rag_models.repository_url
}