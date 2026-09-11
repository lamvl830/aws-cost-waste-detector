from aws_cost_waste_detector.notifications import (
    should_send_finding_notification,
)
from aws_cost_waste_detector.notifier import SnsNotifier
from aws_cost_waste_detector.storage.dynamodb import (
    mark_finding_notified,
)


class FakeSnsClient:
    """
    Fake SNS client that records publish calls.
    """

    def __init__(self):
        self.publish_calls = []

    def publish(self, **kwargs):
        self.publish_calls.append(kwargs)

        return {
            "MessageId": "message-123",
        }


class FakeTable:
    """
    Fake DynamoDB table that records update calls.
    """

    def __init__(self):
        self.update_item_calls = []

    def update_item(self, **kwargs):
        self.update_item_calls.append(kwargs)


def make_notification_item(
    *,
    priority_label: str,
    last_notified_at=None,
):
    return {
        "PK": "RESOURCE#test-resource",
        "SK": "RULE#test-rule",
        "resource_id": "vol-123",
        "title": "EBS volume is currently unattached",
        "priority_label": priority_label,
        "priority_score": 65,
        "estimated_monthly_savings": 40.0,
        "recommendation": (
            "Verify the volume is no longer needed."
        ),
        "last_notified_at": last_notified_at,
    }


def test_high_priority_finding_is_published_and_marked_notified():
    sns_client = FakeSnsClient()
    table = FakeTable()

    notifier = SnsNotifier(
        sns_client,
        topic_arn=(
            "arn:aws:sns:us-east-1:"
            "123456789012:cost-waste-alerts"
        ),
    )

    item = make_notification_item(
        priority_label="HIGH",
    )

    assert should_send_finding_notification(item) is True

    message_id = notifier.send_finding(
        item
    )

    notified_at = mark_finding_notified(
        table,
        item,
    )

    assert message_id == "message-123"
    assert notified_at.endswith("+00:00")

    assert len(sns_client.publish_calls) == 1
    assert len(table.update_item_calls) == 1


def test_previously_notified_finding_is_skipped():
    item = make_notification_item(
        priority_label="HIGH",
        last_notified_at="2026-09-10T12:00:00+00:00",
    )

    assert should_send_finding_notification(item) is False


def test_low_priority_finding_is_skipped():
    item = make_notification_item(
        priority_label="LOW",
    )

    assert should_send_finding_notification(item) is False