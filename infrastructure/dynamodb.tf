# Stores cost-waste findings discovered by the detector.
#
# PK identifies the AWS resource.
# SK identifies the specific waste rule affecting the resource.
resource "aws_dynamodb_table" "waste_findings" {
  name         = var.findings_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "PK"
  range_key = "SK"

  deletion_protection_enabled = var.dynamodb_deletion_protection_enabled

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # DynamoDB encrypts data at rest. Explicitly enabling SSE makes
  # that security behavior visible in the infrastructure definition.
  server_side_encryption {
    enabled = true
  }

  # Allow recovery of the findings table to a previous point in time.
  point_in_time_recovery {
    enabled = var.dynamodb_point_in_time_recovery_enabled
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}