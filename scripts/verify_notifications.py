"""Verify real SNS delivery and DynamoDB notification deduplication."""

import os
from decimal import Decimal

import boto3

from aws_cost_waste_detector.notifications import (
    should_send_finding_notification,
)
from aws_cost_waste_detector.notifier import SnsNotifier
from aws_cost_waste_detector.storage.dynamodb import (
    mark_finding_notified,
)


REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("WASTE_FINDINGS_TABLE", "WasteFindings")
TOPIC_ARN = os.environ["COST_WASTE_ALERTS_TOPIC_ARN"]


def main() -> None:
    profile = os.getenv("AWS_PROFILE", "personal")

    session = boto3.Session(
        profile_name=profile,
        region_name=REGION,
    )

    account_id = session.client("sts").get_caller_identity()["Account"]

    table = session.resource(
        "dynamodb",
        region_name=REGION,
    ).Table(TABLE_NAME)

    sns_client = session.client(
        "sns",
        region_name=REGION,
    )

    notifier = SnsNotifier(
        sns_client,
        topic_arn=TOPIC_ARN,
    )

    # This is not a real AWS resource. It exists only long enough to
    # exercise the notification and deduplication path.
    resource_arn = (
        f"arn:aws:ec2:{REGION}:{account_id}:"
        "volume/vol-notification-test"
    )

    item = {
        "PK": f"RESOURCE#{resource_arn}",
        "SK": "RULE#notification-test",
        "rule_id": "notification-test",
        "account_id": account_id,
        "region": REGION,
        "resource_arn": resource_arn,
        "resource_id": "vol-notification-test",
        "resource_type": "AWS::EC2::Volume",
        "title": "Synthetic high-priority cost-waste finding",
        "description": (
            "Temporary finding used to verify SNS notification delivery."
        ),
        "severity": "HIGH",
        "recommendation": (
            "No action required. This is an integration test."
        ),
        "estimated_monthly_savings": Decimal("100.00"),
        "priority_score": Decimal("85"),
        "priority_label": "HIGH",
        "last_notified_at": None,
    }

    key = {
        "PK": item["PK"],
        "SK": item["SK"],
    }

    try:
        table.put_item(Item=item)

        print("Created synthetic HIGH-priority finding.")

        first_should_notify = should_send_finding_notification(item)

        print(
            "First notification eligible:",
            first_should_notify,
        )

        if not first_should_notify:
            raise RuntimeError(
                "Synthetic HIGH-priority finding was unexpectedly skipped."
            )

        message_id = notifier.send_finding(item)
        notified_at = mark_finding_notified(table, item)

        print("SNS MessageId:", message_id)
        print("Stored last_notified_at:", notified_at)

        stored_item = table.get_item(
            Key=key,
            ConsistentRead=True,
        )["Item"]

        second_should_notify = should_send_finding_notification(
            stored_item
        )

        print(
            "Second notification eligible:",
            second_should_notify,
        )

        if second_should_notify:
            raise RuntimeError(
                "Duplicate notification was not suppressed."
            )

        print()
        print("Notification integration test PASSED.")

    finally:
        table.delete_item(Key=key)
        print("Synthetic DynamoDB finding cleaned up.")


if __name__ == "__main__":
    main()