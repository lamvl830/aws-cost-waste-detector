# Stores cost-waste findings discovered by the scanner.
#
# PK identifies the AWS resource.
# SK identifies the specific waste rule for that resource.
resource "aws_dynamodb_table" "waste_findings" {
  name         = "WasteFindings"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "PK"
  range_key = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  tags = {
    Project     = "aws-cost-waste-detector"
    Environment = "dev"
  }
}