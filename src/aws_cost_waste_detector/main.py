import argparse
import json

import boto3

from aws_cost_waste_detector.reconciliation import find_missing_items
from aws_cost_waste_detector.scanners.ebs import scan_unattached_ebs
from aws_cost_waste_detector.scanners.eip import scan_unused_eips
from aws_cost_waste_detector.storage.dynamodb import (
    list_active_findings,
    resolve_finding,
    save_finding,
)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments used by the scanner.
    """
    parser = argparse.ArgumentParser(
        description="Scan AWS for cost-waste findings"
    )

    parser.add_argument(
        "--profile",
        help="Optional AWS CLI profile name",
    )

    parser.add_argument(
        "--region",
        help="AWS region to scan",
    )

    parser.add_argument(
        "--table-name",
        default="WasteFindings",
        help="DynamoDB table used to store cost-waste findings",
    )

    return parser.parse_args()


def main() -> None:
    """
    Run AWS cost-waste scanners, persist current findings,
    and resolve findings that are no longer detected.
    """
    args = parse_args()

    # Create an AWS session using the optional CLI profile and region.
    session = boto3.Session(
        profile_name=args.profile,
        region_name=args.region,
    )

    region = session.region_name

    if not region:
        raise SystemExit(
            "No AWS region configured. "
            "Pass --region or configure a default AWS region."
        )

    # Determine which AWS account and partition the scanner is running against.
    sts = session.client("sts")
    identity = sts.get_caller_identity()

    account_id = identity["Account"]
    partition = identity["Arn"].split(":", 2)[1]

    # Create AWS service clients/resources used by the application.
    ec2 = session.client(
        "ec2",
        region_name=region,
    )

    dynamodb_resource = session.resource(
        "dynamodb",
        region_name=region,
    )

    table = dynamodb_resource.Table(args.table_name)

    # Capture currently-active historical findings before running the
    # new scan. We compare these with the new findings later.
    stored_active_findings = list_active_findings(
        table,
        account_id=account_id,
        region=region,
    )

    # Collect findings from all registered scanners.
    #
    # We also track which rule IDs were successfully evaluated.
    # Only those rules are eligible for reconciliation later.
    findings = []
    reconciled_rule_ids = set()

    ebs_findings = list(
        scan_unattached_ebs(
            ec2,
            account_id=account_id,
            region=region,
            partition=partition,
        )
    )

    findings.extend(ebs_findings)
    reconciled_rule_ids.add("EBS_CURRENTLY_UNATTACHED")


    eip_findings = list(
        scan_unused_eips(
            ec2,
            account_id=account_id,
            region=region,
            partition=partition,
        )
    )

    findings.extend(eip_findings)
    reconciled_rule_ids.add("EIP_UNUSED")

    # Persist each finding to DynamoDB.
    #
    # save_finding() returns:
    # CREATED -> finding was seen for the first time
    # UPDATED -> finding already existed and was refreshed
    persistence_results = []

    for finding in findings:
        result = save_finding(
            table,
            finding,
        )

        persistence_results.append(
            {
                "resource_id": finding.resource_id,
                "rule_id": finding.rule_id,
                "result": result,
            }
        )

    # Compare the previous active findings with the current scan.
    # Anything previously active but no longer detected is resolved.
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

    # Print all findings returned by the current scan.
    print(
        json.dumps(
            [finding.to_dict() for finding in findings],
            indent=2,
        )
    )

    # Print persistence results for findings that are still active.
    print("\nPersistence results:")
    print(
        json.dumps(
            persistence_results,
            indent=2,
        )
    )

    # Print findings that disappeared and were resolved.
    print("\nResolution results:")
    print(
        json.dumps(
            resolved_results,
            indent=2,
        )
    )

    print(
        f"\nFound {len(findings)} current cost-waste finding(s) "
        f"in {region}."
    )

    print(
        f"Resolved {len(resolved_results)} previous finding(s)."
    )


if __name__ == "__main__":
    main()