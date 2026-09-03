resource "aws_kms_key" "s3_kms" {
  description             = "KMS key for S3 bucket encryption"
  enable_key_rotation     = true
}

locals {
  buckets = [
    "ai-safety-models",
    "ai-safety-datasets",
    "ai-safety-audit-logs",
    "ai-safety-exports"
  ]
}

resource "aws_s3_bucket" "buckets" {
  count  = length(local.buckets)
  bucket = "siih2026-${local.buckets[count.index]}-${var.environment}"
}

resource "aws_s3_bucket_versioning" "buckets_versioning" {
  count  = length(local.buckets)
  bucket = aws_s3_bucket.buckets[count.index].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "buckets_encryption" {
  count  = length(local.buckets)
  bucket = aws_s3_bucket.buckets[count.index].id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_kms.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# Lifecycle policy for Audit Logs (transition to Glacier after 1 year)
resource "aws_s3_bucket_lifecycle_configuration" "audit_logs_lifecycle" {
  bucket = aws_s3_bucket.buckets[2].id # ai-safety-audit-logs

  rule {
    id     = "archive_to_glacier"
    status = "Enabled"

    transition {
      days          = 365
      storage_class = "GLACIER"
    }
    
    # REQ-11 requires 7 years retention for audit logs
    expiration {
      days = 2555 # 7 years
    }
  }
}
