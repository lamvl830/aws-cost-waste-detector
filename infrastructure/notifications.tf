# SNS topic used for HIGH and CRITICAL cost-waste alerts.
resource "aws_sns_topic" "cost_waste_alerts" {
  name = "aws-cost-waste-detector-alerts"

  tags = {
    Project     = "aws-cost-waste-detector"
    Environment = "dev"
  }
}


# Optional email subscription for cost-waste alerts.
#
# The email address is supplied at deployment time instead of being
# committed to source control.
resource "aws_sns_topic_subscription" "cost_waste_alert_email" {
  count = var.alert_email != null ? 1 : 0

  topic_arn = aws_sns_topic.cost_waste_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}