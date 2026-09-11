# Alert when the detector Lambda reports one or more errors.
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name = "${var.project_name}-lambda-errors"

  alarm_description = (
    "AWS Cost Waste Detector Lambda reported one or more errors."
  )

  namespace   = "AWS/Lambda"
  metric_name = "Errors"

  dimensions = {
    FunctionName = aws_lambda_function.cost_waste_detector.function_name
  }

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1

  treat_missing_data = "notBreaching"

  alarm_actions = [
    aws_sns_topic.cost_waste_alerts.arn
  ]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}


# Alert when AWS throttles one or more Lambda invocations.
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name = "${var.project_name}-lambda-throttles"

  alarm_description = (
    "AWS Cost Waste Detector Lambda experienced throttled invocations."
  )

  namespace   = "AWS/Lambda"
  metric_name = "Throttles"

  dimensions = {
    FunctionName = aws_lambda_function.cost_waste_detector.function_name
  }

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1

  treat_missing_data = "notBreaching"

  alarm_actions = [
    aws_sns_topic.cost_waste_alerts.arn
  ]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}