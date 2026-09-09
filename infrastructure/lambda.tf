# Package the Python application source for Lambda.
#
# The contents of src/ are placed at the root of the ZIP so Lambda
# can import the aws_cost_waste_detector package directly.
data "archive_file" "cost_waste_detector" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda_package.zip"
}


# Lambda assumes this role when the scheduled detector runs.
resource "aws_iam_role" "cost_waste_detector_lambda" {
  name = "cost-waste-detector-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


# Grant only the AWS API permissions required by the detector.
resource "aws_iam_role_policy" "cost_waste_detector_lambda" {
  name = "cost-waste-detector-lambda-policy"
  role = aws_iam_role.cost_waste_detector_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "DescribeCostWasteResources"
        Effect = "Allow"

        Action = [
          "ec2:DescribeVolumes",
          "ec2:DescribeAddresses"
        ]

        Resource = "*"
      },
      {
        Sid    = "ReadAWSPrices"
        Effect = "Allow"

        Action = [
          "pricing:GetProducts"
        ]

        Resource = "*"
      },
      {
        Sid    = "PersistFindings"
        Effect = "Allow"

        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Scan"
        ]

        Resource = aws_dynamodb_table.waste_findings.arn
      },
      {
        Sid    = "WriteCloudWatchLogs"
        Effect = "Allow"

        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]

        Resource = "${aws_cloudwatch_log_group.cost_waste_detector.arn}:*"
      }
    ]
  })
}


# Keep Lambda logs for a limited period instead of indefinitely.
resource "aws_cloudwatch_log_group" "cost_waste_detector" {
  name              = "/aws/lambda/aws-cost-waste-detector"
  retention_in_days = 14
}


resource "aws_lambda_function" "cost_waste_detector" {
  function_name = "aws-cost-waste-detector"

  role = aws_iam_role.cost_waste_detector_lambda.arn

  runtime = "python3.12"

  handler = (
    "aws_cost_waste_detector.lambda_handler.lambda_handler"
  )

  filename = data.archive_file.cost_waste_detector.output_path

  source_code_hash = (
    data.archive_file.cost_waste_detector.output_base64sha256
  )

  timeout     = 60
  memory_size = 256

  environment {
    variables = {
      WASTE_FINDINGS_TABLE = aws_dynamodb_table.waste_findings.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.cost_waste_detector,
    aws_iam_role_policy.cost_waste_detector_lambda,
  ]

  tags = {
    Project     = "aws-cost-waste-detector"
    Environment = "dev"
  }
}