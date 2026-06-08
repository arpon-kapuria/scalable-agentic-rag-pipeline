resource "aws_ecr_repository" "rag_api" {
  name                 = "rag-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true   # ← scans for vulnerabilities on every push
  }

  tags = {
    Name = "rag-api"
  }
}

resource "aws_ecr_repository" "rag_models" {
  name                 = "rag-models"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "rag-models"
  }
}

# Lifecycle policy — keep only last 5 images to save storage costs
resource "aws_ecr_lifecycle_policy" "rag_api" {
  repository = aws_ecr_repository.rag_api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "rag_models" {
  repository = aws_ecr_repository.rag_models.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}


# resource "aws_ecr_repository" "rag_sandbox" {
#   name                 = "rag-sandbox"
#   image_tag_mutability = "MUTABLE"

#   image_scanning_configuration {
#     scan_on_push = true
#   }
# }

# resource "aws_ecr_lifecycle_policy" "rag_sandbox" {
#   repository = aws_ecr_repository.rag_sandbox.name
#   policy = jsonencode({
#     rules = [{
#       rulePriority = 1
#       description  = "Keep last 5 images"
#       selection = {
#         tagStatus   = "any"
#         countType   = "imageCountMoreThan"
#         countNumber = 5
#       }
#       action = { type = "expire" }
#     }]
#   })
# }

# output "ecr_sandbox_url" {
#   value = aws_ecr_repository.rag_sandbox.repository_url
# }