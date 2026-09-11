from aws_cost_waste_detector.notifier import SnsNotifier


class FakeSnsClient:
    """
    Fake SNS client used to test notifications without calling AWS.
    """

    def __init__(self):
        self.publish_calls = []

    def publish(self, **kwargs):
        self.publish_calls.append(
            kwargs
        )

        return {
            "MessageId": "message-123",
        }


def test_sns_notifier_publishes_finding():
    client = FakeSnsClient()

    notifier = SnsNotifier(
        client,
        topic_arn=(
            "arn:aws:sns:us-east-1:"
            "123456789012:cost-waste-alerts"
        ),
    )

    item = {
        "resource_id": "vol-123",
        "title": "EBS volume is currently unattached",
        "priority_label": "HIGH",
        "priority_score": 65,
        "estimated_monthly_savings": 40.0,
        "recommendation": (
            "Verify the volume is no longer needed."
        ),
    }

    message_id = notifier.send_finding(
        item
    )

    assert message_id == "message-123"
    assert len(client.publish_calls) == 1

    call = client.publish_calls[0]

    assert (
        call["TopicArn"]
        == "arn:aws:sns:us-east-1:"
        "123456789012:cost-waste-alerts"
    )

    assert (
        call["Subject"]
        == "AWS Cost Waste Alert: HIGH priority"
    )

    assert "vol-123" in call["Message"]
    assert "HIGH (65)" in call["Message"]
    assert "$40.00/month" in call["Message"]