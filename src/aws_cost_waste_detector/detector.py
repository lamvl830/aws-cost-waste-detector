from typing import Any

import boto3

from aws_cost_waste_detector.notifications import (
    should_send_finding_notification,
)
from aws_cost_waste_detector.notifier import SnsNotifier
from aws_cost_waste_detector.pricing.ebs import AwsEbsPriceProvider
from aws_cost_waste_detector.pricing.eip import AwsEipPriceProvider
from aws_cost_waste_detector.prioritization import (
    calculate_current_finding_priority,
)
from aws_cost_waste_detector.reconciliation import find_missing_items
from aws_cost_waste_detector.reporting import (
    build_cost_summary,
)
from aws_cost_waste_detector.scanners.ebs import scan_unattached_ebs
from aws_cost_waste_detector.scanners.eip import scan_unused_eips
from aws_cost_waste_detector.storage.dynamodb import (
    finding_key,
    list_active_findings,
    mark_finding_notified,
    resolve_finding,
    save_finding,
)


def run_detector(
    session: boto3.Session,
    *,
    region: str,
    table_name: str = "WasteFindings",
    notifier: SnsNotifier | None = None,
    grace_period_days: int = 7,
) -> dict[str, Any]:
    """
    Run the complete AWS cost-waste detection workflow.

    This function contains no CLI-specific behavior so it can be
    reused by both the command-line interface and AWS Lambda.
    """
    sts = session.client("sts")
    identity = sts.get_caller_identity()

    account_id = identity["Account"]
    partition = identity["Arn"].split(":", 2)[1]

    ec2 = session.client(
        "ec2",
        region_name=region,
    )

    # AWS Pricing is exposed through us-east-1 even when the
    # resources being evaluated exist in another AWS region.
    pricing_client = session.client(
        "pricing",
        region_name="us-east-1",
    )

    ebs_price_provider = AwsEbsPriceProvider(
        pricing_client,
    )

    eip_price_provider = AwsEipPriceProvider(
        pricing_client,
    )

    dynamodb_resource = session.resource(
        "dynamodb",
        region_name=region,
    )

    table = dynamodb_resource.Table(
        table_name
    )

    # Capture active findings before the current scan so we can
    # detect findings that have disappeared.
    stored_active_findings = list_active_findings(
        table,
        account_id=account_id,
        region=region,
    )

    findings = []
    reconciled_rule_ids = set()

    ebs_findings = list(
        scan_unattached_ebs(
            ec2,
            account_id=account_id,
            region=region,
            partition=partition,
            price_provider=ebs_price_provider,
        )
    )

    findings.extend(
        ebs_findings
    )

    reconciled_rule_ids.add(
        "EBS_CURRENTLY_UNATTACHED"
    )

    eip_findings = list(
        scan_unused_eips(
            ec2,
            account_id=account_id,
            region=region,
            partition=partition,
            price_provider=eip_price_provider,
        )
    )

    findings.extend(
        eip_findings
    )

    reconciled_rule_ids.add(
        "EIP_UNUSED"
    )

    persistence_results = []

    for finding in findings:
        result = save_finding(
            table,
            finding,
            grace_period_days=grace_period_days,
        )

        persistence_results.append(
            {
                "resource_id": finding.resource_id,
                "rule_id": finding.rule_id,
                "result": result,
            }
        )

    notification_results = []
    ranked_findings = []

    for finding in findings:
        stored_item = next(
            (
                item
                for item in stored_active_findings
                if item.get("resource_id") == finding.resource_id
                and item.get("rule_id") == finding.rule_id
            ),
            None,
        )

        priority = calculate_current_finding_priority(
            finding,
            existing_item=stored_item,
        )

        notification_item = {
            **finding.to_dict(),
            **finding_key(finding),
            **priority,
            "last_notified_at": (
                stored_item.get("last_notified_at")
                if stored_item is not None
                else None
            ),
        }

        if (
            notifier is not None
            and should_send_finding_notification(
                notification_item
            )
        ):
            # Only mark a finding as notified after SNS publishes.
            # A failed publish remains eligible for retry.
            message_id = notifier.send_finding(
                notification_item
            )

            notified_at = mark_finding_notified(
                table,
                notification_item,
            )

            notification_results.append(
                {
                    "resource_id": finding.resource_id,
                    "rule_id": finding.rule_id,
                    "message_id": message_id,
                    "notified_at": notified_at,
                }
            )

        ranked_findings.append(
            {
                **finding.to_dict(),
                **priority,
            }
        )

    ranked_findings.sort(
        key=lambda item: item["priority_score"],
        reverse=True,
    )

    missing_findings = find_missing_items(
        findings,
        stored_active_findings,
        reconciled_rule_ids=reconciled_rule_ids,
    )

    resolved_results = []

    for item in missing_findings:
        resolve_finding(
            table,
            item,
        )

        resolved_results.append(
            {
                "resource_id": item.get("resource_id"),
                "rule_id": item.get("rule_id"),
                "result": "RESOLVED",
            }
        )

    summary = build_cost_summary(
        ranked_findings,
    )

    return {
        "account_id": account_id,
        "region": region,
        "findings": ranked_findings,
        "summary": summary,
        "persistence_results": persistence_results,
        "resolution_results": resolved_results,
        "notification_results": notification_results,
    }