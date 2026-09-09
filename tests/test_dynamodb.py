from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.storage.dynamodb import (
    finding_key,
    finding_to_item,
    put_new_finding,
    save_finding,
    update_existing_finding,
)

def make_finding() -> Finding:
    """
    -> Create a reusable test finding.
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

    # A newly-created item should have matching first/last seen timestamps.
    assert item["first_seen"] == item["last_seen"]


from botocore.exceptions import ClientError


class FakeTable:
    """
    -> Minimal fake DynamoDB table used to verify write behavior
    -> without making real AWS requests.
    """

    def __init__(self, item_exists: bool = False):
        self.item_exists = item_exists
        self.put_item_calls = []
        self.update_item_calls = []

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

    def update_item(self, **kwargs):
        self.update_item_calls.append(kwargs)


def test_put_new_finding():
    finding = make_finding()
    table = FakeTable()

    put_new_finding(table, finding)

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

    update_existing_finding(table, finding)

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

    # first_seen shouldn't be overwritten when a finding is seen again
    assert "first_seen" not in call["UpdateExpression"]


def test_save_finding_created():
    finding = make_finding()
    table = FakeTable(item_exists=False)

    result = save_finding(table, finding)

    assert result == "CREATED"
    assert len(table.put_item_calls) == 1
    assert len(table.update_item_calls) == 0


def test_save_finding_updated():
    finding = make_finding()
    table = FakeTable(item_exists=True)

    result = save_finding(table, finding)

    assert result == "UPDATED"
    assert len(table.put_item_calls) == 1
    assert len(table.update_item_calls) == 1