variable "aws_region" {
  description = "AWS region where the detector will be deployed."
  type        = string
  default     = "us-east-1"
}


variable "environment" {
  description = "Deployment environment name used for tagging and resource naming."
  type        = string
  default     = "dev"

  validation {
    condition = contains(
      ["dev", "staging", "prod"],
      var.environment
    )

    error_message = "environment must be dev, staging, or prod."
  }
}


variable "project_name" {
  description = "Base name used for AWS Cost Waste Detector resources."
  type        = string
  default     = "aws-cost-waste-detector"
}


variable "findings_table_name" {
  description = "Name of the DynamoDB table used to store findings."
  type        = string
  default     = "WasteFindings"
}


variable "scan_schedule" {
  description = "EventBridge Scheduler expression controlling how often scans run."
  type        = string
  default     = "rate(1 day)"
}


variable "finding_grace_period_days" {
  description = "Number of days a finding must persist before becoming OPEN."
  type        = number
  default     = 7

  validation {
    condition     = var.finding_grace_period_days >= 0
    error_message = "finding_grace_period_days cannot be negative."
  }
}


variable "alert_email" {
  description = "Email address that receives high-priority cost-waste alerts."
  type        = string
  default     = null
  nullable    = true
}


variable "lambda_role_name" {
  description = "Name of the IAM role used by the detector Lambda."
  type        = string
  default     = "cost-waste-detector-lambda-role"
}


variable "scheduler_name" {
  description = "Name of the EventBridge Scheduler schedule."
  type        = string
  default     = "aws-cost-waste-detector-daily"
}


variable "scheduler_role_name" {
  description = "Name of the IAM role used by EventBridge Scheduler."
  type        = string
  default     = "cost-waste-detector-scheduler-role"
}


variable "alerts_topic_name" {
  description = "Name of the SNS topic used for cost-waste alerts."
  type        = string
  default     = "aws-cost-waste-detector-alerts"
}


variable "dynamodb_point_in_time_recovery_enabled" {
  description = "Enable point-in-time recovery for the findings table."
  type        = bool
  default     = true
}


variable "dynamodb_deletion_protection_enabled" {
  description = "Protect the findings table from accidental deletion."
  type        = bool
  default     = false
}


variable "report_retention_days" {
  description = "Number of days generated HTML reports are retained in S3."
  type        = number
  default     = 30

  validation {
    condition     = var.report_retention_days > 0
    error_message = "report_retention_days must be greater than zero."
  }
}