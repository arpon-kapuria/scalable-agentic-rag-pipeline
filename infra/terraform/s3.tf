resource "aws_s3_bucket" "documents" {
  bucket        = "rag-platform-documents-dev-001"  # ← renamed to avoid conflict
  force_destroy = true   # ← changed to true for easy dev teardown

  tags = {
    Name = "Documents Bucket"
  }
}

resource "aws_s3_bucket_versioning" "docs_ver" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

# REMOVED: Transfer Acceleration — costs extra per GB, not needed for dev
# REMOVED: Intelligent Tiering lifecycle — adds complexity, not needed for dev

resource "aws_s3_bucket_cors_configuration" "docs_cors" {
  bucket = aws_s3_bucket.documents.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = ["*"]   # ← open for dev, restrict in prod
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}