from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.reconciliation import find_missing_items


def make_finding(
    resource_id: str,
    rule_id: str,
) -> Finding:
    """
    Create a reusable finding for reconciliation tests.
    """
    return Finding(
        rule_id=rule_id,
        account_id="123456789012",
        region="us-east-1",
        resource_arn=(
            f"arn:aws:ec2:us-east-1:123456789012:volume/{resource_id}"
        ),
        resource_id=resource_id,
        resource_type="AWS::EC2::Volume",
        title="Test finding",
        description="Synthetic reconciliation test finding.",
        severity="LOW",
        recommendation="No action required.",
        estimated_monthly_savings=None,
        metadata={},
    )


def make_stored_item(
    resource_id: str,
    rule_id: str,
) -> dict:
    """
    Create a stored DynamoDB finding using the same identity
    format as the application.
    """
    return {
        "PK": (
            "RESOURCE#"
            f"arn:aws:ec2:us-east-1:123456789012:volume/{resource_id}"
        ),
        "SK": f"RULE#{rule_id}",
        "rule_id": rule_id,
        "status": "OPEN",
    }


def test_present_finding_is_not_missing():
    current_findings = [
        make_finding(
            "vol-123",
            "EBS_CURRENTLY_UNATTACHED",
        )
    ]

    stored_items = [
        make_stored_item(
            "vol-123",
            "EBS_CURRENTLY_UNATTACHED",
        )
    ]

    missing = find_missing_items(
        current_findings,
        stored_items,
        reconciled_rule_ids={
            "EBS_CURRENTLY_UNATTACHED",
        },
    )

    assert missing == []


def test_missing_finding_is_returned():
    current_findings = []

    stored_items = [
        make_stored_item(
            "vol-123",
            "EBS_CURRENTLY_UNATTACHED",
        )
    ]

    missing = find_missing_items(
        current_findings,
        stored_items,
        reconciled_rule_ids={
            "EBS_CURRENTLY_UNATTACHED",
        },
    )

    assert len(missing) == 1
    assert missing[0]["PK"].endswith("vol-123")


def test_rules_on_same_resource_are_reconciled_independently():
    current_findings = [
        make_finding(
            "vol-123",
            "EBS_CURRENTLY_UNATTACHED",
        )
    ]

    stored_items = [
        make_stored_item(
            "vol-123",
            "EBS_CURRENTLY_UNATTACHED",
        ),
        make_stored_item(
            "vol-123",
            "EBS_OVERPROVISIONED",
        ),
    ]

    missing = find_missing_items(
        current_findings,
        stored_items,
        reconciled_rule_ids={
            "EBS_CURRENTLY_UNATTACHED",
            "EBS_OVERPROVISIONED",
        },
    )

    assert len(missing) == 1
    assert missing[0]["SK"] == "RULE#EBS_OVERPROVISIONED"


def test_unscanned_rule_is_not_resolved():
    current_findings = []

    stored_items = [
        make_stored_item(
            "vol-123",
            "EC2_OVERPROVISIONED",
        )
    ]

    missing = find_missing_items(
        current_findings,
        stored_items,
        reconciled_rule_ids={
            "EBS_CURRENTLY_UNATTACHED",
            "EIP_UNUSED",
        },
    )

    assert missing == []