from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from aws_cost_waste_detector.lifecycle import determine_status
from aws_cost_waste_detector.models import Finding
from aws_cost_waste_detector.prioritization import (
    calculate_finding_priority,
)
from aws_cost_waste_detector.notifications import notification_timestamp


def finding_key(finding: Finding) -> dict[str, str]:
    """
    Build the DynamoDB primary key for a finding.

    PK identifies the AWS resource.
    SK identifies the specific waste rule affecting the resource.

    This allows one AWS resource to have multiple independent findings.
    """
    return {
        "PK": f"RESOURCE#{finding.resource_arn}",
        "SK": f"RULE#{finding.rule_id}",
    }


def finding_to_item(finding: Finding) -> dict[str, Any]:
    """
    Convert a Finding object into a DynamoDB item.

    New findings begin in the OBSERVED state with an age of zero.
    Their priority is calculated immediately using estimated savings,
    age, and severity.
    """
    now = datetime.now(timezone.utc)

    priority = calculate_finding_priority(
        {
            "first_seen": now.isoformat(),
            "estimated_monthly_savings": (
                finding.estimated_monthly_savings
            ),
            "severity": finding.severity,
        },
        now=now,
    )

    return {
        **finding_key(finding),
        "rule_id": finding.rule_id,
        "account_id": finding.account_id,
        "region": finding.region,
        "resource_arn": finding.resource_arn,
        "resource_id": finding.resource_id,
        "resource_type": finding.resource_type,
        "title": finding.title,
        "description": finding.description,
        "severity": finding.severity,
        "recommendation": finding.recommendation,
        "estimated_monthly_savings": (
            finding.estimated_monthly_savings
        ),
        "metadata": finding.metadata,
        "status": "OBSERVED",
        "first_seen": now.isoformat(),
        "last_seen": now.isoformat(),
        "resolved_at": None,
        "last_notified_at": None,
        "age_days": priority["age_days"],
        "priority_score": priority["priority_score"],
        "priority_label": priority["priority_label"],
    }


def put_new_finding(
    table: Any,
    finding: Finding,
) -> None:
    """
    Store a newly observed finding in DynamoDB.

    The condition prevents an existing finding from being overwritten.
    Existing findings use separate update logic so first_seen and
    lifecycle history can be preserved.
    """
    item = finding_to_item(finding)

    table.put_item(
        Item=item,
        ConditionExpression=(
            "attribute_not_exists(PK) AND "
            "attribute_not_exists(SK)"
        ),
    )


def update_existing_finding(
    table: Any,
    finding: Finding,
    existing_item: dict[str, Any],
    grace_period_days: int = 7,
) -> None:
    """
    Refresh an existing finding in DynamoDB.

    Active findings preserve their original first_seen timestamp so
    the application can determine how long the waste condition has
    continuously existed.

    If a previously RESOLVED finding appears again, it is treated as
    a new occurrence. Its first_seen timestamp is reset, its old
    resolved_at timestamp is cleared, and its priority starts over.
    """
    now = datetime.now(timezone.utc)

    # A resolved finding that reappears starts a new observation window.
    if existing_item.get("status") == "RESOLVED":
        first_seen = now

        status = determine_status(
            first_seen=first_seen,
            currently_detected=True,
            grace_period_days=grace_period_days,
            now=now,
        )

        priority = calculate_finding_priority(
            {
                "first_seen": first_seen.isoformat(),
                "estimated_monthly_savings": (
                    finding.estimated_monthly_savings
                ),
                "severity": finding.severity,
            },
            now=now,
        )

        table.update_item(
            Key=finding_key(finding),
            UpdateExpression=(
                "SET first_seen = :first_seen, "
                "last_seen = :last_seen, "
                "#status = :status, "
                "resolved_at = :resolved_at, "
                "last_notified_at = :last_notified_at, "
                "title = :title, "
                "description = :description, "
                "severity = :severity, "
                "recommendation = :recommendation, "
                "estimated_monthly_savings = :savings, "
                "metadata = :metadata, "
                "age_days = :age_days, "
                "priority_score = :priority_score, "
                "priority_label = :priority_label"
            ),
            ExpressionAttributeNames={
                "#status": "status",
            },
            ExpressionAttributeValues={
                ":first_seen": first_seen.isoformat(),
                ":last_seen": now.isoformat(),
                ":status": status,
                ":resolved_at": None,
                ":last_notified_at": None,
                ":title": finding.title,
                ":description": finding.description,
                ":severity": finding.severity,
                ":recommendation": finding.recommendation,
                ":savings": finding.estimated_monthly_savings,
                ":metadata": finding.metadata,
                ":age_days": priority["age_days"],
                ":priority_score": priority["priority_score"],
                ":priority_label": priority["priority_label"],
            },
        )

        return

    # An already-active finding keeps its original first_seen timestamp.
    first_seen = datetime.fromisoformat(
        existing_item["first_seen"]
    )

    status = determine_status(
        first_seen=first_seen,
        currently_detected=True,
        grace_period_days=grace_period_days,
        now=now,
    )

    priority = calculate_finding_priority(
        {
            "first_seen": first_seen.isoformat(),
            "estimated_monthly_savings": (
                finding.estimated_monthly_savings
            ),
            "severity": finding.severity,
        },
        now=now,
    )

    table.update_item(
        Key=finding_key(finding),
        UpdateExpression=(
            "SET last_seen = :last_seen, "
            "#status = :status, "
            "title = :title, "
            "description = :description, "
            "severity = :severity, "
            "recommendation = :recommendation, "
            "estimated_monthly_savings = :savings, "
            "metadata = :metadata, "
            "age_days = :age_days, "
            "priority_score = :priority_score, "
            "priority_label = :priority_label"
        ),
        ExpressionAttributeNames={
            "#status": "status",
        },
        ExpressionAttributeValues={
            ":last_seen": now.isoformat(),
            ":status": status,
            ":title": finding.title,
            ":description": finding.description,
            ":severity": finding.severity,
            ":recommendation": finding.recommendation,
            ":savings": finding.estimated_monthly_savings,
            ":metadata": finding.metadata,
            ":age_days": priority["age_days"],
            ":priority_score": priority["priority_score"],
            ":priority_label": priority["priority_label"],
        },
    )


