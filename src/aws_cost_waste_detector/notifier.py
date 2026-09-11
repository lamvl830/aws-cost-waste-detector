from typing import Any


class SnsNotifier:
    """
    A notifier that sends messages to an AWS SNS topic.
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
        Publish a finding notification

        Return SNS MessageID
        """
        resource_id = item.get("resource_id", "unknown",)

        title = item.get("title", "AWS cost-waste finding",)

        priority_label = item.get("priority_label", "UNKNOWN",)

        priority_score = item.get("priority_score", 0,)

        monthly_savings = float(item.get("estimated_monthly_savings") or 0 )

        recommendation = item.get("recommendation", "Review the finding.",)

        subject = (f"AWS Cost Waste Alert: "
                   f"{priority_label} priority")

        message = "\n".join(
            [
                "AWS Cost Waste Alert",
                "--------------------",
                f"Resource: {resource_id}",
                f"Finding: {title}",
                (
                    f"Priority: "
                    f"{priority_label} "
                    f"({priority_score})"
                ),
                (
                    f"Estimated savings: "
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

