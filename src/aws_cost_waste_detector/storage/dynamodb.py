from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from aws_cost_waste_detector.models import Finding


def finding_key(finding: Finding) -> dict[str, str]:
    """
    -> Build DynamoDB primary key for finding.

    -> PK identifies AWS resource.
    -> SK identifies the specific waste rule affecting the resource.

    -> Allows for one AWS resource to have multiple independent findings.
    """
    return {
        "PK": f"RESOURCE#{finding.resource_arn}", 
        "SK": f"RULE#{finding.rule_id}",
    }


def finding_to_item(finding: Finding) -> dict[str, Any]:
    """
    -> Convert a Finding object into DynamoDB structure

    -> New findings begin in OBSERVED state.
    -> Logic determines when observed finding should be OPEN/RESOLVED
    """
    now = datetime.now(timezone.utc).isoformat()

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
        "estimated_monthly_savings": finding.estimated_monthly_savings,
        "metadata": finding.metadata,
        "status": "OBSERVED",
        "first_seen": now,
        "last_seen": now,
        "resolved_at": None,
    }


def put_new_finding(table: Any, finding: Finding) -> None:
    """
    -> Store a newly observed finding in DynamoDB.

    -> The condition prevents an existing finding from being overwritten.
    -> Existing findings will later use separate update logic so that
    -> first_seen is preserved.
    """
    item = finding_to_item(finding)

    table.put_item(
        Item=item,
        ConditionExpression=(
            "attribute_not_exists(PK) AND attribute_not_exists(SK)"
        ),
    )


def update_existing_finding(table: Any, finding: Finding) -> None:
    """
    -> Update a finding that has already been observed.

    -> Only the latest observation and mutable finding data
    -> are refreshed.
    """
    now = datetime.now(timezone.utc).isoformat()

    table.update_item(
        Key=finding_key(finding),
        UpdateExpression=(
            "SET last_seen = :last_seen, "
            "title = :title, "
            "description = :description, "
            "severity = :severity, "
            "recommendation = :recommendation, "
            "estimated_monthly_savings = :savings, "
            "metadata = :metadata"
        ),
        ExpressionAttributeValues={
            ":last_seen": now,
            ":title": finding.title,
            ":description": finding.description,
            ":severity": finding.severity,
            ":recommendation": finding.recommendation,
            ":savings": finding.estimated_monthly_savings,
            ":metadata": finding.metadata,
        },
    )


def save_finding(table: Any, finding: Finding) -> str:
    """
    -> Persist a finding while preserving its observation history.

    -> A new finding is inserted with first_seen and last_seen timestamps.
    -> If finding exists, only its mutable fields and last_seen timestamp are updated.

    -> Returns the status of the finding after the operation.
    """
    try:
        put_new_finding(table, finding)
        return "CREATED"
    
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")

        # Conditional insert fails when PK/SK already exists
        if error_code != "ConditionalCheckFailedException":
            raise

        update_existing_finding(table, finding)
        return "UPDATED"