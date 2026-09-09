from typing import Any

from aws_cost_waste_detector.models import Finding


def finding_identity(finding: Finding) -> tuple[str, str]:
    """
    Return the unique DynamoDB identity for a current finding.

    A finding is uniquely identified by its resource ARN and rule ID.
    """
    return (
        f"RESOURCE#{finding.resource_arn}",
        f"RULE#{finding.rule_id}",
    )


def stored_item_identity(item: dict[str, Any]) -> tuple[str, str]:
    """
    Return the unique identity for a finding already stored in DynamoDB.
    """
    return (
        item["PK"],
        item["SK"],
    )


def find_missing_items(
    current_findings: list[Finding],
    stored_items: list[dict[str, Any]],
    reconciled_rule_ids: set[str],
) -> list[dict[str, Any]]:
    """
    Find previously active findings that disappeared from the current scan.

    Only findings belonging to rules that were actually evaluated during
    this scan are eligible for resolution. This prevents one scanner from
    accidentally resolving findings owned by another scanner.
    """

    current_identities = {
        finding_identity(finding)
        for finding in current_findings
    }

    missing_items = []

    for item in stored_items:
        rule_id = item.get("rule_id")

        # Ignore findings belonging to rules that were not evaluated
        # during this scan.
        if rule_id not in reconciled_rule_ids:
            continue

        identity = stored_item_identity(item)

        if identity not in current_identities:
            missing_items.append(item)

    return missing_items