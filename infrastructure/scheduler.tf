# EventBridge Scheduler assumes this role when invoking the detector.
resource "aws_iam_role" "cost_waste_detector_scheduler" {
  name = "cost-waste-detector-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "scheduler.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


# Allow EventBridge Scheduler to invoke only this Lambda function.
resource "aws_iam_role_policy" "cost_waste_detector_scheduler" {
  name = "cost-waste-detector-scheduler-policy"
  role = aws_iam_role.cost_waste_detector_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "lambda:InvokeFunction"
        ]

        Resource = aws_lambda_function.cost_waste_detector.arn
      }
    ]
  })
}


# Run the detector automatically once per day.
resource "aws_scheduler_schedule" "cost_waste_detector" {
  name = "aws-cost-waste-detector-daily"

  schedule_expression = "rate(1 day)"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.cost_waste_detector.arn
    role_arn = aws_iam_role.cost_waste_detector_scheduler.arn
  }

  description = "Run the AWS cost waste detector once per day"
}