from datetime import datetime, timezone

from botocore.exceptions import ClientError

from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.storage.dynamodb import (
    finding_key,
    finding_to_item,
    list_active_findings,
    put_new_finding,
    resolve_finding,
    save_finding,
    update_existing_finding,
)


def make_finding() -> Finding:
    """
    Create a reusable test finding.
    """
    return Finding(
        rule_id="EBS_CURRENTLY_UNATTACHED",
        account_id="123456789012",
        region="us-east-1",
        resource_arn=(
            "arn:aws:ec2:us-east-1:123456789012:volume/vol-123"
        ),
        resource_id="vol-123",
        resource_type="AWS::EC2::Volume",
        title="EBS volume is currently unattached",
        description="Volume vol-123 is currently unattached.",
        severity="LOW",
        recommendation="Verify the volume is no longer needed.",
        estimated_monthly_savings=None,
        metadata={
            "size_gib": 100,
            "volume_type": "gp3",
        },
    )


class FakeTable:
    """
    Minimal fake DynamoDB table used to verify persistence behavior
    without making real AWS requests.
    """

    def __init__(
        self,
        item_exists: bool = False,
        existing_item: dict | None = None,
    ):
        self.item_exists = item_exists
        self.existing_item = existing_item

        # Record calls made by the code under test.
        self.put_item_calls = []
        self.get_item_calls = []
        self.update_item_calls = []
        self.scan_calls = []

        # Tests can preload fake paginated scan responses here.
        self.scan_responses = []

    def put_item(self, **kwargs):
        self.put_item_calls.append(kwargs)

        if self.item_exists:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ConditionalCheckFailedException",
                        "Message": "Item already exists",
                    }
                },
                "PutItem",
            )

    def get_item(self, **kwargs):
        self.get_item_calls.append(kwargs)

        if self.existing_item is None:
            return {}

        return {
            "Item": self.existing_item,
        }

    def update_item(self, **kwargs):
        self.update_item_calls.append(kwargs)

    def scan(self, **kwargs):
        self.scan_calls.append(kwargs)

        if self.scan_responses:
            return self.scan_responses.pop(0)

        return {
            "Items": [],
        }


def test_finding_key():
    finding = make_finding()

    key = finding_key(finding)

    assert key == {
        "PK": (
            "RESOURCE#"
            "arn:aws:ec2:us-east-1:123456789012:volume/vol-123"
        ),
        "SK": "RULE#EBS_CURRENTLY_UNATTACHED",
    }


def test_finding_to_item():
    finding = make_finding()

    item = finding_to_item(finding)

    assert item["PK"] == (
        "RESOURCE#"
        "arn:aws:ec2:us-east-1:123456789012:volume/vol-123"
    )

    assert item["SK"] == "RULE#EBS_CURRENTLY_UNATTACHED"

    assert item["rule_id"] == "EBS_CURRENTLY_UNATTACHED"
    assert item["account_id"] == "123456789012"
    assert item["region"] == "us-east-1"
    assert item["resource_id"] == "vol-123"

    assert item["status"] == "OBSERVED"
    assert item["resolved_at"] is None

    # Newly-created findings begin with matching observation timestamps.
    assert item["first_seen"] == item["last_seen"]


def test_put_new_finding():
    finding = make_finding()
    table = FakeTable()

    put_new_finding(
        table,
        finding,
    )

    assert len(table.put_item_calls) == 1

    call = table.put_item_calls[0]

    assert call["Item"]["resource_id"] == "vol-123"
    assert call["Item"]["status"] == "OBSERVED"

    assert call["ConditionExpression"] == (
        "attribute_not_exists(PK) AND attribute_not_exists(SK)"
    )


def test_update_existing_finding():
    finding = make_finding()
    table = FakeTable()

    existing_item = {
        "first_seen": datetime.now(timezone.utc).isoformat(),
    }

    update_existing_finding(
        table,
        finding,
        existing_item,
    )

    assert len(table.update_item_calls) == 1

    call = table.update_item_calls[0]

    assert call["Key"] == {
        "PK": (
            "RESOURCE#"
            "arn:aws:ec2:us-east-1:123456789012:volume/vol-123"
        ),
        "SK": "RULE#EBS_CURRENTLY_UNATTACHED",
    }

    assert "last_seen = :last_seen" in call["UpdateExpression"]

    values = call["ExpressionAttributeValues"]

    assert values[":title"] == "EBS volume is currently unattached"
    assert values[":severity"] == "LOW"
    assert values[":savings"] is None

    # first_seen should never be overwritten by a later observation.
    assert "first_seen" not in call["UpdateExpression"]


def test_save_finding_created():
    finding = make_finding()
    table = FakeTable(
        item_exists=False,
    )

    result = save_finding(
        table,
        finding,
    )

    assert result == "CREATED"

    assert len(table.put_item_calls) == 1
    assert len(table.get_item_calls) == 0
    assert len(table.update_item_calls) == 0


def test_save_finding_updated():
    finding = make_finding()

    existing_item = {
        "first_seen": datetime.now(timezone.utc).isoformat(),
    }

    table = FakeTable(
        item_exists=True,
        existing_item=existing_item,
    )

    result = save_finding(
        table,
        finding,
    )

    assert result == "UPDATED"

    assert len(table.put_item_calls) == 1
    assert len(table.get_item_calls) == 1
    assert len(table.update_item_calls) == 1

    # We request a consistent read because lifecycle state depends
    # on the existing first_seen value.
    assert table.get_item_calls[0]["ConsistentRead"] is True


