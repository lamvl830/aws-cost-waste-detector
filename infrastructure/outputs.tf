output "aws_region" {
  description = "AWS region where the detector is deployed."
  value       = var.aws_region
}


output "environment" {
  description = "Deployment environment."
  value       = var.environment
}


output "dynamodb_table_name" {
  description = "DynamoDB table used to store cost-waste findings."
  value       = aws_dynamodb_table.waste_findings.name
}


output "lambda_function_name" {
  description = "Name of the detector Lambda function."
  value       = aws_lambda_function.cost_waste_detector.function_name
}


output "lambda_function_arn" {
  description = "ARN of the detector Lambda function."
  value       = aws_lambda_function.cost_waste_detector.arn
}


output "sns_topic_arn" {
  description = "SNS topic used for HIGH and CRITICAL finding alerts."
  value       = aws_sns_topic.cost_waste_alerts.arn
}


output "scheduler_name" {
  description = "EventBridge Scheduler schedule used to run the detector."
  value       = aws_scheduler_schedule.cost_waste_detector.name
}


output "scan_schedule" {
  description = "Configured schedule expression for automatic scans."
  value       = var.scan_schedule
}


output "cloudwatch_log_group" {
  description = "CloudWatch log group for detector Lambda execution logs."
  value       = aws_cloudwatch_log_group.cost_waste_detector.name
}


output "alert_email_configured" {
  description = "Whether an alert email was configured for SNS notifications."
  value       = var.alert_email != null
}


output "report_bucket_name" {
  description = "Private S3 bucket containing generated HTML reports."
  value       = aws_s3_bucket.reports.bucket
}