def save_finding(
    table: Any,
    finding: Finding,
) -> str:
    """
    Persist a finding while preserving its observation history.

    A new finding is inserted with first_seen and last_seen timestamps.

    If the finding already exists, retrieve its existing history,
    recalculate its lifecycle status and priority, and update its
    mutable fields.

    Returns:
        CREATED when the finding is first inserted.
        UPDATED when the finding already exists.
    """
    try:
        put_new_finding(
            table,
            finding,
        )

        return "CREATED"

    except ClientError as error:
        error_code = error.response.get(
            "Error",
            {},
        ).get("Code")

        # Only treat a conditional failure as an existing finding.
        # Other AWS errors should still propagate.
        if error_code != "ConditionalCheckFailedException":
            raise

        # Retrieve the existing item so first_seen can be used
        # to determine lifecycle state and finding age.
        response = table.get_item(
            Key=finding_key(finding),
            ConsistentRead=True,
        )

        existing_item = response.get("Item")

        if existing_item is None:
            raise RuntimeError(
                "Finding already existed but could not be "
                "retrieved from DynamoDB."
            )

        update_existing_finding(
            table,
            finding,
            existing_item,
        )

        return "UPDATED"


def mark_finding_notified(
    table: Any,
    item: dict[str, Any],
) -> str:
    """
    Record when finding notification was successfully sent.

    The timestamp is persisted so future detector runs can avoid
    repeatedly notifying about same finding.
    """
    notified_at = notification_timestamp()

    table.update_item(
        Key={
            "PK": item["PK"],
            "SK": item["SK"],
        },
        UpdateExpression=(
            "SET last_notified_at = :last_notified_at"
        ),
        ExpressionAttributeValues={
            ":last_notified_at": notified_at,
        },
    )

    return notified_at


def resolve_finding(
    table: Any,
    existing_item: dict[str, Any],
) -> None:
    """
    Mark a previously detected finding as RESOLVED.

    A finding is resolved when it existed in DynamoDB during a previous
    scan but is no longer returned by the current scanner.

    first_seen and last_seen are preserved so the historical observation
    window remains available.
    """
    now = datetime.now(
        timezone.utc
    ).isoformat()

    table.update_item(
        Key={
            "PK": existing_item["PK"],
            "SK": existing_item["SK"],
        },
        UpdateExpression=(
            "SET #status = :status, "
            "resolved_at = :resolved_at"
        ),
        ExpressionAttributeNames={
            "#status": "status",
        },
        ExpressionAttributeValues={
            ":status": "RESOLVED",
            ":resolved_at": now,
        },
    )


def list_active_findings(
    table: Any,
    *,
    account_id: str,
    region: str,
) -> list[dict[str, Any]]:
    """
    Retrieve active findings for one AWS account and region.

    Only OBSERVED and OPEN findings are returned. RESOLVED findings
    are historical records and should not participate in reconciliation.

    DynamoDB Scan is acceptable for the current small-scale MVP.
    A secondary index can replace this later as the dataset grows.
    """
    items = []

    scan_kwargs = {
        "FilterExpression": (
            "account_id = :account_id AND "
            "#region = :region AND "
            "#status IN (:observed, :open)"
        ),
        "ExpressionAttributeNames": {
            "#region": "region",
            "#status": "status",
        },
        "ExpressionAttributeValues": {
            ":account_id": account_id,
            ":region": region,
            ":observed": "OBSERVED",
            ":open": "OPEN",
        },
    }

    while True:
        response = table.scan(
            **scan_kwargs
        )

        items.extend(
            response.get(
                "Items",
                [],
            )
        )

        last_evaluated_key = response.get(
            "LastEvaluatedKey"
        )

        if not last_evaluated_key:
            break

        # Continue scanning from where the previous page stopped.
        scan_kwargs["ExclusiveStartKey"] = (
            last_evaluated_key
        )

    return items