def test_update_existing_finding_keeps_observed_before_grace_period():
    finding = make_finding()
    table = FakeTable()

    existing_item = {
        "first_seen": datetime.now(timezone.utc).isoformat(),
    }

    update_existing_finding(
        table,
        finding,
        existing_item,
        grace_period_days=7,
    )

    call = table.update_item_calls[0]
    values = call["ExpressionAttributeValues"]

    assert values[":status"] == "OBSERVED"


def test_update_existing_finding_becomes_open_after_grace_period():
    finding = make_finding()
    table = FakeTable()

    first_seen = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    existing_item = {
        "first_seen": first_seen.isoformat(),
    }

    # A zero-day grace period guarantees an immediate OPEN transition.
    update_existing_finding(
        table,
        finding,
        existing_item,
        grace_period_days=0,
    )

    call = table.update_item_calls[0]
    values = call["ExpressionAttributeValues"]

    assert values[":status"] == "OPEN"


def test_update_existing_finding_reactivates_resolved_finding():
    finding = make_finding()
    table = FakeTable()

    old_first_seen = datetime(
        2026,
        8,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    existing_item = {
        "status": "RESOLVED",
        "first_seen": old_first_seen.isoformat(),
        "resolved_at": datetime(
            2026,
            8,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        ).isoformat(),
    }

    update_existing_finding(
        table,
        finding,
        existing_item,
    )

    assert len(table.update_item_calls) == 1

    call = table.update_item_calls[0]
    values = call["ExpressionAttributeValues"]

    # A resolved finding that appears again should begin a new
    # observation window rather than immediately becoming OPEN.
    assert values[":status"] == "OBSERVED"

    # The previous first_seen timestamp should be replaced because
    # this is a new occurrence of the waste condition.
    assert values[":first_seen"] != old_first_seen.isoformat()

    # The finding is active again, so it should no longer have
    # a resolution timestamp.
    assert values[":resolved_at"] is None


def test_resolve_finding():
    table = FakeTable()

    existing_item = {
        "PK": (
            "RESOURCE#"
            "arn:aws:ec2:us-east-1:123456789012:volume/vol-123"
        ),
        "SK": "RULE#EBS_CURRENTLY_UNATTACHED",
    }

    resolve_finding(
        table,
        existing_item,
    )

    assert len(table.update_item_calls) == 1

    call = table.update_item_calls[0]

    assert call["Key"] == existing_item

    values = call["ExpressionAttributeValues"]

    assert values[":status"] == "RESOLVED"
    assert values[":resolved_at"] is not None

    # Resolution should preserve the original observation history.
    assert "first_seen" not in call["UpdateExpression"]
    assert "last_seen" not in call["UpdateExpression"]


def test_list_active_findings_filters_by_account_region_and_status():
    table = FakeTable()

    table.scan_responses = [
        {
            "Items": [
                {
                    "PK": "RESOURCE#one",
                    "SK": "RULE#one",
                    "status": "OPEN",
                }
            ]
        }
    ]

    items = list_active_findings(
        table,
        account_id="123456789012",
        region="us-east-1",
    )

    assert len(items) == 1

    call = table.scan_calls[0]

    assert call["ExpressionAttributeValues"] == {
        ":account_id": "123456789012",
        ":region": "us-east-1",
        ":observed": "OBSERVED",
        ":open": "OPEN",
    }

    assert call["ExpressionAttributeNames"] == {
        "#region": "region",
        "#status": "status",
    }


def test_list_active_findings_handles_pagination():
    table = FakeTable()

    table.scan_responses = [
        {
            "Items": [
                {
                    "PK": "RESOURCE#one",
                    "SK": "RULE#one",
                }
            ],
            "LastEvaluatedKey": {
                "PK": "RESOURCE#one",
                "SK": "RULE#one",
            },
        },
        {
            "Items": [
                {
                    "PK": "RESOURCE#two",
                    "SK": "RULE#two",
                }
            ]
        },
    ]

    items = list_active_findings(
        table,
        account_id="123456789012",
        region="us-east-1",
    )

    assert len(items) == 2
    assert len(table.scan_calls) == 2

    second_call = table.scan_calls[1]

    assert second_call["ExclusiveStartKey"] == {
        "PK": "RESOURCE#one",
        "SK": "RULE#one",
    }

def test_new_finding_stores_priority_fields():
    finding = make_finding()

    item = finding_to_item(
        finding
    )

    # A brand-new LOW severity finding with no known savings
    # starts at age zero and therefore has a LOW priority.
    assert item["age_days"] == 0
    assert item["priority_score"] == 0
    assert item["priority_label"] == "LOW"


def test_existing_finding_update_stores_priority_fields():
    finding = make_finding()
    table = FakeTable()

    existing_item = {
        "status": "OBSERVED",
        "first_seen": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    update_existing_finding(
        table,
        finding,
        existing_item,
    )

    assert len(table.update_item_calls) == 1

    call = table.update_item_calls[0]
    values = call["ExpressionAttributeValues"]

    assert ":age_days" in values
    assert ":priority_score" in values
    assert ":priority_label" in values

    assert values[":age_days"] == 0
    assert values[":priority_score"] == 0
    assert values[":priority_label"] == "LOW"

    assert "age_days = :age_days" in call["UpdateExpression"]
    assert (
        "priority_score = :priority_score"
        in call["UpdateExpression"]
    )
    assert (
        "priority_label = :priority_label"
        in call["UpdateExpression"]
    )