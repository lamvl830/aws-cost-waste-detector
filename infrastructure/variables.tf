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


variable "scan_regions" {
  description = "AWS regions scanned for cost-waste findings. If not configured, only aws_region is scanned."
  type        = list(string)
  default     = null

  validation {
    condition = (
      var.scan_regions == null
      ? true
      : length(var.scan_regions) > 0
    )

    error_message = "scan_regions must contain at least one AWS region when configured."
  }
}


variable "ec2_idle_lookback_days" {
  description = "Number of days of CloudWatch metrics used to evaluate whether an EC2 instance appears idle."
  type        = number
  default     = 7

  validation {
    condition = (
      var.ec2_idle_lookback_days > 0
      && floor(var.ec2_idle_lookback_days) == var.ec2_idle_lookback_days
    )

    error_message = "ec2_idle_lookback_days must be a positive whole number."
  }
}


variable "ec2_idle_average_cpu_threshold_percent" {
  description = "Maximum average CPU utilization percentage for an EC2 instance to be considered idle."
  type        = number
  default     = 5

  validation {
    condition = (
      var.ec2_idle_average_cpu_threshold_percent >= 0
      && var.ec2_idle_average_cpu_threshold_percent <= 100
    )
    error_message = "ec2_idle_average_cpu_threshold_percent must be between 0 and 100."
  }
}


variable "ec2_idle_maximum_cpu_threshold_percent" {
  description = "Maximum observed CPU utilization percentage for an EC2 instance to be considered idle."
  type        = number
  default     = 20

  validation {
    condition = (
      var.ec2_idle_maximum_cpu_threshold_percent >= 0
      && var.ec2_idle_maximum_cpu_threshold_percent <= 100
    )
    error_message = "ec2_idle_maximum_cpu_threshold_percent must be between 0 and 100."
  }
}


variable "ec2_idle_network_in_threshold_mib" {
  description = "Maximum inbound network traffic in MiB over the lookback window for an EC2 instance to be considered idle."
  type        = number
  default     = 100

  validation {
    condition     = var.ec2_idle_network_in_threshold_mib >= 0
    error_message = "ec2_idle_network_in_threshold_mib cannot be negative."
  }
}


variable "ec2_idle_network_out_threshold_mib" {
  description = "Maximum outbound network traffic in MiB over the lookback window for an EC2 instance to be considered idle."
  type        = number
  default     = 100

  validation {
    condition     = var.ec2_idle_network_out_threshold_mib >= 0
    error_message = "ec2_idle_network_out_threshold_mib cannot be negative."
  }
}


variable "ec2_idle_minimum_metric_coverage" {
  description = "Minimum fraction of expected CloudWatch datapoints required before an EC2 instance can be classified as idle."
  type        = number
  default     = 0.80

  validation {
    condition = (
      var.ec2_idle_minimum_metric_coverage > 0
      && var.ec2_idle_minimum_metric_coverage <= 1
    )

    error_message = "ec2_idle_minimum_metric_coverage must be greater than 0 and no greater than 1."
  }
}

variable "lambda_timeout_seconds" {
  description = "Maximum execution time in seconds for the detector Lambda."
  type        = number
  default     = 180

  validation {
    condition = (
      var.lambda_timeout_seconds >= 1
      && var.lambda_timeout_seconds <= 900
      && floor(var.lambda_timeout_seconds) == var.lambda_timeout_seconds
    )

    error_message = "lambda_timeout_seconds must be a whole number between 1 and 900."
  }
}