# Store generated HTML cost-waste reports.
#
# bucket_prefix lets AWS create a globally unique bucket name while
# keeping the project's name recognizable.
resource "aws_s3_bucket" "reports" {
  bucket_prefix = "${var.project_name}-reports-"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}


# Prevent any form of public access to generated reports.
resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


# Disable ACL-based ownership and keep ownership with the
# customer's AWS account.
resource "aws_s3_bucket_ownership_controls" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}


# Encrypt generated reports at rest using S3-managed encryption.
resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


# Automatically remove old reports so the bucket does not grow forever.
resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    id     = "expire-old-reports"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = var.report_retention_days
    }
  }
}