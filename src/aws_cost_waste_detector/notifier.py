from typing import Any


class SnsNotifier:
    """
    Send AWS Cost Waste Detector notifications through SNS.
    """

    def __init__(
        self,
        sns_client: Any,
        *,
        topic_arn: str,
    ):
        self.sns_client = sns_client
        self.topic_arn = topic_arn

    def send_finding(
        self,
        item: dict[str, Any],
    ) -> str:
        """
        Publish an individual HIGH or CRITICAL finding notification.

        Returns the SNS MessageId.
        """
        resource_id = item.get(
            "resource_id",
            "unknown",
        )

        title = item.get(
            "title",
            "AWS cost-waste finding",
        )

        priority_label = item.get(
            "priority_label",
            "UNKNOWN",
        )

        priority_score = item.get(
            "priority_score",
            0,
        )

        monthly_savings = float(
            item.get(
                "estimated_monthly_savings"
            )
            or 0
        )

        recommendation = item.get(
            "recommendation",
            "Review the finding.",
        )

        subject = (
            "AWS Cost Waste Alert: "
            f"{priority_label} priority"
        )

        message = "\n".join(
            [
                "AWS Cost Waste Alert",
                "--------------------",
                f"Resource: {resource_id}",
                f"Finding: {title}",
                (
                    "Priority: "
                    f"{priority_label} "
                    f"({priority_score})"
                ),
                (
                    "Estimated savings: "
                    f"${monthly_savings:.2f}/month"
                ),
                f"Recommendation: {recommendation}",
            ]
        )

        response = self.sns_client.publish(
            TopicArn=self.topic_arn,
            Subject=subject,
            Message=message,
        )

        return response["MessageId"]

    def send_report_summary(
        self,
        *,
        account_id: str,
        region: str,
        summary: dict[str, Any],
        report_url: str,
    ) -> str:
        """
        Publish a scan summary containing the private HTML report link.

        This notification is separate from individual HIGH/CRITICAL
        finding alerts and gives the customer one consolidated view of
        all current opportunities.
        """
        total_findings = int(
            summary.get(
                "total_findings",
                0,
            )
        )

        monthly_savings = float(
            summary.get(
                "total_monthly_savings",
                0,
            )
            or 0
        )

        annual_savings = float(
            summary.get(
                "total_annual_savings",
                0,
            )
            or 0
        )

        subject = (
            "AWS Cost Waste Report: "
            f"{total_findings} finding"
        )

        if total_findings != 1:
            subject += "s"

        message = "\n".join(
            [
                "AWS Cost Waste Detector",
                "-----------------------",
                f"AWS Account: {account_id}",
                f"Region: {region}",
                f"Current findings: {total_findings}",
                (
                    "Estimated monthly savings: "
                    f"${monthly_savings:.2f}"
                ),
                (
                    "Estimated annual savings: "
                    f"${annual_savings:.2f}"
                ),
                "",
                "View the full private report:",
                report_url,
                "",
                (
                    "The report link is temporary and will expire "
                    "automatically."
                ),
                (
                    "Savings are estimates. The detector does not "
                    "automatically delete or modify AWS resources."
                ),
            ]
        )

        response = self.sns_client.publish(
            TopicArn=self.topic_arn,
            Subject=subject,
            Message=message,
        )

        return response["MessageId"]